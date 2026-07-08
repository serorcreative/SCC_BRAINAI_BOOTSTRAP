"""Configuration du bootstrap BrainAI (JSON, sans dépendance).

Le bootstrap **fait démarrer BrainAI** : il charge sa configuration, initialise ses
sous-systèmes (Control Plane, Patrimony, Memory, Knowledge, Event Bus), enregistre
les premiers Agents et déclare « BrainAI READY ». Il **réutilise** les composants
existants via leurs interfaces publiques, sans les modifier.

Déterminisme : ``as_of`` fige l'horodatage du démarrage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.errors import ConfigError

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[3]      # .../17_BRAINAI_BOOTSTRAP
DEFAULT_SCC_ROOT = BOOTSTRAP_ROOT.parent                   # .../01_CCSC
DEFAULT_CONFIG_PATH = BOOTSTRAP_ROOT / "config" / "brainai.json"

DEFAULT_AS_OF = "2026-07-06T00:00:00+00:00"

# Premiers Agents enregistrés au démarrage (rôles pivots du modèle d'Agents).
DEFAULT_FIRST_AGENTS = [
    "SCC-AGENT-0001",  # Architecte
    "SCC-AGENT-0002",  # Gouvernance
    "SCC-AGENT-0003",  # Gardien de la Fondation
    "SCC-AGENT-0020",  # Superviseur (BrainAI)
]


@dataclass
class BrainAIConfig:
    bootstrap_root: Path = BOOTSTRAP_ROOT
    scc_root: Path = DEFAULT_SCC_ROOT
    data_dir: Path = BOOTSTRAP_ROOT / "data"
    as_of: str = DEFAULT_AS_OF
    first_agents: List[str] = field(default_factory=lambda: list(DEFAULT_FIRST_AGENTS))
    authorized_actors: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # -- emplacements des composants réutilisés ------------------------- #
    @property
    def control_plane_src(self) -> Path:
        return self.scc_root / "09_CONTROL_PLANE" / "src"

    @property
    def memory_src(self) -> Path:
        return self.scc_root / "11_BRAINAI_MEMORY" / "src"

    @property
    def knowledge_src(self) -> Path:
        return self.scc_root / "04_KNOWLEDGE" / "src"

    @property
    def kernel_src(self) -> Path:
        return self.scc_root / "10_BRAINAI" / "src"

    @property
    def reasoning_src(self) -> Path:
        return self.scc_root / "13_BRAINAI_REASONING" / "src"

    @property
    def planning_src(self) -> Path:
        return self.scc_root / "14_BRAINAI_PLANNING" / "src"

    @property
    def decision_src(self) -> Path:
        return self.scc_root / "15_BRAINAI_DECISION" / "src"

    @property
    def execution_src(self) -> Path:
        return self.scc_root / "16_BRAINAI_EXECUTION" / "src"

    @property
    def cognition_data(self) -> Path:
        return self.data_dir / "cognition"

    @property
    def agents_dir(self) -> Path:
        return self.scc_root / "00_SYSTEM" / "agents"

    # -- répertoires d'état du bootstrap -------------------------------- #
    @property
    def memory_data_dir(self) -> Path:
        return self.data_dir / "memory"

    @property
    def knowledge_root(self) -> Path:
        return self.data_dir / "knowledge"

    def ensure_directories(self) -> None:
        for d in (self.data_dir, self.memory_data_dir, self.knowledge_root):
            d.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        return {"bootstrap_root": str(self.bootstrap_root), "scc_root": str(self.scc_root),
                "data_dir": str(self.data_dir), "as_of": self.as_of,
                "first_agents": list(self.first_agents)}


def _resolve(base: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def load_config(path: Optional[Path] = None) -> BrainAIConfig:
    config = BrainAIConfig()
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    if not target.exists():
        if path is not None:
            raise ConfigError(f"Configuration introuvable : {target}")
        return config
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Configuration illisible ({target}) : {exc}") from exc

    base = config.bootstrap_root
    if "scc_root" in raw:
        config.scc_root = _resolve(base, raw["scc_root"])
    paths = raw.get("paths", {})
    if "data_dir" in paths:
        config.data_dir = _resolve(base, paths["data_dir"])
    config.as_of = str(raw.get("as_of", DEFAULT_AS_OF))
    config.first_agents = list(raw.get("first_agents", config.first_agents))
    config.authorized_actors = list(raw.get("authorized_actors", config.authorized_actors))
    config.extra = dict(raw.get("extra", {}))
    return config


__all__ = ["BOOTSTRAP_ROOT", "DEFAULT_SCC_ROOT", "DEFAULT_AS_OF", "DEFAULT_FIRST_AGENTS",
           "BrainAIConfig", "load_config"]
