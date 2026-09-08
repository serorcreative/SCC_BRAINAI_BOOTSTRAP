"""L9 — Multi-Builder / BuildProvider interchangeable — déterministe, 0 $, fakes/local, aucun provider payant."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from brainai_app import composition, providers, server
from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.delivered import DeliveredStore
from brainai_app.delivery.preview_capability import LocalPreviewAdapter
from brainai_app.delivery.runner import BuildRunStore
from brainai_app.delivery.service import run_delivery
from brainai_app.delivery.verify import VerificationStore
from scc_brainai_bootstrap.builder.adapter_contract import require_contract
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.build_authorization import BuildAuthorizationStore, resolve_cost_gate
from scc_brainai_bootstrap.builder.cost_estimate import PROVIDER_CALL, estimate_costs, CostEstimateStore
from scc_brainai_bootstrap.builder.local_site import (
    LocalDeterministicSiteAdapter, PROVIDER_NAME, render_index_html)
from scc_brainai_bootstrap.builder.site import SITE_ENTRYPOINT, produce_site_build
from scc_brainai_bootstrap.builder.solution_architecture import SolutionArchitectureStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.workspace import Workspace
from scc_brainai_bootstrap.core.clock import digest

CLOCK = lambda: "2026-09-08T00:00:00+00:00"  # noqa: E731

_SPECIFICATION = {
    "product_objective": "Page de présentation d'un refuge animalier",
    "users_and_roles": ["Personnel", "Adoptant"],
    "functional_scope": ["Animaux", "Adoptants"],
    "features": ["Fiche animal", "Rejoindre"],
    "entities_and_data": ["Animal", "Adoptant"],
    "key_journeys": ["Découvrir"],
    "constraints": ["Statique"],
    "acceptance_criteria": ["Se charge"],
    "assumptions": ["Public"],
    "open_questions": [],
    "out_of_scope": ["Paiement"],
}
_SPEC = {"specification_id": "spec_l9", "status": "proposed", "specification": _SPECIFICATION}


def _ws(tmp_path):
    ws = Workspace(tmp_path / "exec", "site")
    ws.ensure()
    return ws


# 1. RÉSOLUTION BUILDPROVIDER
def test_build_providers_set_canonical():
    assert providers.BUILD_PROVIDERS == ("claude_code", "deterministic_local")
    assert providers.LOCAL_BUILDER == "deterministic_local"


def test_default_delivery_unchanged_is_claude_code():
    caps = providers.real_delivery()
    assert caps.site_build.name == "claude_code"
    assert providers.resolve_build_site().name == "claude_code"


def test_explicit_local_selected_no_silent_substitution():
    caps = providers.real_delivery(build_provider="deterministic_local")
    assert caps.site_build.name == "deterministic_local"
    assert providers.resolve_build_site("deterministic_local").name == "deterministic_local"


def test_unknown_build_provider_fail_closed():
    with pytest.raises(LookupError):
        providers.resolve_build_site("provider_inexistant")
    with pytest.raises(LookupError):
        providers.real_delivery(build_provider="provider_inexistant")
    with pytest.raises(LookupError):
        providers.resolve_build_site(" deterministic_local ")


def test_contract_t2_complete_both_providers():
    local = providers.resolve_build_site("deterministic_local")
    claude = providers.resolve_build_site("claude_code")
    require_contract(local)
    require_contract(claude)
    lc = local.contract().to_dict()
    assert lc["cost_report"]["mode"] == "unavailable" and lc["cost_report"]["fabricated"] is False
    assert lc["native_budget"] == {"usd_cap": "none", "call_cap": "none"}
    assert lc["confinement"]["workspace"] is True
    cc = claude.contract().to_dict()
    assert cc["cost_report"]["mode"] == "real_from_envelope"


# 2. CONSTRUCTION LOCALE RÉELLE
def test_local_build_via_produce_site_build(tmp_path):
    ws = _ws(tmp_path)
    build_store = BuildStore(tmp_path / "b.jsonl")
    tool_store = ToolInvocationStore(tmp_path / "t.jsonl")
    out = produce_site_build(spec_source=_SPEC, adapter=LocalDeterministicSiteAdapter(),
                             store=build_store, tool_store=tool_store, workspace=ws, project_id="site",
                             budget_remaining_usd=0.0, cwd=ws.path, clock=CLOCK)
    assert out["recorded"] is True
    fact = out["fact"]
    assert fact["status"] == "proposed"
    assert fact["adapter"] == "deterministic_local"
    assert fact["cost"]["kind"] == "unavailable"
    assert fact["artefact"]["relative_path"] == SITE_ENTRYPOINT
    written = (ws.path / SITE_ENTRYPOINT).read_text(encoding="utf-8")
    assert "refuge animalier" in written
    tinv = tool_store.read_all()
    assert len(tinv) == 1 and tinv[0]["tool"] == "deterministic_local" and tinv[0]["status"] == "succeeded"


def test_render_index_html_deterministic_and_escaped():
    a = render_index_html(_SPECIFICATION)
    b = render_index_html(_SPECIFICATION)
    assert a == b and a.strip().startswith("<!DOCTYPE html>")
    inj = dict(_SPECIFICATION, product_objective="<script>x</script>")
    assert "<script>x</script>" not in render_index_html(inj)
    assert "&lt;script&gt;" in render_index_html(inj)


# 3. MÊME run_delivery
def test_run_delivery_with_local_builder_delivers(tmp_path):
    build_store = BuildStore(tmp_path / "b.jsonl")
    tool_store = ToolInvocationStore(tmp_path / "t.jsonl")
    rep = run_delivery(spec_source=_SPEC, workspace=_ws(tmp_path), project_id="site", pursuit_ref="p_l9",
                       site_build=LocalDeterministicSiteAdapter(), preview=LocalPreviewAdapter(),
                       budget=BudgetLedger(tmp_path / "bud.jsonl", ceiling_usd=1.0, max_calls=2),
                       build_store=build_store, tool_store=tool_store,
                       run_store=BuildRunStore(tmp_path / "r.jsonl"),
                       verification_store=VerificationStore(tmp_path / "v.jsonl"),
                       delivered_store=DeliveredStore(tmp_path / "d.jsonl"), clock=CLOCK)
    assert rep["status"] == "delivered"
    builds = build_store.read_all()
    assert builds and builds[-1]["adapter"] == "deterministic_local"


# 4. AUCUN BYPASS USER GO / COST GATE
_OPTIONS = [
    {"id": "opt_a", "summary": "s", "components": ["web", "db"], "external_services": [],
     "dependencies": ["python"], "risks": ["r"], "scalability": "m", "maintainability": "b"},
    {"id": "opt_b", "summary": "s", "components": ["web", "worker"], "external_services": ["queue"],
     "dependencies": ["python", "redis"], "risks": ["ops"], "scalability": "b", "maintainability": "m"},
]
_AS_OF = "2026-09-08T00:00:00+00:00"


class _Boundary(Exception):
    pass


class _Sentinel:
    def __init__(self):
        self.calls = 0
        self.build_providers = []

    def __call__(self, build_provider=None):
        self.calls += 1
        self.build_providers.append(build_provider)
        raise _Boundary("frontière providers.real_delivery() atteinte")


class FakeOutcome:
    state = "awaiting"; wait_reason = "governance"; refused = None; need = None

    def __init__(self, pursuit_id, spec_id, build_id, gate_fp):
        self.pursuit_id = pursuit_id
        self.as_of = _AS_OF
        self.steps = [{"faculty": "specification", "status": "proposed", "fact_id": spec_id},
                      {"faculty": "build", "status": "proposed", "fact_id": build_id}]
        self.proposal = {"cost_gate": {"gate_fingerprint": gate_fp}}


@pytest.fixture()
def gate_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAINAI_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setattr(composition, "_SESSIONS", {})

    def seed(pursuit_id):
        root = composition._pursuit_dir(pursuit_id)
        root.mkdir(parents=True, exist_ok=True)
        spec_sha = digest(_SPECIFICATION)
        spec_fact = SpecificationStore(root / "spec.jsonl").record({
            "fact_type": "specification", "status": "proposed", "specification": _SPECIFICATION,
            "brief_ref": "b", "brief_sha256": "x", "model": "demo", "adapter": "demo", "as_of": _AS_OF})
        spec_id = spec_fact["specification_id"]
        build_fact = BuildStore(root / "build.jsonl").record({
            "fact_type": "build", "status": "proposed", "artefact": {"file": "m.json"},
            "spec_ref": spec_id, "spec_sha256": spec_sha, "model": "demo", "adapter": "demo", "as_of": _AS_OF})
        build_id = build_fact["build_id"]
        arch_store = SolutionArchitectureStore(root / "architectures.jsonl")
        arch_fact = arch_store.record({
            "fact_type": "solution_architecture", "status": "proposed", "pursuit_ref": pursuit_id,
            "cost_source": PROVIDER_CALL, "spec_ref": spec_id, "spec_sha256": spec_sha,
            "options": _OPTIONS, "as_of": _AS_OF})
        est_store = CostEstimateStore(root / "cost_estimates.jsonl")
        for opt in _OPTIONS:
            est_store.record(estimate_costs(opt, pursuit_ref=pursuit_id,
                                            architecture_ref=arch_fact["architecture_id"], as_of=_AS_OF))
        gate = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                                 pursuit_ref=pursuit_id, current_spec=spec_fact)
        assert gate["status"] == "resolved", gate
        return root, spec_id, build_id, spec_fact, gate["gate"]["gate_fingerprint"]

    return seed


def test_build_provider_does_not_bypass_gate_without_go(gate_env, monkeypatch):
    sentinel = _Sentinel()
    monkeypatch.setattr(providers, "real_delivery", sentinel)
    root, sid, bid, _s, fp = gate_env("p_nogo")
    res = composition._deliver(root, FakeOutcome("p_nogo", sid, bid, fp), actor="t", budget_usd=1.0,
                               build_provider="deterministic_local")
    assert res["status"] == "refused" and res["reason"] == "no_valid_current_go"
    assert res["significant_construction"] is False
    assert sentinel.calls == 0


def test_build_provider_reaches_boundary_only_after_valid_go(gate_env, monkeypatch):
    sentinel = _Sentinel()
    monkeypatch.setattr(providers, "real_delivery", sentinel)
    root, sid, bid, _s, fp = gate_env("p_go")
    composition.authorize("p_go", presented_spec_ref=sid, presented_gate_fingerprint=fp, decision="approved")
    with pytest.raises(_Boundary):
        composition._deliver(root, FakeOutcome("p_go", sid, bid, fp), actor="t", budget_usd=1.0,
                             build_provider="deterministic_local")
    assert sentinel.calls == 1
    assert sentinel.build_providers == ["deterministic_local"]


def test_unknown_build_provider_with_valid_go_fail_closed(gate_env):
    root, sid, bid, _s, fp = gate_env("p_unknown")
    composition.authorize("p_unknown", presented_spec_ref=sid, presented_gate_fingerprint=fp, decision="approved")
    with pytest.raises(LookupError):
        composition._deliver(root, FakeOutcome("p_unknown", sid, bid, fp), actor="t", budget_usd=1.0,
                             build_provider="provider_inexistant")


# 5. PASSAGE RÉEL DEPUIS /v1/pursue
def _req(url, *, token=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-BrainAI-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


@pytest.fixture()
def live_server():
    httpd = server.make_server("127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", server.SESSION_TOKEN
    finally:
        httpd.shutdown()


def test_server_forwards_build_provider_opaque(live_server, monkeypatch):
    base, token = live_server
    captured = {}

    def _stub(pursuit_ref, *, mode="demo", build_provider=None):
        captured["pursuit_ref"] = pursuit_ref
        captured["build_provider"] = build_provider
        return {"conversation": {}, "pursuit": {}, "steps": [], "deliverables": []}

    monkeypatch.setattr(server, "realize", _stub)
    code, _ = _req(base + "/v1/pursue", token=token,
                   body={"kind": "realize", "pursuit_ref": "p1", "build_provider": " deterministic_local "})
    assert code == 200
    assert captured["build_provider"] == " deterministic_local "


def test_server_build_provider_type_strict_and_absent(live_server, monkeypatch):
    base, token = live_server
    captured = {}

    def _stub(pursuit_ref, *, mode="demo", build_provider=None):
        captured["bp"] = build_provider
        return {"conversation": {}, "pursuit": {}, "steps": [], "deliverables": []}

    monkeypatch.setattr(server, "realize", _stub)
    code, _ = _req(base + "/v1/pursue", token=token,
                   body={"kind": "realize", "pursuit_ref": "p1", "build_provider": 123})
    assert code == 400
    code, _ = _req(base + "/v1/pursue", token=token, body={"kind": "realize", "pursuit_ref": "p1"})
    assert code == 200 and captured["bp"] is None


def test_server_unknown_build_provider_is_400(live_server, monkeypatch):
    base, token = live_server

    def _raise(pursuit_ref, *, mode="demo", build_provider=None):
        raise LookupError(f"BuildProvider inconnu : {build_provider!r}")

    monkeypatch.setattr(server, "realize", _raise)
    code, body = _req(base + "/v1/pursue", token=token,
                      body={"kind": "realize", "pursuit_ref": "p1", "build_provider": "inconnu"})
    assert code == 400 and "inconnu" in body["error"]
