"""TEST-RUN-SEAM-MIN — contrat rouge du seam ``test.run``.

Ce banc est local, déterministe et sans fournisseur facturable. Il fixe le comportement attendu avant
l'implémentation : ``build → test → verify → delivered``, arrêt fail-closed, faits append-only sûrs et
résolution provider-neutral sans fallback.
"""

from __future__ import annotations

import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from brainai_app import providers
from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.delivered import DeliveredStore
from brainai_app.delivery.runner import BuildRunStore
from brainai_app.delivery.service import run_delivery
from brainai_app.delivery.serving import WorkspacePreview
from brainai_app.delivery.verify import VerificationStore
from scc_brainai_bootstrap.builder.diagnostics import DIAG_MAX
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.local_test import LocalDeterministicTestAdapter
from scc_brainai_bootstrap.builder.site import SITE_ENTRYPOINT
from scc_brainai_bootstrap.builder.testing import TestResultStore, produce_test_run
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.workspace import Workspace


_SPEC = {"specification_id": "spec_test_run", "status": "proposed", "specification": {
    "product_objective": "Page de test du pipeline de livraison",
    "users_and_roles": ["Visiteur"], "functional_scope": ["Présentation"],
    "features": ["Accueil"], "entities_and_data": ["Page"], "key_journeys": ["Consulter"],
    "constraints": ["Statique"], "acceptance_criteria": ["HTML valide"],
    "assumptions": ["Local"], "open_questions": [], "out_of_scope": ["Réseau externe"]}}

_HTML = "<!doctype html><html><head><title>Test</title></head><body><h1>OK</h1></body></html>"


class FakeSite:
    capability = "build"
    name = "fake_build"
    model = "fake"
    max_budget_usd = 0.0

    def __init__(self) -> None:
        self.calls = 0

    def build(self, spec, *, cwd, budget_remaining_usd):
        self.calls += 1
        (Path(cwd) / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
        return {"called": True,
                "envelope": {"type": "result", "subtype": "success", "is_error": False},
                "exit_code": 0, "timed_out": False, "prompt": "fake build",
                "argv": ["fake-build"], "stdout": "", "stderr": ""}


class FakeTestRun:
    capability = "test.run"
    name = "fake_test"

    def __init__(self, *, verdict="passed", stdout="test passed", stderr="") -> None:
        self.verdict = verdict
        self.stdout = stdout
        self.stderr = stderr
        self.calls = 0

    def run(self, *, cwd, artifact_ref):
        self.calls += 1
        timed_out = self.verdict == "timeout"
        exit_code = 0 if self.verdict == "passed" else (None if timed_out else 1)
        return {"called": True, "argv": ["fake-test"], "exit_code": exit_code,
                "timed_out": timed_out, "stdout": self.stdout, "stderr": self.stderr}


class FakePreview:
    capability = "preview.local"
    name = "fake_preview"

    def __init__(self) -> None:
        self.opened = 0

    def open(self, workspace, *, entrypoint=SITE_ENTRYPOINT):
        self.opened += 1
        return WorkspacePreview(workspace, entrypoint=entrypoint).start()


class RaisingTestRun(FakeTestRun):
    def run(self, *, cwd, artifact_ref):
        self.calls += 1
        raise RuntimeError("token=NE-DOIT-PAS-FUITER")


class WrongCapabilityTestRun(FakeTestRun):
    capability = "test.other"


def _clock():
    current = datetime(2026, 10, 23, tzinfo=timezone.utc)

    def tick():
        nonlocal current
        value = current.isoformat()
        current += timedelta(seconds=1)
        return value

    return tick


def _workspace(tmp_path):
    workspace = Workspace(tmp_path / "exec", "site")
    workspace.ensure()
    return workspace


def _stores(tmp_path):
    return {
        "build_store": BuildStore(tmp_path / "build.jsonl"),
        "tool_store": ToolInvocationStore(tmp_path / "tool.jsonl"),
        "run_store": BuildRunStore(tmp_path / "run.jsonl"),
        "verification_store": VerificationStore(tmp_path / "verification.jsonl"),
        "test_result_store": TestResultStore(tmp_path / "test_result.jsonl"),
        "delivered_store": DeliveredStore(tmp_path / "delivered.jsonl"),
    }


def _run(tmp_path, *, test_run, site=None, preview=None, pursuit_ref="p_test"):
    stores = _stores(tmp_path)
    report = run_delivery(
        spec_source=_SPEC, workspace=_workspace(tmp_path), project_id="site", pursuit_ref=pursuit_ref,
        site_build=site or FakeSite(), test_run=test_run, preview=preview or FakePreview(),
        budget=BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0, max_calls=2),
        clock=_clock(), **stores)
    return report, stores


