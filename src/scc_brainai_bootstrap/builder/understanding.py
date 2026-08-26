"""Capacité de **compréhension** — produire un Brief structuré à partir d'un besoin (JALON-ZERO, B).

BrainAI dépend d'une **capacité**, jamais d'un outil (R8) : le noyau demande « comprends ce besoin,
propose un Brief » ; l'outil concret (ici **Claude Code** non-interactif) est un **adaptateur**
interchangeable (demain Codex, Gemini, Cursor…). Un modèle **propose**, il ne décide jamais (R5) :
la sortie est un **fait proposition** (``status: proposed``), soumis à validation humaine.

Confinement de l'appel : ``argv`` only (jamais shell), ``cwd`` neutre, **env minimal** (``HOME``
requis pour l'auth de session, ``PATH``/``LANG`` ; rien d'autre), **timeout**, **plafond coût**
(``--max-budget-usd``). Le coût réel est lu dans l'enveloppe (``total_cost_usd``) — sinon
``unavailable``, **jamais fabriqué** (R2). Aucun retry (R6). Stdlib pur.

Les primitives runtime Claude Code (enveloppe, coût, diagnostic RV-1 + redaction) proviennent de l'API
**publique** de :mod:`claude_code_runtime` — source unique. Des **alias de compatibilité** non publics
(``_extract_cost``/``_diagnostic``/``_redact``/``_DIAG_MAX``) sont conservés pour les références internes
historiques.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import (
    DIAG_MAX,
    diagnostic,
    extract_cost,
    parse_envelope,
    redact,
)
from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract, claude_text_contract
from scc_brainai_bootstrap.builder.cognitive_identity import CONDENSED_IDENTITY, compose_prompt
from scc_brainai_bootstrap.builder.provider_env import (
    AUTH_KEYCHAIN_HOME, auth_channel, confined_env, inbound_channels)
from scc_brainai_bootstrap.builder.tool_runner import (
    DEFAULT_WATCHDOG_S, SAFETY_WATCHDOG_EXCEEDED, run_confined)

# Alias de compatibilité — NON publics (hors ``__all__``). Préservent les noms internes historiques
# encore référencés (``understanding._redact``, ``understanding._DIAG_MAX``, …). Comportement identique.
_extract_cost = extract_cost
_diagnostic = diagnostic
_redact = redact
_DIAG_MAX = DIAG_MAX

# Schéma **structuré** attendu du Brief (sortie forcée par ``--json-schema``). Champs minimaux d'une
# compréhension de besoin : objectif reformulé, contexte, acteurs, périmètre, hypothèses, questions
# ouvertes, contraintes — un modèle **décrit** le besoin, il ne décide ni ne spécifie (R5).
BRIEF_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "objective": {"type": "string"},                              # objectif reformulé
        "context": {"type": "string"},                                # contexte
        "actors": {"type": "array", "items": {"type": "string"}},     # acteurs / utilisateurs pressentis
        "scope": {"type": "array", "items": {"type": "string"}},      # périmètre initial
        "assumptions": {"type": "array", "items": {"type": "string"}},  # hypothèses
        "open_questions": {"type": "array", "items": {"type": "string"}},  # questions ouvertes
        "constraints": {"type": "array", "items": {"type": "string"}},  # contraintes identifiées
    },
    "required": ["objective", "context", "actors", "scope", "assumptions",
                 "open_questions", "constraints"],
}

_BRIEF_REQUIRED = tuple(BRIEF_SCHEMA["required"])


def build_prompt(need: str) -> str:
    """Prompt déterministe : demande un Brief structuré (aucun secret, aucune donnée fabriquée).

    Préfixé par l'**essence** de l'identité (``CONDENSED_IDENTITY``) via :func:`compose_prompt` — la voix à
    coût réduit des facultés à sortie structurée : BrainAI reste le chef de projet qui nomme ses hypothèses,
    même quand la sortie est un schéma. Contrat et :data:`BRIEF_SCHEMA` inchangés (COGNITIVE-IDENTITY-001 T3)."""
    mission = (
        "Tu produis un BRIEF de compréhension à partir d'un besoin utilisateur en langage naturel. "
        "Réponds UNIQUEMENT via le schéma imposé : objectif reformulé, contexte, acteurs ou "
        "utilisateurs pressentis, périmètre initial, hypothèses, questions ouvertes, contraintes "
        "identifiées. Ne réalise aucune action, ne rédige aucune spécification, ne propose aucune "
        "décision : décris et cadre le besoin. Toute hypothèse faite faute d'information est nommée "
        "comme telle dans le champ ``assumptions`` — jamais présentée comme un fait.\n\n"
        f"BESOIN : {need}"
    )
    return compose_prompt(CONDENSED_IDENTITY, mission)


def build_proposal(*, need: str, prompt: str, capability: str, adapter: str, model: str,
                   envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool,
                   as_of: str, argv: Any = None, stdout: Any = None,
                   stderr: Any = None, pursuit_ref: Optional[str] = None) -> Dict[str, Any]:
    """Construit un **fait proposition** honnête (pur, testable).

    ``proposed`` uniquement si : pas de timeout, ``exit_code == 0`` (ou ``None``), enveloppe lisible,
    non ``is_error``, ``subtype == "success"``, ET Brief conforme. Sinon ``failed`` — sans crash, avec
    ``error`` (jamais ``"success"``) et un ``diagnostic`` brut borné assaini. Coût toujours enregistré
    (réel ou ``unavailable``). ``diagnostic = None`` sur un fait ``proposed``. Porte ``fact_type='brief'``
    et un ``pursuit_ref`` optionnel (ancrage de provenance vers la Pursuit ; ``None`` hors orchestration)."""
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    base: Dict[str, Any] = {
        "fact_type": "brief",
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "need": need,
        "pursuit_ref": pursuit_ref,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "BRIEF_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    diag = diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                      timed_out=timed_out, envelope=envelope)
    nonzero_exit = exit_code is not None and exit_code != 0
    # Échec d'appel : watchdog de sécurité / exit non nul / enveloppe illisible / erreur cerveau / subtype ≠ success.
    if (timed_out or envelope is None or nonzero_exit
            or envelope.get("is_error") or envelope.get("subtype") != "success"):
        if timed_out:
            reason = SAFETY_WATCHDOG_EXCEEDED   # PAS un timeout de cognition : fusible de dernier recours
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
        return {**base, "status": "failed", "brief": None, "error": reason, "diagnostic": diag}
    # Réponse présente : valider le format Brief.
    result = envelope.get("result")
    brief: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                brief = parsed
        except json.JSONDecodeError:
            brief = None
    elif isinstance(result, dict):
        brief = result
    if not isinstance(brief, dict) or not all(k in brief for k in _BRIEF_REQUIRED):
        return {**base, "status": "failed", "brief": None, "error": "format Brief invalide",
                "diagnostic": diag}
    return {**base, "status": "proposed", "brief": brief, "error": None, "diagnostic": None}


@runtime_checkable
class NeedUnderstandingCapability(Protocol):
    """**Capacité** « comprendre un besoin » (R8) — BrainAI en dépend, jamais d'un outil concret.

    Contrat minimal : produire, pour un ``need`` en langage naturel, la matière brute d'un fait
    proposition (enveloppe/exit/timeout/prompt), **après** contrôle du budget. L'implémentation
    concrète (ici Claude Code) est interchangeable ; le reste du système ne connaît que ce Protocol,
    jamais la commande ``claude``."""

    capability: str
    name: str

    def propose(self, need: str, *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeUnderstandingAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`NeedUnderstandingCapability` (R8)."""

    capability = "understanding"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = DEFAULT_WATCHDOG_S, claude_bin: str = "claude",
                 auth_mode: str = AUTH_KEYCHAIN_HOME, isolated_home: Optional[str] = None,
                 oauth_token: Optional[str] = None):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin
        self.auth_mode = auth_mode              # bascule d'auth (B1 défaut) — étanchéité J3/T1
        self.isolated_home = isolated_home
        self.oauth_token = oauth_token

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré, modèle explicite,
        plafond coût, outils fichier/bash **désactivés** (Brief = texte seul)."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(BRIEF_SCHEMA, ensure_ascii=False),
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        # Env confiné **centralisé** (provider_env) selon la bascule d'auth : B1 (défaut, barreau trousseau)
        # = comportement historique ; cible = HOME isolé + jeton explicite (étanchéité J3/T1, RS-030). Le canal
        # d'auth est **déclaré** (provider_env.auth_channel/inbound_channels) et indépendant de la techno (AM6).
        return confined_env(self.auth_mode, isolated_home=self.isolated_home, oauth_token=self.oauth_token)

    def contract(self) -> AdapterContract:
        """Contrat d'adaptateur complet (T2) : capacité, canal d'auth (RV-2), canaux entrants (RV-2 étendue),
        coût réel/unavailable (I6), plafond natif = **arrêt agrégé** (RS-039), confinement (aucun outil fichier)."""
        return claude_text_contract(
            capability=self.capability, auth_channel=auth_channel(self.auth_mode),
            inbound_channels=inbound_channels(self.auth_mode),
            tools_disallowed=["Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch"])

    def propose(self, need: str, *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le reste
        ne couvre pas le plafond. Renvoie ``{called, envelope, exit_code, timed_out, prompt, argv,
        stdout, stderr}`` — ne construit pas le fait (séparation : voir :func:`build_proposal`)."""
        prompt = build_prompt(need)
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


__all__ = ["BRIEF_SCHEMA", "build_prompt", "parse_envelope", "build_proposal",
           "NeedUnderstandingCapability", "ClaudeCodeUnderstandingAdapter"]
