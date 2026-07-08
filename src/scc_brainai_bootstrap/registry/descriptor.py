"""AgentDescriptor — la **description** d'un agent (données pures, jamais de logique).

Le descripteur porte l'identité, les capacités et les métadonnées d'un agent. Il ne
contient aucune implémentation : le Bootstrap et le registre ne dépendent que de lui.
Le schéma est **forward-compatible** — des métadonnées d'orchestration (provider, coût,
latence, priorité, disponibilité, fiabilité, confidentialité, contraintes) sont prévues
mais facultatives, et un sac ``extra`` absorbe tout champ futur sans casser le modèle.

Déterminisme : capacités triées, id dérivé du contenu si absent, empreinte de contenu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import digest, short_id


class AgentState:
    """Cycle de vie gouverné d'un agent dans le catalogue."""
    PROPOSED = "proposed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    ALL = (PROPOSED, ACTIVE, DEPRECATED, RETIRED)


class Autonomy:
    """Niveaux d'autonomie suggérés (valeurs ouvertes ; les fiches SCC utilisent A0..A4)."""
    OBSERVE = "observe"
    SUGGEST = "suggest"
    ACT_WITH_VALIDATION = "act_with_validation"
    AUTONOMOUS = "autonomous"


@dataclass
class AgentDescriptor:
    # -- identité ------------------------------------------------------- #
    id: str = ""
    namespace: str = "brainai"           # brainai, scc, domoo, transalyn, …
    name: str = ""
    role: str = ""
    version: str = "0.0.0"
    description: str = ""
    # -- fonction ------------------------------------------------------- #
    capabilities: List[str] = field(default_factory=list)   # slugs domaine.action
    state: str = AgentState.PROPOSED
    autonomy: str = Autonomy.SUGGEST
    trust: str = ""                       # niveau de confiance requis (ex. fiches : T1..T3)
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)   # ids d'agents ou capacités
    # -- métadonnées d'orchestration (facultatives, prévues pour l'avenir) #
    provider: str = ""
    vendor: str = ""
    cost: Optional[float] = None
    latency: Optional[float] = None
    priority: int = 0                     # tri des fournisseurs (plus grand = préféré)
    availability: str = "unknown"         # available / unavailable / unknown
    reliability: Optional[float] = None
    confidentiality: str = ""
    constraints: List[str] = field(default_factory=list)
    # -- traçabilité ---------------------------------------------------- #
    source: str = ""
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    as_of: str = ""
    hash: str = ""
    id_generated: bool = False

    # -- déterminisme --------------------------------------------------- #
    def _identity(self) -> Dict[str, Any]:
        return {"namespace": self.namespace, "name": self.name, "role": self.role}

    def _content(self) -> Dict[str, Any]:
        # empreinte sémantique — n'inclut pas la provenance (chemin de fichier).
        return {
            "id": self.id, "namespace": self.namespace, "name": self.name,
            "role": self.role, "version": self.version, "description": self.description,
            "capabilities": sorted(self.capabilities), "state": self.state,
            "autonomy": self.autonomy, "trust": self.trust,
            "permissions": sorted(self.permissions), "dependencies": sorted(self.dependencies),
            "provider": self.provider, "vendor": self.vendor, "cost": self.cost,
            "latency": self.latency, "priority": self.priority,
            "availability": self.availability, "reliability": self.reliability,
            "confidentiality": self.confidentiality, "constraints": sorted(self.constraints),
            "tags": sorted(self.tags), "extra": self.extra,
        }

    def finalize(self, as_of: str = "") -> "AgentDescriptor":
        if as_of:
            self.as_of = as_of
        self.capabilities = sorted(set(self.capabilities))
        self.permissions = sorted(set(self.permissions))
        self.dependencies = sorted(set(self.dependencies))
        self.tags = sorted(set(self.tags))
        if not self.id:
            self.id = short_id("agent", self._identity())
            self.id_generated = True
        self.hash = digest(self._content())
        return self

    # -- requêtes ------------------------------------------------------- #
    def provides(self, capability: str) -> bool:
        return capability in self.capabilities

    def is_active(self) -> bool:
        return self.state == AgentState.ACTIVE

    # -- sérialisation -------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "namespace": self.namespace, "name": self.name,
            "role": self.role, "version": self.version, "description": self.description,
            "capabilities": list(self.capabilities), "state": self.state,
            "autonomy": self.autonomy, "trust": self.trust,
            "permissions": list(self.permissions), "dependencies": list(self.dependencies),
            "provider": self.provider, "vendor": self.vendor, "cost": self.cost,
            "latency": self.latency, "priority": self.priority,
            "availability": self.availability, "reliability": self.reliability,
            "confidentiality": self.confidentiality, "constraints": list(self.constraints),
            "source": self.source, "tags": list(self.tags), "extra": dict(self.extra),
            "as_of": self.as_of, "hash": self.hash, "id_generated": self.id_generated,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentDescriptor":
        known = {f for f in cls.__dataclass_fields__}      # noqa: E1101
        extra = dict(d.get("extra", {}) or {})
        # tout champ inconnu (schéma futur) est préservé dans extra.
        for k, v in d.items():
            if k not in known:
                extra[k] = v
        return cls(
            id=str(d.get("id", "")), namespace=str(d.get("namespace", "brainai")),
            name=str(d.get("name", "")), role=str(d.get("role", "")),
            version=str(d.get("version", "0.0.0")), description=str(d.get("description", "")),
            capabilities=list(d.get("capabilities", []) or []),
            state=str(d.get("state", AgentState.PROPOSED)),
            autonomy=str(d.get("autonomy", Autonomy.SUGGEST)), trust=str(d.get("trust", "")),
            permissions=list(d.get("permissions", []) or []),
            dependencies=list(d.get("dependencies", []) or []),
            provider=str(d.get("provider", "")), vendor=str(d.get("vendor", "")),
            cost=d.get("cost"), latency=d.get("latency"), priority=int(d.get("priority", 0)),
            availability=str(d.get("availability", "unknown")), reliability=d.get("reliability"),
            confidentiality=str(d.get("confidentiality", "")),
            constraints=list(d.get("constraints", []) or []),
            source=str(d.get("source", "")), tags=list(d.get("tags", []) or []),
            extra=extra,
        )


__all__ = ["AgentDescriptor", "AgentState", "Autonomy"]
