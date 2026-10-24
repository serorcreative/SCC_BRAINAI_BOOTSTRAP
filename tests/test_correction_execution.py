"""Correction gouvernée : même livraison, nouveau workspace, accord consommé."""
import json
from types import SimpleNamespace

import pytest

from brainai_app import composition, providers
from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.corrections import CorrectionError, correction_attempt
from brainai_app.delivery.delivered import DeliveredStore
from brainai_app.delivery.runner import BuildRunStore
from brainai_app.delivery.service import run_delivery
from brainai_app.delivery.verify import VerificationStore
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.testing import TestResultStore
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.workspace import Workspace
from test_build_runtime_test_run_seam import FakeSite, FakeTestRun, FakePreview, _SPEC, _clock
from test_l8_cost_gate import l8_env, FakeOutcome
from scc_brainai_bootstrap.builder.local_test import LocalDeterministicTestAdapter


class InvalidSite(FakeSite):
    def build(self, spec, *, cwd, budget_remaining_usd):
        raw = super().build(spec, cwd=cwd, budget_remaining_usd=budget_remaining_usd)
        (cwd / 'index.html').write_text('<html><body>sans titre</body></html>')
        return raw


@pytest.fixture
def prepared(l8_env, monkeypatch):
    root, sid, bid, spec, fp = l8_env('p_corr')
    monkeypatch.setenv('BRAINAI_DELIVERY_MAX_CALLS', '4')
    stores = dict(build_store=BuildStore(root / 'site_build.jsonl'),
                  tool_store=ToolInvocationStore(root / 'tinv.jsonl'),
                  run_store=BuildRunStore(root / 'run_events.jsonl'),
                  verification_store=VerificationStore(root / 'verifications.jsonl'),
                  test_result_store=TestResultStore(root / 'test_results.jsonl'),
                  delivered_store=DeliveredStore(root / 'delivered.jsonl'))
    failed = run_delivery(
        spec_source=_SPEC, workspace=Workspace(root / 'delivery_exec', 'site'),
        project_id='site', pursuit_ref='p_corr', site_build=InvalidSite(),
        test_run=LocalDeterministicTestAdapter(timeout=5), preview=FakePreview(),
        budget=BudgetLedger(root / 'budget.jsonl', ceiling_usd=1.0, max_calls=4),
        clock=_clock(), **stores)
    proposal = composition.propose_delivery_correction(
        'p_corr', parent_run_ref=failed['provenance']['run_id'],
        test_result_ref=failed['test_result']['test_result_id'], suggestion='Corriger la structure')
    assert proposal['status'] == 'proposed'
    correction = proposal['correction']['correction_id']
    outcome = FakeOutcome('p_corr', sid, bid, fp)
    auth_args = dict(correction_ref=correction, presented_spec_ref=sid,
                     presented_gate_fingerprint=fp, budget_usd=1.0)
    composition.authorize('p_corr', presented_spec_ref=sid, presented_gate_fingerprint=fp,
                          decision='approved')
    builder, test, preview = FakeSite(), FakeTestRun(), FakePreview()
    monkeypatch.setattr(providers, 'real_delivery',
                        lambda **kwargs: SimpleNamespace(site_build=builder, test_run=test, preview=preview))
    return SimpleNamespace(root=root, correction=correction, spec=spec, fp=fp, outcome=outcome,
                           auth_args=auth_args, builder=builder, test=test, preview=preview,
                           failed=failed, stores=stores)


def approve(p, decision='approved'):
    return composition.authorize_delivery_correction('p_corr', decision=decision, **p.auth_args)


def execute(p):
    return composition._deliver(p.root, p.outcome, actor='tester', budget_usd=1.0,
                                correction_ref=p.correction)


def test_correction_success_new_run_retests_preserves_source_and_cumulative_budget(prepared):
    p = prepared
    source = p.root / 'delivery_exec' / 'workspaces' / 'site' / 'index.html'
    original = source.read_bytes()
    past = {store.path: store.path.read_bytes() for store in p.stores.values() if store.path.exists()}
    assert approve(p)['status'] == 'recorded'
    assert p.builder.calls == p.test.calls == p.preview.opened == 0
    report = execute(p)
    assert report['status'] == 'delivered'
    assert p.builder.calls == p.test.calls == p.preview.opened == 1
    assert source.read_bytes() == original
    assert all(path.read_bytes().startswith(data) for path, data in past.items())
    assert report['provenance']['parent_run_ref'] == p.failed['provenance']['run_id']
    assert report['provenance']['correction_id'] == p.correction
    assert report['delivered']['correction_ref'] == p.correction
    assert report['delivered']['workspace_ref'] == report['provenance']['workspace_ref']
    assert (p.root / report['delivered']['workspace_ref'] / 'index.html').exists()
    assert report['provenance']['run_id'] != p.failed['provenance']['run_id']
    assert report['test_result']['test_result_id'] != p.failed['test_result']['test_result_id']
    assert (p.root / 'correction_exec' / p.correction / 'workspaces' / 'site' / 'index.html').is_file()
    assert BudgetLedger(p.root / 'budget.jsonl', ceiling_usd=1, max_calls=4).calls_made() == 4
    assert execute(p)['status'] == 'refused'
    assert p.builder.calls == 1
    assert approve(p)['status'] == 'refused'


