"""Tests de la retrouvabilité Entrée → décision (INPUT-DECISION-LINK-001).

Prouve : depuis une Entrée, retrouver la (les) décision(s) qu'elle a produite(s) — par **lecture
pure** exploitant la traçabilité existante (``input.analyzed`` → ``deliberation_id`` →
``decision.traceability.deliberation``), sans nouvel événement ni stockage. Couvre la projection
``{decision_id, status, class, subject}``, l'**évolution du statut** (proposée → validée), l'état
vide, et l'innocuité (aucun effet de bord).
"""

from __future__ import annotations

from scc_brainai_bootstrap.presentation import OPERATIONS, Presentation

PROV = {"origin": "test", "medium": "inline"}
SUBJECT = "Faut-il préparer la première interface ?"


def _record_analyze_decide(boot):
    iid = boot.record_input(SUBJECT, PROV)["input_id"]
    boot.analyze_input(iid)
    decision_id = boot.decide_from_input(iid)["decision_id"]
    return iid, decision_id


def test_input_decisions_links_entry_to_its_decision(boot):
    iid, decision_id = _record_analyze_decide(boot)
    res = boot.input_decisions(iid)
    assert res["ok"] is True and res["input_id"] == iid
    ids = [d["decision_id"] for d in res["decisions"]]
    assert decision_id in ids                               # la décision est retrouvable depuis l'Entrée


def test_input_decisions_projection_fields_and_subject(boot):
    iid, decision_id = _record_analyze_decide(boot)
    d = next(x for x in boot.input_decisions(iid)["decisions"] if x["decision_id"] == decision_id)
    assert set(d) == {"decision_id", "status", "class", "subject"}   # projection stricte
    assert d["status"] == "proposed"                        # statut de gouvernance courant
    assert d["subject"] == SUBJECT                           # sujet = contenu de l'Entrée (autoritatif)


def test_input_decisions_reflects_current_status_after_validation(boot):
    iid, decision_id = _record_analyze_decide(boot)
    assert boot.input_decisions(iid)["decisions"][0]["status"] == "proposed"
    boot.validate_decision(decision_id, "tester")           # transition gouvernée proposed → validated
    after = next(x for x in boot.input_decisions(iid)["decisions"] if x["decision_id"] == decision_id)
    assert after["status"] == "validated"                   # « ce qu'elle est devenue » — statut relu


def test_input_decisions_empty_when_no_analysis(boot):
    iid = boot.record_input("Jamais analysée", PROV)["input_id"]
    res = boot.input_decisions(iid)
    assert res["ok"] is True and res["decisions"] == []


def test_input_decisions_empty_when_analyzed_but_not_decided(boot):
    iid = boot.record_input(SUBJECT, PROV)["input_id"]
    boot.analyze_input(iid)                                  # analysée mais aucune décision proposée
    assert boot.input_decisions(iid)["decisions"] == []


def test_input_decisions_unknown_entry(boot):
    res = boot.input_decisions("in_inexistante")
    assert res["ok"] is False and "error" in res


def test_input_decisions_is_read_only_no_event(boot):
    iid, _ = _record_analyze_decide(boot)
    before = len(boot.recorder.events)
    boot.input_decisions(iid)
    boot.input_decisions(iid)
    assert len(boot.recorder.events) == before              # lecture pure : aucun événement émis


def test_presentation_input_decisions_passthrough(boot):
    iid, _ = _record_analyze_decide(boot)
    env = Presentation(bootstrap=boot).input_decisions(iid)
    assert env["operation"] == "input_decisions" and env["kind"] == "read"
    assert env["data"]["ok"] is True and isinstance(env["data"]["decisions"], list)


def test_contract_exposes_input_decisions_as_read():
    assert OPERATIONS["input_decisions"]["kind"] == "read"
