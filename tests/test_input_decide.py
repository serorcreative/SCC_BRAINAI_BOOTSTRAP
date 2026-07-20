"""Tests du pont Entrée → décision (INPUT-DECIDE-001).

Prouve : proposer une décision gouvernée **à partir de l'analyse existante** d'une Entrée, en
réutilisant la délibération déjà produite — **sans** réexécuter ``reason()``, **sans** seconde
délibération, **sans** muter l'Entrée. Décision **proposée** (validation humaine requise),
provenance ``decision.traceability.deliberation``, **idempotence**, et erreurs conventionnelles.
"""

from __future__ import annotations

from scc_brainai_bootstrap.presentation import OPERATIONS, Presentation

PROV = {"origin": "test", "medium": "inline"}
SUBJECT = "Faut-il préparer la première interface ?"


def _record_and_analyze(boot):
    iid = boot.record_input(SUBJECT, PROV)["input_id"]
    delib_id = boot.analyze_input(iid)["analysis"]["deliberation_id"]
    return iid, delib_id


def test_decide_from_input_reuses_existing_deliberation(boot):
    iid, delib_id = _record_and_analyze(boot)
    res = boot.decide_from_input(iid)
    assert res["ok"] is True and res["input_id"] == iid
    assert res["deliberation_id"] == delib_id               # même délibération, réutilisée
    assert res["decision_id"]
    assert res["status"] == "proposed" and res["needs_human_validation"] is True


def test_decide_from_input_creates_no_second_deliberation_no_new_analysis(boot):
    iid, _ = _record_and_analyze(boot)
    delibs_before = len(boot.cognition.reasoning.deliberations)
    analyzed_before = [e for e in boot.input_history(iid)["events"] if e["topic"] == "input.analyzed"]
    boot.decide_from_input(iid)
    # aucune 2ᵉ délibération (aucun reason()), aucun nouvel événement input.analyzed
    assert len(boot.cognition.reasoning.deliberations) == delibs_before
    analyzed_after = [e for e in boot.input_history(iid)["events"] if e["topic"] == "input.analyzed"]
    assert len(analyzed_after) == len(analyzed_before)


def test_decide_from_input_provenance_links_to_deliberation(boot):
    iid, delib_id = _record_and_analyze(boot)
    res = boot.decide_from_input(iid)
    dec = boot.cognition.decision.get(res["decision_id"])
    assert dec["traceability"]["deliberation"] == delib_id   # décision ← délibération (persistée)


def test_decide_from_input_is_idempotent(boot):
    iid, _ = _record_and_analyze(boot)
    a = boot.decide_from_input(iid)
    b = boot.decide_from_input(iid)
    assert a["decision_id"] == b["decision_id"]              # adressé-contenu → aucun doublon


def test_decide_from_input_decision_is_proposed_awaiting_validation(boot):
    iid, _ = _record_and_analyze(boot)
    res = boot.decide_from_input(iid)
    dec = boot.cognition.decision.get(res["decision_id"])
    assert dec["status"] == "proposed"                       # proposée, jamais exécutée
    # non exécutable tant qu'elle n'est pas validée (souveraineté humaine)
    assert res["decision_id"] not in [
        (d.get("id") or d.get("decision_id")) for d in boot.overview()["executable_decisions"]
    ]


def test_decide_from_input_does_not_mutate_entry(boot):
    iid, _ = _record_and_analyze(boot)
    boot.decide_from_input(iid)
    assert boot.input(iid)["content"] == SUBJECT             # Entrée intacte après proposition


def test_decide_from_input_unknown_entry(boot):
    res = boot.decide_from_input("in_inexistante")
    assert res["ok"] is False and "error" in res             # convention des lectures/actions


def test_decide_from_input_without_analysis(boot):
    iid = boot.record_input("Jamais analysée", PROV)["input_id"]
    res = boot.decide_from_input(iid)
    assert res["ok"] is False and "aucune analyse" in res["error"]


def test_presentation_input_decide_passthrough(boot):
    iid, _ = _record_and_analyze(boot)
    env = Presentation(bootstrap=boot).input_decide(iid)
    assert env["operation"] == "input_decide" and env["kind"] == "action"
    assert env["data"]["ok"] is True and env["data"]["decision_id"]


def test_contract_exposes_input_decide_as_action():
    assert OPERATIONS["input_decide"]["kind"] == "action"
