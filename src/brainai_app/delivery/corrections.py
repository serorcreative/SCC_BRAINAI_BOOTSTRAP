"""Correction gouvernée reliée aux preuves de livraison persistées.

Proposition et autorisation inertes ; une tentative consomme ensuite l'accord
avant de déléguer au service de livraison existant, sans GO implicite.
Les journaux sont lus strictement : une ligne corrompue ne peut disparaître
pour rendre un échec ou une autorisation artificiellement exploitable.
"""
from __future__ import annotations

import hashlib
import json
import re
import os
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from scc_brainai_bootstrap.builder.diagnostics import DIAG_MAX, redact
from scc_brainai_bootstrap.builder.site import MAX_ARTIFACT_BYTES
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError
from scc_brainai_bootstrap.core.clock import short_id
from scc_brainai_bootstrap.core.clock import digest
from scc_brainai_bootstrap.builder.confirmations import declared_actor


class CorrectionError(ValueError):
    """Preuves absentes, ambiguës, incohérentes ou périmées."""


def _clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return redact(str(value or ''))[:DIAG_MAX]


def _required(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', value):
        raise CorrectionError('référence requise et bornée')
    return value


def _journal(path: Path) -> List[Dict[str, Any]]:
    if path.is_symlink():
        raise CorrectionError('journal symlink refusé')
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
        facts = [json.loads(line) for line in lines if line.strip()]
    except (OSError, ValueError):
        raise CorrectionError('journal absent ou illisible') from None
    if any(not isinstance(fact, dict) for fact in facts):
        raise CorrectionError('journal non objet')
    return facts


def _unique(facts: List[Dict[str, Any]], field: str, value: str) -> Dict[str, Any]:
    matches = [fact for fact in facts if fact.get(field) == value]
    if len(matches) != 1:
        raise CorrectionError('preuve absente ou ambiguë')
    return matches[0]


def _terminal_step(facts: List[Dict[str, Any]], run: str, step: str,
                   expected_status: str) -> Dict[str, Any]:
    matches = [f for f in facts if f.get('fact_type') == 'build_step'
               and f.get('run_ref') == run and f.get('step') == step]
    terminal = [f for f in matches if f.get('status') in ('succeeded', 'failed', 'skipped')]
    if (len(terminal) != 1 or matches[-1] != terminal[0]
            or terminal[0].get('status') != expected_status
            or not isinstance(terminal[0].get('refs'), dict)):
        raise CorrectionError('étape source incohérente')
    return terminal[0]['refs']


def _proposal(*, root: Path, pursuit_ref: str, parent_run_ref: str,
                       test_result_ref: str, suggestion: str,
                       clock: Callable[[], str] = _clock) -> Dict[str, Any]:
    """Relit les faits de session et construit une proposition, sans aucun appel.

    ``root`` est fourni par la composition (session de la Pursuit), jamais par
    un fournisseur. Le lot actuel couvre l'échec de test après build réussi du
    site initial ; l'exécution exige ensuite une autorisation distincte.
    ``suggestion`` est une hypothèse déclarative, pas une cause prouvée ni une
    instruction à exécuter. Le contenu source est vérifié mais pas sauvegardé
    ici : aucune mutation de produit n'est autorisée par cette fonction.
    """
    pursuit_ref = _required(pursuit_ref)
    parent_run_ref = _required(parent_run_ref)
    test_result_ref = _required(test_result_ref)
    if not isinstance(suggestion, str) or not suggestion.strip():
        raise CorrectionError('proposition textuelle requise')
    root = Path(root)
    runs = _journal(root / 'run_events.jsonl')
    source_runs = [f for f in runs if f.get('fact_type') == 'build_run'
                   and f.get('run_id') == parent_run_ref]
    terminal = [f for f in source_runs if f.get('status') in
                ('failed', 'succeeded', 'cancelled', 'interrupted')]
    if (not source_runs or len(terminal) != 1 or terminal[0] != source_runs[-1]
            or terminal[0].get('status') != 'failed'
            or any(f.get('pursuit_ref') != pursuit_ref for f in source_runs)):
        raise CorrectionError('run source non échoué, ambigu ou hors Pursuit')
    if any(f.get('prev_run_ref') for f in source_runs):
        raise CorrectionError('ce lot exige un échec initial, sans chaîne de corrections')
    build_refs = _terminal_step(runs, parent_run_ref, 'build', 'succeeded')
    test_refs = _terminal_step(runs, parent_run_ref, 'test', 'failed')
    if test_refs.get('test_result_id') != test_result_ref:
        raise CorrectionError('résultat de test non rattaché au run')
    build = _unique(_journal(root / 'site_build.jsonl'), 'build_id',
                    _required(build_refs.get('build_id')))
    result = _unique(_journal(root / 'test_results.jsonl'), 'test_result_id', test_result_ref)
    artifact = build.get('artefact')
    if (build.get('status') != 'proposed' or not isinstance(artifact, dict)
            or result.get('fact_type') != 'test_result' or result.get('capability') != 'test.run'
            or result.get('status') != 'failed'
            or result.get('artifact_ref') != artifact.get('relative_path')
            or result.get('artifact_sha256') != artifact.get('sha256')):
        raise CorrectionError('preuves build/test incohérentes')
    spec_ref = _required(build.get('spec_ref'))
    relative_path = artifact.get('relative_path')
    if not isinstance(relative_path, str) or not relative_path or len(relative_path) > 256:
        raise CorrectionError('chemin artefact invalide')
    expected_sha = artifact.get('sha256')
    if (not isinstance(expected_sha, str) or len(expected_sha) != 64
            or any(c not in '0123456789abcdef' for c in expected_sha)):
        raise CorrectionError('empreinte source invalide')
    workspace = Workspace(root / 'delivery_exec', 'site')
    try:
        if root.resolve() not in workspace.path.parents:
            raise CorrectionError('workspace source hors session')
        target = workspace.resolve_within(relative_path)
        if not target.is_file():
            raise CorrectionError('artefact source absent')
        with target.open('rb') as handle:
            data = handle.read(MAX_ARTIFACT_BYTES + 1)
        if not data or len(data) > MAX_ARTIFACT_BYTES or hashlib.sha256(data).hexdigest() != expected_sha:
            raise CorrectionError('artefact source périmé ou invalide')
    except (OSError, WorkspaceError):
        raise CorrectionError('artefact source inaccessible ou non confiné') from None
    diagnostic = result.get('diagnostic')
    if not isinstance(diagnostic, dict):
        raise CorrectionError('diagnostic source invalide')
    fact = {
        'fact_type': 'correction_proposal', 'status': 'proposed',
        'pursuit_ref': pursuit_ref, 'parent_run_ref': parent_run_ref,
        'source_build_ref': build['build_id'], 'source_spec_ref': spec_ref,
        'test_result_ref': test_result_ref,
        'artifact_ref': relative_path, 'artifact_sha256': expected_sha,
        'observed_failure': 'test_failed', 'cause_status': 'not_established',
        'diagnostic': {k: _text(diagnostic.get(k)) for k in ('stdout', 'stderr')},
        'suggestion': _text(suggestion), 'execution_authorized': False,
        'as_of': clock(),
    }
    return {'correction_id': short_id('correction', fact), **fact}


def propose_correction(*, root: Path, pursuit_ref: str, parent_run_ref: str,
                       test_result_ref: str, suggestion: str,
                       clock: Callable[[], str] = _clock) -> Dict[str, Any]:
    fact = _proposal(root=root, pursuit_ref=pursuit_ref, parent_run_ref=parent_run_ref,
                     test_result_ref=test_result_ref, suggestion=suggestion, clock=clock)
    destination = root / 'correction_proposals.jsonl'
    if destination.exists() or destination.is_symlink():
        _journal(destination)  # ne jamais prolonger un journal déjà corrompu
    try:
        with destination.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(fact, ensure_ascii=False) + '\n')
    except OSError:
        raise CorrectionError('persistance de proposition impossible') from None
    return fact


