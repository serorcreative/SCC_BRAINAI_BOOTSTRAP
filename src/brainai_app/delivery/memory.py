"""Écriture mémoire **minimale** à la livraison — ``11_MEMORY`` / ``BrainMemoryStore`` (JALON 2, T5).

**Écriture seule.** Aucune récupération / recherche / rappel (la mémoire de récupération contextuelle reste J4).
On consigne, à la livraison, l'expérience propre du Kernel : projet/pursuit, décisions clés, résultat livré,
références artefact/preview, **provenance par IDs de faits**. Rien de sensible (le store caviarde de son côté).

Le store réel (``scc_brainai_memory``) est rendu importable par **injection de chemin** (``config.memory_src``),
exactement comme :class:`MemoryComponent`. En test, on injecte un **répertoire mémoire factice** (``data_dir``
temporaire) — jamais le ``data/`` réel. Ce module ne fabrique pas de mémoire : il **délègue** à ``record_event``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.config import BrainAIConfig


class MemoryUnavailable(RuntimeError):
    """``11_MEMORY`` n'a pas pu être raccordé (chemin absent/illisible). Jamais silencieux."""


def open_memory_store(data_dir: Path, *, config: Optional[BrainAIConfig] = None) -> Any:
    """Construit un ``BrainMemoryStore`` **réel** pointé sur ``data_dir`` (répertoire factice en test). Injection
    de chemin non invasive via ``config.memory_src``. Lève :class:`MemoryUnavailable` si indisponible."""
    cfg = config or BrainAIConfig()
    src = str(cfg.memory_src)
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        mem = importlib.import_module("scc_brainai_memory")
    except Exception as exc:  # noqa: BLE001
        raise MemoryUnavailable(f"11_MEMORY non raccordable ({src}) : {exc}") from exc
    memcfg = mem.MemoryConfig(data_dir=Path(data_dir))
    return mem.BrainMemoryStore(config=memcfg)


def write_delivery_memory(store: Any, *, pursuit_ref: str, project: str, result: str,
                          decisions: List[str], artifact_ref: Any, preview_ref: Any,
                          provenance_ids: Dict[str, Any], actor: str = "brainai",
                          as_of: str = "") -> Any:
    """Écrit **un** événement mémoire minimal de livraison via ``store.record_event`` (écriture seule).

    ``provenance_ids`` : IDs des faits sources (build, verification, delivered, tool, confirmation…) — la mémoire
    pointe la provenance, elle ne la duplique pas. Ne lit jamais la mémoire. Renvoie l'entrée écrite (ou son reflet)."""
    data = {
        "pursuit_ref": pursuit_ref,
        "project": project,
        "result": result,
        "decisions": list(decisions),
        "artifact_ref": artifact_ref,
        "preview_ref": preview_ref,
        "provenance_ids": dict(provenance_ids),
        "as_of": as_of,
    }
    return store.record_event("pursuit_delivered", data, actor=actor,
                              tags=["jalon2", "delivered", "pursuit"])


__all__ = ["MemoryUnavailable", "open_memory_store", "write_delivery_memory"]