@pytest.mark.parametrize('mode', ['missing', 'declined', 'revoked', 'stale_gate', 'changed_budget',
                                 'changed_artifact', 'corrupt_ledger', 'same_spec'])
def test_correction_refusals_never_execute(prepared, monkeypatch, mode):
    p = prepared
    if mode not in ('missing', 'declined', 'same_spec'):
        assert approve(p)['status'] == 'recorded'
    if mode == 'declined':
        assert approve(p, 'declined')['status'] == 'recorded'
    elif mode == 'revoked':
        assert approve(p, 'declined')['status'] == 'recorded'
    elif mode == 'stale_gate':
        p.outcome.proposal['cost_gate']['gate_fingerprint'] = 'fp_stale'
    elif mode == 'changed_budget':
        monkeypatch.setenv('BRAINAI_DELIVERY_MAX_CALLS', '5')
    elif mode == 'changed_artifact':
        (p.root / 'delivery_exec/workspaces/site/index.html').write_text('mutated')
    elif mode == 'corrupt_ledger':
        with (p.root / 'budget.jsonl').open('a') as f:
            f.write('{broken\n')
    elif mode == 'same_spec':
        from scc_brainai_bootstrap.core.clock import digest
        path = p.root / 'site_build.jsonl'
        source = json.loads(path.read_text())
        source['spec_sha256'] = digest(p.spec['specification'])
        path.write_text(json.dumps(source) + '\n')
        assert approve(p)['status'] == 'refused'
    assert execute(p)['status'] == 'refused'
    assert p.builder.calls == p.test.calls == p.preview.opened == 0


@pytest.mark.parametrize('verdict', ['failed', 'timeout'])
def test_corrective_test_failure_is_terminal_without_retry(prepared, verdict):
    p = prepared
    p.test.verdict = verdict
    assert approve(p)['status'] == 'recorded'
    report = execute(p)
    assert report['status'] == 'failed'
    assert p.builder.calls == p.test.calls == 1
    assert p.preview.opened == 0
    assert not p.stores['delivered_store'].read_all()
    assert execute(p)['status'] == 'refused'


def test_exhausted_cumulative_budget_never_restarts(prepared, monkeypatch):
    p = prepared
    monkeypatch.setenv('BRAINAI_DELIVERY_MAX_CALLS', '2')
    assert approve(p)['status'] == 'recorded'
    report = execute(p)
    assert report['status'] == 'budget_exhausted'
    assert p.builder.calls == p.test.calls == 0
    assert BudgetLedger(p.root / 'budget.jsonl', ceiling_usd=1, max_calls=2).calls_made() == 2


def test_claim_survives_interruption_and_blocks_reentry(prepared):
    p = prepared
    assert approve(p)['status'] == 'recorded'
    args = dict(root=p.root, pursuit_ref='p_corr', correction_id=p.correction,
                spec=p.spec, gate_fingerprint=p.fp, ceiling_usd=1.0, max_calls=4)
    with pytest.raises(RuntimeError):
        with correction_attempt(**args):
            raise RuntimeError('simulated stop before tool call')
    with pytest.raises(CorrectionError):
        with correction_attempt(**args):
            pytest.fail('consumed attempt reentered')
    assert p.builder.calls == 0


def test_real_validator_corrects_invalid_html_and_preserves_failure(prepared, monkeypatch):
    p = prepared
    test = LocalDeterministicTestAdapter(timeout=5)
    monkeypatch.setattr(providers, 'real_delivery',
                        lambda **kwargs: SimpleNamespace(site_build=p.builder, test_run=test, preview=p.preview))
    assert p.failed['test_result']['status'] == 'failed'
    assert p.failed['test_result']['exit_code'] == 11
    assert approve(p)['status'] == 'recorded'
    report = composition.execute_delivery_correction('p_corr', **p.auth_args)
    assert report['status'] == 'delivered'
    assert report['test_result']['exit_code'] == 0
    assert report['test_result']['artifact_sha256'] != p.failed['test_result']['artifact_sha256']
    assert report['verification']['verdict'] == 'passed'
    assert (p.root / 'delivery_exec/workspaces/site/index.html').read_text() == '<html><body>sans titre</body></html>'


def test_public_execution_cannot_bypass_correction_approval(prepared):
    p = prepared
    assert composition.execute_delivery_correction('p_corr', **p.auth_args)['status'] == 'refused'
    assert p.builder.calls == 0


def test_simultaneous_submissions_only_execute_once(prepared):
    from concurrent.futures import ThreadPoolExecutor
    p = prepared
    assert approve(p)['status'] == 'recorded'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(p), range(2)))
    assert sorted(r['status'] for r in results) == ['delivered', 'refused']
    assert p.builder.calls == p.test.calls == 1


def test_build_go_revocation_still_blocks_approved_correction(prepared):
    p = prepared
    assert approve(p)['status'] == 'recorded'
    composition.authorize('p_corr', presented_spec_ref=p.spec['specification_id'],
                          presented_gate_fingerprint=p.fp, decision='declined')
    assert execute(p)['status'] == 'refused'
    assert p.builder.calls == p.test.calls == 0
