"""Capacité de **conversation** — dialoguer avec l'utilisateur au sein d'une Pursuit (BRAINAI-CONVERSATION-001).

**Doctrine :** *Pursuit = unité de cognition · Fact = unité de mémoire/trace · Conversation = canal.* Le
dialogue de compréhension appartient à **la même Pursuit** que la future réalisation — il n'a **pas** d'identité
propre. Cette faculté ne construit **rien** (aucun Brief/Spécification/Manifeste) : elle **répond, questionne,
challenge, aide à réfléchir**, et **apprécie** la maturité du besoin (``readiness``).

BrainAI dépend d'une **capacité**, jamais d'un outil (R8) : l'outil concret (ici **Claude Code**) est un
adaptateur interchangeable. La ``readiness`` est une **appréciation cognitive / proposition** : elle ne déclenche
**jamais** la réalisation — **BrainAI propose, seule une confirmation humaine autorisera** le passage à l'arc
(Tâche 2). Confinement identique aux autres capacités : ``argv`` only, env minimal, timeout, **plafond coût**
contrôlé **avant** l'appel (R2/B4), **aucun retry** (R6). Primitives runtime via :mod:`claude_code_runtime`.
Stdlib pur. **Tâche 1 = contrat seul** (aucune orchestration, aucun appel réel, aucun fait produit).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import diagnostic, extract_cost, parse_envelope
from scc_brainai_bootstrap.builder.tool_runner import run_confined

# Schéma **structuré** de sortie d'un tour de conversation (forcé par ``--json-schema``). ``reply`` = réponse
# naturelle ; ``readiness`` = appréciation (``continue`` tant que le besoin n'est pas mûr ; ``ready`` quand il
# l'est) ; ``matured_need`` = besoin reformulé prêt à réaliser (fourni seulement quand ``ready``).
CONVERSATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {"type": "string"},                                   # réponse conversationnelle
        "readiness": {"type": "string", "enum": ["continue", "ready"]},  # appréciation cognitive
        "matured_need": {"type": "string"},                            # besoin mûri (si ready)
    },
    "required": ["reply", "readiness"],
}

# Champs requis d'un tour valide + valeurs d'appréciation admises (garde-fou du contrat).
_TURN_REQUIRED = tuple(CONVERSATION_SCHEMA["required"])
_READINESS_VALUES = tuple(CONVERSATION_SCHEMA["properties"]["readiness"]["enum"])


def build_prompt(message: str, history: List[Dict[str, Any]]) -> str:
    """Prompt déterministe d'un tour de dialogue. ``history`` : tours antérieurs (``{role, content}``) relus par
    le moteur depuis le ``pursuit_id`` — jamais depuis l'UI. BrainAI **dialogue** et **apprécie** la maturité ;
    il ne construit rien et n'autorise rien."""
    lines: List[str] = []
    for turn in history or []:
        role = "Utilisateur" if turn.get("role") == "user" else "BrainAI"
        lines.append(f"{role}: {turn.get('content', '')}")
    convo = "\n".join(lines)
    return (
        "Tu es BrainAI, un partenaire de réflexion (architecte, ingénieur, associé). Dialogue NATURELLEMENT : "
        "réponds, pose des questions, challenge, aide à réfléchir, propose des pistes, demande des précisions. "
        "NE CONSTRUIS RIEN (aucun brief, aucune spécification, aucun manifeste). Apprécie la maturité du besoin : "
        "``readiness='continue'`` tant qu'il n'est pas assez clair ; ``readiness='ready'`` lorsqu'il l'est — et "
        "fournis alors ``matured_need`` (le besoin reformulé, prêt à réaliser). La ``readiness`` est une "
        "APPRÉCIATION : elle ne lance jamais la réalisation ; seule une confirmation humaine l'autorisera. "
        "Réponds UNIQUEMENT via le schéma imposé.\n\n"
        + (f"HISTORIQUE :\n{convo}\n\n" if convo else "")
        + f"MESSAGE : {message}"
    )


