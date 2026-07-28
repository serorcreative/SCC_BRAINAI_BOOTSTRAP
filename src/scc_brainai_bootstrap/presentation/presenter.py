"""Presentation — la couche officielle de présentation de BrainAI.

**Unique frontière** entre le Bootstrap (le cerveau) et toutes les interfaces futures
(CLI, Web, Desktop, Mobile, API REST). Elle **présente** les opérations déjà publiques
du Bootstrap sous une API stable et versionnée (voir ``contract``).

Discipline (garde-fous) :

* **aucune logique métier** — chaque méthode est une délégation de 1–2 lignes ;
* **elle ne décide jamais** — les actions sont de simples transferts vers des appels
  publics du Bootstrap, qui portent seuls la gouvernance ;
* **elle ne modifie jamais** un moteur ;
* **aucune duplication** — ``data`` réutilise telles quelles les sorties du Bootstrap ;
* **aucune dépendance UI / réseau / framework** — stdlib pur.

Sens de dépendance : ``Presentation`` dépend du Bootstrap ; **jamais l'inverse**.

Couture d'extraction (documentée) : cette couche ne dépend que de l'API **publique** du
Bootstrap + stdlib. Le jour où un critère est atteint (contrat éprouvé par ≥ 1 interface
réelle, ou 2ᵉ consommateur, ou versionnement indépendant requis), le sous-paquet
``presentation/`` se déplace quasi tel quel vers un dépôt ``SCC_BRAINAI_PRESENTATION``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import scc_brainai_bootstrap.presentation.contract as contract
from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.core.config import BrainAIConfig, load_config


class Presentation:
    def __init__(self, bootstrap: Optional[BrainAIBootstrap] = None,
                 config: Optional[BrainAIConfig] = None):
        self._boot = bootstrap or BrainAIBootstrap(config=config or load_config())

    # -- introspection du contrat --------------------------------------- #
    @property
    def bootstrap(self) -> BrainAIBootstrap:
        return self._boot

    @property
    def contract_version(self) -> str:
        return contract.CONTRACT_VERSION

    def describe(self) -> Dict[str, Any]:
        return contract.describe()

    def _wrap(self, operation: str, data: Any) -> Dict[str, Any]:
        return contract.envelope(operation, data, self._boot.config.as_of)

    # -- lectures (aucun effet de bord sur le domaine) ------------------ #
    def overview(self) -> Dict[str, Any]:
        return self._wrap("overview", self._boot.overview())

    def doctor(self) -> Dict[str, Any]:
        return self._wrap("doctor", self._boot.doctor())

    def session(self) -> Dict[str, Any]:
        return self._wrap("session", self._boot.session_summary())

    def agents(self, namespace: str = None, capability: str = None) -> Dict[str, Any]:
        return self._wrap("agents", self._boot.agents_catalog(namespace=namespace,
                                                              capability=capability))

    def capabilities(self) -> Dict[str, Any]:
        return self._wrap("capabilities", self._boot.capability_index())

    def resolve(self, capability: str) -> Dict[str, Any]:
        return self._wrap("resolve", self._boot.resolve_capability(capability))

    def status(self) -> Dict[str, Any]:
        return self._wrap("status", self._boot.status_summary())

    def learnings(self, kind: str = None, status: str = None) -> Dict[str, Any]:
        return self._wrap("learnings", self._boot.learnings(kind=kind, status=status))

    def events(self, topic: str = None) -> Dict[str, Any]:
        return self._wrap("events", self._boot.journal(topic=topic))

    def inputs(self) -> Dict[str, Any]:
        return self._wrap("inputs", self._boot.inputs())

    def input(self, input_id: str) -> Dict[str, Any]:
        return self._wrap("input", self._boot.input(input_id))

    def input_history(self, input_id: str) -> Dict[str, Any]:
        return self._wrap("input_history", self._boot.input_history(input_id))

    def input_analysis(self, input_id: str) -> Dict[str, Any]:
        return self._wrap("input_analysis", self._boot.input_analysis(input_id))

    def input_decisions(self, input_id: str) -> Dict[str, Any]:
        return self._wrap("input_decisions", self._boot.input_decisions(input_id))

    def journal_exists(self) -> bool:
        """Helper de lecture : le journal persistant existe-t-il ? (sans démarrer)."""
        return self._boot.events_path.exists()

    # -- actions (transfert vers un appel public ; jamais de décision propre) #
    def start(self, on_step: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        return self._wrap("start", self._boot.run(on_step=on_step))

    def run(self, query: str, route: str = "auto", deep: bool = False,
            record: bool = True, urgency: float = 0.3) -> Dict[str, Any]:
        return self._wrap("run", self._boot.run_query(query, route=route, deep=deep,
                                                      record=record, urgency=urgency))

    def decide(self, question: str, urgency: float = 0.3) -> Dict[str, Any]:
        return self._wrap("decide", self._boot.decide(question, urgency=urgency))

    def plan(self, objective: str) -> Dict[str, Any]:
        return self._wrap("plan", self._boot.plan(objective))

    def validate_decision(self, decision_id: str, approver: str, reason: str = "") -> Dict[str, Any]:
        return self._wrap("validate_decision",
                          self._boot.validate_decision(decision_id, approver, reason))

    def execute_decision(self, decision_id: str, actor: str) -> Dict[str, Any]:
        return self._wrap("execute_decision",
                          self._boot.execute_decision(decision_id, actor=actor))

    def learn(self) -> Dict[str, Any]:
        return self._wrap("learn", self._boot.learn())

    def validate_learning(self, item_id: str, approver: str, reason: str = "",
                          action: str = "validate") -> Dict[str, Any]:
        return self._wrap("validate_learning",
                          self._boot.validate_learning(item_id, approver, reason, action=action))

    def record_input(self, text: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        return self._wrap("record_input", self._boot.record_input(text, provenance))

    def analyze_input(self, input_id: str) -> Dict[str, Any]:
        return self._wrap("analyze_input", self._boot.analyze_input(input_id))

    def input_decide(self, input_id: str) -> Dict[str, Any]:
        return self._wrap("input_decide", self._boot.decide_from_input(input_id))

    def dossiers(self) -> Dict[str, Any]:
        return self._wrap("dossiers", self._boot.list_dossiers())

    def dossier(self, dossier_id: str) -> Dict[str, Any]:
        return self._wrap("dossier", self._boot.get_dossier(dossier_id))

    def dossier_inputs(self, dossier_id: str) -> Dict[str, Any]:
        return self._wrap("dossier_inputs", self._boot.dossier_inputs(dossier_id))

    def open_dossier(self, seed: str, correlation_key: str, actor: str) -> Dict[str, Any]:
        return self._wrap("open_dossier", self._boot.open_dossier(seed, correlation_key, actor))

    def attach_input(self, dossier_id: str, input_id: str, actor: str) -> Dict[str, Any]:
        return self._wrap("attach_input", self._boot.attach_input(dossier_id, input_id, actor))

    def detach_input(self, dossier_id: str, input_id: str, actor: str) -> Dict[str, Any]:
        return self._wrap("detach_input", self._boot.detach_input(dossier_id, input_id, actor))


__all__ = ["Presentation"]
