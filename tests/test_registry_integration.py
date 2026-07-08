"""Tests d'intégration du registre dans le Bootstrap + CLI."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.cli import main


def test_catalog_lists_cognitive_and_scc_agents(boot):
    cat = boot.agents_catalog()
    ids = {a["id"] for a in cat["agents"]}
    assert {"brainai-memory", "brainai-planning"} <= ids       # moteurs (manifests)
    assert {"SCC-AGENT-0001"} <= ids                           # fiches SCC (adaptées)
    assert set(boot.agents.namespaces()) == {"brainai", "scc"}


def test_catalog_filter_by_namespace_and_capability(boot):
    brainai = boot.agents_catalog(namespace="brainai")
    assert brainai["count"] == 5 and all(a["namespace"] == "brainai" for a in brainai["agents"])
    planners = boot.agents_catalog(capability="planning.propose")
    assert [a["id"] for a in planners["agents"]] == ["brainai-planning"]


def test_capability_index_maps_engines(boot):
    caps = boot.capability_index()["capabilities"]
    assert caps["memory.recall"] == ["brainai-memory"]
    assert caps["execution.run"] == ["brainai-execution"]


def test_resolve_capability_binds_engine(boot):
    result = boot.resolve_capability("decision.evaluate")
    assert result["resolved"] is True
    assert result["selected"] == "brainai-decision"
    assert any(e["topic"] == "capability.resolved" for e in boot.bus.events)


def test_resolve_unknown_capability(boot):
    result = boot.resolve_capability("vision.describe")
    assert result["resolved"] is False
    assert result["provider_count"] == 0


def test_no_engine_import_at_bootstrap_construction():
    # à la seule construction, aucun moteur cognitif n'est importé (découplage).
    import sys
    from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
    from scc_brainai_bootstrap.core.config import load_config
    for m in ("scc_brainai_planning", "scc_brainai_decision", "scc_brainai_execution"):
        sys.modules.pop(m, None)
    BrainAIBootstrap(config=load_config())             # construction seule, pas de run()
    assert "scc_brainai_planning" not in sys.modules   # importé seulement à l'invocation


def test_registry_audit_healthy(boot):
    audit = boot.agents.audit()
    assert audit["ok"] is True
    assert audit["ids_unique"] is True
    assert audit["malformed"] == []


def test_boot_still_registers_four_pivots(boot):
    report = boot.run()
    assert len(report["agents"]) == 4
    assert {a["id"] for a in report["agents"]} == {
        "SCC-AGENT-0001", "SCC-AGENT-0002", "SCC-AGENT-0003", "SCC-AGENT-0020"}


def _cli_config(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def test_cli_agents(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "agents", "--namespace", "brainai"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "brainai-memory" in out and "capacités" in out


def test_cli_capabilities(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "capabilities", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["capabilities"]["planning.propose"] == ["brainai-planning"]


def test_cli_resolve(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "resolve", "memory.recall"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "brainai-memory" in out and "retenu" in out


def test_cli_resolve_unknown_returns_1(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "resolve", "vision.describe"])
    assert rc == 1
