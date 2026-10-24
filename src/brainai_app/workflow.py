"""Raccord UI borné : présentation durable, GO inerte, exécution explicite unique.

Réutilise les services applicatifs ; aucun fournisseur ou mécanisme cognitif
nouveau. Une présentation est liée au dernier tour, à la spec, au budget et au
sélecteur de build. Une livraison initiale réclamée ne se rejoue jamais ici.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from brainai_app import composition as C
from brainai_app.continuity import _read
from brainai_app.recall import _resolve_pursuit_dir_readonly
from brainai_app.delivery.corrections import correction_target
from scc_brainai_bootstrap.core.clock import short_id

_FIELDS = {
    'prepare': {'budget_usd', 'build_provider'},
    'resume': set(), 'learning': set(),
    'authorize': {'presentation_ref', 'decision'},
    'deliver': {'presentation_ref'},
    'propose_correction': {'parent_run_ref', 'test_result_ref', 'suggestion'},
    'authorize_correction': {'presentation_ref', 'correction_ref', 'decision'},
    'execute_correction': {'presentation_ref', 'correction_ref'},
}


def validate(payload):
    action = payload.get('action')
    if not isinstance(action, str) or action not in _FIELDS:
        raise ValueError('action inconnue')
    if set(payload) - ({'kind', 'action', 'mode'} | _FIELDS[action] |
                       (set() if action == 'learning' else {'pursuit_ref'})):
        raise ValueError('champs inattendus')
    required = _FIELDS[action] if action != 'prepare' else set()
    for key in required | (set() if action == 'learning' else {'pursuit_ref'}):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError('champ requis invalide')
    if action != 'learning' and not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', payload['pursuit_ref']):
        raise ValueError('référence invalide')
    if 'decision' in payload and payload['decision'] not in ('approved', 'declined'):
        raise ValueError('décision invalide')
    budget = payload.get('budget_usd', 2.0)
    if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
        raise ValueError('budget invalide')
    if 'build_provider' in payload and payload['build_provider'] is not None and (
            not isinstance(payload['build_provider'], str) or not payload['build_provider'].strip()):
        raise ValueError('sélecteur invalide')


def _append(root, fact):
    path = root / 'interface_events.jsonl'
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(fact, ensure_ascii=False) + '\n')
        handle.flush(); os.fsync(handle.fileno())


@contextmanager
def _lock(root):
    fd = os.open(root / 'interface.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _turn(root, ref):
    turns = C.TurnStore(root / 'turns.jsonl').read_all(strict=True)
    own = [t for t in turns if t.get('pursuit_ref') == ref]
    if not own:
        raise ValueError('dialogue absent')
    return own[-1]['turn_id']


def _presentation(root, ref, requested):
    events = _read(root / 'interface_events.jsonl')
    presentations = [e for e in events if e.get('kind') == 'presentation']
    if not presentations:
        raise ValueError('présentation absente')
    p = presentations[-1]
    if (p['presentation_ref'] != requested or p['pursuit_ref'] != ref
            or p['turn_ref'] != _turn(root, ref)
            or short_id('present', {k: v for k, v in p.items() if k != 'presentation_ref'}) != requested):
        raise ValueError('présentation périmée')
    return p, events


def dispatch(payload):
    """Validation de forme séparée, erreurs opérationnelles sans contenu brut."""
    validate(payload)
    action = payload['action']
    if action == 'learning':
        return C.propose_learning()
    ref = payload['pursuit_ref']
    root = _resolve_pursuit_dir_readonly(ref)
    if root is None or not root.is_dir() or root.is_symlink():
        return {'status': 'refused', 'reason': 'session_absente_ou_invalide'}
    try:
        if action == 'resume':
            result = C.resume(ref)
            events = _read(root / 'interface_events.jsonl')
            result['interface_history'] = events
            claims = any(e.get('kind') == 'initial_claim' for e in events)
            known = any((e.get('report') or {}).get('run') for e in events if e.get('kind') == 'delivery_report')
            result['interface_requires_reconciliation'] = claims and not known
            return result
        with _lock(root):
            if action == 'prepare':
                if payload.get('mode') != 'real':
                    return {'status': 'refused', 'reason': 'preparation_reelle_explicitement_requise'}
                budget = payload.get('budget_usd', 2.0)
                provider = payload.get('build_provider')
                vm = C.realize(ref, mode='real', budget_usd=budget, prepare_only=True)
                gate = (vm['pursuit'].get('proposal') or {}).get('cost_gate')
                if not gate:
                    vm['workflow'] = {'status': 'refused', 'reason': 'cost_gate_absent'}
                    return vm
                specs = _read(root / 'spec.jsonl')
                spec = next(s for s in specs if s.get('specification_id') == gate['spec_ref'])
                fact = dict(kind='presentation', status='prepared', pursuit_ref=ref,
                            turn_ref=_turn(root, ref), spec_ref=gate['spec_ref'],
                            gate_fingerprint=gate['gate_fingerprint'], cost_gate=gate,
                            specification=spec['specification'], budget_usd=budget,
                            build_provider=provider, as_of=datetime.now(timezone.utc).isoformat())
                fact['presentation_ref'] = short_id('present', fact)
                _append(root, fact)
                vm['workflow'] = fact
                return vm
            if action == 'propose_correction':
                return C.propose_delivery_correction(ref, **{k: payload[k] for k in _FIELDS[action]})
            p, events = _presentation(root, ref, payload['presentation_ref'])
            args = dict(presented_spec_ref=p['spec_ref'], presented_gate_fingerprint=p['gate_fingerprint'])
            if action == 'authorize':
                return C.authorize(ref, decision=payload['decision'], **args)
            args.update(budget_usd=p['budget_usd'], build_provider=p['build_provider'])
            if action == 'authorize_correction':
                return C.authorize_delivery_correction(ref, correction_ref=payload['correction_ref'],
                                                      decision=payload['decision'], **args)
            if payload.get('mode') != 'real':
                return {'status': 'refused', 'reason': 'execution_reelle_explicitement_requise'}
            if action == 'execute_correction':
                report = C.execute_delivery_correction(ref, correction_ref=payload['correction_ref'], **args)
            else:
                # Garder l'artefact initial intact même après nouvel accord ou double clic.
                if any(e.get('kind') == 'initial_claim' for e in events) or _read(root / 'run_events.jsonl'):
                    return {'status': 'refused', 'reason': 'tentative_existante_utiliser_correction_ou_reconcilier'}
                spec, build = correction_target(root, ref, p['spec_ref'], p['gate_fingerprint'])
                outcome = SimpleNamespace(pursuit_id=ref, as_of=datetime.now(timezone.utc).isoformat(), need=None,
                    steps=[{'faculty': 'specification', 'status': 'proposed', 'fact_id': spec['specification_id']},
                           {'faculty': 'build', 'status': 'proposed', 'fact_id': build}],
                    proposal={'cost_gate': p['cost_gate']})
                _append(root, {'kind': 'initial_claim', 'pursuit_ref': ref,
                               'presentation_ref': p['presentation_ref']})
                report = C._deliver(root, outcome, actor=None, budget_usd=p['budget_usd'],
                                    build_provider=p['build_provider'])
            _append(root, {'kind': 'delivery_report', 'pursuit_ref': ref, 'report': report})
            return report
    except Exception:
        return {'status': 'refused', 'reason': 'operation_refusee_preuves_perimees_illisibles_ou_occupees',
                'execution_status': 'not_confirmed', 'automatic_retry': False}
