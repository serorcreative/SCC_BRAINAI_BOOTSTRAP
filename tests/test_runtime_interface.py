"""Parcours HTTP continu ; cognition factice déclarée, exécution locale réelle."""
import json
from dataclasses import replace

import pytest

from brainai_app import composition as C, providers
from test_brainai_app_ui import live_server, _req, _ready_fake_caps
from test_l8_cost_gate import _OPTIONS


@pytest.fixture
def runtime(tmp_path, monkeypatch, live_server):
    monkeypatch.setenv('BRAINAI_STATE_ROOT', str(tmp_path / 'state'))
    monkeypatch.setenv('BRAINAI_DELIVERY_MAX_CALLS', '6')
    C._SESSIONS.clear()
    caps = _ready_fake_caps()
    conversation = caps.conversation
    latest = {'message': ''}
    class Conversation:
        capability = 'conversation'; name = 'test_fake'; model = 'test_fake'
        def propose(self, message, **kwargs):
            latest['message'] = message
            return conversation.propose(message, **kwargs)
    class Specification:
        capability = 'specification'; name = 'test_fake'; model = 'test_fake'
        def propose(self, brief, **kwargs):
            spec = dict(C._DEMO_SPEC)
            spec['product_objective'] = latest['message']
            return {'called': True, 'envelope': C._demo_envelope(spec), 'exit_code':0,
                    'stdout':'', 'stderr':'', 'timed_out':False, 'prompt':'(test)', 'argv':['test']}
    class Architecture:
        capability = 'architect.solution'; name = 'test_fake'; model = 'test_fake'
        def propose(self, spec, **kwargs):
            return {'called': True, 'envelope': C._demo_envelope({'options': _OPTIONS}),
                    'exit_code': 0, 'stdout': '', 'stderr': '', 'timed_out': False,
                    'prompt': '(test)', 'argv': ['test']}
    caps = replace(caps, architecture=Architecture(), conversation=Conversation(), specification=Specification())
    monkeypatch.setattr(C, '_capabilities', lambda *args, **kwargs: caps)
    url, token = live_server
    def post(body, authenticated=True):
        return _req(url + '/v1/pursue', method='POST', token=token if authenticated else None, body=body)
    post.url, post.token = url, token
    return post, caps


def start(post):
    _, env = post(dict(kind='converse', mode='real', message='Une page pour un refuge'))
    ref = env['data']['pursuit']['pursuit_id']
    _, env = post(dict(kind='converse', mode='real', message='Une page statique', pursuit_ref=ref))
    assert env['data']['pursuit']['wait_reason'] == 'confirmation'
    return ref


def flow(post, action, ref=None, **kw):
    body = dict(kind='workflow', action=action, mode='real', **kw)
    if ref: body['pursuit_ref'] = ref
    code, env = post(body)
    assert code == 200, env
    return env['data']


def prepare(post, ref):
    vm = flow(post, 'prepare', ref, budget_usd=2, build_provider='deterministic_local')
    assert vm['workflow']['status'] == 'prepared', vm
    return vm['workflow']


def approve(post, ref, p):
    return flow(post, 'authorize', ref, presentation_ref=p['presentation_ref'], decision='approved')


def test_http_end_to_end_gate_delivery_resume_learning(runtime):
    post, _ = runtime
    refs = []
    for _ in range(2):
        ref = start(post); refs.append(ref)
        p = prepare(post, ref)
        assert not (C._pursuit_dir(ref) / 'site_build.jsonl').exists()
        assert flow(post, 'deliver', ref, presentation_ref=p['presentation_ref'])['status'] == 'refused'
        assert approve(post, ref, p)['status'] == 'recorded'
        report = flow(post, 'deliver', ref, presentation_ref=p['presentation_ref'])
        assert report['status'] == 'delivered', report
        assert report['test_result']['status'] == 'passed'
        assert report['verification']['verdict'] == 'passed'
        assert report['memory_11_id']
        assert flow(post, 'deliver', ref, presentation_ref=p['presentation_ref'])['status'] == 'refused'
        C._SESSIONS.clear()
        resumed = flow(post, 'resume', ref)
        assert resumed['status'] == 'resumed'
        assert resumed['memory']['found'] and not resumed['execution_authorized']
    learning = flow(post, 'learning')
    assert learning['status'] == 'proposed' and not learning['applied']
    assert len(learning['memory_ids']) == 2


def test_changed_dialogue_invalidates_presented_gate(runtime):
    post, _ = runtime
    ref = start(post); p = prepare(post, ref)
    post(dict(kind='converse', mode='real', pursuit_ref=ref, message='Changer le besoin'))
    assert approve(post, ref, p)['status'] == 'refused'
    assert not (C._pursuit_dir(ref) / 'site_build.jsonl').exists()


