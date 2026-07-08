"""Registre d'agents déclaratif & orienté capacités.

Catalogue **déclaratif** des agents disponibles pour BrainAI (et, à terme, pour tout
l'écosystème SCC). Il **décrit** les agents — id, rôle, capacités, métadonnées — sans
jamais intégrer leur logique métier. Le raisonnement de routage s'appuie sur les
**capacités** (`domaine.action`), une capacité pouvant avoir plusieurs fournisseurs.

Découplage strict : ``Bootstrap → Registry → Adapter → Agent``. Le registre n'importe
aucun moteur ; l'import d'une implémentation n'a lieu que dans son **adaptateur**, à
l'invocation. Ajouter un agent = ajouter une **description** (+ un adaptateur si besoin),
sans modifier le Bootstrap. Déterministe, gouverné, générique (multi-projets).
"""

from __future__ import annotations

from scc_brainai_bootstrap.registry.adapter import (
    AdapterRegistry,
    AgentAdapter,
    CapabilityResolver,
)
from scc_brainai_bootstrap.registry.capability import (
    capability_domain,
    invalid_capabilities,
    is_valid_capability,
)
from scc_brainai_bootstrap.registry.descriptor import (
    AgentDescriptor,
    AgentState,
    Autonomy,
)
from scc_brainai_bootstrap.registry.registry import AgentRegistry
from scc_brainai_bootstrap.registry.sources import (
    DescriptorSource,
    FicheSource,
    ManifestSource,
)

__all__ = [
    "AgentDescriptor",
    "AgentState",
    "Autonomy",
    "AgentRegistry",
    "DescriptorSource",
    "ManifestSource",
    "FicheSource",
    "AgentAdapter",
    "AdapterRegistry",
    "CapabilityResolver",
    "is_valid_capability",
    "capability_domain",
    "invalid_capabilities",
]
