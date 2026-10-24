"""Propositions correctives : preuves persistées, inertes, sans exécution."""
import hashlib
import json

import pytest

from brainai_app.delivery.corrections import CorrectionError, propose_correction
from scc_brainai_bootstrap.builder.workspace import Workspace


def fixture_state(tmp_path):
    workspace = Workspace(tmp_path / 'delivery_exec', 'site')
    workspace.ensure()
    data = b'<html>invalid product</html>'
    (workspace.path / 'index.html').write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    journals = {
        'run_events.jsonl': [
            {'fact_type': 'build_run', 'run_id': 'run_1', 'pursuit_ref': 'p1', 'status': 'prepared'},
            {'fact_type': 'build_run', 'run_id': 'run_1', 'pursuit_ref': 'p1', 'status': 'running'},
            {'fact_type': 'build_step', 'run_ref': 'run_1', 'step': 'build', 'status': 'succeeded',
             'refs': {'build_id': 'build_1'}},
            {'fact_type': 'build_step', 'run_ref': 'run_1', 'step': 'test', 'status': 'failed',
             'refs': {'test_result_id': 'test_1'}},
            {'fact_type': 'build_run', 'run_id': 'run_1', 'pursuit_ref': 'p1', 'status': 'failed'}],
        'site_build.jsonl': [{'build_id': 'build_1', 'spec_ref': 'spec_1', 'status': 'proposed',
            'artefact': {'relative_path': 'index.html', 'sha256': sha}}],
        'test_results.jsonl': [{'fact_type': 'test_result', 'test_result_id': 'test_1',
            'capability': 'test.run', 'artifact_ref': 'index.html', 'artifact_sha256': sha,
            'status': 'failed', 'timed_out': False, 'exit_code': 11,
            'diagnostic': {'stdout': '', 'stderr': 'token=EXAMPLE_SECRET'}, 'tool_ref': None}],
    }
    for name, facts in journals.items():
        (tmp_path / name).write_text(''.join(json.dumps(f) + '\n' for f in facts))
    return workspace, journals


def propose(root, **overrides):
    args = dict(root=root, pursuit_ref='p1', parent_run_ref='run_1', test_result_ref='test_1',
                suggestion='Corriger la structure HTML', clock=lambda: '2026-10-24T10:00:00Z')
    args.update(overrides)
    return propose_correction(**args)


def test_proposal_is_inert_bounded_redacted_and_traceable(tmp_path):
    workspace, _ = fixture_state(tmp_path)
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = propose(tmp_path, suggestion='token=SUGGESTION_SECRET ' + 'x' * 5000)
    assert result['status'] == 'proposed'
    assert result['parent_run_ref'] == 'run_1'
    assert result['source_spec_ref'] == 'spec_1'
    assert result['test_result_ref'] == 'test_1'
    assert result['execution_authorized'] is False
    assert result['cause_status'] == 'not_established'
    assert len(result['suggestion']) <= 1200
    assert 'EXAMPLE_SECRET' not in json.dumps(result)
    assert 'SUGGESTION_SECRET' not in json.dumps(result)
    assert all((tmp_path / path).read_bytes() == content for path, content in before.items())
    assert (workspace.path / 'index.html').exists()
    created = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*') if p.is_file()} - before.keys()
    assert created == {'correction_proposals.jsonl'}


@pytest.mark.parametrize('override', [dict(pursuit_ref='other'), dict(parent_run_ref='other'),
                                     dict(test_result_ref='other'), dict(suggestion=''),
                                     dict(suggestion=None)])
def test_bad_request_refused_without_writes(tmp_path, override):
    fixture_state(tmp_path)
    with pytest.raises(CorrectionError):
        propose(tmp_path, **override)
    assert not (tmp_path / 'correction_proposals.jsonl').exists()


@pytest.mark.parametrize('mode', ['running', 'passed', 'duplicate', 'foreign', 'unlinked',
                                 'corrupt', 'nonobject', 'mutated', 'escape', 'symlink'])
