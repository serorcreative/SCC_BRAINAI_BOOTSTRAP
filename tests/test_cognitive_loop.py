"""Tests de la grande boucle cognitive : Reasoning → Decision → [humain] → Execution."""

from __future__ import annotations

import json

import pytest

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main
from scc_brainai_bootstrap.core.config import load_config

QUESTION = "Faut-il publier l API maintenant ou differer ?"


@pytest.fixture
def loop_config(tmp_path):
    cfg = load_config()
    cfg.data_dir = tmp_path / "data"
    cfg.authorized_actors = ["frederique"]
    return cfg


@pytest.fixture
def loop_boot(loop_config):
    return BrainAIBootstrap(config=loop_config)


def test_stack_available(loop_boot):
    assert loop_boot.cognition.available() is True


def test_decide_produces_candidate(loop_boot):
    d = loop_boot.decide(QUESTION)
    assert d["ok"] is True
    assert d["decision_id"].startswith("dec_")
    assert d["status"] == "proposed"
    assert d["needs_human_validation"] is True
    assert len(d["options"]) >= 2
    assert any(o["selected"] for o in d["options"])


def test_execute_before_validation_refused(loop_boot):
    d = loop_boot.decide(QUESTION)
    r = loop_boot.execute_decision(d["decision_id"], actor="frederique")
    assert r["ok"] is False
    assert r["status"] == "refused"
    assert "decision_validated" in r["refusals"]


def test_full_loop_validate_then_execute(loop_boot):
    d = loop_boot.decide(QUESTION)
    v = loop_boot.validate_decision(d["decision_id"], "frederique", "go")
    assert v["ok"] is True and v["status"] == "validated"
    e = loop_boot.execute_decision(d["decision_id"], actor="frederique")
    assert e["ok"] is True
    assert e["status"] == "succeeded"
    assert e["steps"] and e["steps"][0]["job_id"]      # délégué au Runtime


def test_execute_unauthorized_actor_refused(loop_boot):
    d = loop_boot.decide(QUESTION)
    loop_boot.validate_decision(d["decision_id"], "frederique", "go")
    r = loop_boot.execute_decision(d["decision_id"], actor="intrus")
    assert r["ok"] is False
    assert r["status"] == "refused"
    assert "actor_authorized" in r["refusals"]


def test_loop_events_on_bus(loop_boot):
    d = loop_boot.decide(QUESTION)
    loop_boot.validate_decision(d["decision_id"], "frederique", "go")
    loop_boot.execute_decision(d["decision_id"], actor="frederique")
    topics = {e["topic"] for e in loop_boot.recorder.events}
    assert {"decision.proposed", "decision.validated", "execution.prepared",
            "execution.done"} <= topics


def test_decide_deterministic(tmp_path):
    def decide(dirname):
        cfg = load_config(); cfg.data_dir = tmp_path / dirname
        cfg.authorized_actors = ["frederique"]
        return BrainAIBootstrap(config=cfg).decide(QUESTION)
    a, b = decide("a"), decide("b")
    assert a["decision_id"] == b["decision_id"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_cli_full_loop(tmp_path, capsys):
    cfg = tmp_path / "brainai.json"
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00",
                               "authorized_actors": ["frederique"]}), encoding="utf-8")
    rc = main(["--config", str(cfg), "decide", QUESTION, "--json"])
    did = json.loads(capsys.readouterr().out)["decision_id"]
    assert rc == 0
    rc = main(["--config", str(cfg), "validate", did, "--by", "frederique", "--reason", "go"])
    assert rc == 0 and json.loads(capsys.readouterr().out)["status"] == "validated"
    rc = main(["--config", str(cfg), "execute", did, "--by", "frederique", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "succeeded"
