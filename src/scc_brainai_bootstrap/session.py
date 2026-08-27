"""SessionStore — continuité de session (mode « live »).

Chaque invocation de BrainAI démarre un processus neuf ; sans état de session, ces
invocations seraient des one-shots isolés. Le ``SessionStore`` persiste un **manifeste
de session** (`data/session.json`) qui **survit aux redémarrages** : identité stable de
la session, **compteur de démarrages**, dernier état de démarrage et **totaux d'activité
cumulés**. Les invocations successives forment ainsi une **session continue**.

Déterminisme : identité dérivée du contenu (jamais de l'horodatage machine), `as_of`
figé, compteurs dérivés de l'état persisté — aucune horloge murale. Stdlib pur.

L2 store-safety : toute mutation suit LOCK → RELOAD → VALIDATE → MUTATE → ATOMIC_WRITE
→ UNLOCK, sur un **lockfile dédié** (`session.lock`) et via écriture atomique. Un
``session.json`` présent mais corrompu/incohérent est **fail-closed** (:class:`SessionStateError`),
jamais réinitialisé silencieusement ; seule une **absence réelle** autorise la création.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from scc_brainai_bootstrap.core.atomicio import atomic_write_text
from scc_brainai_bootstrap.core.clock import short_id
from scc_brainai_bootstrap.core.config import BrainAIConfig
from scc_brainai_bootstrap.core.errors import SessionStateError
from scc_brainai_bootstrap.core.locking import StoreLock

# Activités cumulées au fil de la session (continuité observable).
ACTIVITIES = ("runs", "decisions", "plans", "executions", "learn_runs", "learnings_validated")


class SessionStore:
    def __init__(self, config: BrainAIConfig, lock_timeout: float = 10.0):
        self._config = config
        self._lock_timeout = float(lock_timeout)

    @property
    def path(self) -> Path:
        return self._config.data_dir / "session.json"

    def _lock_path(self) -> Path:
        # Lockfile DÉDIÉ (L2 §5) : jamais session.json, dont l'inode change à chaque os.replace.
        return self._config.data_dir / "session.lock"

    def _lock(self) -> StoreLock:
        self._config.ensure_directories()
        return StoreLock(self._lock_path(), timeout=self._lock_timeout)

    def load(self) -> Optional[Dict[str, Any]]:
        """Absence réelle → ``None`` (création autorisée). Présent mais illisible / JSON invalide /
        non-``dict`` / sans ``session_id`` non vide → :class:`SessionStateError` (fail-closed, aucun reset)."""
        p = self.path
        if not p.exists():
            return None                                                          # ABSENCE réelle
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise SessionStateError(f"session.json illisible : {exc}") from exc  # FAIL-CLOSED
        try:
            state = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SessionStateError(f"session.json JSON invalide : {exc}") from exc
        if not isinstance(state, dict):
            raise SessionStateError("session.json n'est pas un objet JSON")
        if not str(state.get("session_id", "")).strip():
            raise SessionStateError("session.json sans session_id (état incohérent)")
        return state

    def _save(self, state: Dict[str, Any]) -> None:
        self._config.ensure_directories()
        atomic_write_text(self.path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

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
        démarrages et met à jour l'instantané du dernier démarrage.

        L2 : LOCK → RELOAD → VALIDATE → MUTATE → ATOMIC_WRITE → UNLOCK. ``_new_state`` n'est
        créé que si le fichier est **réellement absent** ; une corruption lève (aucun reset)."""
        with self._lock():
            state = self.load()                         # lève sur corruption -> aucun reset
            if state is None:                           # création UNIQUEMENT si absence réelle
                state = self._new_state()
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
        """Incrémente un compteur d'activité (best-effort). Sans session **réellement** existante,
        no-op historique ; une corruption lève :class:`SessionStateError` (jamais silencieux)."""
        with self._lock():
            state = self.load()                         # lève sur corruption
            if state is None:                           # absence réelle -> no-op historique
                return
            totals = state.setdefault("totals", {})
            totals[activity] = int(totals.get(activity, 0)) + n
            self._save(state)

    def summary(self) -> Dict[str, Any]:
        state = self.load()                             # une corruption remonte (jamais "aucune session")
        if state is None:
            return {"exists": False}
        return {"exists": True, **state}


__all__ = ["SessionStore", "ACTIVITIES"]