def _load_proposal(root, pursuit_ref, correction_id):
    fact = _unique(_journal(root / 'correction_proposals.jsonl'), 'correction_id',
                   _required(correction_id))
    if fact.get('pursuit_ref') != pursuit_ref:
        raise CorrectionError('proposition hors Pursuit')
    expected = _proposal(root=root, pursuit_ref=pursuit_ref,
                         parent_run_ref=fact.get('parent_run_ref'),
                         test_result_ref=fact.get('test_result_ref'),
                         suggestion=fact.get('suggestion'), clock=lambda: fact.get('as_of'))
    if expected != fact:
        raise CorrectionError('proposition modifiée ou preuves périmées')
    return fact


def _target(root, pursuit_ref, spec_ref, gate_fingerprint):
    """Le GO de coût existant reste nécessaire, jamais fabriqué par le correctif."""
    from scc_brainai_bootstrap.builder.build_authorization import (
        BuildAuthorizationStore, authorization_status, resolve_cost_gate)
    from scc_brainai_bootstrap.builder.solution_architecture import SolutionArchitectureStore
    from scc_brainai_bootstrap.builder.cost_estimate import CostEstimateStore

    spec = _unique(_journal(root / 'spec.jsonl'), 'specification_id', _required(spec_ref))
    if (spec.get('status') != 'proposed' or not isinstance(spec.get('specification'), dict)
            or spec.get('pursuit_ref', pursuit_ref) != pursuit_ref):
        raise CorrectionError('spécification corrective invalide')
    for name in ('architectures.jsonl', 'cost_estimates.jsonl', 'build_authorizations.jsonl'):
        _journal(root / name)
    gate = resolve_cost_gate(architecture_store=SolutionArchitectureStore(root / 'architectures.jsonl'),
                            cost_estimate_store=CostEstimateStore(root / 'cost_estimates.jsonl'),
                            pursuit_ref=pursuit_ref, current_spec=spec)
    if (gate.get('status') != 'resolved'
            or gate['gate']['gate_fingerprint'] != gate_fingerprint
            or authorization_status(BuildAuthorizationStore(root / 'build_authorizations.jsonl'),
                                    pursuit_ref=pursuit_ref, gate_fingerprint=gate_fingerprint) != 'approved'):
        raise CorrectionError('nouveau Cost Gate et USER GO valides requis')
    return spec


