"""Tests du point d'entrée unique `run_query` (routage automatique)."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main


def test_informational_query_routes_to_kernel(boot):
    result = boot.run_query("Quelles doctrines gouvernent la gouvernance ?")
    assert result["route"] == "kernel"
    assert result["ok"] is True
    assert result["intent"] == "governance"
    assert "decision_id" not in result


def test_decisional_query_routes_to_decide(boot):
    result = boot.run_query("Faut-il publier l API maintenant ou différer ?")
    assert result["route"] == "decide"
    assert result["ok"] is True
    assert result["decision_id"].startswith("dec_") or result["decision_id"]
    assert result["needs_human_validation"] is True
    assert result["options"]


def test_forced_kernel_on_decisional_query(boot):
    result = boot.run_query("Faut-il publier maintenant ?", route="kernel")
    assert result["route"] == "kernel"
    assert "intent" in result


def test_forced_decide_on_informational_query(boot):
    result = boot.run_query("Explique l architecture du Runtime.", route="decide")
    assert result["route"] == "decide"
    assert result["decision_id"]


def test_routing_event_on_bus(boot):
    boot.run_query("Faut-il choisir A ou B ?")
    routed = [e for e in boot.bus.events if e["topic"] == "run.routed"]
    assert routed and routed[0]["payload"]["route"] == "decide"


def test_run_query_deterministic(config):
    import copy
    cfg_a = copy.copy(config); cfg_a.data_dir = config.data_dir.parent / "ra"
    cfg_b = copy.copy(config); cfg_b.data_dir = config.data_dir.parent / "rb"
    q = "Faut-il migrer vers le nouveau schéma ?"
    a = BrainAIBootstrap(config=cfg_a).run_query(q)
    b = BrainAIBootstrap(config=cfg_b).run_query(q)
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)


def _cli_config(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def test_cli_run_auto_routes_to_decide(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "run", "Faut-il publier l API maintenant ou différer ?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "route       : decide" in out
    assert "décision" in out
    assert "valider" in out


def test_cli_run_auto_routes_to_kernel(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "run", "Quelles doctrines gouvernent la gouvernance ?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "route       : kernel" in out
    assert "intention   : governance" in out


def test_cli_run_force_kernel(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "run", "Faut-il publier ?", "--route", "kernel"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "route       : kernel" in out
