"""Adaptateurs des composants réutilisés — initialisation via interfaces publiques.

Chaque adaptateur localise dynamiquement le ``src/`` d'un composant existant, l'importe
et l'initialise **sans le modifier**. Tolérant : un composant absent est signalé
(``ready=False``) sans faire échouer le démarrage global (mode dégradé).
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, Optional

from scc_brainai_bootstrap.core.config import BrainAIConfig


def _add_path(path) -> bool:
    if not path.exists():
        return False
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return True


class ControlPlaneComponent:
    name = "control_plane"

    def __init__(self, config: BrainAIConfig):
        self._config = config
        self.instance = None

    def init(self) -> Dict[str, Any]:
        if not _add_path(self._config.control_plane_src):
            return {"name": self.name, "ready": False, "detail": "src introuvable"}
        try:
            cp = importlib.import_module("scc_control_plane").ControlPlane()
            health = cp.health()
            self.instance = cp
            return {"name": self.name, "ready": True,
                    "detail": f"santé={health.get('overall')}",
                    "data": {"overall": health.get("overall")}}
        except Exception as exc:  # noqa: BLE001
            return {"name": self.name, "ready": False, "detail": str(exc)}


class MemoryComponent:
    name = "memory"

    def __init__(self, config: BrainAIConfig):
        self._config = config
        self.store = None

    def init(self) -> Dict[str, Any]:
        if not _add_path(self._config.memory_src):
            return {"name": self.name, "ready": False, "detail": "src introuvable"}
        try:
            if self.store is None:      # idempotent : une seule instance de store par process
                mem = importlib.import_module("scc_brainai_memory")
                cfg = mem.MemoryConfig(data_dir=self._config.memory_data_dir)
                self.store = mem.BrainMemoryStore(config=cfg)
            counts = self.store.counts()
            return {"name": self.name, "ready": True,
                    "detail": f"entrées={sum(counts.values())}", "data": {"counts": counts}}
        except Exception as exc:  # noqa: BLE001
            return {"name": self.name, "ready": False, "detail": str(exc)}


class KnowledgeComponent:
    name = "knowledge"

    def __init__(self, config: BrainAIConfig):
        self._config = config
        self.engine = None

    def init(self) -> Dict[str, Any]:
        if not _add_path(self._config.knowledge_src):
            return {"name": self.name, "ready": False, "detail": "src introuvable"}
        try:
            engine_mod = importlib.import_module("scc_knowledge.engine")
            cfg_mod = importlib.import_module("scc_knowledge.core.config")
            root = self._config.knowledge_root
            cfg = cfg_mod.KnowledgeConfig(
                engine_root=root, knowledge_path=root / "knowledge.json",
                graph_path=root / "graph.json")
            self.engine = engine_mod.KnowledgeEngine(config=cfg)
            return {"name": self.name, "ready": True,
                    "detail": f"entrées={self.engine.count()}",
                    "data": {"entries": self.engine.count()}}
        except Exception as exc:  # noqa: BLE001
            return {"name": self.name, "ready": False, "detail": str(exc)}


class KernelComponent:
    name = "kernel"

    def __init__(self, config: BrainAIConfig):
        self._config = config
        self.kernel = None

    def init(self) -> Dict[str, Any]:
        if not _add_path(self._config.kernel_src):
            return {"name": self.name, "ready": False, "detail": "src introuvable"}
        try:
            self.kernel = importlib.import_module("scc_brainai").BrainAIKernel()
            providers = self.kernel.providers.available()
            return {"name": self.name, "ready": True,
                    "detail": f"providers={providers}", "data": {"providers": providers}}
        except Exception as exc:  # noqa: BLE001
            return {"name": self.name, "ready": False, "detail": str(exc)}


__all__ = ["ControlPlaneComponent", "MemoryComponent", "KnowledgeComponent", "KernelComponent"]
