"""Capacité de **compréhension** — produire un Brief structuré à partir d'un besoin (JALON-ZERO, B).

BrainAI dépend d'une **capacité**, jamais d'un outil (R8) : le noyau demande « comprends ce besoin,
propose un Brief » ; l'outil concret (ici **Claude Code** non-interactif) est un **adaptateur**
interchangeable (demain Codex, Gemini, Cursor…). Un modèle **propose**, il ne décide jamais (R5) :
la sortie est un **fait proposition** (``status: proposed``), soumis à validation humaine.

Confinement de l'appel : ``argv`` only (jamais shell), ``cwd`` neutre, **env minimal** (``HOME``
requis pour l'auth de session, ``PATH``/``LANG`` ; rien d'autre), **timeout**, **plafond coût**
(``--max-budget-usd``). Le coût réel est lu dans l'enveloppe (``total_cost_usd``) — sinon
``unavailable``, **jamais fabriqué** (R2). Aucun retry (R6). Stdlib pur.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.tool_runner import run_confined

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
    """Prompt déterministe : demande un Brief structuré (aucun secret, aucune donnée fabriquée)."""
    return (
        "Tu produis un BRIEF de compréhension à partir d'un besoin utilisateur en langage naturel. "
        "Réponds UNIQUEMENT via le schéma imposé : objectif reformulé, contexte, acteurs ou "
        "utilisateurs pressentis, périmètre initial, hypothèses, questions ouvertes, contraintes "
        "identifiées. Ne réalise aucune action, ne rédige aucune spécification, ne propose aucune "
        "décision : décris et cadre le besoin.\n\n"
        f"BESOIN : {need}"
    )


def parse_envelope(stdout: str) -> Optional[Dict[str, Any]]:
    """Parse l'enveloppe JSON de Claude Code (``--output-format json``), ou ``None`` si invalide."""
    try:
        obj = json.loads(stdout)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_cost(envelope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Coût **réel** si présent dans l'enveloppe, sinon ``unavailable`` — jamais inventé."""
    if envelope is not None and isinstance(envelope.get("total_cost_usd"), (int, float)):
        return {"value": float(envelope["total_cost_usd"]), "kind": "real"}
    return {"value": None, "kind": "unavailable"}


def build_proposal(*, need: str, prompt: str, capability: str, adapter: str, model: str,
                   envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool,
                   as_of: str) -> Dict[str, Any]:
    """Construit un **fait proposition** honnête à partir du résultat de l'adaptateur (pur, testable).

    Succès (``proposed``) uniquement si l'appel a réussi ET la réponse respecte le schéma Brief ;
    sinon ``failed`` (timeout, erreur, ou format invalide) — **sans crash**, avec l'erreur reflétée.
    Le coût est toujours enregistré (réel ou ``unavailable``)."""
    cost = _extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    base: Dict[str, Any] = {
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "need": need,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "BRIEF_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    # Échec d'appel (timeout / exit non nul / enveloppe illisible / erreur cerveau).
    if timed_out or envelope is None or envelope.get("is_error") or envelope.get("subtype") != "success":
        reason = "timeout" if timed_out else (
            "enveloppe illisible" if envelope is None else
            str(envelope.get("api_error_status") or envelope.get("subtype") or "erreur d'appel"))
        return {**base, "status": "failed", "brief": None, "error": reason}
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
        return {**base, "status": "failed", "brief": None, "error": "format Brief invalide"}
    return {**base, "status": "proposed", "brief": brief, "error": None}


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
                 timeout: float = 120.0, claude_bin: str = "claude"):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin

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
        # Env minimal : HOME est requis pour l'auth de session locale ; rien d'autre de sensible.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"), "LANG": "C.UTF-8"}
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        return env

    def propose(self, need: str, *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le
        reste ne couvre pas le plafond. Renvoie ``{envelope, exit_code, timed_out, prompt, called}``
        — ne construit pas le fait (séparation : voir :func:`build_proposal`)."""
        prompt = build_prompt(need)
        if budget_remaining_usd < self.max_budget_usd:
            return {"called": False, "envelope": None, "exit_code": None, "timed_out": False,
                    "prompt": prompt, "refused": "budget insuffisant"}
        result = run_confined(self.build_argv(prompt), cwd=cwd, timeout=self.timeout, env=self._env())
        envelope = None if result["timed_out"] else parse_envelope(result["stdout"])
        return {"called": True, "envelope": envelope, "exit_code": result["exit_code"],
                "timed_out": result["timed_out"], "prompt": prompt}


__all__ = ["BRIEF_SCHEMA", "build_prompt", "parse_envelope", "build_proposal",
           "NeedUnderstandingCapability", "ClaudeCodeUnderstandingAdapter"]