def test_delivery_dag_runs_build_test_verify_in_order(tmp_path):
    test_run = FakeTestRun()
    preview = FakePreview()
    report, stores = _run(tmp_path, test_run=test_run, preview=preview)

    assert report["status"] == "delivered"
    assert [(step["step"], step["status"]) for step in report["run"]["steps"]] == [
        ("build", "succeeded"), ("test", "succeeded"), ("verify", "succeeded")]
    assert test_run.calls == 1 and preview.opened == 1
    assert report["test_result"]["artifact_sha256"] == report["build"]["artefact"]["sha256"]
    test_verifications = [v for v in stores["verification_store"].read_all() if v["kind"] == "test"]
    assert len(test_verifications) == 1
    assert test_verifications[0]["sha256"] == report["build"]["artefact"]["sha256"]
    assert report["verification"]["kind"] == "http"
    charges = [f for f in BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0,
                                       max_calls=2).read_all()
               if f["fact_type"] == "budget_charge"]
    assert [f["label"] for f in charges] == ["build", "test"]
    assert charges[-1]["cost_kind"] == "unavailable" and charges[-1]["cost_value"] is None


@pytest.mark.parametrize("verdict", ["failed", "timeout"])
def test_failed_tests_stop_before_preview_verify_and_delivered(tmp_path, verdict):
    test_run = FakeTestRun(verdict=verdict)
    preview = FakePreview()
    report, stores = _run(tmp_path, test_run=test_run, preview=preview)

    assert report["status"] == "failed"
    assert [(step["step"], step["status"]) for step in report["run"]["steps"]] == [
        ("build", "succeeded"), ("test", "failed")]
    assert test_run.calls == 1
    assert preview.opened == 0
    assert stores["delivered_store"].read_all() == []
    assert not [v for v in stores["verification_store"].read_all() if v["kind"] == "http"]


def test_test_result_is_append_only_bounded_redacted_and_in_provenance(tmp_path):
    secret = "TOPSECRET-DO-NOT-LEAK"
    test_run = FakeTestRun(stdout=f"token={secret} " + ("x" * (DIAG_MAX + 200)),
                           stderr="Authorization: Bearer abcdefghijklmnopqrstuvwxyz")
    report, stores = _run(tmp_path, test_run=test_run)

    facts = stores["test_result_store"].read_all()
    assert len(facts) == 1
    fact = facts[0]
    assert fact["fact_type"] == "test_result" and fact["status"] == "passed"
    assert fact["artifact_sha256"] == report["build"]["artefact"]["sha256"]
    assert fact["cost"] == {"value": None, "kind": "unavailable"}
    assert secret not in fact["diagnostic"]["stdout"]
    assert "abcdefghijklmnopqrstuvwxyz" not in fact["diagnostic"]["stderr"]
    assert len(fact["diagnostic"]["stdout"]) <= DIAG_MAX
    assert len(fact["diagnostic"]["stderr"]) <= DIAG_MAX

    tool_facts = [f for f in stores["tool_store"].read_all() if f["tool"] == "fake_test"]
    assert len(tool_facts) == 1 and tool_facts[0]["invocation_id"] == fact["tool_ref"]
    assert secret not in tool_facts[0]["stdout"]
    assert "abcdefghijklmnopqrstuvwxyz" not in tool_facts[0]["stderr"]
    assert len(tool_facts[0]["stdout"]) <= DIAG_MAX and len(tool_facts[0]["stderr"]) <= DIAG_MAX
    assert report["provenance"]["test_result_id"] == fact["test_result_id"]
    assert report["provenance"]["test_tool_ref"] == tool_facts[0]["invocation_id"]
    assert report["provenance"]["test_verification_id"]
    delivered = stores["delivered_store"].read_all()[0]
    assert delivered["test_result_ref"] == fact["test_result_id"]
    assert delivered["test_verification_ref"] == report["provenance"]["test_verification_id"]


