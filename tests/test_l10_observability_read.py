"""Tests L10 — Variante MIN : connexion READ-ONLY de l'observabilité 09_CONTROL_PLANE.

Déterministe, 0 LLM, 0 USD, 0 réseau. Prouve : résolution, fail-closed, adaptateur inerte, voie publique unique,
appel EXCLUSIF de global_state()+component_health(), absence de toute autre méthode / RuntimeProbe /
ensure_directories / write_state_report / state_dir, provenance ToolInvocationStore, redaction, déterminisme,
absence de couplage réseau/subprocess/13-15-16/SAB-NEXUS-Base44. 09_CONTROL_PLANE n'est jamais modifié.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from scc_brainai_bootstrap.builder.observability_read import (
    OBS_HEALTH, OBSERVABILITY_READ_CAPABILITIES, PROVIDER_NAME,
    LocalControlPlaneReadAdapter, ObservabilityReadHandle, ObservabilityReadError,
    produce_observability_read,
)
from scc_brainai_bootstrap.builder.claude_code_runtime import DIAG_MAX
from brainai_app.providers import (
    resolve_observability_read, OBSERVABILITY_READ_PROVIDERS, LOCAL_CONTROL_PLANE,
)

CLK = "2026-07-06T00:00:00+00:00"


class FakeToolStore:
    def __init__(self):
        self.records = []

    def record(self, **kw):
        self.records.append(kw)
        return {"invocation_id": "tinv_fake"}


def _fake_module(calls, *, gs=None, ch=None):
    mod = types.ModuleType("scc_control_plane")

    class FakeConfig:
        def __init__(self):
            self.as_of = CLK

        def ensure_directories(self):
            calls.append("ensure_directories")     # NE DOIT JAMAIS être appelé (Variante MIN)

    def load_config(path=None):
        calls.append("load_config")
        return FakeConfig()

    class FakeControlPlane:
        def __init__(self, config):
            calls.append("__init__")
            self.config = config

        def global_state(self):
            calls.append("global_state")
            return dict(gs if gs is not None else {"counts": {"jobs": 0}, "detail": "ok"})

        def component_health(self):
            calls.append("component_health")
            return dict(ch if ch is not None else {"overall": "OK", "components": []})

        # --- méthodes INTERDITES : lèvent si appelées (espions) ---
        def health(self): calls.append("health"); raise AssertionError("health called")
        def snapshot(self): calls.append("snapshot"); raise AssertionError("snapshot called")
        def state_report(self): calls.append("state_report"); raise AssertionError("state_report called")
        def self_check(self): calls.append("self_check"); raise AssertionError("self_check called")
        def supervise_runtime(self): calls.append("supervise_runtime"); raise AssertionError
        def supervise_jobs(self): calls.append("supervise_jobs"); raise AssertionError
        def supervise_sessions(self): calls.append("supervise_sessions"); raise AssertionError
        def supervise_events(self): calls.append("supervise_events"); raise AssertionError
        def supervise_agents(self): calls.append("supervise_agents"); raise AssertionError
        def supervise_engines(self): calls.append("supervise_engines"); raise AssertionError
        def metrics(self): calls.append("metrics"); raise AssertionError
        def alerts(self): calls.append("alerts"); raise AssertionError
        def diagnostics(self): calls.append("diagnostics"); raise AssertionError
        def write_state_report(self, tag="state"):
            calls.append("write_state_report"); raise AssertionError("write_state_report called")

    def _probe_boom(*a, **k):
        calls.append("RuntimeProbe"); raise AssertionError("RuntimeProbe instantiated")

    mod.ControlPlane = FakeControlPlane
    mod.load_config = load_config
    mod.RuntimeProbe = _probe_boom          # présence ; ne doit JAMAIS être instancié par notre code
    return mod


@pytest.fixture
def fake_cp(monkeypatch):
    calls = []
    mod = _fake_module(calls)
    monkeypatch.setitem(sys.modules, "scc_control_plane", mod)
    return calls, mod


def _read(tmp_path, tool_store):
    h = resolve_observability_read(OBS_HEALTH)
    return h.read(control_plane_src=tmp_path, scc_root=tmp_path, tool_store=tool_store,
                  project_id="proj", clock=lambda: CLK)


# A. résolution
def test_resolution_returns_handle(fake_cp):
    h = resolve_observability_read(OBS_HEALTH)
    assert isinstance(h, ObservabilityReadHandle)
    assert h.provider == PROVIDER_NAME == LOCAL_CONTROL_PLANE
    assert hasattr(h, "read")
    assert OBSERVABILITY_READ_PROVIDERS == (LOCAL_CONTROL_PLANE,)


# B. provider / capacité inconnus → fail-closed
def test_unknown_provider_and_capability_lookup_error():
    with pytest.raises(LookupError):
        resolve_observability_read(OBS_HEALTH, provider="nope")
    with pytest.raises(LookupError):
        resolve_observability_read("observability.nope")


# C. adaptateur INERTE : aucune méthode d'exécution
def test_adapter_is_inert():
    a = LocalControlPlaneReadAdapter()
    for forbidden in ("read", "run", "_run", "execute", "global_state", "component_health", "call"):
        assert not hasattr(a, forbidden), forbidden
    assert callable(a.contract)
    assert a.name == PROVIDER_NAME


# D+E+F+G+H+I+O+N. voie unique : appelle EXACTEMENT global_state+component_health, rien d'autre ; provenance
def test_read_calls_only_allowed_methods_and_records_provenance(fake_cp, tmp_path):
    calls, _ = fake_cp
    ts = FakeToolStore()
    out = _read(tmp_path, ts)
    # E/F : séquence exacte, aucune méthode interdite
    assert calls == ["load_config", "__init__", "global_state", "component_health"]
    for forbidden in ("health", "snapshot", "state_report", "self_check", "write_state_report",
                      "supervise_runtime", "metrics", "alerts", "diagnostics", "RuntimeProbe",
                      "ensure_directories"):
        assert forbidden not in calls, forbidden
    # N : résultat typé
    assert out["capability"] == OBS_HEALTH and out["provider"] == PROVIDER_NAME and out["ok"] is True
    assert set(out["result"].keys()) == {"global_state", "component_health"}
    # O : provenance enregistrée
    assert len(ts.records) == 1 and out["tool_ref"] == "tinv_fake"
    rec = ts.records[0]
    assert rec["tool"] == f"{PROVIDER_NAME}:{OBS_HEALTH}" and rec["status"] == "succeeded"
    assert rec["timed_out"] is False


# J. aucun state_dir créé
def test_no_state_dir_created(fake_cp, tmp_path):
    _read(tmp_path, FakeToolStore())
    assert not (tmp_path / "state").exists()
    assert list(tmp_path.iterdir()) == []            # aucune écriture dans la racine autorisée


# K+L+S. aucune dépendance réseau / subprocess / 13-15-16 (couplages RÉELS via AST — jamais la prose/docstring).
# Les mentions documentaires (SAB/NEXUS/Base44) dans les docstrings ne sont PAS des couplages : on ne contrôle
# QUE les imports réels du module (import / from ... import).
def test_no_forbidden_couplings_in_imports():
    import ast
    import scc_brainai_bootstrap.builder.observability_read as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
                imported.add(node.module.split(".")[0])
    forbidden = {"socket", "urllib", "requests", "http", "http.client", "subprocess",
                 "scc_brainai_reasoning", "scc_brainai_decision", "scc_brainai_execution"}
    hits = sorted(imported & forbidden)
    assert not hits, hits


# M. déterminisme
def test_determinism(fake_cp, tmp_path):
    a = _read(tmp_path, FakeToolStore())
    b = _read(tmp_path, FakeToolStore())
    assert a == b


# P. redaction / bornage SEC-3 (chaîne longue tronquée à DIAG_MAX)
def test_redaction_bounds_long_detail(monkeypatch, tmp_path):
    calls = []
    long_detail = "x" * (DIAG_MAX + 50)
    mod = _fake_module(calls, gs={"counts": {"jobs": 0}, "detail": long_detail})
    monkeypatch.setitem(sys.modules, "scc_control_plane", mod)
    out = _read(tmp_path, FakeToolStore())
    assert len(out["result"]["global_state"]["detail"]) <= DIAG_MAX


# fail-closed : control_plane_src None + provenance de refus enregistrée
def test_fail_closed_missing_src_records_then_raises(fake_cp):
    ts = FakeToolStore()
    h = resolve_observability_read(OBS_HEALTH)
    with pytest.raises(ObservabilityReadError):
        h.read(control_plane_src=None, scc_root=None, tool_store=ts, project_id="p", clock=lambda: CLK)
    assert len(ts.records) == 1 and ts.records[0]["status"] == "failed"


# fail-closed : structure inattendue (global_state non-dict)
def test_fail_closed_unexpected_structure(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls, gs=None)
    # remplace global_state pour renvoyer une liste (structure inattendue)
    mod.ControlPlane.global_state = lambda self: ["not", "a", "dict"]
    monkeypatch.setitem(sys.modules, "scc_control_plane", mod)
    with pytest.raises(ObservabilityReadError):
        _read(tmp_path, FakeToolStore())


# fail-closed : capacité invalide passée directement à produce
def test_produce_rejects_unknown_capability(tmp_path):
    with pytest.raises(ObservabilityReadError):
        produce_observability_read(capability="observability.nope",
                                   adapter=LocalControlPlaneReadAdapter(),
                                   control_plane_src=tmp_path, scc_root=tmp_path,
                                   tool_store=FakeToolStore(), project_id="p", clock=lambda: CLK)
