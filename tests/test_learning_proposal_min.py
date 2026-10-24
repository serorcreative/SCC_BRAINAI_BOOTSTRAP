"""Memory-11 → Learning-12 depuis des livraisons exercées, sans cognition payante."""
import json
from types import SimpleNamespace

import pytest

from brainai_app import composition, providers
from brainai_app.delivery.memory import open_memory_store, write_delivery_memory
from test_l8_cost_gate import l8_env, FakeOutcome
from test_build_runtime_test_run_seam import FakeSite, FakePreview
from scc_brainai_bootstrap.builder.local_test import LocalDeterministicTestAdapter


@pytest.fixture
def deliveries(l8_env, monkeypatch):
    monkeypatch.setattr(providers, 'real_delivery', lambda **kw: SimpleNamespace(
        site_build=FakeSite(), test_run=LocalDeterministicTestAdapter(timeout=5), preview=FakePreview()))

    def deliver(ref):
        root, sid, bid, spec, fp = l8_env(ref)
        composition.authorize(ref, presented_spec_ref=sid, presented_gate_fingerprint=fp,
                              decision='approved')
        report = composition._deliver(root, FakeOutcome(ref, sid, bid, fp), actor='tester', budget_usd=1)
        assert report['status'] == 'delivered', report
        return root, report
    return deliver


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()
            and 'learning' not in p.relative_to(root).parts}


def test_actual_deliveries_produce_traceable_proposals_without_source_changes(deliveries, monkeypatch):
    reports = [deliveries('p_learn_a')[1], deliveries('p_learn_b')[1]]
    before = snapshot(composition._state_root())
    monkeypatch.setattr(providers, 'real_delivery', lambda **kw: pytest.fail('provider called'))
    result = composition.propose_learning()
    assert result['status'] == 'proposed'
    assert result['audit']['ok']
    assert result['applied'] is False and result['needs_human_validation'] is True
    ids = {r['memory_11_id'] for r in reports}
    assert set(result['memory_ids']) == ids
    assert result['recommendations']
    assert all(r['status'] == 'proposed' and set(r['evidence']) == ids
               and r['data']['applied'] is False for r in result['recommendations'])
    assert snapshot(composition._state_root()) == before
    again = composition.propose_learning()
    assert [(i['id'], i['status'], i['evidence']) for i in again['items']] == [
        (i['id'], i['status'], i['evidence']) for i in result['items']]


@pytest.mark.parametrize('count', [0, 1])
def test_no_invented_recurrence(deliveries, count):
    for n in range(count):
        deliveries('p_single_' + str(n))
    result = composition.propose_learning()
    assert result['status'] == 'insufficient_evidence'
    assert len(result['memory_ids']) == count
    assert result['items'] == []


def test_duplicate_memory_does_not_create_second_experience(deliveries):
    _, report = deliveries('p_duplicate')
    store = open_memory_store(composition._state_root() / 'memory')
    write_delivery_memory(store, pursuit_ref='p_duplicate', project='site', result='Repeated journal entry',
                          decisions=[], artifact_ref=report['build']['artefact'],
                          preview_ref=report['preview_ref'], provenance_ids=report['provenance'])
    result = composition.propose_learning()
    assert result['status'] == 'insufficient_evidence'
    assert len(result['memory_ids']) == 1
    assert result['excluded'][0]['reason'] == 'duplicate_delivery'


@pytest.mark.parametrize('file', ['delivered.jsonl', 'run_events.jsonl', 'test_results.jsonl'])
def test_corrupt_source_refuses_without_learning_write(deliveries, file):
    root, _ = deliveries('p_corrupt')
    with (root / file).open('a') as f:
        f.write('{broken')
    assert composition.propose_learning()['status'] == 'refused'
    assert not (composition._state_root() / 'learning/learnings.jsonl').exists()


def test_unresolved_delivery_is_excluded_not_invented(deliveries):
    root, _ = deliveries('p_missing')
    (root / 'delivered.jsonl').unlink()
    result = composition.propose_learning()
    assert result['status'] == 'insufficient_evidence'
    assert result['memory_ids'] == []
    assert result['excluded'][0]['reason'] == 'unverified_delivery'


@pytest.mark.parametrize('damage', ['json', 'hash', 'id', 'status', 'duplicate', 'symlink'])
def test_corrupt_learning_never_overwritten(deliveries, damage):
    deliveries('p_a'); deliveries('p_b')
    assert composition.propose_learning()['status'] == 'proposed'
    path = composition._state_root() / 'learning/learnings.jsonl'
    lines = path.read_text().splitlines()
    if damage == 'json':
        path.write_text(path.read_text() + '{broken')
    elif damage == 'symlink':
        target = path.with_name('preserved.jsonl')
        path.rename(target); path.symlink_to(target)
    elif damage == 'duplicate':
        path.write_text(path.read_text() + lines[0] + '\n')
    else:
        item = json.loads(lines[0]); item[damage] = 'INVALID'
        lines[0] = json.dumps(item); path.write_text('\n'.join(lines) + '\n')
    before = path.read_bytes()
    assert composition.propose_learning()['status'] == 'refused'
    assert path.read_bytes() == before


