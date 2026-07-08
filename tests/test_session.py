"""Tests de la continuité de session (mode « live »)."""

from __future__ import annotations

import copy
import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main


def test_session_created_on_first_boot(boot):
    report = boot.run()
    sess = report["session"]
    assert sess["session_id"].startswith("ses_")
    assert sess["boots"] == 1
    assert sess["created_as_of"] == boot.config.as_of
    assert set(sess["totals"]) == {
        "runs", "decisions", "plans", "executions", "learn_runs", "learnings_validated"}


def test_session_persists_and_continues(config):
    def at(name="s"):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir / name
        return BrainAIBootstrap(config=cfg)

    a = at(); a.run()
    b = at(); rb = b.run()
    assert rb["session"]["boots"] == 2                 # continuité cross-instance
    assert a.session.summary()["session_id"] == rb["session"]["session_id"]


def test_activity_totals_accumulate(boot):
    boot.handle("Explique l'architecture")             # runs +1
    boot.learn()                                       # learn_runs +1
    boot.decide("Faut-il A ou B ?")                    # decisions +1
    boot.plan("Améliorer la gouvernance")              # plans +1
    totals = boot.session_summary()["totals"]
    assert totals["runs"] >= 1
    assert totals["learn_runs"] >= 1
    assert totals["decisions"] >= 1
    assert totals["plans"] >= 1


def test_validated_learning_counted(boot):
    for q in ["Explique l'architecture", "Explique l'architecture", "état du système",
              "état du système", "Montre le graphe"]:
        boot.handle(q)
    boot.learn()
    recs = boot.learnings(kind="recommendation")["items"]
    for r in recs:
        boot.validate_learning(r["id"], "frederique", "go")
    assert boot.session_summary()["totals"]["learnings_validated"] == len(recs)


def test_session_summary_without_boot_is_readonly(boot):
    # aucune invocation : pas de session, et la lecture n'en crée pas
    summary = boot.session_summary()
    assert summary == {"exists": False}
    assert not boot.session.path.exists()
    assert boot._booted is False


def test_session_continued_event_on_bus(boot):
    boot.run()
    topics = [e["topic"] for e in boot.bus.events]
    assert "session.continued" in topics
    assert topics[-1] == "brainai.ready"               # ready reste terminal


def test_session_deterministic_fresh_state(config):
    def run(name):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir.parent / name
        return BrainAIBootstrap(config=cfg).run()["session"]
    a, b = run("sa"), run("sb")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _cli_config(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def test_cli_session_before_start(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "session"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "aucune" in out


def test_cli_session_after_starts(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    main(["--config", str(cfg), "start"])
    main(["--config", str(cfg), "run", "Explique l architecture", "--route", "kernel"])
    capsys.readouterr()
    rc = main(["--config", str(cfg), "session", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["exists"] is True
    assert data["boots"] >= 2
    assert data["totals"]["runs"] >= 1


def test_cli_start_shows_session_line(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "start"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "session" in out and "démarrage n°1" in out