def test_test_capability_unknown_or_absent_fails_closed_before_execution(tmp_path):
    assert providers.resolve_test_run().name == "deterministic_local_test"
    with pytest.raises(LookupError):
        providers.resolve_test_run("provider_inconnu")
    with pytest.raises(LookupError):
        providers.resolve_test_run(" deterministic_local_test ")
    with pytest.raises(LookupError):
        providers.real_delivery(test_provider="")
    with pytest.raises(LookupError):
        providers.real_delivery(build_provider="")

    site = FakeSite()
    stores = _stores(tmp_path)
    kwargs = dict(spec_source=_SPEC, workspace=_workspace(tmp_path), project_id="site", pursuit_ref="p_absent",
                  site_build=site, preview=FakePreview(),
                  budget=BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0, max_calls=2),
                  clock=_clock(), **stores)
    kwargs.pop("test_result_store")
    assert inspect.signature(run_delivery).parameters["test_run"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        run_delivery(**kwargs)
    assert site.calls == 0
    assert stores["build_store"].read_all() == []
    assert stores["tool_store"].read_all() == []


@pytest.mark.parametrize("bad_test_run", [None, WrongCapabilityTestRun()])
def test_invalid_test_capability_is_rejected_before_workspace_or_build(tmp_path, bad_test_run):
    workspace = Workspace(tmp_path / "never-created", "site")
    site = FakeSite()
    stores = _stores(tmp_path)
    with pytest.raises(TypeError):
        run_delivery(
            spec_source=_SPEC, workspace=workspace, project_id="site", pursuit_ref="p_bad_cap",
            site_build=site, test_run=bad_test_run, preview=FakePreview(),
            budget=BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0, max_calls=2),
            clock=_clock(), **stores)
    assert not workspace.path.exists()
    assert site.calls == 0 and stores["build_store"].read_all() == []


def test_missing_test_result_store_is_rejected_before_workspace_or_build(tmp_path):
    workspace = Workspace(tmp_path / "never-created", "site")
    site = FakeSite()
    stores = _stores(tmp_path)
    stores["test_result_store"] = None
    with pytest.raises(TypeError):
        run_delivery(
            spec_source=_SPEC, workspace=workspace, project_id="site", pursuit_ref="p_no_store",
            site_build=site, test_run=FakeTestRun(), preview=FakePreview(),
            budget=BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0, max_calls=2),
            clock=_clock(), **stores)
    assert not workspace.path.exists()
    assert site.calls == 0 and stores["build_store"].read_all() == []


def test_real_local_test_adapter_runs_once_with_complete_contract(tmp_path):
    workspace = _workspace(tmp_path)
    target = workspace.path / SITE_ENTRYPOINT
    target.write_text(_HTML, encoding="utf-8")
    sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    adapter = LocalDeterministicTestAdapter(timeout=5)
    result = produce_test_run(
        adapter=adapter, artifact_ref={"relative_path": SITE_ENTRYPOINT, "sha256": sha256},
        store=TestResultStore(tmp_path / "result.jsonl"),
        tool_store=ToolInvocationStore(tmp_path / "tool.jsonl"), workspace=workspace,
        project_id="site", clock=_clock())

    assert result["status"] == "passed" and result["artifact_sha256"] == sha256
    tools = ToolInvocationStore(tmp_path / "tool.jsonl").read_all()
    assert len(tools) == 1 and tools[0]["status"] == "succeeded"
    assert tools[0]["argv"][-1] == sha256
    assert "[REDACTED-HEX]" not in tools[0]["argv"]
    contract = adapter.contract().to_dict()
    assert contract["cost_report"] == {"mode": "unavailable", "fabricated": False}
    assert contract["confinement"]["network"] == {"required": False, "isolation": "not_proven"}


