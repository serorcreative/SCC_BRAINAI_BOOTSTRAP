"""BRAINAI-CONVERSATION-001 · Tâche 1 — contrat de la capacité **conversation** (dialoguer). Tests **0 €** :
schéma structuré, prompt déterministe, argv confiné (jamais shell), et **refus budgétaire sans appel réel**
(``run_confined`` jamais atteint). Aucune orchestration, aucun fait produit, aucun appel facturable."""

from __future__ import annotations

from pathlib import Path

import pytest

from scc_brainai_bootstrap.builder import conversation as C
from scc_brainai_bootstrap.builder.conversation import (
    CONVERSATION_SCHEMA,
    ClaudeCodeConversationAdapter,
    ConversationCapability,
    build_prompt,
)


def test_schema_shape_reply_and_readiness_appraisal():
    props = CONVERSATION_SCHEMA["properties"]
    assert CONVERSATION_SCHEMA["additionalProperties"] is False
    assert set(CONVERSATION_SCHEMA["required"]) == {"reply", "readiness"}   # matured_need facultatif
    assert props["readiness"]["enum"] == ["continue", "ready"]             # appréciation, pas autorisation
    assert props["reply"]["type"] == "string" and props["matured_need"]["type"] == "string"


def test_build_prompt_is_deterministic_and_carries_message_and_history():
    p0 = build_prompt("Je veux un outil", [])
    assert p0 == build_prompt("Je veux un outil", [])                       # déterministe
    assert "Je veux un outil" in p0 and "HISTORIQUE" not in p0             # pas d'historique au 1er tour
    assert "NE CONSTRUIS RIEN" in p0 and "confirmation humaine" in p0      # dialogue, pas réalisation
    hist = [{"role": "user", "content": "salut"}, {"role": "assistant", "content": "bonjour"}]
    p1 = build_prompt("et ensuite ?", hist)
    assert "HISTORIQUE" in p1 and "Utilisateur: salut" in p1 and "BrainAI: bonjour" in p1
    assert "MESSAGE : et ensuite ?" in p1


def test_adapter_conforms_to_capability_protocol():
    assert isinstance(ClaudeCodeConversationAdapter(), ConversationCapability)


def test_argv_is_confined_json_structured_and_builds_nothing():
    adapter = ClaudeCodeConversationAdapter(model="haiku", max_budget_usd=0.5)
    argv = adapter.build_argv("un prompt")
    assert argv[0] == "claude" and "-p" in argv and "un prompt" in argv
    assert "--json-schema" in argv and "--model" in argv and "haiku" in argv
    assert "--max-budget-usd" in argv and "0.5" in argv
    # un tour de dialogue est du texte seul : les outils qui construisent/lisent sont désactivés
    for tool in ("Bash", "Edit", "Write", "Read"):
        assert tool in argv
    assert "--disallowedTools" in argv


def test_propose_refuses_when_budget_insufficient_without_any_real_call(monkeypatch, tmp_path):
    # Preuve 0 € : si le budget restant ne couvre pas le plafond, run_confined n'est JAMAIS atteint (R2/B4).
    def _boom(*a, **k):
        raise AssertionError("run_confined ne doit pas être appelé quand le budget est insuffisant")
    monkeypatch.setattr(C, "run_confined", _boom)
    adapter = ClaudeCodeConversationAdapter(max_budget_usd=0.5)
    out = adapter.propose("bonjour", history=[], cwd=Path(tmp_path), budget_remaining_usd=0.1)
    assert out["called"] is False and out["envelope"] is None and out["refused"] == "budget insuffisant"
    assert "bonjour" in out["prompt"]                                      # prompt calculé, mais aucun appel
