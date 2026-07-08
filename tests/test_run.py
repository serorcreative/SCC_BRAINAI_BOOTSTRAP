"""Tests du cycle de bout en bout : bootstrap → Kernel (10) → Memory (11)."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main


def test_handle_end_to_end(boot):
    result = boot.handle("Quelles doctrines gouvernent la gouvernance ?")
    assert result["ok"] is True
    assert result["intent"] == "governance"
    assert result["agents"]                       # des agents ont été mobilisés
    assert result["runtime"]["status"] == "succeeded"
    assert result["synthesis"]


def test_handle_boots_if_needed(boot):
    # aucun run() préalable : handle démarre BrainAI à la volée
    assert boot._booted is False
    result = boot.handle("état de santé du système")
    assert boot._booted is True
    assert result["ok"] is True
    assert result["intent"] == "inspect"


def test_experience_recorded_in_memory(boot):
    result = boot.handle("Explique l'architecture")
    assert result["recorded"] is not None
    assert result["recorded"]["trace_id"].startswith("mem_")
    # la mémoire contient bien la trace + les événements du cycle
    counts = boot.memory.store.counts()
    assert counts.get("trace", 0) >= 1
    assert counts.get("event", 0) >= 7


def test_no_record_option(boot):
    result = boot.handle("Montre le graphe", record=False)
    assert result["ok"] is True
    assert result["recorded"] is None


def test_deep_cognitive_pass(boot):
    result = boot.handle("analyse l'architecture", deep=True)
    assert result["runtime"]["kind"] == "brain_pass"
    assert result["runtime"]["status"] == "succeeded"


def test_lifecycle_events_on_bus(boot):
    boot.handle("état du système")
    topics = {e["topic"] for e in boot.bus.events}
    assert {"request.received", "request.handled", "experience.recorded"} <= topics


def test_deterministic_handle(config):
    import copy
    cfg_a = copy.copy(config); cfg_a.data_dir = config.data_dir.parent / "a"
    cfg_b = copy.copy(config); cfg_b.data_dir = config.data_dir.parent / "b"
    a = BrainAIBootstrap(config=cfg_a).handle("état du système")
    b = BrainAIBootstrap(config=cfg_b).handle("état du système")
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)


def test_cli_run(tmp_path, capsys):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    rc = main(["--config", str(cfg), "run", "Quelles doctrines gouvernent la gouvernance ?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "intention   : governance" in out
    assert "synthèse" in out