def test_human_decision_survives_reanalysis(deliveries):
    deliveries('p_a'); deliveries('p_b')
    result = composition.propose_learning()
    from scc_brainai_bootstrap.learning import LearningLayer
    from scc_brainai_bootstrap.core.config import BrainAIConfig
    store = open_memory_store(composition._state_root() / 'memory')
    engine = LearningLayer(BrainAIConfig(data_dir=composition._state_root())).engine(store)
    chosen = result['recommendations'][0]['id']
    engine.reject(chosen, 'frederique', 'ne pas retenir')
    new = composition.propose_learning()
    item = next(i for i in new['items'] if i['id'] == chosen)
    assert item['status'] == 'rejected'
    assert item['validation']['approver'] == 'frederique'
    assert new['applied'] is False


@pytest.mark.parametrize('damage', ['failed_test', 'wrong_hash', 'failed_run', 'wrong_pursuit', 'wrong_verification'])
def test_inconsistent_historical_evidence_not_used(deliveries, damage):
    root, _ = deliveries('p_bad')
    name = ('test_results.jsonl' if damage in ('failed_test', 'wrong_hash') else
            'run_events.jsonl' if damage in ('failed_run', 'wrong_pursuit') else 'verifications.jsonl')
    path = root / name
    facts = [json.loads(line) for line in path.read_text().splitlines()]
    if damage == 'failed_test':
        facts[0]['status'] = 'failed'
    elif damage == 'wrong_hash':
        facts[0]['artifact_sha256'] = '0' * 64
    elif damage == 'failed_run':
        facts[-1]['status'] = 'failed'
    elif damage == 'wrong_pursuit':
        facts[-1]['pursuit_ref'] = 'p_other'
    else:
        facts[0]['proof']['test_result_id'] = 'testres_other'
    path.write_text(''.join(json.dumps(f) + '\n' for f in facts))
    result = composition.propose_learning()
    assert result['status'] == 'insufficient_evidence'
    assert result['memory_ids'] == []


def test_memory_truncated_tail_refused_without_repair(deliveries):
    deliveries('p_a')
    path = composition._state_root() / 'memory/brain_memory.jsonl'
    with path.open('a') as f:
        f.write('{broken')
    before = path.read_bytes()
    assert composition.propose_learning()['status'] == 'refused'
    assert path.read_bytes() == before


def test_atomic_publish_failure_preserves_previous_proposals(deliveries, monkeypatch):
    deliveries('p_a'); deliveries('p_b')
    assert composition.propose_learning()['status'] == 'proposed'
    path = composition._state_root() / 'learning/learnings.jsonl'
    before = path.read_bytes()
    from brainai_app import learning
    def fail(*args):
        raise OSError('simulated disk failure secret=NOT_FOR_OUTPUT')
    monkeypatch.setattr(learning.os, 'replace', fail)
    result = composition.propose_learning()
    assert result['status'] == 'refused'
    assert 'NOT_FOR_OUTPUT' not in str(result)
    assert path.read_bytes() == before


def test_unavailable_learning_preserves_previous_proposals(deliveries, monkeypatch):
    deliveries('p_a'); deliveries('p_b')
    composition.propose_learning()
    path = composition._state_root() / 'learning/learnings.jsonl'
    before = path.read_bytes()
    from brainai_app.learning import LearningLayer
    monkeypatch.setattr(LearningLayer, 'engine', lambda *args: None)
    assert composition.propose_learning()['status'] == 'refused'
    assert path.read_bytes() == before


def test_parallel_request_refused_while_registry_locked(deliveries):
    import fcntl
    deliveries('p_a'); deliveries('p_b')
    composition.propose_learning()
    directory = composition._state_root() / 'learning'
    before = (directory / 'learnings.jsonl').read_bytes()
    with (directory / '.proposal.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert composition.propose_learning()['status'] == 'refused'
    assert (directory / 'learnings.jsonl').read_bytes() == before


def test_fresh_process_recovers_sources_without_session_cache(deliveries):
    import os
    import subprocess
    import sys
    from pathlib import Path
    deliveries('p_a'); deliveries('p_b')
    first = composition.propose_learning()
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
    code = 'import json; from brainai_app.composition import propose_learning; print(json.dumps(propose_learning()))'
    run = subprocess.run([sys.executable, '-c', code], env=env, text=True, capture_output=True, check=True)
    result = json.loads(run.stdout)
    assert result['status'] == 'proposed'
    assert result['memory_ids'] == first['memory_ids']
    assert [i['id'] for i in result['items']] == [i['id'] for i in first['items']]
