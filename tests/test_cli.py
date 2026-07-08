"""Tests de la CLI de démarrage."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.bootstrap import READY_BANNER
from scc_brainai_bootstrap.cli import main


def _cfg_file(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def test_cli_start_prints_ready(tmp_path, capsys):
    rc = main(["--config", str(_cfg_file(tmp_path)), "start"])
    out = capsys.readouterr().out
    assert rc == 0
    assert READY_BANNER in out
    assert "[1/8] config" in out
    assert "[7/8] agents" in out


def test_cli_start_json(tmp_path, capsys):
    rc = main(["--config", str(_cfg_file(tmp_path)), "start", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ready"] is True
    assert data["banner"] == READY_BANNER


def test_cli_status(tmp_path, capsys):
    rc = main(["--config", str(_cfg_file(tmp_path)), "status"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["patrimony"]["present"] >= 20
    assert data["first_agents"]
