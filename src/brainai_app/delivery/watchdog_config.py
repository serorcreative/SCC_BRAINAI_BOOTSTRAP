"""Configuration **gouvernée** du **watchdog de sécurité** par appel (palier immédiat ; palier suivant = RS-059).

Le plafond wall-clock d'un appel outil n'est plus une **constante câblée** (l'ancien ``timeout=180`` était une
**échéance de cognition** qui coupait une réflexion longue mais saine) : c'est une **configuration explicite,
traçable et surchargeable** — argument explicite > variable d'environnement (``BRAINAI_CALL_WATCHDOG_S``) > défaut
(``DEFAULT_WATCHDOG_S`` = 3600 s), sur le **même patron** que ``budget_config`` (RS-047).

**Sémantique honnête (à ne pas travestir)** : ce plafond est un **fusible de dernier recours** contre un
sous-processus **abandonné / zombie**, **pas** une durée maximale de réflexion. Tant que l'infrastructure ne sait
pas distinguer *activité* de *blocage* (streaming + timeout d'inactivité + annulation = **RS-059**, palier suivant),
le plafond est fixé **très au-dessus** de toute cognition saine réaliste. Un dépassement est étiqueté
``safety_watchdog_exceeded`` (:data:`scc_brainai_bootstrap.builder.tool_runner.SAFETY_WATCHDOG_EXCEEDED`), jamais
« timeout de réflexion ». Un process **mort** (``exit_code != 0``) reste capté immédiatement et séparément. Stdlib pur.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from scc_brainai_bootstrap.builder.tool_runner import DEFAULT_WATCHDOG_S

ENV_WATCHDOG_S = "BRAINAI_CALL_WATCHDOG_S"


@dataclass(frozen=True)
class CallWatchdogConfig:
    """Watchdog de sécurité gouverné. ``role`` déclaré honnêtement : filet anti-zombie, **pas** une limite de
    cognition (``cognition_deadline=False``)."""

    timeout_s: float
    timeout_source: str                        # "explicit" | "env" | "default"
    role: str = "last_resort_safety_watchdog"
    cognition_deadline: bool = False           # JAMAIS une échéance de réflexion (RS-059 = vraie distinction)

    def to_dict(self) -> dict:
        return {"timeout_s": self.timeout_s, "timeout_source": self.timeout_source,
                "role": self.role, "cognition_deadline": self.cognition_deadline}


def load_call_watchdog(timeout_s: Optional[float] = None) -> CallWatchdogConfig:
    """Résout le watchdog : **explicite > env (``BRAINAI_CALL_WATCHDOG_S``) > défaut (3600 s)**, source tracée.

    Une valeur env/explicite **≤ 0** ou illisible est ignorée (repli sur le défaut) : on ne fabrique jamais un
    plafond absurde qui transformerait le fusible en cutoff de cognition."""
    if isinstance(timeout_s, (int, float)) and timeout_s > 0:
        return CallWatchdogConfig(timeout_s=float(timeout_s), timeout_source="explicit")
    raw = os.environ.get(ENV_WATCHDOG_S)
    if raw is not None:
        try:
            val = float(raw)
            if val > 0:
                return CallWatchdogConfig(timeout_s=val, timeout_source="env")
        except (TypeError, ValueError):
            pass
    return CallWatchdogConfig(timeout_s=float(DEFAULT_WATCHDOG_S), timeout_source="default")


__all__ = ["ENV_WATCHDOG_S", "CallWatchdogConfig", "load_call_watchdog"]