def build_turn(*, message: str, prompt: str, capability: str, adapter: str, model: Optional[str],
               envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool, as_of: str,
               argv: Any = None, stdout: Any = None, stderr: Any = None,
               pursuit_ref: Optional[str] = None) -> Dict[str, Any]:
    """Construit un **fait tour** honnête (pur, testable) — miroir de :func:`build_proposal`.

    ``proposed`` uniquement si : pas de timeout, ``exit_code == 0`` (ou ``None``), enveloppe lisible, non
    ``is_error``, ``subtype == "success"``, ET tour conforme (``reply`` chaîne, ``readiness`` ∈ enum). Sinon
    ``failed`` — sans crash, avec ``error`` (jamais ``"success"``) et un ``diagnostic`` brut borné assaini.
    Coût toujours enregistré (réel ou ``unavailable``). ``diagnostic = None`` sur un fait ``proposed``. Porte
    ``fact_type='turn'`` et un ``pursuit_ref`` (ancrage de provenance vers la Pursuit). **Ne construit rien**
    (aucun brief/spéc/manifeste) : un tour n'est que du dialogue et une **appréciation** de maturité."""
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    base: Dict[str, Any] = {
        "fact_type": "turn",
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "message": message,
        "pursuit_ref": pursuit_ref,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "CONVERSATION_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
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
        return {**base, "status": "failed", "reply": None, "readiness": None, "matured_need": None,
                "error": reason, "diagnostic": diag}
    # Réponse présente : valider le format du tour.
    result = envelope.get("result")
    turn: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                turn = parsed
        except json.JSONDecodeError:
            turn = None
    elif isinstance(result, dict):
        turn = result
    valid = (isinstance(turn, dict) and all(k in turn for k in _TURN_REQUIRED)
             and isinstance(turn.get("reply"), str) and turn.get("readiness") in _READINESS_VALUES)
    if not valid:
        return {**base, "status": "failed", "reply": None, "readiness": None, "matured_need": None,
                "error": "format tour invalide", "diagnostic": diag}
    matured = turn.get("matured_need")
    matured = matured if isinstance(matured, str) and matured.strip() else None
    return {**base, "status": "proposed", "reply": turn["reply"], "readiness": turn["readiness"],
            "matured_need": matured, "error": None, "diagnostic": None}


@runtime_checkable
class ConversationCapability(Protocol):
    """**Capacité** « dialoguer » (R8) — BrainAI en dépend, jamais d'un outil concret.

    Contrat minimal : produire, pour un ``message`` et un ``history`` (tours antérieurs de la **même** Pursuit),
    la matière brute d'un tour (enveloppe/exit/timeout/prompt), **après** contrôle du budget. L'implémentation
    concrète (ici Claude Code) est interchangeable ; le reste du système ne connaît que ce Protocol."""

    capability: str
    name: str
    model: str

    def propose(self, message: str, *, history: List[Dict[str, Any]], cwd: Path,
                budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeConversationAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`ConversationCapability` (R8)."""

    capability = "conversation"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = 120.0, claude_bin: str = "claude"):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré, modèle explicite, plafond coût,
        outils fichier/bash **désactivés** — un tour de dialogue est du texte seul, il ne construit rien."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(CONVERSATION_SCHEMA, ensure_ascii=False),
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

    def propose(self, message: str, *, history: List[Dict[str, Any]], cwd: Path,
                budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le reste ne couvre
        pas le plafond (``run_confined`` **non atteint**). Renvoie ``{called, envelope, exit_code, timed_out,
        prompt, argv, stdout, stderr}`` — ne construit pas le fait (séparation)."""
        prompt = build_prompt(message, history)
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


__all__ = ["CONVERSATION_SCHEMA", "build_prompt", "build_turn", "ConversationCapability",
           "ClaudeCodeConversationAdapter"]
