"""Tests de la chaîne apprenante : Memory (vécu) → Learning (propositions)."""

from __future__ import annotations

import copy
import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap


# Vécu reproductible : quelques demandes traitées de bout en bout.
_EXPERIENCE = [
    "Quelles doctrines gouvernent la gouvernance ?",
    "Explique l'architecture",
    "Explique l'architecture",
    "état du système",
    "état du système",
    "Montre le graphe",
]


def _accumulate(boot):
    for q in _EXPERIENCE:
        boot.handle(q)
    return boot


def test_learn_produces_proposals(boot):
    _accumulate(boot)
    result = boot.learn()
    assert result["ok"] is True
    assert result["analyzed_entries"] > 0
    assert result["total_learnings"] > 0
    assert result["needs_human_validation"] is True
    # toute recommandation est une proposition (jamais appliquée d'office)
    for r in result["recommendations"]:
        assert r["status"] == "proposed"


def test_learn_reads_living_memory(boot):
    _accumulate(boot)
    result = boot.learn()
    # le vécu analysé correspond bien à la mémoire vivante du bootstrap
    total_mem = sum(boot.memory.store.counts().values())
    assert result["analyzed_entries"] == total_mem


def test_learn_empty_memory_is_graceful(boot):
    result = boot.learn()                 # aucun handle préalable
    assert result["ok"] is True
    assert result["analyzed_entries"] == 0
    assert result["total_learnings"] == 0
    assert result["recommendations"] == []


def test_learnings_listing(boot):
    _accumulate(boot)
    boot.learn()
    listing = boot.learnings()
    assert listing["ok"] is True
    assert listing["count"] == sum(listing["counts"].values())
    assert all(it["status"] == "proposed" for it in listing["items"])


def test_learnings_filter_by_kind(boot):
    _accumulate(boot)
    boot.learn()
    sigs = boot.learnings(kind="signal")
    assert sigs["ok"] is True
    assert sigs["items"] and all(it["kind"] == "signal" for it in sigs["items"])


def test_validate_learning(boot):
    _accumulate(boot)
    boot.learn()
    item_id = boot.learnings(kind="signal")["items"][0]["id"]
    res = boot.validate_learning(item_id, "frederique", "utile")
    assert res["ok"] is True
    assert res["status"] == "validated"
    assert any(e["topic"] == "learning.validated" for e in boot.bus.events)


def test_reject_learning(boot):
    _accumulate(boot)
    boot.learn()
    item_id = boot.learnings(kind="signal")["items"][0]["id"]
    res = boot.validate_learning(item_id, "frederique", "hors sujet", action="reject")
    assert res["ok"] is True
    assert res["status"] == "rejected"


def test_validate_unknown_learning_fails(boot):
    _accumulate(boot)
    boot.learn()
    res = boot.validate_learning("nope_000000", "frederique")
    assert res["ok"] is False


def test_learning_event_on_bus(boot):
    _accumulate(boot)
    boot.learn()
    assert any(e["topic"] == "learning.analyzed" for e in boot.bus.events)


def test_learning_validation_persists_cross_process(config):
    def mk(name):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir.parent / name
        return BrainAIBootstrap(config=cfg)

    # dossier partagé : accumuler + apprendre, puis valider en process distinct
    shared = config.data_dir.parent / "shared"
    def at_shared():
        cfg = copy.copy(config); cfg.data_dir = shared
        return BrainAIBootstrap(config=cfg)

    b1 = at_shared(); _accumulate(b1); b1.learn()
    item_id = b1.learnings(kind="signal")["items"][0]["id"]

    b2 = at_shared()
    assert b2.validate_learning(item_id, "frederique")["ok"] is True

    b3 = at_shared()
    got = [it for it in b3.learnings()["items"] if it["id"] == item_id][0]
    assert got["status"] == "validated"


def test_learning_deterministic(config):
    def learn_at(name):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir.parent / name
        b = BrainAIBootstrap(config=cfg)
        _accumulate(b)
        b.learn()
        return b.learnings()
    a, b = learn_at("da"), learn_at("db")
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)


def test_doctor_includes_learning(boot):
    doc = boot.doctor()
    assert "learning" in doc["sections"]["availability"]
    assert doc["sections"]["availability"]["learning"] is True
    assert "learning" in doc["sections"]["audits"]
    assert doc["sections"]["audits"]["learning"] is True
