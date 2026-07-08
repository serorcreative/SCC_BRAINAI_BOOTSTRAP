"""CognitiveStack — la grande boucle cognitive câblée.

Instancie et **relie** les couches Reasoning (13), Planning (14), Decision (15) et
Execution (16) via leurs interfaces publiques, en partageant les instances (les
passerelles pointent les unes vers les autres) et en dirigeant tout l'état vers le
dossier du bootstrap (`data/cognition/…`). Aucun composant n'est modifié.

Chaîne : délibérer (Reasoning) → formaliser une décision gouvernée (Decision) →
[validation humaine] → exécuter sous contrôle (Execution → Runtime).
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Optional

from scc_brainai_bootstrap.core.config import BrainAIConfig


def _add_path(path) -> bool:
    if not path.exists():
        return False
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return True


class CognitiveStack:
    def __init__(self, config: BrainAIConfig):
        self._config = config
        self._reasoning = None
        self._planning = None
        self._decision = None
        self._execution = None
        self._built = False
        self._error = ""

    # -- disponibilité --------------------------------------------------- #
    def available(self) -> bool:
        try:
            self._build()
            return self._built
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    @property
    def error(self) -> str:
        return self._error

    def _build(self) -> None:
        if self._built:
            return
        c = self._config
        for p in (c.reasoning_src, c.planning_src, c.decision_src, c.execution_src):
            if not _add_path(p):
                raise RuntimeError(f"couche introuvable : {p}")
        cog = c.cognition_data

        # Reasoning (13)
        rmod = importlib.import_module("scc_brainai_reasoning")
        rcfg = rmod.ReasoningConfig(data_dir=cog / "reasoning", ground_facts=False, as_of=c.as_of)
        self._reasoning = rmod.ReasoningEngine(config=rcfg)

        # Planning (14) — intègre Reasoning (instance partagée)
        pmod = importlib.import_module("scc_brainai_planning")
        insight_mod = importlib.import_module("scc_brainai_planning.sources.insight_source")
        pcfg = pmod.PlanningConfig(data_dir=cog / "planning", integrate_learning=False,
                                   integrate_reasoning=True, as_of=c.as_of)
        self._planning = pmod.PlanningEngine(
            config=pcfg, insight_source=insight_mod.InsightSource(pcfg, reasoning_engine=self._reasoning))

        # Decision (15) — passerelle vers Reasoning + Planning (instances partagées)
        dmod = importlib.import_module("scc_brainai_decision")
        dgw_mod = importlib.import_module("scc_brainai_decision.sources.decision_gateway")
        dcfg = dmod.DecisionConfig(data_dir=cog / "decision", integrate_learning=False, as_of=c.as_of)
        self._decision = dmod.DecisionEngine(
            config=dcfg, gateway=dgw_mod.DecisionGateway(
                dcfg, reasoning_engine=self._reasoning, planning_engine=self._planning))

        # Execution (16) — passerelle vers Decision + Planning (instances partagées)
        emod = importlib.import_module("scc_brainai_execution")
        egw_mod = importlib.import_module("scc_brainai_execution.sources.source_gateway")
        ecfg = emod.ExecutionConfig(data_dir=cog / "execution", integrate_decision=True,
                                    integrate_planning=True, as_of=c.as_of,
                                    authorized_actors=list(c.authorized_actors))
        self._execution = emod.ExecutionEngine(
            config=ecfg, gateway=egw_mod.SourceGateway(
                ecfg, decision_engine=self._decision, planning_engine=self._planning))

        self._built = True

    # -- accès aux moteurs ---------------------------------------------- #
    @property
    def reasoning(self):
        self._build(); return self._reasoning

    @property
    def planning(self):
        self._build(); return self._planning

    @property
    def decision(self):
        self._build(); return self._decision

    @property
    def execution(self):
        self._build(); return self._execution


__all__ = ["CognitiveStack"]
