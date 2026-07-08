"""Tests de l'agrégateur lecture seule `overview` (point d'entrée du futur UI)."""

from __future__ import annotations

import copy
import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main

_EXPERIENCE = ["Explique l'architecture", "Explique l'architecture",
               "état du système", "état du système", "Montre le graphe"]


def test_overview_shape(boot):
    ov = boot.overview()
    for key in ("state", "session", "agents", "capabilities", "open_decisions",
                "learnings", "recent_events", "diagnostics", "recommended_next_action"):
        assert key in ov
    assert ov["state"]["verdict"] in ("healthy", "degraded")
    assert ov["agents"]["counts"]["agents"] >= 9
    assert ov["capabilities"]["count"] >= 12


def test_overview_is_read_only(boot):
    # aucun démarrage, aucun événement persisté, aucune session ouverte
    boot.overview()
    assert boot._booted is False
    assert not boot.events_path.exists()
    assert not boot.session.path.exists()


def test_overview_does_not_bump_session(config):
    b = BrainAIBootstrap(config=config)
    b.overview(); b.overview()
    assert b.session.summary() == {"exists": False}     # overview n'ouvre jamais de session


def test_overview_reflects_activity(boot):
    for q in _EXPERIENCE:
        boot.handle(q)
    boot.learn()
    ov = boot.overview()
    assert ov["session"]["exists"] is True
    assert ov["learnings"]["proposed"]["count"] > 0
    assert ov["recent_events"]                          # le journal a été peuplé par handle


def test_overview_lists_open_decisions(boot):
    boot.decide("Faut-il publier ou différer ?")
    ov = boot.overview()
    assert len(ov["open_decisions"]) == 1
    assert ov["open_decisions"][0]["status"] == "proposed"


# -- Prochaine action recommandée : règles déterministes ---------------- #
def test_reco_fresh_state_suggests_start(boot):
    reco = boot.overview()["recommended_next_action"]
    assert reco["action"] == "démarrer BrainAI"
    assert reco["command"] == "scc-brainai start"


def test_reco_open_decision_takes_priority(boot):
    for q in _EXPERIENCE:
        boot.handle(q)
    boot.learn()                                        # crée des apprentissages proposés
    boot.decide("Faut-il publier ou différer ?")        # ... mais la décision prime
    reco = boot.overview()["recommended_next_action"]
    assert reco["action"] == "valider une décision"
    assert "validate" in reco["command"]


def test_reco_proposed_learnings_when_no_decision(boot):
    for q in _EXPERIENCE:
        boot.handle(q)
    boot.learn()
    reco = boot.overview()["recommended_next_action"]
    assert reco["action"] == "revoir les apprentissages"
    assert "learnings --status proposed" in reco["command"]


def test_overview_deterministic_fresh_state(config):
    def ov(name):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir.parent / name
        return BrainAIBootstrap(config=cfg).overview()
    a, b = ov("oa"), ov("ob")
    # le journal reflète le data_dir : exclu de la comparaison (comme events_file).
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)


def _cli_config(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def test_cli_overview_text(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "overview"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "BrainAI OVERVIEW" in out
    assert "prochaine action recommandée" in out


def test_cli_overview_json(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "overview", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "recommended_next_action" in data
    assert data["agents"]["counts"]["agents"] >= 9
