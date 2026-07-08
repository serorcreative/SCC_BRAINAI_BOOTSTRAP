"""Adaptateurs & résolution par capacité — la **liaison** vers les implémentations.

Le registre décrit ; l'**adaptateur** relie une description à une implémentation
concrète, de façon **paresseuse** : l'implémentation (un moteur, un service, un modèle)
n'est chargée qu'à l'invocation, jamais au démarrage. C'est le **seul** endroit où un
agent réel est atteint — ``Bootstrap → Registry → Adapter → Agent``.

Découplage : l'adaptateur ne connaît qu'un **binder** (callable zéro-argument fourni à
l'enregistrement) qui retourne l'implémentation. Le code du registre n'importe donc
aucun moteur ; les imports restent chez celui qui enregistre le binder.

``CapabilityResolver`` choisit, pour une capacité, le **fournisseur** retenu parmi N,
par une politique **déterministe pilotée par les métadonnées** (priorité, fiabilité,
id) — aucune règle spécifique à un fournisseur n'est codée en dur.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from scc_brainai_bootstrap.registry.descriptor import AgentDescriptor


class AgentAdapter:
    """Liaison paresseuse entre un descripteur et son implémentation."""

    def __init__(self, descriptor: AgentDescriptor,
                 binder: Optional[Callable[[], Any]] = None):
        self.descriptor = descriptor
        self._binder = binder
        self._bound: Any = None
        self._tried = False

    @property
    def has_binder(self) -> bool:
        return self._binder is not None

    def bind(self) -> Any:
        """Charge l'implémentation à la demande (une seule fois), ou None."""
        if not self._tried:
            self._tried = True
            if self._binder is not None:
                try:
                    self._bound = self._binder()
                except Exception:  # noqa: BLE001 - dégradation gracieuse
                    self._bound = None
        return self._bound

    def available(self) -> bool:
        if self.descriptor.availability == "unavailable":
            return False
        return self.bind() is not None


class AdapterRegistry:
    """Enregistrement **découplé** des binders (id d'agent → callable d'implémentation)."""

    def __init__(self) -> None:
        self._binders: Dict[str, Callable[[], Any]] = {}

    def register(self, agent_id: str, binder: Callable[[], Any]) -> None:
        self._binders[agent_id] = binder

    def has(self, agent_id: str) -> bool:
        return agent_id in self._binders

    def adapter_for(self, descriptor: AgentDescriptor) -> AgentAdapter:
        return AgentAdapter(descriptor, self._binders.get(descriptor.id))

    @property
    def ids(self) -> List[str]:
        return sorted(self._binders)


class CapabilityResolver:
    """Résout une capacité vers un fournisseur retenu (parmi plusieurs possibles)."""

    def __init__(self, registry, adapters: AdapterRegistry):
        self._registry = registry
        self._adapters = adapters

    def providers(self, capability: str) -> List[AgentDescriptor]:
        return self._registry.by_capability(capability)

    def resolve(self, capability: str) -> Dict[str, Any]:
        """Sélectionne le **premier fournisseur disponible** dans l'ordre de préférence
        (priorité, fiabilité, id). Retourne le candidat retenu et la liste complète."""
        candidates = self._registry.by_capability(capability)
        detailed: List[Dict[str, Any]] = []
        selected: Optional[str] = None
        for desc in candidates:
            adapter = self._adapters.adapter_for(desc)
            available = adapter.available()
            detailed.append({"id": desc.id, "namespace": desc.namespace,
                             "provider": desc.provider, "priority": desc.priority,
                             "bound": adapter.has_binder, "available": available})
            if selected is None and available:
                selected = desc.id
        return {
            "capability": capability,
            "selected": selected,
            "resolved": selected is not None,
            "provider_count": len(candidates),
            "candidates": detailed,
        }


__all__ = ["AgentAdapter", "AdapterRegistry", "CapabilityResolver"]
