"""AgentRegistry — le **catalogue déclaratif** des agents.

Charge des descripteurs depuis des sources pluggables, les indexe par **id**,
**capacité** et **namespace**, et répond aux requêtes d'orchestration. Il ne connaît
que des *descriptions* : aucune logique métier, aucun import de moteur.

Gouvernance : cycle de vie ``proposed → active → deprecated → retired`` avec transitions
tracées (activation par un approbateur identifié). Déterminisme : itérations triées,
identifiants dérivés du contenu, ``as_of`` figé. Garde-fou capacités : validation
**légère** du format (signalement non bloquant).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.config import BrainAIConfig
from scc_brainai_bootstrap.registry.capability import invalid_capabilities
from scc_brainai_bootstrap.registry.descriptor import AgentDescriptor, AgentState
from scc_brainai_bootstrap.registry.sources import DescriptorSource

_ALLOWED_TRANSITIONS = {
    AgentState.PROPOSED: {AgentState.ACTIVE, AgentState.RETIRED},
    AgentState.ACTIVE: {AgentState.DEPRECATED, AgentState.RETIRED},
    AgentState.DEPRECATED: {AgentState.ACTIVE, AgentState.RETIRED},
    AgentState.RETIRED: set(),
}


class AgentRegistry:
    def __init__(self, config: BrainAIConfig,
                 sources: Optional[List[DescriptorSource]] = None):
        self._config = config
        self._sources: List[DescriptorSource] = list(sources or [])
        self._by_id: Dict[str, AgentDescriptor] = {}
        self._registered: set = set()          # agents « premiers » activés au démarrage
        self._malformed: List[Dict[str, Any]] = []
        self._loaded = False

    def add_source(self, source: DescriptorSource) -> None:
        self._sources.append(source)
        self._loaded = False

    # -- chargement ----------------------------------------------------- #
    def load(self, force: bool = False) -> "AgentRegistry":
        if self._loaded and not force:
            return self
        self._by_id = {}
        self._malformed = []
        for src in self._sources:
            for desc in src.descriptors():
                desc.finalize(self._config.as_of)
                bad = invalid_capabilities(desc.capabilities)
                if bad:                        # garde-fou léger : signaler, ne pas bloquer
                    self._malformed.append({"agent": desc.id, "capabilities": bad})
                self._by_id[desc.id] = desc    # dernière source gagne (surcharge possible)
        self._loaded = True
        return self

    def _ensure(self) -> None:
        if not self._loaded:
            self.load()

    # -- consultation --------------------------------------------------- #
    def all(self) -> List[AgentDescriptor]:
        self._ensure()
        return [self._by_id[k] for k in sorted(self._by_id)]

    def get(self, agent_id: str) -> Optional[AgentDescriptor]:
        self._ensure()
        return self._by_id.get(agent_id)

    def by_namespace(self, namespace: str) -> List[AgentDescriptor]:
        return [d for d in self.all() if d.namespace == namespace]

    def by_capability(self, capability: str, active_only: bool = True) -> List[AgentDescriptor]:
        """Fournisseurs d'une capacité (many-to-many), triés par préférence."""
        out = [d for d in self.all()
               if d.provides(capability) and (not active_only or d.is_active())]
        # préférence : priorité décroissante, fiabilité décroissante, puis id.
        return sorted(out, key=lambda d: (-d.priority,
                                          -(d.reliability if d.reliability is not None else 0.0),
                                          d.id))

    def capabilities(self) -> Dict[str, List[str]]:
        """Index capacité → ids de fournisseurs (actifs), trié."""
        index: Dict[str, List[str]] = {}
        for d in self.all():
            if not d.is_active():
                continue
            for cap in d.capabilities:
                index.setdefault(cap, []).append(d.id)
        return {k: sorted(v) for k, v in sorted(index.items())}

    def namespaces(self) -> List[str]:
        return sorted({d.namespace for d in self.all()})

    def counts(self) -> Dict[str, Any]:
        self._ensure()
        by_state: Dict[str, int] = {}
        for d in self._by_id.values():
            by_state[d.state] = by_state.get(d.state, 0) + 1
        return {"agents": len(self._by_id), "capabilities": len(self.capabilities()),
                "namespaces": len(self.namespaces()), "by_state": dict(sorted(by_state.items()))}

    @property
    def malformed(self) -> List[Dict[str, Any]]:
        self._ensure()
        return list(self._malformed)

    # -- gouvernance (cycle de vie) ------------------------------------- #
    def transition(self, agent_id: str, target: str, approver: str,
                   reason: str = "") -> Dict[str, Any]:
        self._ensure()
        d = self._by_id.get(agent_id)
        if d is None:
            return {"ok": False, "error": f"agent introuvable : {agent_id}"}
        if target not in AgentState.ALL:
            return {"ok": False, "error": f"état inconnu : {target}"}
        if target not in _ALLOWED_TRANSITIONS.get(d.state, set()):
            return {"ok": False, "error": f"transition refusée : {d.state} → {target}"}
        if not approver:
            return {"ok": False, "error": "approbateur requis"}
        d.state = target
        d.extra.setdefault("governance", []).append(
            {"to": target, "by": approver, "reason": reason, "as_of": self._config.as_of})
        d.finalize(self._config.as_of)
        return {"ok": True, "agent": agent_id, "state": target}

    # -- démarrage (compat) : agents « premiers » ----------------------- #
    def register_first(self) -> List[AgentDescriptor]:
        """Active et recense les rôles pivots (``config.first_agents``) au démarrage."""
        self._ensure()
        for aid in self._config.first_agents:
            if aid not in self._by_id:         # fiche absente : descripteur placeholder
                self._by_id[aid] = AgentDescriptor(
                    id=aid, namespace="scc", name="(fiche absente)",
                    source="registry:placeholder").finalize(self._config.as_of)
            self._registered.add(aid)
        return [self._by_id[a] for a in sorted(self._registered)]

    def to_list(self) -> List[Dict[str, Any]]:
        self._ensure()
        return [self._by_id[a].to_dict() for a in sorted(self._registered)]

    # -- audit ---------------------------------------------------------- #
    def audit(self) -> Dict[str, Any]:
        self._ensure()
        ids_unique = len(self._by_id) == len({d.id for d in self._by_id.values()})
        return {
            "ok": ids_unique and not self._malformed,
            "ids_unique": ids_unique,
            "capabilities_well_formed": not self._malformed,
            "malformed": list(self._malformed),
            "counts": self.counts(),
        }


__all__ = ["AgentRegistry"]
