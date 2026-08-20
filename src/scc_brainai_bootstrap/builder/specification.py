"""Capacité de **spécification** — produire une Spécification structurée à partir d'un Brief (JALON-ZERO).

Rung suivant de la tranche verticale, après la **compréhension** (:mod:`understanding`). BrainAI dépend
d'une **capacité**, jamais d'un outil (R8) : le noyau demande « spécifie ce Brief » ; l'outil concret
(ici **Claude Code** non-interactif) est un **adaptateur** interchangeable. Un modèle **propose**, il ne
décide jamais (R5) : la sortie est un **fait `specification`** (``status: proposed``), soumis à
validation humaine — elle ne devient **jamais** officielle automatiquement et **ne déclenche aucun Build**.

La Spécification est dérivée **exclusivement** du Brief fourni : aucune lecture implicite d'un état
officiel, aucun besoin inventé, aucune décision d'architecture, aucune réalisation. L'entrée est un **fait
Brief source complet** (``proposal_id`` + ``status == "proposed"`` + ``brief`` structuré) ; ``brief_ref``
et ``brief_sha256`` en sont **extraits** — impossible d'associer une référence à un autre contenu. Un
Brief source ``failed`` / sans ``proposal_id`` / sans ``brief`` / non ``proposed`` est **refusé avant tout
appel externe** (:func:`validate_brief_source`). Le Brief source n'est **jamais modifié** (R5).

Chemin normal unique : :func:`produce_specification` (validation source → garde budget → appel confiné →
horodatage réel injectable → fait → enregistrement), **un fait par tentative externe**, **aucun retry**
(R6). Aucun driver externe ne recompose ces étapes.

**Primitives runtime partagées.** L'enveloppe (``parse_envelope``), le coût honnête (``extract_cost``) et
le diagnostic RV-1 borné/assaini (``diagnostic``) proviennent de l'API **publique** de
:mod:`claude_code_runtime` — source unique de la redaction des secrets, sans dépendance à un symbole privé.
Stdlib pur.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import diagnostic, extract_cost, parse_envelope
from scc_brainai_bootstrap.builder.cognitive_identity import CONDENSED_IDENTITY, compose_prompt
from scc_brainai_bootstrap.builder.tool_runner import run_confined
from scc_brainai_bootstrap.core.clock import digest

# Schéma **structuré** attendu de la Spécification (sortie forcée par ``--json-schema``). Onze champs
# minimaux d'une spécification produit ; un modèle **décrit et cadre** le produit à partir du Brief, il
# ne prend aucune décision d'architecture et ne planifie aucune réalisation (R5). ``product_objective``
# est une chaîne ; les dix autres champs sont des **listes de chaînes**.
SPEC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "product_objective": {"type": "string"},                                  # objectif produit
        "users_and_roles": {"type": "array", "items": {"type": "string"}},         # utilisateurs et rôles
        "functional_scope": {"type": "array", "items": {"type": "string"}},        # périmètre fonctionnel
        "features": {"type": "array", "items": {"type": "string"}},                # fonctionnalités attendues
        "entities_and_data": {"type": "array", "items": {"type": "string"}},       # entités et données principales
        "key_journeys": {"type": "array", "items": {"type": "string"}},            # parcours essentiels
        "constraints": {"type": "array", "items": {"type": "string"}},             # contraintes
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},     # critères d'acceptation
        "assumptions": {"type": "array", "items": {"type": "string"}},             # hypothèses
        "open_questions": {"type": "array", "items": {"type": "string"}},          # questions ouvertes
        "out_of_scope": {"type": "array", "items": {"type": "string"}},            # explicitement hors périmètre
    },
    "required": ["product_objective", "users_and_roles", "functional_scope", "features",
                 "entities_and_data", "key_journeys", "constraints", "acceptance_criteria",
                 "assumptions", "open_questions", "out_of_scope"],
}

_SPEC_REQUIRED = tuple(SPEC_SCHEMA["required"])


class BriefSourceError(ValueError):
    """Fait Brief source invalide : absent, mal typé, sans ``proposal_id``, sans ``brief``, ou non ``proposed``."""


def validate_brief_source(source: Any) -> Tuple[str, Dict[str, Any]]:
    """Valide un **fait Brief source** et renvoie ``(proposal_id, brief)`` — ou lève :class:`BriefSourceError`.

    Refuse **avant tout appel externe** : objet non-dict, ``proposal_id`` absent/non-chaîne, ``status`` ≠
    ``proposed`` (un fait ``failed`` est donc refusé), ``brief`` absent/non-dict/vide. ``brief_ref`` et
    ``brief_sha256`` étant tous deux dérivés de **ce seul objet**, on ne peut pas associer une référence à
    un autre contenu."""
    if not isinstance(source, dict):
        raise BriefSourceError("fait Brief source requis (objet)")
    pid = source.get("proposal_id")
    if not isinstance(pid, str) or not pid:
        raise BriefSourceError("proposal_id manquant ou invalide")
    if source.get("status") != "proposed":
        raise BriefSourceError(f"Brief source non proposed (status={source.get('status')!r})")
    brief = source.get("brief")
    if not isinstance(brief, dict) or not brief:
        raise BriefSourceError("brief structuré manquant")
    return pid, brief


def build_prompt(brief: Dict[str, Any]) -> str:
    """Prompt déterministe : spécifie **exclusivement** à partir du Brief fourni (sérialisé canonique).

    N'invente aucun besoin, ne prend aucune décision d'architecture, ne rédige aucun code, ne planifie
    aucune réalisation : décrit et cadre le **produit** au niveau spécification.

    Préfixé par l'**essence** de l'identité (``CONDENSED_IDENTITY``) via :func:`compose_prompt` : BrainAI
    nomme ses hypothèses, tranche les choix structurants et tisse les angles morts dans son raisonnement —
    jamais relégués dans une section décorative. Contrat et :data:`SPEC_SCHEMA` inchangés (T3)."""
    brief_json = json.dumps(brief, sort_keys=True, ensure_ascii=False, indent=2)
    mission = (
        "Tu produis une SPÉCIFICATION produit structurée à partir d'un BRIEF de compréhension déjà "
        "établi. Appuie-toi EXCLUSIVEMENT sur le BRIEF fourni : n'invente aucun besoin, ne contredis "
        "pas le Brief, ne prends aucune décision d'architecture, ne rédige aucun code, ne planifie "
        "aucune réalisation. Réponds UNIQUEMENT via le schéma imposé : objectif produit, utilisateurs "
        "et rôles, périmètre fonctionnel, fonctionnalités attendues, entités et données principales, "
        "parcours essentiels, contraintes, critères d'acceptation, hypothèses, questions ouvertes, "
        "éléments explicitement hors périmètre. Nomme comme telle toute hypothèse faite faute "
        "d'information. Sur les choix structurants, tranche explicitement plutôt que de rester neutre "
        "(et si deux options se valent réellement, dis-le). Les angles morts identifiés sont intégrés "
        "au raisonnement de la spécification, jamais relégués dans une rubrique décorative.\n\n"
        f"BRIEF (source, ne pas contredire) :\n{brief_json}"
    )
    return compose_prompt(CONDENSED_IDENTITY, mission)


def _valid_specification(obj: Any) -> bool:
    """Validation **locale stricte** au schéma : dict, **ensemble EXACT** des clés de ``SPEC_SCHEMA``
    (aucune manquante, **aucune propriété supplémentaire**), ``product_objective`` chaîne, tous les autres
    champs **listes de chaînes**. Piloté par ``SPEC_SCHEMA`` pour rester cohérent avec le contrat."""
    if not isinstance(obj, dict):
        return False
    props = SPEC_SCHEMA["properties"]
    if set(obj.keys()) != set(props.keys()):        # ensemble exact — refuse manquant ET supplémentaire
        return False
    for key, spec in props.items():
        val = obj[key]
        if spec["type"] == "string":
            if not isinstance(val, str):
                return False
        else:                                        # "array" d'items "string"
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                return False
    return True


def build_specification(*, brief_source: Dict[str, Any], prompt: str, capability: str, adapter: str,
                        model: str, envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool,
                        as_of: str, argv: Any = None, stdout: Any = None,
                        stderr: Any = None) -> Dict[str, Any]:
    """Construit un **fait `specification`** honnête (pur, testable), distinct du fait Brief.

    L'entrée est le **fait Brief source complet** : ``brief_ref`` (= ``proposal_id``) et ``brief_sha256``
    (empreinte déterministe du contenu) en sont **extraits** ; le Brief source est validé et **jamais
    modifié** (R5). ``proposed`` uniquement si : pas de timeout, ``exit_code == 0`` (ou ``None``),
    enveloppe lisible, non ``is_error``, ``subtype == "success"``, ET Spécification **localement valide**
    (schéma strict). Sinon ``failed`` — sans crash, ``error`` (jamais ``"success"``), ``diagnostic`` RV-1
    borné assaini. Coût toujours enregistré (réel ou ``unavailable``). ``diagnostic = None`` si ``proposed``.
    N'attribue **aucun** identifiant : c'est le :class:`SpecificationStore` qui l'adresse au contenu."""
    proposal_id, brief = validate_brief_source(brief_source)     # défensif : source cohérente et intacte
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    brief_sha256 = digest(brief)                                 # empreinte déterministe du Brief source (S2)
    base: Dict[str, Any] = {
        "fact_type": "specification",
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "brief_ref": proposal_id,
        "brief_sha256": brief_sha256,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "SPEC_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    # Diagnostic RV-1 — API publique claude_code_runtime : source unique de la redaction des secrets.
    diag = diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                      timed_out=timed_out, envelope=envelope)
    nonzero_exit = exit_code is not None and exit_code != 0
    # Échec d'appel : timeout / exit non nul / enveloppe illisible / erreur cerveau / subtype ≠ success.
    if (timed_out or envelope is None or nonzero_exit
            or envelope.get("is_error") or envelope.get("subtype") != "success"):
        if timed_out:
            reason = "timeout"
        elif envelope is None:
            reason = "enveloppe illisible"
        elif nonzero_exit:
            reason = f"exit non nul ({exit_code})"
        elif envelope.get("is_error") and envelope.get("subtype") == "success":
            reason = "erreur client sans détail (voir diagnostic)"
        else:
            reason = str(envelope.get("api_error_status") or envelope.get("subtype") or "erreur d'appel")
        if reason == "success":     # garde-fou : ``error`` ne peut jamais afficher "success"
            reason = "erreur client sans détail (voir diagnostic)"
        return {**base, "status": "failed", "specification": None, "error": reason, "diagnostic": diag}
    # Réponse présente : valider localement le format Spécification (schéma strict).
    result = envelope.get("result")
    spec: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                spec = parsed
        except json.JSONDecodeError:
            spec = None
    elif isinstance(result, dict):
        spec = result
    if not _valid_specification(spec):
        return {**base, "status": "failed", "specification": None,
                "error": "format Spécification invalide", "diagnostic": diag}
    return {**base, "status": "proposed", "specification": spec, "error": None, "diagnostic": None}


