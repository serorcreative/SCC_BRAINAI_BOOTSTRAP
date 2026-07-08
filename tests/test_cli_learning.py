"""Tests CLI de la chaîne apprenante (learn / learnings / learn-validate)."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.cli import main


def _cli_config(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def _seed(cfg):
    for q in ["Explique l architecture", "Explique l architecture", "état du système"]:
        main(["--config", str(cfg), "run", q, "--route", "kernel"])


def test_cli_learn(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    _seed(cfg)
    capsys.readouterr()
    rc = main(["--config", str(cfg), "learn"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "vécu analysé" in out
    assert "apprentissages" in out


def test_cli_learn_json(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    _seed(cfg)
    capsys.readouterr()
    rc = main(["--config", str(cfg), "learn", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ok"] is True
    assert data["total_learnings"] >= 0


def test_cli_plan_closed_loop(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    _seed(cfg)
    main(["--config", str(cfg), "learn"])
    # valider toutes les recommandations
    capsys.readouterr()
    main(["--config", str(cfg), "learnings", "--kind", "recommendation", "--json"])
    recs = json.loads(capsys.readouterr().out)["items"]
    for r in recs:
        main(["--config", str(cfg), "learn-validate", r["id"], "--by", "frederique"])
    capsys.readouterr()
    rc = main(["--config", str(cfg), "plan", "Améliorer la gouvernance documentaire"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "plan" in out and "tâches" in out
    if recs:
        assert "boucle fermée" in out


def test_cli_learnings_and_validate(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    _seed(cfg)
    main(["--config", str(cfg), "learn"])
    capsys.readouterr()
    rc = main(["--config", str(cfg), "learnings", "--kind", "signal", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["items"], "au moins un signal attendu"
    item_id = data["items"][0]["id"]

    rc = main(["--config", str(cfg), "learn-validate", item_id, "--by", "frederique"])
    res = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert res["status"] == "validated"