def test_real_local_test_adapter_rejects_invalid_html(tmp_path):
    workspace = _workspace(tmp_path)
    target = workspace.path / SITE_ENTRYPOINT
    target.write_text("<html><body>incomplet</body></html>", encoding="utf-8")
    sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    store = TestResultStore(tmp_path / "result.jsonl")
    tools = ToolInvocationStore(tmp_path / "tool.jsonl")

    result = produce_test_run(
        adapter=LocalDeterministicTestAdapter(timeout=5),
        artifact_ref={"relative_path": SITE_ENTRYPOINT, "sha256": sha256},
        store=store, tool_store=tools, workspace=workspace, project_id="site", clock=_clock())
    assert result["status"] == "failed" and result["attempted"] is True
    assert result["exit_code"] == 11 and result["tool_ref"]
    assert tools.read_all()[0]["status"] == "failed"


@pytest.mark.parametrize("payload", [
    {"called": True, "argv": [], "exit_code": "zero", "timed_out": "no"},
    {"called": True, "argv": ["fake-test"], "exit_code": False, "timed_out": False},
])
def test_malformed_adapter_result_fails_without_fabricated_tool_invocation(tmp_path, payload):
    class MalformedTestRun(FakeTestRun):
        def run(self, *, cwd, artifact_ref):
            self.calls += 1
            return dict(payload)

    adapter = MalformedTestRun()
    report, stores = _run(tmp_path, test_run=adapter)
    assert report["status"] == "failed" and report["run"]["status"] == "failed"
    assert adapter.calls == 1
    result = stores["test_result_store"].read_all()[0]
    assert result["status"] == "failed" and result["tool_ref"] is None
    assert result["attempted"] is True
    assert [fact for fact in stores["tool_store"].read_all() if fact["tool"] == "fake_test"] == []


def test_adapter_refusal_records_failure_without_tool_or_budget_charge(tmp_path):
    class RefusingTestRun(FakeTestRun):
        def run(self, *, cwd, artifact_ref):
            self.calls += 1
            return {"called": False, "refused": "local policy"}

    adapter = RefusingTestRun()
    report, stores = _run(tmp_path, test_run=adapter)
    assert report["status"] == "failed" and adapter.calls == 1
    result = stores["test_result_store"].read_all()[0]
    assert result["status"] == "failed" and result["attempted"] is False
    assert result["tool_ref"] is None
    charges = [fact for fact in BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0,
                                              max_calls=2).read_all()
               if fact["fact_type"] == "budget_charge"]
    assert [fact["label"] for fact in charges] == ["build"]


def test_pre_hash_mismatch_and_escape_are_refused_before_adapter_call(tmp_path):
    workspace = _workspace(tmp_path)
    target = workspace.path / SITE_ENTRYPOINT
    target.write_text(_HTML, encoding="utf-8")
    adapter = FakeTestRun()
    store = TestResultStore(tmp_path / "result.jsonl")
    tools = ToolInvocationStore(tmp_path / "tool.jsonl")

    result = produce_test_run(
        adapter=adapter, artifact_ref={"relative_path": SITE_ENTRYPOINT, "sha256": "0" * 64},
        store=store, tool_store=tools, workspace=workspace, project_id="site", clock=_clock())
    assert result["status"] == "failed" and result["tool_ref"] is None
    assert adapter.calls == 0 and tools.read_all() == []

    escaped = produce_test_run(
        adapter=adapter, artifact_ref={"relative_path": "../escape.html", "sha256": "0" * 64},
        store=store, tool_store=tools, workspace=workspace, project_id="site", clock=_clock())
    assert escaped["status"] == "failed" and escaped["attempted"] is False
    assert adapter.calls == 0 and tools.read_all() == []
    assert len(store.read_all()) == 2