@runtime_checkable
class SpecificationCapability(Protocol):
    """**Capacité** « spécifier un Brief » (R8) — BrainAI en dépend, jamais d'un outil concret.

    Contrat minimal : produire, pour un ``brief`` structuré, la matière brute d'un fait `specification`
    (enveloppe/exit/timeout/prompt), **après** contrôle du budget. L'implémentation concrète (ici Claude
    Code) est interchangeable ; le reste du système ne connaît que ce Protocol, jamais la commande
    ``claude``."""

    capability: str
    name: str
    model: str

    def propose(self, brief: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeSpecificationAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`SpecificationCapability` (R8)."""

    capability = "specification"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = 120.0, claude_bin: str = "claude"):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré, modèle explicite,
        plafond coût, outils fichier/bash **désactivés** (Spécification = texte seul, aucun Build)."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(SPEC_SCHEMA, ensure_ascii=False),
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        # Env minimal confiné, **composition identique** à la compréhension (T3/B1) : PATH/LANG, plus
        # HOME/USER/LOGNAME si présents (résolution de l'utilisateur pour l'auth hors-bande du trousseau).
        # Aucun secret, aucun token : l'environnement du parent n'est jamais hérité globalement.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"), "LANG": "C.UTF-8"}
        for k in ("HOME", "USER", "LOGNAME"):
            if os.environ.get(k):
                env[k] = os.environ[k]
        return env

    def propose(self, brief: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le reste ne
        couvre pas le plafond (``run_confined`` **non atteint**). Renvoie ``{called, envelope, exit_code,
        timed_out, prompt, argv, stdout, stderr}`` — ne construit pas le fait (voir
        :func:`build_specification`)."""
        prompt = build_prompt(brief)
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


def produce_specification(*, brief_source: Dict[str, Any], adapter: SpecificationCapability,
                          store: Any, budget_remaining_usd: float, cwd: Path,
                          clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """**Chemin normal unique** Brief → Spécification. Aucun driver externe ne recompose ces étapes.

    Séquence : (1) **valide** le fait Brief source (refus **avant** toute frontière externe si invalide) ;
    (2) appelle ``adapter.propose`` — dont la **garde budget** ; (3) si refus budget, **aucun fait** (aucune
    frontière franchie) ; (4) sinon **horodatage réel** via ``clock`` (injectable), construction du fait,
    enregistrement dans ``store`` — **exactement un fait par tentative externe**, **aucun retry** (R6).

    Renvoie ``{"attempted", "recorded", "refused", "fact"}``."""
    _, brief = validate_brief_source(brief_source)               # (1) refus AVANT tout appel externe
    raw = adapter.propose(brief, cwd=cwd, budget_remaining_usd=budget_remaining_usd)  # (2) garde budget incluse
    if not raw.get("called"):                                    # (3) refus budget : aucune frontière, aucun fait
        return {"attempted": False, "recorded": False, "refused": raw.get("refused"), "fact": None}
    as_of = clock()                                              # (4) horodatage réel (jamais figé)
    fact = build_specification(
        brief_source=brief_source, prompt=raw["prompt"], capability=adapter.capability,
        adapter=adapter.name, model=adapter.model, envelope=raw["envelope"], exit_code=raw["exit_code"],
        timed_out=raw["timed_out"], as_of=as_of, argv=raw.get("argv"),
        stdout=raw.get("stdout"), stderr=raw.get("stderr"))
    recorded = store.record(fact)                                # un seul fait, jamais de retry
    return {"attempted": True, "recorded": True, "refused": None, "fact": recorded}


__all__ = ["SPEC_SCHEMA", "BriefSourceError", "validate_brief_source", "build_prompt",
           "build_specification", "produce_specification", "SpecificationCapability",
           "ClaudeCodeSpecificationAdapter"]
