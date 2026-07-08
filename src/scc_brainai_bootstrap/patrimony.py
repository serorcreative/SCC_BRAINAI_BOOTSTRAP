"""Patrimony Manager — inventaire du **patrimoine** de BrainAI.

Le patrimoine est l'ensemble des composants et actifs dont BrainAI dispose : les
couches SCC (moteurs, Runtime, API, Control Plane, couches BrainAI) et les
catalogues. Le manager en tient un **inventaire en lecture seule** (présence,
emplacement, importabilité) — la connaissance qu'a BrainAI de ce dont il est fait.

Aucune écriture dans les composants ; simple recensement déterministe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.core.config import BrainAIConfig

# Patrimoine officiel : (nom logique, chemin relatif à scc_root, catégorie).
_PATRIMONY = [
    ("foundation", "00_SYSTEM/foundation", "socle"),
    ("orchestrator", "00_SYSTEM/orchestrator", "socle"),
    ("graph", "00_SYSTEM/graph", "savoir"),
    ("decisions", "00_SYSTEM/decisions", "gouvernance"),
    ("meta_model", "00_SYSTEM/meta_model", "savoir"),
    ("agents_catalog", "00_SYSTEM/agents", "catalogue"),
    ("engine_ingestion", "01_INGESTION", "moteur"),
    ("engine_extraction", "03_EXTRACTION", "moteur"),
    ("engine_knowledge", "04_KNOWLEDGE", "moteur"),
    ("engine_memory", "05_MEMORY", "moteur"),
    ("engine_reasoning", "06_REASONING", "moteur"),
    ("runtime", "07_RUNTIME", "execution"),
    ("api", "08_API", "exposition"),
    ("control_plane", "09_CONTROL_PLANE", "supervision"),
    ("brainai_kernel", "10_BRAINAI", "brainai"),
    ("brainai_memory", "11_BRAINAI_MEMORY", "brainai"),
    ("brainai_learning", "12_BRAINAI_LEARNING", "brainai"),
    ("brainai_reasoning", "13_BRAINAI_REASONING", "brainai"),
    ("brainai_planning", "14_BRAINAI_PLANNING", "brainai"),
    ("brainai_decision", "15_BRAINAI_DECISION", "brainai"),
    ("brainai_execution", "16_BRAINAI_EXECUTION", "brainai"),
]


@dataclass
class PatrimonyItem:
    name: str
    path: str
    category: str
    present: bool

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "path": self.path, "category": self.category,
                "present": self.present}


class PatrimonyManager:
    def __init__(self, config: BrainAIConfig):
        self._config = config
        self._items: List[PatrimonyItem] = []

    def inventory(self) -> List[PatrimonyItem]:
        if self._items:
            return self._items
        for name, rel, category in _PATRIMONY:
            present = (self._config.scc_root / rel).exists()
            self._items.append(PatrimonyItem(name, rel, category, present))
        return self._items

    def summary(self) -> Dict[str, Any]:
        items = self.inventory()
        present = sum(1 for i in items if i.present)
        by_category: Dict[str, int] = {}
        for i in items:
            by_category[i.category] = by_category.get(i.category, 0) + (1 if i.present else 0)
        return {
            "total": len(items),
            "present": present,
            "missing": [i.name for i in items if not i.present],
            "by_category": dict(sorted(by_category.items())),
            "items": [i.to_dict() for i in items],
        }


__all__ = ["PatrimonyItem", "PatrimonyManager"]