def test_artifact_mutation_makes_test_fail_and_stops_preview(tmp_path):
    class MutatingTestRun(FakeTestRun):
        def run(self, *, cwd, artifact_ref):
            self.calls += 1
            (Path(cwd) / artifact_ref["relative_path"]).write_text("mutated", encoding="utf-8")
            return {"called": True, "argv": ["fake-test"], "exit_code": 0,
                    "timed_out": False, "stdout": "raw tool success", "stderr": ""}

    preview = FakePreview()
    report, stores = _run(tmp_path, test_run=MutatingTestRun(), preview=preview)
    assert report["status"] == "failed" and preview.opened == 0
    assert report["test_result"]["status"] == "failed"
    assert report["test_verification"]["verdict"] == "failed"
    # Couche brute honnête : le processus a réussi ; la vérification de l'artefact, elle, a échoué.
    assert stores["tool_store"].read_all()[-1]["status"] == "succeeded"
    assert stores["delivered_store"].read_all() == []


def test_adapter_exception_becomes_terminal_failed_fact_without_secret_or_preview(tmp_path):
    adapter = RaisingTestRun()
    preview = FakePreview()
    report, stores = _run(tmp_path, test_run=adapter, preview=preview)

    assert report["status"] == "failed" and report["run"]["status"] == "failed"
    assert [(step["step"], step["status"]) for step in report["run"]["steps"]] == [
        ("build", "succeeded"), ("test", "failed")]
    assert adapter.calls == 1 and preview.opened == 0
    result = stores["test_result_store"].read_all()[0]
    assert result["status"] == "failed" and result["attempted"] is True
    assert result["tool_ref"] is None
    assert "NE-DOIT-PAS-FUITER" not in result["diagnostic"]["stderr"]
    assert stores["delivered_store"].read_all() == []


def test_test_result_store_really_appends_two_distinct_facts(tmp_path):
    workspace = _workspace(tmp_path)
    target = workspace.path / SITE_ENTRYPOINT
    target.write_text(_HTML, encoding="utf-8")
    sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    store = TestResultStore(tmp_path / "result.jsonl")
    tools = ToolInvocationStore(tmp_path / "tool.jsonl")
    adapter = FakeTestRun()
    clock = _clock()

    for _ in range(2):
        result = produce_test_run(
            adapter=adapter, artifact_ref={"relative_path": SITE_ENTRYPOINT, "sha256": sha256},
            store=store, tool_store=tools, workspace=workspace, project_id="site", clock=clock)
        assert result["status"] == "passed"
    facts = store.read_all()
    assert len(facts) == 2 and facts[0]["test_result_id"] != facts[1]["test_result_id"]
    assert adapter.calls == 2 and len(tools.read_all()) == 2


def test_hard_budget_cap_stops_before_test_without_fabricated_charge(tmp_path):
    stores = _stores(tmp_path)
    test_run = FakeTestRun()
    preview = FakePreview()
    report = run_delivery(
        spec_source=_SPEC, workspace=_workspace(tmp_path), project_id="site", pursuit_ref="p_cap",
        site_build=FakeSite(), test_run=test_run, preview=preview,
        budget=BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0, max_calls=1),
        clock=_clock(), **stores)

    assert report["status"] == "budget_exhausted"
    assert test_run.calls == 0 and preview.opened == 0
    assert stores["test_result_store"].read_all() == []
    budget_facts = BudgetLedger(tmp_path / "budget.jsonl", ceiling_usd=1.0, max_calls=1).read_all()
    charges = [fact for fact in budget_facts if fact["fact_type"] == "budget_charge"]
    assert [fact["label"] for fact in charges] == ["build"]
    assert any(fact["fact_type"] == "budget_exhausted" for fact in budget_facts)


def test_failed_build_never_calls_test_run(tmp_path):
    class FailingSite(FakeSite):
        def build(self, spec, *, cwd, budget_remaining_usd):
            self.calls += 1
            return {"called": True,
                    "envelope": {"type": "result", "subtype": "error", "is_error": True},
                    "exit_code": 1, "timed_out": False, "prompt": "fake build",
                    "argv": ["fake-build"], "stdout": "", "stderr": "build failed"}

    test_run = FakeTestRun()
    preview = FakePreview()
    report, stores = _run(tmp_path, test_run=test_run, site=FailingSite(), preview=preview)
    assert report["status"] == "failed"
    assert test_run.calls == 0 and preview.opened == 0
    assert stores["test_result_store"].read_all() == []
