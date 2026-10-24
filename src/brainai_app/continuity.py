"""Projection de reprise : distingue dialogue, mémoire livrée et exécution.

Aucun runner, aucun provider, aucun constat automatique de mort de worker.
Un état running sur disque exige un examen ; il n'autorise jamais un replay.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


class ReadOnlyCapability:
    """Satisfait le contrat d'injection, mais interdit toute cognition à la reprise."""
    capability = 'resume.read_only'
    name = 'read_only'
    model = None

    def propose(self, *args, **kwargs):
        raise RuntimeError('aucune capacité exécutable dans une reprise en lecture')


def _read(path: Path):
    if path.is_symlink():
        raise ValueError('journal symlink refusé')
    if not path.exists():
        return []
    facts = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if any(not isinstance(f, dict) for f in facts):
        raise ValueError('journal non objet')
    return facts


def read_delivery_state(root: Path, pursuit_ref: str):
    """Expose seulement des faits présents ; aucune inférence de livraison courante."""
    from brainai_app.delivery.vocab import RUN_TERMINAL, RUN_PREPARED, RUN_RUNNING
    facts = _read(root / 'run_events.jsonl')
    # Valider aussi les preuves et charges : une queue cassée ne doit pas disparaître.
    for name in ('site_build.jsonl', 'test_results.jsonl', 'verifications.jsonl', 'delivered.jsonl',
                 'correction_proposals.jsonl'):
        _read(root / name)
    budget = _read(root / 'budget.jsonl')
    charges = [f for f in budget if f.get('fact_type') == 'budget_charge']
    for charge in charges:
        value = charge.get('cost_value')
        if charge.get('cost_kind') == 'real' and (
                type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError('coût réel invalide')
    known_cost = sum(f['cost_value'] for f in charges if f.get('cost_kind') == 'real')
    unknown_cost = any(f.get('cost_kind') != 'real' for f in charges)
    correction_events = _read(root / 'correction_events.jsonl')
    runs, interrupted = {}, set()
    for fact in facts:
        if fact.get('fact_type') == 'build_run':
            rid = fact.get('run_id')
            if (not isinstance(rid, str) or not rid or fact.get('pursuit_ref') != pursuit_ref
                    or fact.get('status') not in (*RUN_TERMINAL, RUN_PREPARED, RUN_RUNNING)):
                raise ValueError('run incohérent ou hors Pursuit')
            runs[rid] = {k: fact.get(k) for k in ('run_id', 'status', 'as_of', 'prev_run_ref')}
        elif fact.get('fact_type') == 'run_interrupted':
            if fact.get('pursuit_ref') != pursuit_ref or fact.get('run_ref') not in runs:
                raise ValueError('constat interruption non rattaché')
            interrupted.add(fact['run_ref'])
    for rid, run in runs.items():
        run['interruption_recorded'] = rid in interrupted
        run['requires_reconciliation'] = run['status'] not in RUN_TERMINAL
    claimed = []
    for event in correction_events:
        if event.get('pursuit_ref') != pursuit_ref:
            raise ValueError('événement correctif hors Pursuit')
        if event.get('kind') == 'claimed':
            claimed.append(event.get('correction_id'))
    return dict(runs=list(runs.values()), consumed_corrections=claimed,
                live_worker_status='not_checked', artifact_revalidated=False,
                budget={'journal_present': (root / 'budget.jsonl').exists(),
                        'calls_recorded': len(charges), 'known_cost_usd': known_cost,
                        'has_unavailable_cost': unknown_cost,
                        'total_cost_usd': None if unknown_cost or not budget else known_cost},
                automatic_replay=False)
