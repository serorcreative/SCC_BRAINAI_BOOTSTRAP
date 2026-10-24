"""LEARNING-PROPOSAL-MIN : raccord des livraisons mémorisées à Learning-12.

Le moteur natif conserve ses seuils et ses décisions humaines. Seul son registre
de propositions est écrit ; aucune action, validation ou application automatique.
Les preuves décrivent une livraison passée, pas l'état actuel de son artefact.
"""
from __future__ import annotations

import copy
import fcntl
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from brainai_app.continuity import _read
from brainai_app.delivery.memory import open_memory_store
from brainai_app.recall import _resolve_pursuit_dir_readonly
from scc_brainai_bootstrap.core.config import BrainAIConfig
from scc_brainai_bootstrap.learning import LearningLayer


class _MemorySnapshot:
    """Interface minimale en lecture pour le MemorySource natif ; aucun append."""
    def __init__(self, entries):
        self.entries = copy.deepcopy(entries)

    def search(self, **kwargs):
        return copy.deepcopy(self.entries)


def _one(facts, key, value):
    if not isinstance(value, str) or not value:
        return None
    matches = [f for f in facts if f.get(key) == value]
    if len(matches) > 1:
        raise ValueError('preuve ambiguë')
    return matches[0] if matches else None


def _delivery_key(entry):
    data = entry.get('data') or {}
    ref = data.get('pursuit_ref')
    if data.get('status') != 'delivered' or not isinstance(ref, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', ref):
        return None
    root = _resolve_pursuit_dir_readonly(ref)
    if root is None or root.is_symlink():
        return None
    provenance = data.get('provenance_ids') or {}
    delivered = _one(_read(root / 'delivered.jsonl'), 'delivered_id', provenance.get('delivered_id'))
    # Lire les journaux même lorsqu'une référence manque : corruption jamais escamotée.
    runs = _read(root / 'run_events.jsonl')
    tests = _read(root / 'test_results.jsonl')
    verifications = _read(root / 'verifications.jsonl')
    if not delivered or delivered.get('pursuit_ref') != ref:
        return None
    test = _one(tests, 'test_result_id', delivered.get('test_result_ref'))
    if not test or test.get('status') != 'passed' or provenance.get('test_result_id') != test['test_result_id']:
        return None
    artifact = delivered.get('artifact_ref') or {}
    # Memory-11 caviarde les SHA-256. Ne pas désactiver cette protection : la
    # liaison se fait par les IDs et l'empreinte se vérifie dans les faits sources.
    remembered = data.get('artifact_ref') or {}
    if any(remembered.get(k) != artifact.get(k) for k in ('relative_path', 'byte_size')):
        return None
    sha = artifact.get('sha256')
    if not sha or test.get('artifact_sha256') != sha:
        return None
    for field, kind in (('verification_ref', 'http'), ('test_verification_ref', 'test')):
        verification = _one(verifications, 'verification_id', delivered.get(field))
        if not verification or verification.get('verdict') != 'passed' or verification.get('sha256') != sha or verification.get('kind') != kind:
            return None
        if kind == 'test' and verification.get('proof', {}).get('test_result_id') != test['test_result_id']:
            return None
    rid = provenance.get('run_id')
    states = [f for f in runs if f.get('fact_type') == 'build_run' and f.get('run_id') == rid]
    if not states or states[-1].get('status') != 'succeeded' or any(f.get('pursuit_ref') != ref for f in states):
        return None
    step_refs = [f.get('refs', {}) for f in runs if f.get('fact_type') == 'build_step'
                 and f.get('run_ref') == rid and f.get('status') == 'succeeded']
    for field, source in (('build_id', 'build_ref'), ('test_result_id', 'test_result_ref'),
                          ('verification_id', 'verification_ref'),
                          ('test_verification_id', 'test_verification_ref')):
        value = delivered.get(source)
        if not value or provenance.get(field) != value or not any(r.get(field) == value for r in step_refs):
            return None
    return ref, delivered['delivered_id']


def _experience(root):
    store = open_memory_store(root / 'memory')
    if getattr(store, 'truncated_tail', False) or getattr(store, 'reconciliation_required', False):
        raise ValueError('mémoire à réconcilier')
    if not store.audit()['ok']:
        raise ValueError('audit mémoire refusé')
    entries, excluded, seen = [], [], set()
    for entry in sorted(store.search(subtype='pursuit_delivered', limit=0), key=lambda e: e['id']):
        key = _delivery_key(entry)
        if key is None or key in seen:
            excluded.append({'memory_id': entry['id'], 'reason': 'unverified_delivery' if key is None else 'duplicate_delivery'})
        else:
            seen.add(key)
            entries.append(entry)
    return entries, excluded


def _validate_registry(path):
    """Empêche le chargeur permissif natif de réparer implicitement un registre."""
    seen = set()
    for raw in _read(path):
        if (not raw.get('id') or not raw.get('hash') or raw['id'] in seen
                or raw.get('status') not in ('proposed', 'validated', 'rejected', 'revoked')
                or raw.get('kind') not in ('signal', 'pattern', 'lesson', 'recommendation', 'hypothesis')
                or not isinstance(raw.get('evidence'), list) or not raw['evidence']):
            raise ValueError('registre Learning invalide')
        seen.add(raw['id'])


def _analyze(root, entries, excluded):
    directory = root / 'learning'
    if directory.is_symlink():
        raise ValueError('répertoire Learning symlink')
    directory.mkdir(parents=True, exist_ok=True)
    registry = directory / 'learnings.jsonl'
    fd = os.open(str(directory / '.proposal.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _validate_registry(registry)
        # Learning-12 réécrit son registre natif : le faire dans un dossier temporaire
        # puis publier atomiquement seulement après les audits, sous verrou local.
        with tempfile.TemporaryDirectory(prefix='.proposal-', dir=str(directory)) as staging:
            config = BrainAIConfig(data_dir=Path(staging), as_of=datetime.now(timezone.utc).isoformat())
            staged = config.learning_data_dir / 'learnings.jsonl'
            staged.parent.mkdir()
            if registry.exists():
                staged.write_bytes(registry.read_bytes())
            engine = LearningLayer(config).engine(_MemorySnapshot(entries))
            if engine is None or not engine.audit()['ok']:
                raise ValueError('Learning indisponible ou audit initial refusé')
            if any(copy.deepcopy(item).finalize().id != item.id for item in engine.items):
                raise ValueError('identifiant Learning incohérent')
            analysis = engine.analyze()
            audit = engine.audit()
            if not audit['ok']:
                raise ValueError('audit Learning refusé')
            items = [item.to_dict() for item in engine.items]
            with staged.open('rb') as handle:
                os.fsync(handle.fileno())
            os.chmod(staged, 0o600)
            os.replace(str(staged), str(registry))
            return dict(status='proposed' if items else 'insufficient_evidence',
                        items=items, recommendations=[i for i in items if i['kind'] == 'recommendation'],
                        memory_ids=[e['id'] for e in entries], excluded=excluded,
                        analysis=analysis, audit=audit, applied=False, needs_human_validation=True,
                        artifact_revalidated=False, scope='historical_verified_deliveries')


def propose_from_deliveries(root: Path):
    """Une demande explicite ; aucune livraison ni réparation mémoire déclenchée."""
    try:
        entries, excluded = _experience(root)
        return _analyze(root, entries, excluded)
    except Exception:
        # Les erreurs natives peuvent contenir des chemins ou du contenu utilisateur.
        return {'status': 'refused', 'reason': 'Preuves ou registre Learning indisponibles, incohérents ou occupés.',
                'applied': False, 'needs_human_validation': True}