@pytest.mark.parametrize('body', [[], {'kind': 'workflow', 'action': 'unknown'},
    {'kind': 'workflow', 'action': 'prepare', 'pursuit_ref': '../escape'},
    {'kind': 'workflow', 'action': 'prepare', 'pursuit_ref': 'p', 'budget_usd': True},
    {'kind': 'workflow', 'action': 'learning', 'apply': True}])
def test_invalid_requests_refused(runtime, body):
    post, _ = runtime
    assert post(body)[0] == 400


def test_workflow_requires_token(runtime):
    post, _ = runtime
    assert post({'kind': 'workflow', 'action': 'learning'}, False)[0] == 401


def test_http_failed_test_then_explicit_correction_and_recall(runtime, monkeypatch):
    from pathlib import Path
    from scc_brainai_bootstrap.builder.local_site import LocalDeterministicSiteAdapter
    original = LocalDeterministicSiteAdapter.build
    def controlled_failure(self, spec, *, cwd, budget_remaining_usd):
        raw = original(self, spec, cwd=cwd, budget_remaining_usd=budget_remaining_usd)
        if 'échec' in spec['product_objective']:
            (Path(cwd) / 'index.html').write_text('<html><body>sans titre</body></html>')
        return raw
    monkeypatch.setattr(LocalDeterministicSiteAdapter, 'build', controlled_failure)
    post, _ = runtime
    ref = start(post)
    post(dict(kind='converse', mode='real', pursuit_ref=ref, message='échec contrôlé'))
    p = prepare(post, ref); approve(post, ref, p)
    failed = flow(post, 'deliver', ref, presentation_ref=p['presentation_ref'])
    assert failed['status'] == 'failed' and failed['test_result']['exit_code'] == 11
    assert not (C._pursuit_dir(ref) / 'delivered.jsonl').exists()
    source = C._pursuit_dir(ref) / 'delivery_exec/workspaces/site/index.html'
    before = source.read_bytes()
    proposal = flow(post, 'propose_correction', ref, parent_run_ref=failed['provenance']['run_id'],
                    test_result_ref=failed['test_result']['test_result_id'], suggestion='Ajouter un titre')
    correction = proposal['correction']['correction_id']
    post(dict(kind='converse', mode='real', pursuit_ref=ref, message='Page corrigée avec titre'))
    p = prepare(post, ref); approve(post, ref, p)
    args = dict(presentation_ref=p['presentation_ref'], correction_ref=correction)
    assert flow(post, 'execute_correction', ref, **args)['status'] == 'refused'
    assert flow(post, 'authorize_correction', ref, decision='approved', **args)['status'] == 'recorded'
    delivered = flow(post, 'execute_correction', ref, **args)
    assert delivered['status'] == 'delivered', delivered
    assert delivered['provenance']['parent_run_ref'] == failed['provenance']['run_id']
    assert source.read_bytes() == before
    assert flow(post, 'execute_correction', ref, **args)['status'] == 'refused'
    resumed = flow(post, 'resume', ref)
    assert resumed['memory']['found']
    assert [r['status'] for r in resumed['delivery']['runs']] == ['failed', 'succeeded']


def test_claim_survives_interrupted_delivery_without_replay(runtime, monkeypatch):
    post, _ = runtime
    ref = start(post); p = prepare(post, ref); approve(post, ref, p)
    calls = []
    def interrupted(*args, **kwargs):
        calls.append(1)
        raise OSError('simulated interruption')
    monkeypatch.setattr(C, '_deliver', interrupted)
    first = flow(post, 'deliver', ref, presentation_ref=p['presentation_ref'])
    assert first['execution_status'] == 'not_confirmed'
    assert flow(post, 'deliver', ref, presentation_ref=p['presentation_ref'])['status'] == 'refused'
    assert calls == [1]
    resumed = flow(post, 'resume', ref)
    assert resumed['interface_requires_reconciliation'] is True


def test_modified_presentation_cannot_authorize(runtime):
    import json
    post, _ = runtime
    ref = start(post); p = prepare(post, ref)
    path = C._pursuit_dir(ref) / 'interface_events.jsonl'
    facts = [json.loads(line) for line in path.read_text().splitlines()]
    facts[-1]['budget_usd'] = 999
    path.write_text(''.join(json.dumps(fact) + '\n' for fact in facts))
    assert approve(post, ref, p)['status'] == 'refused'
    assert not (C._pursuit_dir(ref) / 'site_build.jsonl').exists()


def test_declined_and_old_presentation_cannot_deliver(runtime):
    post, _ = runtime
    ref = start(post); old = prepare(post, ref); current = prepare(post, ref)
    assert approve(post, ref, old)['status'] == 'refused'
    assert flow(post, 'authorize', ref, presentation_ref=current['presentation_ref'], decision='declined')['status'] == 'recorded'
    assert flow(post, 'deliver', ref, presentation_ref=current['presentation_ref'])['status'] == 'refused'
    assert not (C._pursuit_dir(ref) / 'site_build.jsonl').exists()
