"""Reprise explicite sans replay : état disque, mémoire réelle, zéro fournisseur."""
import json
from types import SimpleNamespace

import pytest

from brainai_app import composition as C
from brainai_app.delivery.memory import open_memory_store, write_delivery_memory
from scc_brainai_bootstrap.builder.brainai import BrainAI, resume_intent
from scc_brainai_bootstrap.builder.turns import TurnStore
from test_correction_execution import prepared, l8_env, approve, execute


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv('BRAINAI_STATE_ROOT', str(tmp_path / 'state'))
    C._SESSIONS.clear()
    ref = 'pursuit_resume'
    root = C._pursuit_dir(ref)
    root.mkdir(parents=True)
    store = TurnStore(root / 'turns.jsonl')
    turn = store.record(dict(fact_type='turn', pursuit_ref=ref, status='proposed',
                             message='Un site', reply='Précisez le besoin', readiness='continue',
                             as_of='2026-10-24T07:00:00Z', cost={'value': None, 'kind': 'unavailable'}))
    # Toute résolution facturable ou livraison serait une régression.
    def forbidden(*args, **kwargs):
        pytest.fail('resume called provider or delivery')
    monkeypatch.setattr(C, '_capabilities', forbidden)
    monkeypatch.setattr(C, '_deliver', forbidden)
    return SimpleNamespace(root=root, ref=ref, store=store, turn=turn)


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_resume_after_cache_loss_is_readonly_and_same_pursuit(session):
    p = session
    before = tree(C._state_root())
    result = C.resume(p.ref)
    assert result['status'] == 'resumed'
    assert result['pursuit_ref'] == p.ref
    assert result['dialogue']['state'] == 'active'
    assert result['dialogue']['continuity']['last_turn_ref'] == p.turn['turn_id']
    assert result['dialogue']['continuity']['history'] == [
        {'role': 'user', 'content': 'Un site'}, {'role': 'assistant', 'content': 'Précisez le besoin'}]
    assert result['memory']['found'] is False
    assert result['execution_authorized'] is False
    assert tree(C._state_root()) == before
    C._SESSIONS.clear()
    assert C.resume(p.ref)['dialogue']['continuity'] == result['dialogue']['continuity']


def test_resume_uses_real_memory11_without_claiming_delivery_current(session):
    p = session
    store = open_memory_store(C._state_root() / 'memory')
    write_delivery_memory(store, pursuit_ref=p.ref, project='site', result='version livrée',
                          decisions=[], artifact_ref={'relative_path': 'index.html'}, preview_ref=None,
                          provenance_ids={'run_id': 'r_old'}, as_of='t0')
    before = tree(C._state_root())
    r = C.resume(p.ref)
    assert r['memory']['found'] and len(r['memory']['memory_ids']) == 1
    assert r['memory']['continuity']['result'] == 'version livrée'
    assert r['delivery']['runs'] == []
    assert r['delivery']['artifact_revalidated'] is False
    assert tree(C._state_root()) == before


@pytest.mark.parametrize('bad', ['', '../escape', '/tmp/x', None, 42])
def test_invalid_ref_refused_without_creation(session, bad):
    before = tree(C._state_root())
    assert C.resume(bad)['status'] == 'refused'
    assert tree(C._state_root()) == before


def test_absent_ref_does_not_create_session(session):
    assert C.resume('pursuit_absent')['status'] == 'refused'
    assert not C._pursuit_dir('pursuit_absent').exists()


@pytest.mark.parametrize('tail', ['{broken', '[]', 'null'])
def test_corrupted_turn_tail_blocks_resume(session, tail):
    with session.store.path.open('a') as f:
        f.write(tail + '\n')
    assert C.resume(session.ref)['status'] == 'refused'


def test_last_failed_turn_does_not_restore_old_convergence(session):
    p = session
    p.store.record(dict(fact_type='turn', pursuit_ref=p.ref, status='proposed', message='m', reply='r',
                        readiness='ready', matured_need='Faire un site', as_of='t1'))
    p.store.record(dict(fact_type='turn', pursuit_ref=p.ref, status='failed', message='nouveau', as_of='t2'))
    r = C.resume(p.ref)
    assert r['status'] == 'resumed'
    assert r['dialogue']['state'] == 'terminal'
    assert r['dialogue']['proposal'] is None
    assert r['dialogue']['continuity']['last_turn_status'] == 'failed'


def test_ready_turn_is_proposal_not_execution(session):
    p = session
    p.store.record(dict(fact_type='turn', pursuit_ref=p.ref, status='proposed', message='m', reply='r',
                        readiness='ready', matured_need='Faire un site', as_of='t1'))
    r = C.resume(p.ref)
    assert r['dialogue']['state'] == 'awaiting'
    assert r['dialogue']['wait_reason'] == 'confirmation'
    assert r['execution_authorized'] is False


def test_running_run_is_unresolved_not_declared_dead_or_replayed(session):
    p = session
    facts = [dict(fact_type='build_run', run_id='r1', pursuit_ref=p.ref, status='running', as_of='t0')]
    (p.root / 'run_events.jsonl').write_text('\n'.join(map(json.dumps, facts)) + '\n')
    before = tree(C._state_root())
    r = C.resume(p.ref)
    assert r['delivery']['runs'][0]['status'] == 'running'
    assert r['delivery']['runs'][0]['requires_reconciliation'] is True
    assert r['delivery']['live_worker_status'] == 'not_checked'
    assert tree(C._state_root()) == before


