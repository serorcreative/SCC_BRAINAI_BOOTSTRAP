"""Tests de la séquence de démarrage (les 8 étapes → BrainAI READY)."""

from __future__ import annotations

from scc_brainai_bootstrap.bootstrap import READY_BANNER


def test_brainai_ready(report):
    assert report["ready"] is True
    assert report["banner"] == READY_BANNER
    assert report["degraded"] == []


def test_eight_step_order(report):
    names = [s["name"] for s in report["steps"]]
    assert names == ["config", "control_plane", "patrimony", "memory",
                     "knowledge", "event_bus", "agents"]
    assert all(s["ok"] for s in report["steps"])


def test_step1_config(report):
    s = report["steps"][0]
    assert s["name"] == "config" and s["ok"]
    assert s["data"]["first_agents"] == 4


def test_step2_control_plane(report):
    s = next(s for s in report["steps"] if s["name"] == "control_plane")
    assert s["ok"]
    assert s["data"].get("overall") == "ok"


def test_step3_patrimony(report):
    assert report["patrimony"]["present"] == report["patrimony"]["total"]
    assert report["patrimony"]["present"] >= 20


def test_step4_memory_and_step5_knowledge(report):
    mem = next(s for s in report["steps"] if s["name"] == "memory")
    kno = next(s for s in report["steps"] if s["name"] == "knowledge")
    assert mem["ok"] and kno["ok"]


def test_step6_event_bus(report):
    s = next(s for s in report["steps"] if s["name"] == "event_bus")
    assert s["ok"]
    assert report["event_count"] > 0


def test_step7_first_agents(report):
    assert len(report["agents"]) == 4
    ids = {a["id"] for a in report["agents"]}
    assert {"SCC-AGENT-0001", "SCC-AGENT-0002", "SCC-AGENT-0003", "SCC-AGENT-0020"} == ids
    # les fiches sont réellement chargées (noms non vides)
    assert all(a["name"] and a["name"] != "(fiche absente)" for a in report["agents"])


def test_ready_event_published(report):
    ready_events = [e for e in report["events"] if e["topic"] == "brainai.ready"]
    assert ready_events and ready_events[0]["payload"]["ready"] is True
