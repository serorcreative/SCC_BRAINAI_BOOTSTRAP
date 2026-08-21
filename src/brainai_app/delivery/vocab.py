"""Vocabulaire d'états run/étape — **enveloppe** le vrai ``16_EXECUTION`` (JALON 2, « 07_RUNTIME : ENVELOPPER … vocabulaire »).

Doctrine « connecter, pas reconstruire » : les statuts ne sont **pas recopiés** en dur. Ce module raccorde les
énumérations réelles ``RunStatus``/``StepStatus`` de ``scc_brainai_execution.core.model`` (source unique de
vérité) via injection de chemin (``config.execution_src``), exactement comme pour ``11_MEMORY``/``14_PLANNING``.

**Ce qui est REPRIS** (du sibling) : ``prepared``/``running``/``succeeded``/``failed``/``cancelled`` (run) et
``pending``/``running``/``succeeded``/``failed``/``skipped`` (étape). Le **scheduler** de ``16/07``, lui, est
**REMPLACÉ** (jamais patché) par le worker de :mod:`.runner` : on n'emprunte que le **modèle/vocabulaire**, pas
l'exécution — le sibling ne possède pas l'exécution subprocess réelle de J2.

**Extension J2 explicite** : ``interrupted`` (run laissé non terminal par un worker mort) n'existe pas dans
``RunStatus`` — c'est un ajout J2 (A2), déclaré ici sans prétendre qu'il vient du sibling. Si le sibling est
indisponible, on **lève** (jamais de vocabulaire fabriqué en silence)."""

from __future__ import annotations

import importlib
import sys
from typing import Any, Optional

from scc_brainai_bootstrap.core.config import BrainAIConfig


class ExecutionVocabUnavailable(RuntimeError):
    """``16_EXECUTION`` non raccordable (chemin absent/illisible). Jamais silencieux."""


def _load_execution_model(config: Optional[BrainAIConfig] = None) -> Any:
    cfg = config or BrainAIConfig()
    src = str(cfg.execution_src)
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        return importlib.import_module("scc_brainai_execution.core.model")
    except Exception as exc:  # noqa: BLE001
        raise ExecutionVocabUnavailable(f"16_EXECUTION non raccordable ({src}) : {exc}") from exc


_model = _load_execution_model()
RunStatus = _model.RunStatus
StepStatus = _model.StepStatus

# Statuts REPRIS du sibling (source unique de vérité — on lit .value, on ne réécrit pas la chaîne).
RUN_PREPARED = RunStatus.PREPARED.value
RUN_RUNNING = RunStatus.RUNNING.value
RUN_SUCCEEDED = RunStatus.SUCCEEDED.value
RUN_FAILED = RunStatus.FAILED.value
RUN_CANCELLED = RunStatus.CANCELLED.value

STEP_PENDING = StepStatus.PENDING.value
STEP_RUNNING = StepStatus.RUNNING.value
STEP_SUCCEEDED = StepStatus.SUCCEEDED.value
STEP_FAILED = StepStatus.FAILED.value
STEP_SKIPPED = StepStatus.SKIPPED.value

# Extension J2 (A2) — n'existe PAS dans RunStatus ; ajout honnête, non attribué au sibling.
RUN_INTERRUPTED = "interrupted"

RUN_TERMINAL = frozenset({RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED, RUN_INTERRUPTED})
STEP_TERMINAL = frozenset({STEP_SUCCEEDED, STEP_FAILED, STEP_SKIPPED})


__all__ = ["ExecutionVocabUnavailable", "RunStatus", "StepStatus",
           "RUN_PREPARED", "RUN_RUNNING", "RUN_SUCCEEDED", "RUN_FAILED", "RUN_CANCELLED", "RUN_INTERRUPTED",
           "STEP_PENDING", "STEP_RUNNING", "STEP_SUCCEEDED", "STEP_FAILED", "STEP_SKIPPED",
           "RUN_TERMINAL", "STEP_TERMINAL"]
