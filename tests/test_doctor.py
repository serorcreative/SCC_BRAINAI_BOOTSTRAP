"""Tests du diagnostic complet (scc-brainai doctor)."""

from __future__ import annotations

import json

import pytest

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.cli import main
from scc_brainai_bootstrap.core.config import load_config


@pytest.fixture
def doc(boot):
    return boot.doctor()


def test_doctor_healthy(doc):
    assert doc["verdict"] == "healthy"
    assert doc["banner"] == "BrainAI HEALTHY"
    assert doc["issues"] == []


def test_doctor_sections(doc):
    s = doc["sections"]
    assert s["patrimony"]["present"] == s["patrimony"]["total"]
    assert all(s["availability"].values())          # 8 composants disponibles
    assert s["health"]["control_plane"] == "ok"
    assert s["health"]["domains"] >= 10
    assert all(s["audits"].values())                # memory + 4 couches cognitives


def test_doctor_all_layers_audited(doc):
    audits = doc["sections"]["audits"]
    assert {"memory", "reasoning", "planning", "decision", "execution"} <= set(audits)


def test_doctor_degraded_when_root_missing(tmp_path):
    cfg = load_config()
    cfg.data_dir = tmp_path / "data"
    cfg.scc_root = tmp_path / "nowhere"
    report = BrainAIBootstrap(config=cfg).doctor()
    assert report["verdict"] == "degraded"
    assert report["banner"] == "BrainAI DEGRADED"
    assert report["issues"]


def test_doctor_event_on_bus(boot):
    boot.doctor()
    assert any(e["topic"] == "doctor.run" for e in boot.recorder.events)


def test_doctor_deterministic(tmp_path):
    def diagnose(name):
        cfg = load_config(); cfg.data_dir = tmp_path / name
        return BrainAIBootstrap(config=cfg).doctor()
    a, b = diagnose("a"), diagnose("b")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_cli_doctor_healthy(tmp_path, capsys):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    rc = main(["--config", str(cfg), "doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "BrainAI HEALTHY" in out
    assert "patrimoine" in out and "audits" in out


def test_cli_doctor_json(tmp_path, capsys):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")}}), encoding="utf-8")
    rc = main(["--config", str(cfg), "doctor", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["verdict"] == "healthy"
