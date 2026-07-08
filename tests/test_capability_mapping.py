"""Tests du mapping déclaratif capacités ← fiches SCC (BUILD-012)."""

from __future__ import annotations

import json

from scc_brainai_bootstrap.cli import main
from scc_brainai_bootstrap.core.config import load_config
from scc_brainai_bootstrap.registry import AgentRegistry, FicheSource
from scc_brainai_bootstrap.registry.sources import load_capability_map

_PIVOTS = ["SCC-AGENT-0001", "SCC-AGENT-0002", "SCC-AGENT-0003", "SCC-AGENT-0020"]


# --------------------------------------------------------------------- #
# Loader du mapping déclaratif
# --------------------------------------------------------------------- #
def test_load_map_ignores_meta_and_keeps_lists(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"__meta__": {"v": 1}, "A": ["x.y"], "B": "nope"}), encoding="utf-8")
    m = load_capability_map(p)
    assert m == {"A": ["x.y"]}                       # méta ignorée, valeur non-liste ignorée


def test_load_map_absent_or_malformed(tmp_path):
    assert load_capability_map(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"; bad.write_text("{not json", encoding="utf-8")
    assert load_capability_map(bad) == {}


def test_shipped_map_covers_pivots_with_valid_slugs():
    from scc_brainai_bootstrap.registry.capability import is_valid_capability
    m = load_capability_map(load_config().capability_map_path)
    assert set(m) == set(_PIVOTS)
    for slugs in m.values():
        assert slugs and all(is_valid_capability(s) for s in slugs)


# --------------------------------------------------------------------- #
# FicheSource applique le mapping (aucune inférence)
# --------------------------------------------------------------------- #
def _registry_with_map(cap_map):
    cfg = load_config()
    src = FicheSource(cfg.agents_dir, _PIVOTS, namespace="scc", capability_map=cap_map)
    return AgentRegistry(cfg, sources=[src]).load()


def test_fiche_source_attaches_mapped_capabilities():
    reg = _registry_with_map({"SCC-AGENT-0001": ["architecture.arbitrate"]})
    assert reg.get("SCC-AGENT-0001").capabilities == ["architecture.arbitrate"]
    assert reg.get("SCC-AGENT-0002").capabilities == []       # non mappé → aucune capacité


def test_fiche_source_without_map_has_no_capabilities():
    reg = _registry_with_map({})
    assert all(reg.get(p).capabilities == [] for p in _PIVOTS)


def test_mapping_light_format_guard_non_blocking():
    reg = _registry_with_map({"SCC-AGENT-0001": ["BADSLUG"]})
    assert reg.get("SCC-AGENT-0001") is not None              # non bloquant
    assert any(x["agent"] == "SCC-AGENT-0001" for x in reg.malformed)


# --------------------------------------------------------------------- #
# Intégration Bootstrap : les agents SCC entrent dans l'index
# --------------------------------------------------------------------- #
def test_scc_agents_enter_capability_index(boot):
    caps = boot.capability_index()["capabilities"]
    assert caps["governance.oversee"] == ["SCC-AGENT-0001"]
    assert caps["governance.enforce"] == ["SCC-AGENT-0002"]
    assert caps["foundation.guard"] == ["SCC-AGENT-0003"]
    assert caps["orchestration.compose"] == ["SCC-AGENT-0020"]


def test_catalog_filter_by_scc_capability(boot):
    res = boot.agents_catalog(capability="architecture.arbitrate")
    assert [a["id"] for a in res["agents"]] == ["SCC-AGENT-0001"]


def test_scc_capability_resolves_to_unexecutable_candidate(boot):
    # le registre DÉCRIT (candidat présent) ; les MOTEURS exécutent (pas d'adaptateur ⇒
    # indisponible ⇒ non résolu). Séparation des rôles prouvée.
    result = boot.resolve_capability("orchestration.supervise")
    assert result["provider_count"] == 1
    assert result["candidates"][0]["id"] == "SCC-AGENT-0020"
    assert result["candidates"][0]["available"] is False
    assert result["resolved"] is False


def test_pivots_report_capabilities_after_boot(boot):
    report = boot.run()
    by_id = {a["id"]: a for a in report["agents"]}
    assert by_id["SCC-AGENT-0001"]["capabilities"]            # capacités présentes
    assert len(report["agents"]) == 4                         # toujours 4 pivots


def test_registry_audit_still_healthy_with_mapping(boot):
    assert boot.agents.audit()["ok"] is True


def test_capability_index_deterministic_cross_process():
    def index():
        cfg = load_config()
        from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
        import tempfile, pathlib
        cfg.data_dir = pathlib.Path(tempfile.mkdtemp()) / "data"
        return BrainAIBootstrap(config=cfg).capability_index()["capabilities"]
    assert json.dumps(index(), sort_keys=True) == json.dumps(index(), sort_keys=True)


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #
def _cli_config(tmp_path):
    from scc_brainai_bootstrap.core.config import DEFAULT_SCC_ROOT
    cfg = tmp_path / "brainai.json"
    cfg.write_text(json.dumps({"scc_root": str(DEFAULT_SCC_ROOT),
                               "paths": {"data_dir": str(tmp_path / "data")},
                               "as_of": "2026-07-06T00:00:00+00:00"}), encoding="utf-8")
    return cfg


def test_cli_agents_filter_by_scc_capability(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "agents", "--capability", "governance.oversee"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SCC-AGENT-0001" in out


def test_cli_capabilities_lists_scc_slugs(tmp_path, capsys):
    cfg = _cli_config(tmp_path)
    rc = main(["--config", str(cfg), "capabilities", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["capabilities"]["contract.validate"] == ["SCC-AGENT-0003"]