def correction_target(root, pursuit_ref, spec_ref, gate_fingerprint):
    """Retrouve la spécification et son manifeste déjà produits par l'arc."""
    spec = _target(root, pursuit_ref, spec_ref, gate_fingerprint)
    manifests = [f for f in _journal(root / 'build.jsonl')
                 if f.get('spec_ref') == spec_ref and f.get('status') == 'proposed']
    if len(manifests) != 1:
        raise CorrectionError('manifeste correctif absent ou ambigu')
    return spec, _required(manifests[0].get('build_id'))


@contextmanager
def _locked(root):
    """Verrou inter-processus POSIX, conservé pendant toute la tentative."""
    import fcntl
    fd = os.open(root / 'correction.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _events(root):
    path = root / 'correction_events.jsonl'
    return _journal(path) if path.exists() or path.is_symlink() else []


def _record(root, fact):
    """Intention durable avant tout outil ; aucune reprise automatique après crash."""
    fact = {'event_id': short_id('correv', fact), **fact}
    fd = os.open(root / 'correction_events.jsonl',
                 os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(fact, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    return fact


def _binding(spec, gate_fingerprint, ceiling_usd, max_calls, provider):
    if (isinstance(ceiling_usd, bool) or not isinstance(ceiling_usd, (float, int))
            or not math.isfinite(ceiling_usd) or ceiling_usd <= 0
            or type(max_calls) is not int or max_calls <= 0
            or (provider is not None and (not isinstance(provider, str) or not provider))):
        raise CorrectionError('budget ou sélection fournisseur invalide')
    return dict(spec_ref=spec['specification_id'], spec_sha256=digest(spec['specification']),
                gate_fingerprint=gate_fingerprint, ceiling_usd=ceiling_usd,
                max_calls=max_calls, build_provider=provider)


def authorize_correction(*, root: Path, pursuit_ref: str, correction_id: str,
                         spec_ref: str, gate_fingerprint: str, decision: str,
                         ceiling_usd: float, max_calls: int, build_provider=None,
                         actor=None, clock=_clock):
    """Décision explicite inerte, liée à une correction et à son budget cumulé."""
    if decision not in ('approved', 'declined'):
        raise CorrectionError('décision corrective invalide')
    with _locked(root):
        proposal = _load_proposal(root, pursuit_ref, correction_id)
        spec = _target(root, pursuit_ref, spec_ref, gate_fingerprint)
        source = _unique(_journal(root / 'site_build.jsonl'), 'build_id', proposal['source_build_ref'])
        if not source.get('spec_sha256') or digest(spec['specification']) == source['spec_sha256']:
            raise CorrectionError('spécification matériellement corrigée requise pour ce lot')
        if any(e.get('correction_id') == correction_id and e.get('kind') == 'claimed' for e in _events(root)):
            raise CorrectionError('tentative corrective déjà consommée')
        return _record(root, dict(kind='authorization', correction_id=correction_id,
                                 pursuit_ref=pursuit_ref, decision=decision, actor=declared_actor(actor),
                                 binding=_binding(spec, gate_fingerprint, ceiling_usd, max_calls, build_provider),
                                 as_of=clock()))


@contextmanager
def correction_attempt(*, root: Path, pursuit_ref: str, correction_id: str,
                       spec, gate_fingerprint: str, ceiling_usd: float, max_calls: int,
                       build_provider=None, clock=_clock):
    """Consomme une fois l'accord, préserve le workspace source et décrit la tentative.

    Le caller exécute le service de livraison existant. Le verrou protège les
    tentatives correctives entre elles ; l'isolation contre un autre processus
    écrivant arbitrairement le workspace n'est pas une garantie de ce lot.
    """
    with _locked(root):
        proposal = _load_proposal(root, pursuit_ref, correction_id)
        current_spec = _target(root, pursuit_ref, spec['specification_id'], gate_fingerprint)
        if current_spec != spec:
            raise CorrectionError('spécification exécutée divergente')
        source = _unique(_journal(root / 'site_build.jsonl'), 'build_id', proposal['source_build_ref'])
        if not source.get('spec_sha256') or digest(spec['specification']) == source['spec_sha256']:
            raise CorrectionError('spécification matériellement corrigée requise pour ce lot')
        binding = _binding(spec, gate_fingerprint, ceiling_usd, max_calls, build_provider)
        events = [e for e in _events(root) if e.get('correction_id') == correction_id]
        decisions = [e for e in events if e.get('kind') == 'authorization']
        if (not decisions or decisions[-1].get('decision') != 'approved'
                or decisions[-1].get('pursuit_ref') != pursuit_ref
                or decisions[-1].get('binding') != binding
                or any(e.get('kind') == 'claimed' for e in events)):
            raise CorrectionError('autorisation corrective absente, obsolète ou consommée')
        # Lecture stricte du ledger cumulatif : ne jamais ignorer une charge illisible.
        _journal(root / 'budget.jsonl')
        workspace = Workspace(root / 'correction_exec' / correction_id, 'site')
        if root.resolve() not in workspace.path.parents or workspace.path.exists():
            raise CorrectionError('workspace de tentative absent et confiné requis')
        _record(root, dict(kind='claimed', correction_id=correction_id, pursuit_ref=pursuit_ref,
                           authorization_ref=decisions[-1]['event_id'], binding=binding, as_of=clock()))
        attempt = {'workspace': workspace, 'parent_run_ref': proposal['parent_run_ref'],
                   'correction_id': correction_id, 'authorization_ref': decisions[-1]['event_id']}
        try:
            yield attempt
        except BaseException:
            _record(root, dict(kind='attempt_interrupted', correction_id=correction_id,
                               pursuit_ref=pursuit_ref, as_of=clock()))
            raise
        else:
            _record(root, dict(kind='attempt_completed', correction_id=correction_id,
                               pursuit_ref=pursuit_ref, run_ref=attempt.get('run_ref'),
                               status=attempt.get('status', 'unknown'), as_of=clock()))
