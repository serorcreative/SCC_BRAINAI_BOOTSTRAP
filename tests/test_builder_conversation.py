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
    build_turn,
)
from scc_brainai_bootstrap.builder.turns import TurnStore


def _env(result_obj, *, ok=True, cost=0.02):
    import json
    return {"type": "result", "subtype": "success" if ok else "error_max_turns", "is_error": not ok,
            "api_error_status": None, "num_turns": 1,
            "result": result_obj if isinstance(result_obj, str) else json.dumps(result_obj, ensure_ascii=False),
            "total_cost_usd": cost, "usage": {"input_tokens": 10, "output_tokens": 20}}


def _mk_turn(*, envelope, exit_code=0, timed_out=False, message="bonjour", as_of="2026-08-07T00:00:00+00:00"):
    return build_turn(message=message, prompt="p", capability="conversation", adapter="claude_code",
                      model="fake-model", envelope=envelope, exit_code=exit_code, timed_out=timed_out,
                      as_of=as_of, argv=["claude"], stdout="out", stderr="", pursuit_ref="pursuit_x")


def test_schema_shape_reply_and_readiness_appraisal():
    props = CONVERSATION_SCHEMA["properties"]
    assert CONVERSATION_SCHEMA["additionalProperties"] is False
    assert set(CONVERSATION_SCHEMA["required"]) == {"reply", "readiness"}   # matured_need facultatif
    assert props["readiness"]["enum"] == ["continue", "ready"]             # appréciation, pas autorisation
    assert props["reply"]["type"] == "string"
    # matured_need STRUCTURÉ (C9) : besoin fondamental + solutions/inconnues/hypothèses (listes d'éléments).
    mn = props["matured_need"]
    assert mn["type"] == "object" and mn["additionalProperties"] is False
    assert set(mn["required"]) == {"besoin_fondamental", "solutions_privilegiees",
                                   "inconnues_nommees", "hypotheses_actives"}
    assert mn["properties"]["besoin_fondamental"]["type"] == "string"
    elem = mn["properties"]["solutions_privilegiees"]["items"]              # ELEMENT = statement + source (additif J1)
    assert elem["type"] == "object" and elem["additionalProperties"] is False
    assert set(elem["required"]) == {"statement"}                          # source OPTIONNELLE
    assert set(elem["properties"]) == {"statement", "source"}
    # EPISTEMIC-PROVENANCE (J1) : « vérifié » est STRUCTURELLEMENT inémettable par le modèle.
    assert set(elem["properties"]["source"]["enum"]) == {"fourni_par_utilisateur", "connaissance_modele",
                                                         "deduit", "suppose", "inconnu"}
    assert "verifie" not in elem["properties"]["source"]["enum"]
    assert "vérifié" not in elem["properties"]["source"]["enum"]


def test_build_prompt_is_deterministic_and_carries_message_and_history():
    p0 = build_prompt("Je veux un outil", [])
    assert p0 == build_prompt("Je veux un outil", [])                       # déterministe
    assert "Je veux un outil" in p0 and "HISTORIQUE" not in p0             # pas d'historique au 1er tour
    assert "NE CONSTRUIS RIEN" in p0 and "confirmation humaine" in p0      # dialogue, pas réalisation
    hist = [{"role": "user", "content": "salut"}, {"role": "assistant", "content": "bonjour"}]
    p1 = build_prompt("et ensuite ?", hist)
    assert "HISTORIQUE" in p1 and "Utilisateur: salut" in p1 and "BrainAI: bonjour" in p1
    assert "MESSAGE : et ensuite ?" in p1


def test_build_prompt_injects_cognitive_identity_before_the_mission():
    # COGNITIVE-IDENTITY-001 — le prompt d'un tour EST identité (nature) puis mission (tâche) : la voix héritée
    # est réinjectée, l'ordre nature → tâche est garanti par compose_prompt.
    from scc_brainai_bootstrap.builder.cognitive_identity import COGNITIVE_IDENTITY
    p = build_prompt("Je veux débattre d'une idée", [])
    assert COGNITIVE_IDENTITY[:60] in p                                    # identité complète injectée
    assert "ta nature" in p.lower()                                        # cadrage nature, pas consigne
    assert p.index(COGNITIVE_IDENTITY[:60]) < p.index("MISSION DU TOUR")   # identité AVANT mission
    assert p.index("MISSION DU TOUR") < p.index("MESSAGE :")               # mission AVANT le message


