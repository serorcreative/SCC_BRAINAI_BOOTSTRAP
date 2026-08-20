"""Tests de l'Event Bus vivant : abonnés, persistance, alertes, commande events."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main
from scc_brainai_bootstrap.event_bus import EventBus
from scc_brainai_bootstrap.subscribers import EventRecorder, LifecycleWatcher


def test_subscribers_attached_before_publish(boot):
    # les abonnés existent dès la construction, avant toute publication
    assert len(boot.recorder) == 0
    report = boot.run()
    # tous les événements du bus ont été captés par l'enregistreur
    assert len(boot.recorder) == report["event_count"]
    assert report["subscribers"]["recorded"] == report["event_count"]


def test_events_persisted_to_journal(boot):
    report = boot.run()
    path = boot.events_path
    assert path.exists()
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == report["event_count"]
    assert lines[-1]["topic"] == "brainai.ready"


def test_watcher_no_alert_on_healthy_boot(report):
    life = report["subscribers"]["lifecycle"]
    assert life["ready_seen"] is True
    assert life["alert_count"] == 0


def test_watcher_alerts_on_degraded(tmp_path):
    from scc_brainai_bootstrap.core.config import load_config
    cfg = load_config()
    cfg.data_dir = tmp_path / "data"
    cfg.scc_root = tmp_path / "nowhere"
    report = BrainAIBootstrap(config=cfg).run()
    life = report["subscribers"]["lifecycle"]
    assert life["alert_count"] >= 1
    assert any(a["topic"] == "brainai.ready" for a in life["alerts"])


def test_handle_publishes_and_records(boot):
    result = boot.handle("état du système")
    topics = [e["topic"] for e in boot.recorder.events]
    assert "request.received" in topics
    assert "experience.recorded" in topics
    assert result["alerts"] == []      # cycle sain


def test_event_recorder_and_watcher_units():
    bus = EventBus("2026-07-06T00:00:00+00:00")
    rec, watch = EventRecorder(), LifecycleWatcher()
    bus.subscribe(rec.on_event)
    bus.subscribe(watch.on_event)
    bus.publish("boot.memory", {"ok": False, "detail": "absent"})
    bus.publish("brainai.ready", {"ready": False, "degraded": ["memory"]})
    assert len(rec) == 2
    assert watch.summary()["alert_count"] == 2
    assert watch.ready_seen is True


def test_event_recorder_dump_is_append_only(tmp_path):
    # JALON-0 T2 — le journal d'événements est append-only : un second dump N'EFFACE PAS le premier
    # (bug REVUE 6 août : write_text tronquait à chaque processus). Curseur → delta seulement, sans duplication.
    path = tmp_path / "events.jsonl"
    rec1 = EventRecorder()                                   # « processus 1 »
    rec1.on_event({"seq": 1, "topic": "a"})
    rec1.on_event({"seq": 2, "topic": "b"})
    rec1.dump(path)
    assert [json.loads(l)["topic"] for l in path.read_text(encoding="utf-8").splitlines()] == ["a", "b"]

    rec2 = EventRecorder()                                   # « processus 2 » : recorder neuf, curseur à 0
    rec2.on_event({"seq": 3, "topic": "c"})
    rec2.dump(path)                                          # MÊME fichier
    assert [json.loads(l)["topic"] for l in path.read_text(encoding="utf-8").splitlines()] == ["a", "b", "c"]

    before = path.read_text(encoding="utf-8")                # idempotence intra-processus
    rec2.dump(path)
    assert path.read_text(encoding="utf-8") == before

    rec2.on_event({"seq": 4, "topic": "d"})                  # delta uniquement, aucune duplication
    rec2.dump(path)
    assert [json.loads(l)["topic"] for l in path.read_text(encoding="utf-8").splitlines()] == ["a", "b", "c", "d"]


def test_cli_events(tmp_path, capsys):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    rc = main(["--config", str(cfg), "events"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["count"] >= 12
    topics = {e["topic"] for e in data["events"]}
    assert "brainai.ready" in topics


def test_cli_events_filter_topic(tmp_path, capsys):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")}}), encoding="utf-8")
    rc = main(["--config", str(cfg), "events", "--topic", "agent.registered"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["count"] == 4
    assert all(e["topic"] == "agent.registered" for e in data["events"])
