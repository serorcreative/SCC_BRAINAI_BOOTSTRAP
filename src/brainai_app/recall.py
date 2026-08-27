"""L4 — rappel en lecture d'une Pursuit mémorisée (CONNECTER, PAS RECONSTRUIRE).

Lecture seule. Réutilise :
- le **rappel Memory-11 existant** (``store.search`` par subtype/tag) pour retrouver la continuité d'une
  Pursuit livrée (raccord L3), en couvrant aussi la compat historique (``data.pursuit_ref``) ;
- le **mécanisme d'arc existant** (``TurnStore`` + le MÊME filtre que le moteur ``_history``) pour dire si
  la Pursuit est **réellement reprenable** — la simple existence d'un répertoire ne suffit pas.

Ne modifie ni Memory-11 ni l'arc ; n'effectue **aucune** reprise (déléguée aux chemins Core existants
``realize`` / ``converse``). Toute corruption Memory-11 est remontée **fail-closed** (jamais avalée).
Aucune fabrication : un champ absent est projeté à ``None``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from brainai_app.delivery.memory import open_memory_store

# Continuité projetée depuis le dernier pursuit_delivered valide (aucune fabrication ; None si absent).
_CONTINUITY_FIELDS = ("need", "result", "status", "as_of", "artifact_ref", "preview_ref", "provenance_ids")


def read_pursuit_delivery(store: Any, pursuit_ref: str) -> List[Dict[str, Any]]:
    """Faits ``pursuit_delivered`` d'une Pursuit : union du rappel L3 (tag ``pursuit:<ref>``) et de la
    compat historique (subtype + ``data.pursuit_ref == ref``), **dédupliqués par ``MemoryEntry.id``** puis
    **triés déterministiquement par id** (le dernier = état le plus récent). ``limit=0`` : aucun plafond
    silencieux (l'exactitude de ``events_count``/dernier prime sur la limite d'affichage par défaut)."""
    by_tag = store.search(subtype="pursuit_delivered", tag=f"pursuit:{pursuit_ref}", limit=0)
    fallback = [e for e in store.search(subtype="pursuit_delivered", limit=0)
                if (e.get("data") or {}).get("pursuit_ref") == pursuit_ref]
    merged: Dict[str, Dict[str, Any]] = {}
    for e in list(by_tag) + list(fallback):
        merged[e["id"]] = e                          # dédup par id (un événement L3 apparaît dans les deux)
    return [merged[k] for k in sorted(merged)]       # tri déterministe par id


def _project_continuity(entry: Dict[str, Any]) -> Dict[str, Any]:
    data = entry.get("data") or {}
    return {k: data.get(k) for k in _CONTINUITY_FIELDS}     # None si absent — jamais fabriqué


def _resolve_pursuit_dir_readonly(pursuit_ref: str) -> Optional[Path]:
    """Résout le répertoire d'arc **sans effet de bord** (contrairement à ``_session_dir`` qui matérialise
    un dossier) : cache mémoire, puis chemin déterministe, puis index legacy — uniquement s'ils EXISTENT."""
    from brainai_app import composition as C
    with C._SESSIONS_LOCK:
        cached = C._SESSIONS.get(pursuit_ref)
    if cached is not None and Path(cached).exists():
        return Path(cached)
    det = C._pursuit_dir(pursuit_ref)
    if det.exists():
        return det
    legacy = C._legacy_lookup(pursuit_ref)
    if legacy is not None and Path(legacy).exists():
        return Path(legacy)
    return None


def _resumable_arc(pursuit_ref: str) -> bool:
    """Reprenable ⇔ il existe au moins un tour d'arc **utile** pour cette Pursuit, selon le **même critère
    que le moteur** (:meth:`BrainAI._history`) : ``turn["pursuit_ref"] == ref and turn["status"] == "proposed"``.
    On lit l'arc par ``TurnStore`` (source de vérité), pas par la seule présence du répertoire."""
    d = _resolve_pursuit_dir_readonly(pursuit_ref)
    if d is None:
        return False
    from scc_brainai_bootstrap.builder.turns import TurnStore
    turns = TurnStore(d / "turns.jsonl").read_all()
    return any(t.get("pursuit_ref") == pursuit_ref and t.get("status") == "proposed" for t in turns)


def retrieve_pursuit(pursuit_ref: str) -> Dict[str, Any]:
    """Retrouve + résume la continuité Memory-11 d'une Pursuit, et indique **indépendamment** si son arc est
    reprenable — sans effectuer la reprise.

    - ``found`` : une continuité Memory-11 existe pour cette Pursuit ;
    - ``continuity`` : projection du **dernier** ``pursuit_delivered`` valide (None si aucun) ;
    - ``memory_ids`` : IDs Memory-11 dédupliqués sous-jacents ;
    - ``events_count`` : nombre réel d'événements dédupliqués ;
    - ``resumable`` : un arc réellement reprenable existe (critère moteur) — indépendant de ``found`` ;
    - ``resume_hint`` : chemins Core existants pour reprendre (aucune reprise ici).

    Lecture seule ; remonte fail-closed toute corruption Memory-11 (``MemoryCorruption``)."""
    from brainai_app.composition import _state_root
    store = open_memory_store(_state_root() / "memory")     # peut lever (fail-closed) : MemoryUnavailable / MemoryCorruption
    events = read_pursuit_delivery(store, pursuit_ref)
    latest = events[-1] if events else None
    resumable = _resumable_arc(pursuit_ref)
    return {
        "pursuit_ref": pursuit_ref,
        "found": bool(events),
        "continuity": _project_continuity(latest) if latest is not None else None,
        "memory_ids": [e["id"] for e in events],
        "events_count": len(events),
        "resumable": resumable,
        "resume_hint": ("realize(pursuit_ref) | converse(message, pursuit_ref=pursuit_ref)"
                        if resumable else None),
    }


__all__ = ["retrieve_pursuit", "read_pursuit_delivery"]
