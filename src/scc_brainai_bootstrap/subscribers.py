"""Abonnés de l'Event Bus — le bus devient vivant.

Deux abonnés branchés par le bootstrap :

* :class:`EventRecorder` — persiste tous les événements du bus en JSONL (journal
  d'observabilité append-only, déterministe) ;
* :class:`LifecycleWatcher` — surveille le flux et lève des **alertes** sur les
  topics d'échec (étape KO, Kernel indisponible, démarrage dégradé, mémorisation
  échouée).

Ces abonnés démontrent que le bus est un vrai point d'abonnement pour l'observabilité
et les couches supérieures. Aucun composant n'est modifié.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class EventRecorder:
    """Persiste les événements du bus (journal d'observabilité déterministe)."""

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        self._dumped = 0    # curseur de persistance : nb d'événements DÉJÀ écrits sur disque

    def on_event(self, event: Dict[str, Any]) -> None:
        self._events.append(event)

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def dump(self, path: Path) -> Path:
        """Persiste le journal en JSONL **append-only** (jamais de troncature).

        N'écrit que les événements **nouveaux** depuis le dernier ``dump`` (curseur ``_dumped``) : un second
        ``dump`` **n'efface pas** le premier, et n'introduit aucune duplication intra-processus. Un processus
        neuf (recorder neuf, curseur à 0) **ajoute** ses événements à la suite du journal existant — l'ancien
        comportement ``write_text`` tronquait le journal à chaque processus (bug de traçabilité, REVUE 6 août)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        new = self._events[self._dumped:]
        if new:
            with path.open("a", encoding="utf-8") as fh:
                for e in new:
                    fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            self._dumped = len(self._events)
        return path


# Topics considérés comme des signaux d'échec (+ sévérité).
_ALERTS = {
    "kernel.unavailable": "error",
    "experience.record_failed": "warning",
}


class LifecycleWatcher:
    """Surveille le cycle de vie et lève des alertes déterministes."""

    def __init__(self) -> None:
        self._alerts: List[Dict[str, Any]] = []
        self._ready_seen = False

    def on_event(self, event: Dict[str, Any]) -> None:
        topic, payload = event["topic"], event.get("payload", {})
        if topic.startswith("boot.") and payload.get("ok") is False:
            self._raise(event, "warning", f"étape KO : {topic[5:]} — {payload.get('detail','')}")
        elif topic in _ALERTS:
            self._raise(event, _ALERTS[topic], payload.get("detail", topic))
        elif topic == "brainai.ready":
            self._ready_seen = True
            if payload.get("ready") is False:
                self._raise(event, "warning",
                            f"démarrage dégradé : {', '.join(payload.get('degraded', []))}")

    def _raise(self, event: Dict[str, Any], severity: str, detail: str) -> None:
        self._alerts.append({"seq": event["seq"], "topic": event["topic"],
                             "severity": severity, "detail": detail})

    @property
    def alerts(self) -> List[Dict[str, Any]]:
        return list(self._alerts)

    @property
    def ready_seen(self) -> bool:
        return self._ready_seen

    def summary(self) -> Dict[str, Any]:
        by_sev: Dict[str, int] = {}
        for a in self._alerts:
            by_sev[a["severity"]] = by_sev.get(a["severity"], 0) + 1
        return {"ready_seen": self._ready_seen, "alert_count": len(self._alerts),
                "by_severity": dict(sorted(by_sev.items())), "alerts": self.alerts}


__all__ = ["EventRecorder", "LifecycleWatcher"]
