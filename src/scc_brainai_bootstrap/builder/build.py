"""Capacité de **build** — produire un manifeste de projet à partir d'une Spécification (JALON-ZERO).

Troisième rung de la tranche verticale (après compréhension puis spécification). BrainAI dépend d'une
**capacité**, jamais d'un outil (R8) : le noyau demande « construis le manifeste de cette Spéc » ; l'outil
concret (ici **Claude Code** non-interactif) est un **adaptateur** interchangeable. Un modèle **propose**,
il ne décide jamais (R5) : la sortie deviendra un **fait `build` proposé** — elle ne devient **jamais**
officielle automatiquement.

**Tâche 1 (contrat seul)** : validation de la Spéc source, schéma strict du manifeste, prompt déterministe,
Protocol de capacité et adaptateur Claude Code confiné (garde budget avant appel). **Aucune** matérialisation,
**aucun** store, **aucun** ``produce_build`` ici — ils viendront en Tâche 2.

Le manifeste est dérivé **exclusivement** de la Spécification : aucune fonctionnalité, entité, utilisateur ou
décision technique inventée. Le modèle **ne produit jamais de chemin ni de nom de fichier** — le chemin est
**imposé par BrainAI** (``manifest.json``, Tâche 2). Primitives runtime via l'API publique
:mod:`claude_code_runtime`. Stdlib pur.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import parse_envelope
from scc_brainai_bootstrap.builder.specification import SPEC_SCHEMA
from scc_brainai_bootstrap.builder.tool_runner import run_confined

_SPEC_REQUIRED = tuple(SPEC_SCHEMA["required"])       # 11 champs d'une Spécification (source unique)

# Nom du fichier artefact — **imposé par BrainAI**, jamais par le modèle (Tâche 2 : matérialisation).
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
    ne portant pas les **11 champs** requis. ``spec_ref`` et ``spec_sha256`` (Tâche 2) seront dérivés de
    **ce seul objet** — on ne peut pas associer une référence à un autre contenu."""
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


@runtime_checkable
class BuildCapability(Protocol):
    """**Capacité** « construire le manifeste d'une Spéc » (R8) — BrainAI en dépend, jamais d'un outil concret.

    Contrat minimal : produire, pour une ``spec`` structurée, la matière brute d'un futur fait `build`
    (enveloppe/exit/timeout/prompt), **après** contrôle du budget. L'implémentation concrète (ici Claude
    Code) est interchangeable ; le reste du système ne connaît que ce Protocol, jamais la commande ``claude``."""

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
        **jamais** de fichier (c'est BrainAI qui matérialise, Tâche 2)."""
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
        timed_out, prompt, argv, stdout, stderr}`` — ne construit ni ne matérialise le fait (Tâche 2)."""
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


__all__ = ["ARTIFACT_FILENAME", "NAME_MAX", "MANIFEST_SCHEMA", "SpecSourceError",
           "validate_spec_source", "build_prompt", "BuildCapability", "ClaudeCodeBuildAdapter"]
