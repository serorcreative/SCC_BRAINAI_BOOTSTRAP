"""Configuration **gouvernée** du budget de livraison (JALON 3, T2 / RS-047).

Les plafonds de livraison ne sont plus des **constantes câblées** (``DELIVERY_CEILING_USD``/``DELIVERY_MAX_CALLS``)
mais une **configuration explicite, traçable et surchargeable** : argument explicite > variable d'environnement
(``BRAINAI_DELIVERY_CEILING_USD`` / ``BRAINAI_DELIVERY_MAX_CALLS``) > défaut. La ``source`` est consignée (gouvernance).

Rappel honnête (RS-039, ancré dans le contrat d'adaptateur) : ``max_calls`` est un **plafond DUR** (BrainAI contrôle
le nombre de franchissements) ; le plafond **USD** reste **best-effort borné** (arrêt agrégé du fournisseur), jamais
présenté comme « dur ». Stdlib pur.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_CEILING_USD = 3.0
DEFAULT_MAX_CALLS = 2
ENV_CEILING = "BRAINAI_DELIVERY_CEILING_USD"
ENV_MAX_CALLS = "BRAINAI_DELIVERY_MAX_CALLS"


@dataclass(frozen=True)
class DeliveryBudgetConfig:
    """Budget de livraison gouverné. ``usd_guarantee`` déclaré honnêtement (best-effort borné, RS-039)."""

    ceiling_usd: float
    max_calls: int
    ceiling_source: str          # "explicit" | "env" | "default"
    max_calls_source: str
    usd_guarantee: str = "best_effort_bounded"   # jamais « hard » (RS-039)
    call_guarantee: str = "hard"                  # compteur d'appels réellement dur

    def to_dict(self) -> dict:
        return {"ceiling_usd": self.ceiling_usd, "max_calls": self.max_calls,
                "ceiling_source": self.ceiling_source, "max_calls_source": self.max_calls_source,
                "usd_guarantee": self.usd_guarantee, "call_guarantee": self.call_guarantee}


def _resolve_float(explicit: Optional[float], env_name: str, default: float) -> tuple:
    if explicit is not None:
        return float(explicit), "explicit"
    env = os.environ.get(env_name)
    if env is not None:
        try:
            return float(env), "env"
        except ValueError:
            pass
    return float(default), "default"


def _resolve_int(explicit: Optional[int], env_name: str, default: int) -> tuple:
    if explicit is not None:
        return int(explicit), "explicit"
    env = os.environ.get(env_name)
    if env is not None:
        try:
            return int(env), "env"
        except ValueError:
            pass
    return int(default), "default"


def load_delivery_budget(*, ceiling_usd: Optional[float] = None,
                         max_calls: Optional[int] = None) -> DeliveryBudgetConfig:
    """Résout le budget de livraison **gouverné** (explicite > env > défaut), avec traçabilité de la source. Le
    plafond USD résolu est **borné** au défaut (garde-fou de sûreté : une config ne peut pas dépasser 3 $ sans acte
    explicite ; un plafond explicite plus haut est respecté mais tracé ``explicit``)."""
    ceil, ceil_src = _resolve_float(ceiling_usd, ENV_CEILING, DEFAULT_CEILING_USD)
    calls, calls_src = _resolve_int(max_calls, ENV_MAX_CALLS, DEFAULT_MAX_CALLS)
    # garde-fou : une valeur env/défaut ne dépasse jamais le plafond de sûreté ; l'explicite peut, mais c'est tracé.
    if ceil_src != "explicit":
        ceil = min(ceil, DEFAULT_CEILING_USD)
    ceil = max(0.01, ceil)
    calls = max(1, calls)
    return DeliveryBudgetConfig(ceiling_usd=ceil, max_calls=calls,
                                ceiling_source=ceil_src, max_calls_source=calls_src)


__all__ = ["DeliveryBudgetConfig", "load_delivery_budget", "DEFAULT_CEILING_USD", "DEFAULT_MAX_CALLS",
           "ENV_CEILING", "ENV_MAX_CALLS"]
