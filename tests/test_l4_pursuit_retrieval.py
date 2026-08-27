"""L4 — rappel en lecture d'une Pursuit (retrieve_pursuit).

Prouve : retrieval L3 normal, ref inexistante, événements multiples (dernier autoritaire), fallback
historique pré-L3, déduplication tag/fallback, found=False mais arc reprenable, arc absent/non reprenable,
corruption Memory-11 remontée fail-closed, aucune fabrication de champs. CONNECTER, PAS RECONSTRUIRE :
Memory-11 et l'arc sont réutilisés en lecture, jamais modifiés.
"""

from __future__ import annotations

import json

import pytest

from brainai_app.recall import read_pursuit_delivery, retrieve_pursuit
from brainai_app.delivery.memory import open_memory_store, write_delivery_memory


def _state(tmp_path, monkeypatch):
    root = tmp_path / "state"
    monkeypatch.setenv("BRAINAI_STATE_ROOT", str(root))       # _state_root() -> ce répertoire isolé
    return root


def _seed_delivery(root, ref, **over):
    store = open_memory_store(root / "memory")
    kw = dict(project="site", result="obj", decisions=["ok"],
              artifact_ref={"relative_path": "index.html"}, preview_ref={"kind": "local_loopback"},
              provenance_ids={"build_id": "b1"}, as_of="t0", need="besoin", status="delivered")
    kw.update(over)
    return write_delivery_memory(store, pursuit_ref=ref, **kw)


def _seed_arc(root, ref, *, proposed=True):
    from brainai_app.composition import _pursuit_dir          # chemin déterministe (lit BRAINAI_STATE_ROOT)
    d = _pursuit_dir(ref)
    d.mkdir(parents=True, exist_ok=True)
    turn = {"pursuit_ref": ref, "status": "proposed" if proposed else "failed", "message": "m", "reply": "r"}
    (d / "turns.jsonl").write_text(json.dumps(turn) + "\n", encoding="utf-8")
    return d


def test_retrieve_l3_normal(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_delivery(root, "pursuit_a", need="mon besoin durable", result="club de sport")
    r = retrieve_pursuit("pursuit_a")
    assert r["found"] is True
    assert r["events_count"] == 1 and len(r["memory_ids"]) == 1
    c = r["continuity"]
    assert c["need"] == "mon besoin durable" and c["result"] == "club de sport"
    assert c["status"] == "delivered" and c["as_of"] == "t0"
    assert c["provenance_ids"] == {"build_id": "b1"}
    assert r["resumable"] is False and r["resume_hint"] is None       # pas d'arc


def test_unknown_ref(tmp_path, monkeypatch):
    _state(tmp_path, monkeypatch)
    r = retrieve_pursuit("pursuit_absent")
    assert r["found"] is False and r["continuity"] is None
    assert r["events_count"] == 0 and r["memory_ids"] == []
    assert r["resumable"] is False and r["resume_hint"] is None


def test_multiple_events_latest_authoritative(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_delivery(root, "pursuit_m", result="v1", provenance_ids={"build_id": "b1"})
    _seed_delivery(root, "pursuit_m", result="v2", provenance_ids={"build_id": "b2"})
    r = retrieve_pursuit("pursuit_m")
    assert r["events_count"] == 2 and len(r["memory_ids"]) == 2
    assert r["continuity"]["result"] == "v2"                          # dernier autoritaire (tri par id)
    assert r["continuity"]["provenance_ids"] == {"build_id": "b2"}
    assert r["memory_ids"] == sorted(r["memory_ids"])                 # ordre déterministe


def test_fallback_pre_l3_without_recall_tag(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    store = open_memory_store(root / "memory")
    # Événement PRÉ-L3 : subtype historique + data.pursuit_ref, SANS tag pursuit:<ref>, sans need/status.
    store.record_event("pursuit_delivered",
                       {"pursuit_ref": "pursuit_old", "project": "site", "result": "ancien",
                        "provenance_ids": {"build_id": "b0"}, "as_of": "t0"},
                       tags=["jalon2", "delivered", "pursuit"])
    r = retrieve_pursuit("pursuit_old")
    assert r["found"] is True and r["events_count"] == 1
    assert r["continuity"]["result"] == "ancien"
    assert r["continuity"]["need"] is None and r["continuity"]["status"] is None   # aucune fabrication


def test_dedup_tag_and_fallback_single_entry(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_delivery(root, "pursuit_d")            # L3 : a le tag ET data.pursuit_ref -> présent dans by_tag ET fallback
    r = retrieve_pursuit("pursuit_d")
    assert r["events_count"] == 1 and len(r["memory_ids"]) == 1       # dédup par id -> un seul
    store = open_memory_store(root / "memory")
    assert len(read_pursuit_delivery(store, "pursuit_d")) == 1        # preuve directe de dédup


def test_memory_absent_but_arc_present(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_arc(root, "pursuit_arc", proposed=True)                     # aucune mémoire livrée ; arc reprenable
    r = retrieve_pursuit("pursuit_arc")
    assert r["found"] is False and r["continuity"] is None
    assert r["resumable"] is True and r["resume_hint"] is not None    # cas valide : found=False / resumable=True


def test_arc_dir_without_turns_not_resumable(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_delivery(root, "pursuit_x")
    from brainai_app.composition import _pursuit_dir
    _pursuit_dir("pursuit_x").mkdir(parents=True, exist_ok=True)      # dossier vide, aucun turns.jsonl
    r = retrieve_pursuit("pursuit_x")
    assert r["found"] is True                                         # mémoire présente
    assert r["resumable"] is False and r["resume_hint"] is None       # existence de dossier insuffisante


def test_arc_turns_only_failed_not_resumable(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_arc(root, "pursuit_f", proposed=False)                      # tours présents mais status != proposed
    r = retrieve_pursuit("pursuit_f")
    assert r["resumable"] is False                                    # même filtre que le moteur (_history)


def test_corruption_memory11_failclosed(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    _seed_delivery(root, "pursuit_c1")
    _seed_delivery(root, "pursuit_c2")                               # 2 lignes de journal
    from scc_brainai_memory.core.errors import MemoryCorruption      # importable après open_memory_store
    journal = root / "memory" / "brain_memory.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2
    lines[0] = "{ ceci n'est pas du JSON valide"                     # corruption AU MILIEU (pas la dernière ligne)
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(MemoryCorruption):
        retrieve_pursuit("pursuit_c1")


def test_no_fabrication_missing_optional_fields(tmp_path, monkeypatch):
    root = _state(tmp_path, monkeypatch)
    store = open_memory_store(root / "memory")
    store.record_event("pursuit_delivered",
                       {"pursuit_ref": "pursuit_min", "result": "r"},   # need/status/as_of/provenance absents
                       tags=["jalon2", "delivered", "pursuit", "pursuit:pursuit_min"])
    c = retrieve_pursuit("pursuit_min")["continuity"]
    assert c["result"] == "r"
    for k in ("need", "status", "as_of", "artifact_ref", "preview_ref", "provenance_ids"):
        assert c[k] is None                                          # aucune fabrication
