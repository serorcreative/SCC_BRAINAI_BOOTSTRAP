"""Tests de l'ingestion des traces d'exécution dans Memory (boucle vécu → mémoire)."""

from __future__ import annotations

import json

import pytest

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.core.config import load_config

QUESTION = "Faut-il publier l API maintenant ou differer ?"


@pytest.fixture
def loop_boot(tmp_path):
    cfg = load_config()
    cfg.data_dir = tmp_path / "data"
    cfg.authorized_actors = ["frederique"]
    return BrainAIBootstrap(config=cfg)


def _run_loop(boot):
    d = boot.decide(QUESTION)
    boot.validate_decision(d["decision_id"], "frederique", "go")
    return boot.execute_decision(d["decision_id"], actor="frederique")


def test_execution_traces_ingested(loop_boot):
    r = _run_loop(loop_boot)
    assert r["status"] == "succeeded"
    assert r["memory_ingested"] >= 1
    counts = loop_boot.memory.store.counts()
    assert counts.get("event", 0) >= r["memory_ingested"]


def test_ingested_events_searchable(loop_boot):
    _run_loop(loop_boot)
    events = loop_boot.memory.store.search(kind="event", tag="execution")
    assert events
    subtypes = {e["subtype"] for e in events}
    assert "execution.succeeded" in subtypes
    # les traces sont tracées côté exécution (session dédiée)
    assert all("ingested" in e["tags"] for e in events)


def test_memorized_event_on_bus(loop_boot):
    _run_loop(loop_boot)
    topics = [e["topic"] for e in loop_boot.recorder.events]
    assert "execution.memorized" in topics


def test_no_ingestion_when_refused(loop_boot):
    d = loop_boot.decide(QUESTION)               # non validée
    r = loop_boot.execute_decision(d["decision_id"], actor="frederique")
    assert r["status"] == "refused"
    assert "memory_ingested" not in r            # rien n'a été exécuté ni mémorisé
    # aucune trace d'exécution : la mémoire n'a même pas été initialisée
    store = loop_boot.memory.store
    assert store is None or store.counts().get("event", 0) == 0


def test_ingestion_deterministic(tmp_path):
    def run(name):
        cfg = load_config(); cfg.data_dir = tmp_path / name
        cfg.authorized_actors = ["frederique"]
        b = BrainAIBootstrap(config=cfg)
        r = _run_loop(b)
        events = b.memory.store.search(kind="event", tag="execution")
        return r["memory_ingested"], [e["subtype"] for e in events]
    a, b = run("a"), run("b")
    assert a == b
