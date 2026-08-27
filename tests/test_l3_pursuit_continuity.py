"""L3 — continuité durable Pursuit → Memory-11 (enrichissement de la frontière de livraison).

Le plus petit raccord utile : l'événement ``pursuit_delivered`` porte désormais l'origine (``need``),
l'identité canonique explicite (``pursuit_id`` == ``pursuit_ref``) et le ``status`` réel, avec un tag de
rappel ``pursuit:<pursuit_ref>`` (axe durable). Changements strictement additifs ; aucune modification de
Memory-11 ; aucun payload fournisseur brut persisté. Ces tests prouvent la reprise future L4 :
« retrouve cette Pursuit et sa continuité utile ».
"""

from __future__ import annotations

import pytest

from brainai_app.delivery.memory import open_memory_store, write_delivery_memory

# Contrat de continuité persistée (exactement) + interdits (payloads fournisseur bruts).
_ALLOWED = {"pursuit_ref", "pursuit_id", "need", "status", "project", "result",
            "decisions", "artifact_ref", "preview_ref", "provenance_ids", "as_of"}
_FORBIDDEN = {"steps", "cost_total", "reply", "proposal"}


def test_delivered_event_carries_canonical_continuity_facts(tmp_path):
    """L'événement livré consigne les faits canoniques de continuité + conserve l'historique + le tag durable."""
    store = open_memory_store(tmp_path / "mem")
    entry = write_delivery_memory(
        store, pursuit_ref="pursuit_abc", project="site", result="club de sport",
        decisions=["convergence confirmée (humain)"],
        artifact_ref={"relative_path": "index.html"}, preview_ref={"kind": "local_loopback"},
        provenance_ids={"build_id": "b1", "delivered_id": "d1"},
        as_of="2026-07-06T00:00:00+00:00", need="un site pour mon club", status="delivered")
    d = entry.data
    assert entry.subtype == "pursuit_delivered"
    assert d["pursuit_ref"] == "pursuit_abc"
    assert d["pursuit_id"] == d["pursuit_ref"]                      # identité canonique explicite
    assert d["need"] == "un site pour mon club"                    # origine durable
    assert d["status"] == "delivered"
    assert d["as_of"] == "2026-07-06T00:00:00+00:00"
    assert d["result"] == "club de sport"
    assert d["artifact_ref"] == {"relative_path": "index.html"}
    assert d["preview_ref"] == {"kind": "local_loopback"}
    assert d["provenance_ids"] == {"build_id": "b1", "delivered_id": "d1"}
    assert d["project"] == "site" and d["decisions"] == ["convergence confirmée (humain)"]   # historique intact
    assert {"jalon2", "delivered", "pursuit", "pursuit:pursuit_abc"}.issubset(set(entry.tags))


def test_close_reopen_retrieve_pursuit_by_durable_axis(tmp_path):
    """Reprise L4 : après fermeture, un NOUVEAU store rouvert sur le même répertoire retrouve la Pursuit
    par son axe durable (subtype + tag ``pursuit:<ref>``) avec sa continuité utile."""
    ref = "pursuit_xyz"
    store = open_memory_store(tmp_path / "mem")
    write_delivery_memory(
        store, pursuit_ref=ref, project="site", result="objectif livré",
        decisions=["ok"], artifact_ref={"relative_path": "index.html"},
        preview_ref={"kind": "local_loopback"}, provenance_ids={"build_id": "b1"},
        as_of="t0", need="mon besoin durable", status="delivered")

    store2 = open_memory_store(tmp_path / "mem")                   # réouverture (autoload depuis le disque)
    hits = store2.search(subtype="pursuit_delivered", tag=f"pursuit:{ref}")
    assert len(hits) == 1
    d = hits[0]["data"]
    assert d["pursuit_ref"] == ref and d["pursuit_id"] == ref
    assert d["need"] == "mon besoin durable"
    assert d["result"] == "objectif livré"
    assert d["status"] == "delivered"
    assert d["provenance_ids"] == {"build_id": "b1"}


def test_backward_compat_pursuit_delivered_without_new_kwargs(tmp_path):
    """Rétrocompatibilité : un appelant historique (sans ``need``/``status``) fonctionne toujours ;
    clés historiques intactes, nouveaux champs aux défauts sûrs."""
    store = open_memory_store(tmp_path / "mem")
    entry = write_delivery_memory(
        store, pursuit_ref="p", project="site", result="club",
        decisions=["confirmée"], artifact_ref={"relative_path": "index.html"},
        preview_ref={"kind": "local_loopback"}, provenance_ids={"build_id": "b1"}, as_of="t0")
    d = entry.data
    assert entry.subtype == "pursuit_delivered"
    for k in ("pursuit_ref", "project", "result", "decisions", "artifact_ref", "preview_ref",
              "provenance_ids", "as_of"):
        assert k in d                                              # historique préservé
    assert d["pursuit_id"] == "p"                                 # défauts additifs
    assert d["need"] is None
    assert d["status"] == "delivered"
    assert {"jalon2", "delivered", "pursuit"}.issubset(set(entry.tags))


def test_no_provider_raw_payload_leak(tmp_path):
    """Anti-fuite : le fait persisté = exactement le contrat de continuité, aucun payload fournisseur brut
    (``steps``/``cost_total``/``reply``/``proposal`` absents)."""
    store = open_memory_store(tmp_path / "mem")
    entry = write_delivery_memory(
        store, pursuit_ref="p", project="site", result="club", decisions=["ok"],
        artifact_ref=None, preview_ref=None, provenance_ids={}, as_of="t0",
        need="besoin", status="delivered")
    keys = set(entry.data.keys())
    assert keys == _ALLOWED                                        # exactement le contrat, rien de plus
    assert not (keys & _FORBIDDEN)                                 # aucun payload fournisseur brut


def test_deliver_passes_need_and_status_from_outcome(tmp_path, monkeypatch):
    """Câblage réel : ``_deliver`` transmet ``need=outcome.need`` et le ``status`` réellement livré à la
    frontière mémoire, sans casser la frontière L2 ``memory_11_id``/``memory_id``."""
    from brainai_app import composition, providers

    captured = {}

    class _Entry:
        id = "mem_00000000002a"

    class _Outcome:
        pursuit_id = "pursuit_w"
        as_of = "2026-07-06T00:00:00+00:00"
        need = "besoin réel utilisateur"

    def _fake_write(store, **kw):
        captured.update(kw)
        return _Entry()

    monkeypatch.setattr(composition, "_spec_fact_for",
                        lambda stores, outcome: {"specification": {"product_objective": "obj"}})
    monkeypatch.setattr(providers, "real_delivery",
                        lambda: type("Caps", (), {"site_build": None, "preview": None})())
    monkeypatch.setattr(composition, "run_delivery",
                        lambda **kw: {"status": "delivered", "build": {"artefact": "a"},
                                      "preview_ref": "p", "provenance": {}})
    monkeypatch.setattr(composition, "open_memory_store", lambda *a, **k: object())
    monkeypatch.setattr(composition, "write_delivery_memory", _fake_write)

    report = composition._deliver(tmp_path, _Outcome(), actor=None, budget_usd=2.0)

    assert captured["need"] == "besoin réel utilisateur"          # origine durable transmise
    assert captured["status"] == "delivered"                     # statut réel livré transmis
    assert captured["pursuit_ref"] == "pursuit_w"
    assert report["memory_11_id"] == "mem_00000000002a"          # frontière L2 intacte
    assert report["memory_id"] == report["memory_11_id"]
