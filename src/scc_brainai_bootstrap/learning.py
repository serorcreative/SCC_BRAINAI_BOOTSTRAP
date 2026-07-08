"""LearningLayer — la chaîne apprenante câblée.

Branche la couche Learning (12) sur la **mémoire vivante du bootstrap** : le
``LearningEngine`` reçoit directement le ``BrainMemoryStore`` déjà initialisé, il
**lit** donc exactement le vécu accumulé par BrainAI (réponses du Kernel, traces
d'exécution ingérées) et en dérive des **apprentissages propositionnels** (signaux,
patterns, leçons, recommandations, hypothèses).

Garde-fous hérités de Learning : aucun apprentissage n'est appliqué ; tout est une
proposition traçable, révocable, soumise à **validation humaine**. Aucun composant
n'est modifié : tout passe par l'interface publique de Learning. L'état des
apprentissages est persisté sous `data/learning/`.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

from scc_brainai_bootstrap.core.config import BrainAIConfig


def _add_path(path) -> bool:
    if not path.exists():
        return False
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return True


class LearningLayer:
    def __init__(self, config: BrainAIConfig):
        self._config = config
        self._engine = None
        self._error = ""

    def _build(self, memory_store: Any) -> None:
        if self._engine is not None:
            return
        c = self._config
        if not _add_path(c.learning_src):
            raise RuntimeError(f"couche introuvable : {c.learning_src}")
        lmod = importlib.import_module("scc_brainai_learning")
        lcfg = lmod.LearningConfig(scc_root=c.scc_root, data_dir=c.learning_data_dir,
                                   as_of=c.as_of)
        # Le store est injecté : Learning lit la mémoire vivante du bootstrap.
        self._engine = lmod.LearningEngine(config=lcfg, memory_store=memory_store,
                                           autoload=True)

    def engine(self, memory_store: Any):
        """Construit (une fois) et retourne le moteur, ou None si indisponible."""
        try:
            self._build(memory_store)
            return self._engine
        except Exception as exc:  # noqa: BLE001 - dégradation gracieuse
            self._error = str(exc)
            return None

    def available(self, memory_store: Any) -> bool:
        return self.engine(memory_store) is not None

    @property
    def error(self) -> str:
        return self._error


__all__ = ["LearningLayer"]