def test_invalid_or_ambiguous_evidence_refused(tmp_path, mode):
    workspace, journals = fixture_state(tmp_path)
    if mode == 'running':
        journals['run_events.jsonl'][-1]['status'] = 'running'
    elif mode == 'passed':
        journals['test_results.jsonl'][0]['status'] = 'passed'
    elif mode == 'duplicate':
        journals['test_results.jsonl'] *= 2
    elif mode == 'foreign':
        journals['run_events.jsonl'][0]['pursuit_ref'] = 'other'
    elif mode == 'unlinked':
        journals['run_events.jsonl'][3]['refs']['test_result_id'] = 'other'
    elif mode == 'mutated':
        (workspace.path / 'index.html').write_text('changed')
    elif mode == 'escape':
        journals['test_results.jsonl'][0]['artifact_ref'] = '../escape'
    elif mode == 'symlink':
        (workspace.path / 'index.html').unlink()
        (workspace.path / 'index.html').symlink_to(tmp_path / 'test_results.jsonl')
    for name, facts in journals.items():
        (tmp_path / name).write_text(''.join(json.dumps(f) + '\n' for f in facts))
    if mode in ('corrupt', 'nonobject'):
        with (tmp_path / 'run_events.jsonl').open('a') as handle:
            handle.write('{bad\n' if mode == 'corrupt' else '[]\n')
    with pytest.raises(CorrectionError):
        propose(tmp_path)
    assert not (tmp_path / 'correction_proposals.jsonl').exists()


def test_existing_proposals_are_preserved(tmp_path):
    fixture_state(tmp_path)
    first = propose(tmp_path)
    path = tmp_path / 'correction_proposals.jsonl'
    original = path.read_bytes()
    second = propose(tmp_path, suggestion='Autre proposition')
    assert path.read_bytes().startswith(original)
    assert second['correction_id'] != first['correction_id']
    assert len(path.read_text().splitlines()) == 2


def test_composition_refuses_missing_session_without_creating_it(tmp_path, monkeypatch):
    from brainai_app import composition
    monkeypatch.setenv('BRAINAI_STATE_ROOT', str(tmp_path))
    for pursuit in ('p_missing_correction', '../outside'):
        reply = composition.propose_delivery_correction(
            pursuit, parent_run_ref='run_1', test_result_ref='test_1', suggestion='Fix')
        assert reply['status'] == 'refused'
    assert list(tmp_path.iterdir()) == []


def test_composition_wires_existing_session_without_loading_providers(tmp_path, monkeypatch):
    from brainai_app import composition, providers
    monkeypatch.setenv('BRAINAI_STATE_ROOT', str(tmp_path))
    root = tmp_path / 'pursuits' / 'p1'
    root.mkdir(parents=True)
    fixture_state(root)

    def forbidden(*args, **kwargs):
        pytest.fail('proposition must not resolve an execution provider')

    monkeypatch.setattr(providers, 'real_delivery', forbidden)
    reply = composition.propose_delivery_correction(
        'p1', parent_run_ref='run_1', test_result_ref='test_1', suggestion='Fix structure')
    assert reply['status'] == 'proposed'
    assert reply['execution_authorized'] is False
    assert not (root / 'build_authorizations.jsonl').exists()


def test_proposal_from_real_delivery_failure(tmp_path):
    from brainai_app.delivery.budget import BudgetLedger
    from brainai_app.delivery.delivered import DeliveredStore
    from brainai_app.delivery.runner import BuildRunStore
    from brainai_app.delivery.service import run_delivery
    from brainai_app.delivery.verify import VerificationStore
    from scc_brainai_bootstrap.builder.builds import BuildStore
    from scc_brainai_bootstrap.builder.testing import TestResultStore
    from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
    from test_build_runtime_test_run_seam import FakeSite, FakeTestRun, FakePreview, _SPEC, _clock

    workspace = Workspace(tmp_path / 'delivery_exec', 'site')
    preview = FakePreview()
    test = FakeTestRun(verdict='failed')
    report = run_delivery(
        spec_source=_SPEC, workspace=workspace, project_id='site', pursuit_ref='p1',
        site_build=FakeSite(), test_run=test, preview=preview,
        budget=BudgetLedger(tmp_path / 'budget.jsonl', ceiling_usd=1.0, max_calls=2),
        build_store=BuildStore(tmp_path / 'site_build.jsonl'),
        tool_store=ToolInvocationStore(tmp_path / 'tinv.jsonl'),
        run_store=BuildRunStore(tmp_path / 'run_events.jsonl'),
        verification_store=VerificationStore(tmp_path / 'verifications.jsonl'),
        test_result_store=TestResultStore(tmp_path / 'test_results.jsonl'),
        delivered_store=DeliveredStore(tmp_path / 'delivered.jsonl'), clock=_clock())
    assert report['status'] == 'failed'
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = propose(tmp_path, parent_run_ref=report['provenance']['run_id'],
                     test_result_ref=report['test_result']['test_result_id'])
    assert result['source_build_ref'] == report['build']['build_id']
    assert result['artifact_sha256'] == report['test_result']['artifact_sha256']
    assert all(p.read_bytes() == content for p, content in before.items())
    assert test.calls == 1 and preview.opened == 0
