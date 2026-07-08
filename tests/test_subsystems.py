"""Tests des sous-systèmes : Event Bus, Patrimony, Agents, mode dégradé."""

from __future__ import annotations

from scc_brainai_bootstrap.core.config import load_config
from scc_brainai_bootstrap.event_bus import EventBus
from scc_brainai_bootstrap.patrimony import PatrimonyManager


def test_event_bus_pubsub():
    bus = EventBus("2026-07-06T00:00:00+00:00")
    received = []
    bus.subscribe(lambda e: received.append(e))
    bus.publish("a", {"x": 1})
    bus.publish("b")
    assert len(bus) == 2
    assert received[0]["topic"] == "a" and received[0]["seq"] == 1
    assert len(bus.by_topic("a")) == 1
    bus.open()
    assert bus.is_open


def test_patrimony_inventory(config):
    pm = PatrimonyManager(config)
    summary = pm.summary()
    assert summary["total"] == 21
    assert summary["present"] >= 20
    assert "brainai" in summary["by_category"]


def test_agents_loaded_from_catalog(boot):
    agents = boot.agents.register_first()
    architecte = next(a for a in agents if a.id == "SCC-AGENT-0001")
    assert "Architecte" in architecte.name
    assert architecte.autonomy.startswith("A")   # A0..A4
    assert architecte.trust.startswith("T")       # T1..T3


def test_degraded_mode_when_component_missing(tmp_path):
    from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
    cfg = load_config()
    cfg.data_dir = tmp_path / "data"
    cfg.scc_root = tmp_path / "nowhere"    # aucun composant localisable
    report = BrainAIBootstrap(config=cfg).run()
    # patrimoine vide -> non prêt, mais le démarrage ne lève pas
    assert report["ready"] is False
    assert "DÉGRADÉ" in report["banner"]


def test_deterministic_boot(config):
    from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
    import json
    a = BrainAIBootstrap(config=config).run()
    b = BrainAIBootstrap(config=config).run()
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)
