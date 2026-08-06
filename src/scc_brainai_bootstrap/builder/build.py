"""Capacité de **build** — produire un manifeste de projet à partir d'une Spécification (JALON-ZERO).

Troisième rung de la tranche verticale (après compréhension puis spécification). BrainAI dépend d'une
**capacité**, jamais d'un outil (R8) : le noyau demande « construis le manifeste de cette Spéc » ; l'outil
concret (ici **Claude Code** non-interactif) est un **adaptateur** interchangeable. Un modèle **propose**,
il ne décide jamais (R5) : la sortie est un **fait `build` proposé** — elle ne devient **jamais** officielle
automatiquement.

Chemin normal unique : :func:`produce_build` (validation source → garde budget → un appel confiné →
validation stricte du manifeste → **matérialisation confinée uniquement si valide** → fait → enregistrement),
**un fait par tentative externe**, **aucun retry** (R6). Le manifeste est dérivé **exclusivement** de la
Spécification ; le modèle **ne produit jamais de chemin ni de nom de fichier** — le chemin est **imposé par
BrainAI** (``manifest.json``), l'écriture passe **uniquement** par :meth:`Workspace.resolve_within` (aucune
évasion), le hash est calculé sur les **octets réellement écrits**, et l'artefact n'est **jamais exécuté**.
Primitives runtime via l'API publique :mod:`claude_code_runtime`. Stdlib pur.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import diagnostic, extract_cost, parse_envelope
from scc_brainai_bootstrap.builder.specification import SPEC_SCHEMA
from scc_brainai_bootstrap.builder.tool_runner import run_confined
from scc_brainai_bootstrap.builder.workspace import Workspace
from scc_brainai_bootstrap.core.clock import digest

_SPEC_REQUIRED = tuple(SPEC_SCHEMA["required"])       # 11 champs d'une Spécification (source unique)

# Nom du fichier artefact — **imposé par BrainAI**, jamais par le modèle.
ARTIFACT_FILENAME = "manifest.json"
# Longueur maximale du titre fonctionnel ``name``.
NAME_MAX = 80

# Schéma **strict** du manifeste (sortie forcée par ``--json-schema``). EXACTEMENT cinq clés, dérivées de
# la Spécification. Aucune clé de chemin/fichier : le modèle ne produit jamais d'emplacement.
MANIFEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},                                    # titre fonctionnel court (≤ 80)
        "summary": {"type": "string"},                                 # résumé une phrase
        "users": {"type": "array", "items": {"type": "string"}},       # dérivés de users_and_roles
        "features": {"type": "array", "items": {"type": "string"}},    # dérivées de features
        "entities": {"type": "array", "items": {"type": "string"}},    # dérivées de entities_and_data
    },
    "required": ["name", "summary", "users", "features", "entities"],
}


class SpecSourceError(ValueError):
    """Fait Spécification source invalide : absent, mal typé, sans ``specification_id``, sans ``specification`` (11 champs), ou non ``proposed``."""


def validate_spec_source(source: Any) -> Tuple[str, Dict[str, Any]]:
    """Valide un **fait Spécification source** et renvoie ``(specification_id, specification)`` — ou lève
    :class:`SpecSourceError`.

    Refuse **avant tout appel externe** : objet non-dict, ``specification_id`` absent/non-chaîne,
    ``status`` ≠ ``proposed`` (un fait ``failed`` est donc refusé), ``specification`` absente/non-dict ou
    ne portant pas les **11 champs** requis. ``spec_ref`` et ``spec_sha256`` sont dérivés de **ce seul
    objet** — on ne peut pas associer une référence à un autre contenu."""
    if not isinstance(source, dict):
        raise SpecSourceError("fait Spécification source requis (objet)")
    sid = source.get("specification_id")
    if not isinstance(sid, str) or not sid:
        raise SpecSourceError("specification_id manquant ou invalide")
    if source.get("status") != "proposed":
        raise SpecSourceError(f"Spécification source non proposed (status={source.get('status')!r})")
    spec = source.get("specification")
    if not isinstance(spec, dict) or not all(k in spec for k in _SPEC_REQUIRED):
        raise SpecSourceError("specification structurée (11 champs) manquante")
    return sid, spec


def _valid_manifest(obj: Any) -> bool:
    """Validation **locale stricte** du manifeste : objet ; **ensemble EXACT** des cinq clés (aucune
    supplémentaire) ; ``name``/``summary`` chaînes **non vides**, ``name`` ≤ ``NAME_MAX`` ; tous les
    éléments de ``users``/``features``/``entities`` sont des chaînes **non vides**."""
    if not isinstance(obj, dict):
        return False
    if set(obj.keys()) != {"name", "summary", "users", "features", "entities"}:
        return False
    name, summary = obj["name"], obj["summary"]
    if not isinstance(name, str) or not name.strip() or len(name) > NAME_MAX:
        return False
    if not isinstance(summary, str) or not summary.strip():
        return False
    for key in ("users", "features", "entities"):
        val = obj[key]
        if not isinstance(val, list) or not all(isinstance(x, str) and x.strip() for x in val):
            return False
    return True


def build_prompt(spec: Dict[str, Any]) -> str:
    """Prompt déterministe : produit un manifeste dérivé **exclusivement** de la Spécification fournie.

    Interdit d'inventer une fonctionnalité, entité, utilisateur ou décision technique absente ; interdit de
    produire un chemin ou un nom de fichier ; exactement les cinq clés imposées."""
    spec_json = json.dumps(spec, sort_keys=True, ensure_ascii=False, indent=2)
    return (
        "Tu produis un MANIFESTE de projet à partir d'une SPÉCIFICATION produit déjà établie. "
        "Appuie-toi EXCLUSIVEMENT sur la SPÉCIFICATION fournie : n'invente AUCUNE fonctionnalité, "
        "entité, utilisateur ni décision technique absente, et ne contredis pas la Spécification. "
        "Réponds UNIQUEMENT via le schéma imposé, avec EXACTEMENT ces cinq clés : "
        f"name (titre fonctionnel court, au plus {NAME_MAX} caractères), summary (résumé en une phrase), "
        "users (dérivés des utilisateurs et rôles), features (dérivées des fonctionnalités), "
        "entities (dérivées des entités et données). Ne produis AUCUN chemin ni nom de fichier, et "
        "AUCUNE propriété supplémentaire.\n\n"
        f"SPÉCIFICATION (source, ne pas contredire) :\n{spec_json}"
    )


def parse_manifest(envelope: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extrait le manifeste **valide** de l'enveloppe (``result``), ou ``None`` si illisible/non conforme."""
    if envelope is None:
        return None
    result = envelope.get("result")
    manifest: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                manifest = parsed
        except json.JSONDecodeError:
            manifest = None
    elif isinstance(result, dict):
        manifest = result
    return manifest if _valid_manifest(manifest) else None


