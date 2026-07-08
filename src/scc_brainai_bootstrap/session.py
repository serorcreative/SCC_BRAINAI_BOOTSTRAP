"""SessionStore — continuité de session (mode « live »).

Chaque invocation de BrainAI démarre un processus neuf ; sans état de session, ces
invocations seraient des one-shots isolés. Le ``SessionStore`` persiste un **manifeste
de session** (`data/session.json`) qui **survit aux redémarrages** : identité stable de
la session, **compteur de démarrages**, dernier état de démarrage et **totaux d'activité
cumulés**. Les invocations successives forment ainsi une **session continue**.

Déterminisme : identité dérivée du contenu (jamais de l'horodatage machine), `as_of`
figé, compteurs dérivés de l'état persisté — aucune horloge murale. Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from scc_brainai_bootstrap.core.clock import short_id
from scc_brainai_bootstrap.core.config import BrainAIConfig

# Activités cumulées au fil de la session (continuité observable).
ACTIVITIES = ("runs", "decisions", "plans", "executions", "learn_runs", "learnings_validated")


class SessionStore:
    def __init__(self, config: BrainAIConfig):
        self._config = config

    @property
    def path(self) -> Path:
        return self._config.data_dir / "session.json"

    def load(self) -> Optional[Dict[str, Any]]:
        p = self.path
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _save(self, state: Dict[str, Any]) -> None:
        self._config.ensure_directories()
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    def _new_state(self) -> Dict[str, Any]:
        return {
            "session_id": short_id("ses", {"scc_root": str(self._config.scc_root),
                                           "as_of": self._config.as_of,
                                           "first_agents": list(self._config.first_agents)}),
            "created_as_of": self._config.as_of,
            "boots": 0,
            "totals": {k: 0 for k in ACTIVITIES},
        }

    def record_boot(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Enregistre (ou poursuit) la session au démarrage. Incrémente le compteur de
        démarrages et met à jour l'instantané du dernier démarrage."""
        state = self.load() or self._new_state()
        state["boots"] = int(state.get("boots", 0)) + 1
        state["last_as_of"] = self._config.as_of
        state["last_ready"] = bool(report.get("ready"))
        state["last_banner"] = report.get("banner")
        state["components"] = {s["name"]: s["ok"] for s in report.get("steps", [])}
        state["agents"] = [a.get("id") for a in report.get("agents", [])]
        pat = report.get("patrimony", {})
        state["patrimony"] = {"present": pat.get("present"), "total": pat.get("total")}
        totals = state.setdefault("totals", {})
        for k in ACTIVITIES:
            totals.setdefault(k, 0)
        self._save(state)
        return state

    def note(self, activity: str, n: int = 1) -> None:
        """Incrémente un compteur d'activité (best-effort ; sans session, no-op)."""
        state = self.load()
        if state is None:
            return
        totals = state.setdefault("totals", {})
        totals[activity] = int(totals.get(activity, 0)) + n
        self._save(state)

    def summary(self) -> Dict[str, Any]:
        state = self.load()
        if state is None:
            return {"exists": False}
        return {"exists": True, **state}


__all__ = ["SessionStore", "ACTIVITIES"]