def test_corrupt_delivery_ledger_blocks_resume(session):
    (session.root / 'budget.jsonl').write_text('{broken\n')
    assert C.resume(session.ref)['status'] == 'refused'


def test_memory_truncated_tail_is_not_silently_ignored(session):
    store = open_memory_store(C._state_root() / 'memory')
    write_delivery_memory(store, pursuit_ref=session.ref, project='site', result='r', decisions=[],
                          artifact_ref=None, preview_ref=None, provenance_ids={})
    path = C._state_root() / 'memory/brain_memory.jsonl'
    with path.open('a') as f:
        f.write('{broken')
    before = path.read_bytes()
    assert C.resume(session.ref)['status'] == 'refused'
    assert path.read_bytes() == before


def test_core_resume_rejects_action_payload_without_calls(session):
    caps = C.demo_capabilities()
    outcome = BrainAI(caps).pursue(resume_intent(session.ref, payload={'decision': 'approved'}),
                                 context=C._session_context(session.root, budget_usd=1))
    assert outcome.refused
    assert not (session.root / 'confirmations.jsonl').exists()


def test_real_process_restart_and_subsequent_conversation_preserve_identity(session, monkeypatch):
    import subprocess
    import sys
    p = session
    # Processus neuf : aucun cache de session ou import Memory-11 du parent.
    code = "from brainai_app.composition import resume; import json; print(json.dumps(resume('pursuit_resume')))"
    before = tree(C._state_root())
    child = json.loads(subprocess.check_output([sys.executable, '-c', code], text=True, timeout=15))
    assert child['status'] == 'resumed' and child['pursuit_ref'] == p.ref
    assert tree(C._state_root()) == before
    caps = C.demo_capabilities()
    seen = {}
    original = caps.conversation.propose
    def capture(message, **kwargs):
        seen.update(kwargs)
        return original(message, **kwargs)
    monkeypatch.setattr(caps.conversation, 'propose', capture)
    monkeypatch.setattr(C, '_capabilities', lambda *a, **kw: caps)
    vm = C.converse('Ajout explicite', pursuit_ref=p.ref)
    assert vm['pursuit']['pursuit_id'] == p.ref
    assert seen['history'] == child['dialogue']['continuity']['history']
    turns = p.store.read_all(strict=True)
    assert len(turns) == 2 and turns[0] == p.turn


@pytest.mark.parametrize('kind', ['other_pursuit', 'duplicate_turn', 'missing_reply', 'symlink'])
def test_inconsistent_source_refused(session, tmp_path, kind):
    p = session
    if kind == 'symlink':
        original = p.store.path.read_bytes()
        p.store.path.unlink()
        other = tmp_path / 'external.jsonl'
        other.write_bytes(original)
        p.store.path.symlink_to(other)
    else:
        fact = dict(p.turn)
        if kind == 'other_pursuit': fact['pursuit_ref'] = 'pursuit_other'
        if kind == 'missing_reply': del fact['reply']
        p.store.path.write_text(json.dumps(fact) + '\n')
        if kind == 'duplicate_turn':
            with p.store.path.open('a') as f: f.write(json.dumps(fact) + '\n')
    assert C.resume(p.ref)['status'] == 'refused'


def test_unknown_cost_and_consumed_correction_survive_recall(session):
    p = session
    from brainai_app.delivery.budget import BudgetLedger
    ledger = BudgetLedger(p.root / 'budget.jsonl', ceiling_usd=1, max_calls=4)
    ledger.record_charge({'value': .2, 'kind': 'real'})
    ledger.record_charge({'value': None, 'kind': 'unavailable'})
    (p.root / 'correction_events.jsonl').write_text(json.dumps(
        dict(kind='claimed', pursuit_ref=p.ref, correction_id='correction_a')) + '\n')
    before = tree(C._state_root())
    result = C.resume(p.ref)
    assert result['delivery']['budget']['calls_recorded'] == 2
    assert result['delivery']['budget']['known_cost_usd'] == .2
    assert result['delivery']['budget']['total_cost_usd'] is None
    assert result['delivery']['consumed_corrections'] == ['correction_a']
    assert tree(C._state_root()) == before


def test_resume_corrected_delivery_reuses_memory_and_never_replays(prepared):
    p = prepared
    TurnStore(p.root / 'turns.jsonl').record(dict(
        fact_type='turn', pursuit_ref='p_corr', status='proposed', message='Site corrigé',
        reply='Spécification préparée', readiness='continue', as_of='t0'))
    assert approve(p)['status'] == 'recorded'
    delivery = execute(p)
    assert delivery['status'] == 'delivered'
    before = tree(C._state_root())
    calls = (p.builder.calls, p.test.calls, p.preview.opened)
    r = C.resume('p_corr')
    assert r['status'] == 'resumed'
    assert r['memory']['found']
    assert r['memory']['continuity']['provenance_ids']['run_id'] == delivery['provenance']['run_id']
    assert r['delivery']['runs'][-1]['run_id'] == delivery['provenance']['run_id']
    assert r['delivery']['runs'][-1]['prev_run_ref'] == p.failed['provenance']['run_id']
    assert r['delivery']['consumed_corrections'] == [p.correction]
    assert (p.builder.calls, p.test.calls, p.preview.opened) == calls
    assert tree(C._state_root()) == before