def _failure_reason(envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool) -> Optional[str]:
    """Raison d'échec d'appel (timeout / illisible / exit≠0 / erreur client / subtype≠success), ou ``None``
    si l'appel a abouti. ``error`` ne peut jamais afficher ``"success"``."""
    nonzero_exit = exit_code is not None and exit_code != 0
    if not (timed_out or envelope is None or nonzero_exit
            or envelope.get("is_error") or envelope.get("subtype") != "success"):
        return None
    if timed_out:
        return "timeout"
    if envelope is None:
        return "enveloppe illisible"
    if nonzero_exit:
        return f"exit non nul ({exit_code})"
    if envelope.get("is_error") and envelope.get("subtype") == "success":
        return "erreur client sans détail (voir diagnostic)"
    reason = str(envelope.get("api_error_status") or envelope.get("subtype") or "erreur d'appel")
    return "erreur client sans détail (voir diagnostic)" if reason == "success" else reason


def build_build(*, spec_source: Dict[str, Any], prompt: str, capability: str, adapter: str, model: str,
                envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool, as_of: str,
                artefact: Optional[Dict[str, Any]] = None, argv: Any = None, stdout: Any = None,
                stderr: Any = None) -> Dict[str, Any]:
    """Construit un **fait `build`** honnête (pur, testable). ``artefact`` (matérialisé : ``relative_path``,
    ``sha256`` des octets écrits, ``byte_size``) n'est retenu que sur le chemin **proposed**.

    ``proposed`` uniquement si : appel abouti (voir :func:`_failure_reason`), manifeste **localement valide**,
    ET artefact matérialisé fourni. Sinon ``failed`` — sans crash, ``error`` (jamais ``"success"``),
    ``diagnostic`` RV-1, **``artefact = None``** (aucune matérialisation en échec). N'attribue **aucun**
    identifiant : c'est le :class:`BuildStore` qui l'adresse au contenu. La Spéc source n'est jamais modifiée (R5)."""
    sid, spec = validate_spec_source(spec_source)
    spec_sha256 = digest(spec)
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    base: Dict[str, Any] = {
        "fact_type": "build",
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "spec_ref": sid,
        "spec_sha256": spec_sha256,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "MANIFEST_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    diag = diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                      timed_out=timed_out, envelope=envelope)
    reason = _failure_reason(envelope, exit_code, timed_out)
    if reason is not None:
        return {**base, "status": "failed", "artefact": None, "error": reason, "diagnostic": diag}
    if parse_manifest(envelope) is None:
        return {**base, "status": "failed", "artefact": None,
                "error": "format manifeste invalide", "diagnostic": diag}
    if not isinstance(artefact, dict):     # garde-fou : succès ⇒ artefact réellement matérialisé
        return {**base, "status": "failed", "artefact": None,
                "error": "artefact non matérialisé", "diagnostic": diag}
    return {**base, "status": "proposed", "artefact": artefact, "error": None, "diagnostic": None}


def materialize_manifest(manifest: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
    """Écrit le manifeste **dans le Workspace confiné**, au chemin **imposé** ``manifest.json`` (jamais fourni
    par le modèle), **uniquement** via :meth:`Workspace.resolve_within` (toute évasion — absolu/``..``/symlink —
    est refusée avant tout effet). Le hash et la taille portent sur les **octets réellement écrits** (relus du
    disque). N'exécute, ne compile, n'installe **rien**."""
    workspace.ensure()
    target = workspace.resolve_within(ARTIFACT_FILENAME)                 # chemin imposé + confiné
    payload = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    target.write_bytes(payload)
    written = target.read_bytes()                                       # octets RÉELLEMENT sur disque
    return {"relative_path": ARTIFACT_FILENAME,
            "sha256": hashlib.sha256(written).hexdigest(),
            "byte_size": len(written)}


@runtime_checkable
class BuildCapability(Protocol):
    """**Capacité** « construire le manifeste d'une Spéc » (R8) — BrainAI en dépend, jamais d'un outil concret."""

    capability: str
    name: str
    model: str

    def propose(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeBuildAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`BuildCapability` (R8)."""

    capability = "build"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = 120.0, claude_bin: str = "claude"):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré, modèle explicite, plafond
        coût, outils fichier/bash **désactivés** — le modèle produit le **contenu** du manifeste, il n'écrit
        **jamais** de fichier (c'est BrainAI qui matérialise)."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(MANIFEST_SCHEMA, ensure_ascii=False),
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        # Env minimal confiné, **composition identique** aux autres capacités (T3/B1) : PATH/LANG, plus
        # HOME/USER/LOGNAME si présents. Aucun secret, aucun token ; l'environnement du parent n'est jamais hérité.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"), "LANG": "C.UTF-8"}
        for k in ("HOME", "USER", "LOGNAME"):
            if os.environ.get(k):
                env[k] = os.environ[k]
        return env

    def propose(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le reste ne
        couvre pas le plafond (``run_confined`` **non atteint**). Renvoie ``{called, envelope, exit_code,
        timed_out, prompt, argv, stdout, stderr}`` — ne construit ni ne matérialise le fait."""
        prompt = build_prompt(spec)
        argv = self.build_argv(prompt)
        if budget_remaining_usd < self.max_budget_usd:
            return {"called": False, "envelope": None, "exit_code": None, "timed_out": False,
                    "prompt": prompt, "argv": argv, "stdout": None, "stderr": None,
                    "refused": "budget insuffisant"}
        result = run_confined(argv, cwd=cwd, timeout=self.timeout, env=self._env())
        envelope = None if result["timed_out"] else parse_envelope(result["stdout"])
        return {"called": True, "envelope": envelope, "exit_code": result["exit_code"],
                "timed_out": result["timed_out"], "prompt": prompt, "argv": argv,
                "stdout": result["stdout"], "stderr": result["stderr"]}


def _system_clock() -> str:
    """Horloge réelle du projet : instant UTC ISO 8601. Injectable en test (paramètre ``clock``)."""
    return datetime.now(timezone.utc).isoformat()


def produce_build(*, spec_source: Dict[str, Any], adapter: BuildCapability, store: Any,
                  workspace: Workspace, budget_remaining_usd: float, cwd: Path,
                  clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """**Chemin normal unique** Spécification → manifeste. Aucun driver externe ne recompose ces étapes.

    Séquence : (1) **valide** la Spéc source (refus **avant** toute frontière externe) ; (2) ``adapter.propose``
    — dont la **garde budget** ; (3) si refus budget, **aucun fait** ; (4) sinon **horodatage réel** via
    ``clock`` ; **matérialisation confinée UNIQUEMENT si** l'appel a abouti ET le manifeste est valide — sinon
    **aucun artefact** ; construction et enregistrement d'**exactement un fait** par tentative, **aucun retry** (R6)."""
    _, spec = validate_spec_source(spec_source)                  # (1) refus AVANT tout appel externe
    raw = adapter.propose(spec, cwd=cwd, budget_remaining_usd=budget_remaining_usd)  # (2) garde budget incluse
    if not raw.get("called"):                                    # (3) refus budget : aucune frontière, aucun fait
        return {"attempted": False, "recorded": False, "refused": raw.get("refused"), "fact": None}
    as_of = clock()                                              # (4) horodatage réel (jamais figé)
    envelope = raw["envelope"]
    reason = _failure_reason(envelope, raw["exit_code"], raw["timed_out"])
    manifest = parse_manifest(envelope) if reason is None else None
    artefact = materialize_manifest(manifest, workspace) if manifest is not None else None  # matérialise SSI valide
    fact = build_build(
        spec_source=spec_source, prompt=raw["prompt"], capability=adapter.capability, adapter=adapter.name,
        model=adapter.model, envelope=envelope, exit_code=raw["exit_code"], timed_out=raw["timed_out"],
        as_of=as_of, artefact=artefact, argv=raw.get("argv"), stdout=raw.get("stdout"), stderr=raw.get("stderr"))
    recorded = store.record(fact)                                # un seul fait, jamais de retry
    return {"attempted": True, "recorded": True, "refused": None, "fact": recorded}


__all__ = ["ARTIFACT_FILENAME", "NAME_MAX", "MANIFEST_SCHEMA", "SpecSourceError",
           "validate_spec_source", "build_prompt", "parse_manifest", "build_build",
           "materialize_manifest", "produce_build", "BuildCapability", "ClaudeCodeBuildAdapter"]