def test_build_prompt_carries_the_four_mechanism_phrases():
    # Les QUATRE traductions locales des mécanismes (M3/M4/M6/M8) sont présentes, sans règle nouvelle ni
    # méthode récitée : progression à chaque tour, plusieurs lectures, prise de position, anti-piétinement.
    p = build_prompt("un message", [])
    assert "l'interrogatoire : une suite de questions sans pensée offerte en retour" in p
    assert "envisage plusieurs lectures possibles" in p
    assert "ne reste pas neutre : indique celle que tu privilégies" in p
    assert "ne pose pas une question de plus : propose" in p               # anti-piétinement : proposer
    assert "la conversation piétine" in p
    # Les consignes historiques sont conservées.
    assert "NE CONSTRUIS RIEN" in p and "confirmation humaine" in p


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


# ===================================================================== #
# build_turn — fait tour honnête (miroir de build_proposal)
# ===================================================================== #
def test_build_turn_proposed_carries_reply_readiness_and_optional_matured():
    fact = _mk_turn(envelope=_env({"reply": "Précise la cible.", "readiness": "continue"}, cost=0.03))
    assert fact["status"] == "proposed" and fact["fact_type"] == "turn"
    assert fact["reply"] == "Précise la cible." and fact["readiness"] == "continue"
    assert fact["matured_need"] is None                                   # absent quand non fourni
    assert fact["cost"] == {"value": 0.03, "kind": "real"} and fact["error"] is None
    assert fact["diagnostic"] is None and fact["pursuit_ref"] == "pursuit_x"
    # Besoin mûri LEGACY (chaîne) : normalisé en structure C9 (rétrocompat D3), sans réécrire le fait source.
    ready = _mk_turn(envelope=_env({"reply": "ok", "readiness": "ready", "matured_need": "Gérer un refuge"}))
    assert ready["status"] == "proposed" and ready["readiness"] == "ready"
    assert ready["matured_need"] == {"besoin_fondamental": "Gérer un refuge", "solutions_privilegiees": [],
                                     "inconnues_nommees": [], "hypotheses_actives": []}
    # Besoin mûri STRUCTURÉ (C9) : conservé tel quel.
    struct = {"besoin_fondamental": "Gérer un refuge", "solutions_privilegiees": [{"statement": "app web"}],
              "inconnues_nommees": [{"statement": "multi-site ?"}], "hypotheses_actives": []}
    ready2 = _mk_turn(envelope=_env({"reply": "ok", "readiness": "ready", "matured_need": struct}))
    assert ready2["status"] == "proposed" and ready2["matured_need"] == struct


def test_build_turn_continue_with_matured_need_is_valid_and_keeps_it():
    # A4-2 CORRIGÉE (défaut révélé par le test produit réel, pursuit_e4b6033b3b08 tour 8) : ``matured_need`` +
    # ``continue`` COEXISTENT — BrainAI a une compréhension mûre ET la conception continue. Tour VALIDE
    # (``proposed``), matured_need CONSERVÉ, message gardé. La réalisation reste gouvernée par ``ready`` + acte
    # humain ``realize`` (A4-1/D3), jamais par ce tour ; rien n'est transformé en ``ready``.
    kept = _mk_turn(envelope=_env({"reply": "je continue la conception", "readiness": "continue",
                                   "matured_need": "Gérer un refuge"}))
    assert kept["status"] == "proposed" and kept["readiness"] == "continue"
    assert kept["matured_need"]["besoin_fondamental"] == "Gérer un refuge"   # CONSERVÉ (jamais None/nulled)
    assert kept["reply"] == "je continue la conception" and kept["error"] is None
    # Un ``matured_need`` vide/blanc sur un ``continue`` reste conforme (il n'est pas un besoin mûri).
    blank = _mk_turn(envelope=_env({"reply": "on continue", "readiness": "continue", "matured_need": "  "}))
    assert blank["status"] == "proposed" and blank["matured_need"] is None


