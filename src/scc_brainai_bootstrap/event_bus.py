"""Event Bus — bus d'événements en process (publish/subscribe, append-only).

Léger, déterministe (horodatage figé ``as_of``, séquence croissante), sans réseau.
Distinct du journal de jobs du Runtime : ce bus véhicule les événements du **cycle
de vie de BrainAI** (démarrage des sous-systèmes, enregistrement d'agents, READY) et
sert de point d'abonnement pour les couches supérieures.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List


class EventBus:
    def __init__(self, as_of: str):
        self._as_of = as_of
        self._events: List[Dict[str, Any]] = []
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._open = False

    def open(self) -> None:
        """Ouvre le bus aux abonnés externes (étape « Event Bus » du démarrage)."""
        self._open = True

    @property
    def is_open(self) -> bool:
        return self._open

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)

    def publish(self, topic: str, payload: Dict[str, Any] = None, actor: str = "brainai") -> Dict[str, Any]:
        event = {"seq": len(self._events) + 1, "topic": topic, "actor": actor,
                 "timestamp": self._as_of, "payload": dict(payload or {})}
        self._events.append(event)
        for sub in self._subscribers:
            sub(event)
        return event

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def by_topic(self, topic: str) -> List[Dict[str, Any]]:
        return [e for e in self._events if e["topic"] == topic]

    def __len__(self) -> int:
        return len(self._events)


__all__ = ["EventBus"]
