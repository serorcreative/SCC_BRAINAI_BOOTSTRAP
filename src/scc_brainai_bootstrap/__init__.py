"""SCC BrainAI Bootstrap — le premier exécutable qui fait démarrer BrainAI.

Charge la configuration, initialise le Control Plane, le Patrimony Manager, Memory,
Knowledge et l'Event Bus, enregistre les premiers Agents, puis déclare « BrainAI
READY ». Réutilise les composants existants via leurs interfaces publiques, sans en
modifier aucun. Stdlib pur, déterministe, sans réseau.
"""

from __future__ import annotations

__version__ = "0.14.0"

from scc_brainai_bootstrap.bootstrap import READY_BANNER, BrainAIBootstrap
from scc_brainai_bootstrap.core.config import BrainAIConfig, load_config
from scc_brainai_bootstrap.event_bus import EventBus
from scc_brainai_bootstrap.patrimony import PatrimonyManager

__all__ = ["__version__", "BrainAIBootstrap", "READY_BANNER", "BrainAIConfig",
           "load_config", "EventBus", "PatrimonyManager"]