def test_build_turn_c8_ready_requires_definable_besoin_fondamental():
    # C8/C9 : un besoin **mûr** doit être **définissable**. Un ``ready`` sans besoin fondamental ⇒ failed.
    empty = _mk_turn(envelope=_env({"reply": "ok", "readiness": "ready",
                                    "matured_need": {"besoin_fondamental": "  ", "solutions_privilegiees": [],
                                                     "inconnues_nommees": [], "hypotheses_actives": []}}))
    assert empty["status"] == "failed" and empty["error"] == "ready sans besoin fondamental"
    none = _mk_turn(envelope=_env({"reply": "ok", "readiness": "ready"}))   # ready sans matured du tout
    assert none["status"] == "failed" and none["error"] == "ready sans besoin fondamental"


def test_build_turn_c8_named_unknowns_do_not_block_ready():
    # C8 : des ``inconnues_nommees`` non vides ne rendent JAMAIS un ready invalide dès lors que le besoin
    # fondamental est défini — l'inconnue peut rester ouverte (générique, aucun domaine).
    m = {"besoin_fondamental": "Rendre un service accessible au plus grand nombre",
         "solutions_privilegiees": [{"statement": "une piste initiale"}],
         "inconnues_nommees": [{"statement": "un point de cadrage encore ouvert"}],
         "hypotheses_actives": [{"statement": "public non expert"}]}
    fact = _mk_turn(envelope=_env({"reply": "restitution", "readiness": "ready", "matured_need": m}))
    assert fact["status"] == "proposed" and fact["readiness"] == "ready"
    assert fact["matured_need"]["inconnues_nommees"] == [{"statement": "un point de cadrage encore ouvert"}]


def test_build_turn_failed_on_bad_readiness_or_unreadable():
    bad_enum = _mk_turn(envelope=_env({"reply": "x", "readiness": "maybe"}))   # enum hors contrat
    assert bad_enum["status"] == "failed" and bad_enum["error"] == "format tour invalide"
    assert bad_enum["reply"] is None and bad_enum["diagnostic"] is not None
    not_json = _mk_turn(envelope=_env("pas du JSON"))
    assert not_json["status"] == "failed" and not_json["error"] == "format tour invalide"
    timed = _mk_turn(envelope=None, timed_out=True)
    assert timed["status"] == "failed" and timed["error"] == "safety_watchdog_exceeded"
    err = _mk_turn(envelope=_env({"reply": "x", "readiness": "ready"}, ok=False))
    assert err["status"] == "failed" and err["error"] != "success"        # jamais "success"


def test_build_turn_cost_unavailable_when_absent():
    env = _env({"reply": "x", "readiness": "continue"}); del env["total_cost_usd"]
    fact = _mk_turn(envelope=env)
    assert fact["cost"] == {"value": None, "kind": "unavailable"}          # jamais fabriqué


# ===================================================================== #
# TurnStore — journal append-only, id adressé-contenu, reconstructible par pursuit_ref
# ===================================================================== #
def test_turnstore_appends_and_reconstructs_by_pursuit(tmp_path):
    store = TurnStore(tmp_path / "turns.jsonl")
    assert store.read_all() == []                                         # vide au départ
    a = store.record(_mk_turn(envelope=_env({"reply": "r1", "readiness": "continue"}), message="m1"))
    b = store.record(_mk_turn(envelope=_env({"reply": "r2", "readiness": "continue"}), message="m2"))
    assert a["turn_id"].startswith("turn_") and b["turn_id"].startswith("turn_")
    all_turns = store.read_all()
    assert [t["message"] for t in all_turns] == ["m1", "m2"]              # ordre d'append (chronologique)
    assert all(t["pursuit_ref"] == "pursuit_x" for t in all_turns)


def test_turnstore_addresses_id_and_ignores_caller_id(tmp_path):
    store = TurnStore(tmp_path / "turns.jsonl")
    fact = _mk_turn(envelope=_env({"reply": "r", "readiness": "continue"}))
    forged = {**fact, "turn_id": "turn_FORGED"}
    stored = store.record(forged)
    assert stored["turn_id"] != "turn_FORGED"                            # id appelant ignoré, recalculé
    # même contenu/horodatage ⇒ même id (déterministe, adressé-contenu)
    store2 = TurnStore(tmp_path / "t2.jsonl")
    assert store2.record(dict(fact))["turn_id"] == stored["turn_id"]
