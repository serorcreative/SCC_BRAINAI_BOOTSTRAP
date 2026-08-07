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

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import parse_envelope
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


__all__ = ["CONVERSATION_SCHEMA", "build_prompt", "ConversationCapability", "ClaudeCodeConversationAdapter"]
