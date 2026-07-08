"""Registre des premiers Agents — chargé depuis le catalogue officiel (lecture seule).

Enregistre les rôles pivots au démarrage (Architecte, Gouvernance, Gardien de la
Fondation, Superviseur BrainAI…) à partir des fiches ``00_SYSTEM/agents``. Ne crée
aucun agent : il **recense et active** des rôles existants.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

from scc_brainai_bootstrap.core.config import BrainAIConfig

_TITLE = re.compile(r"^#\s+(.*)")
_ROW = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$")


@dataclass
class Agent:
    id: str
    name: str = ""
    autonomy: str = ""
    trust: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "autonomy": self.autonomy, "trust": self.trust}


class AgentRegistry:
    def __init__(self, config: BrainAIConfig):
        self._config = config
        self._agents: Dict[str, Agent] = {}

    def _load_fiche(self, agent_id: str) -> Agent:
        d = self._config.agents_dir
        matches = sorted(d.glob(f"{agent_id}-*.md")) if d.exists() else []
        if not matches:
            return Agent(id=agent_id, name="(fiche absente)")
        text = matches[0].read_text(encoding="utf-8")
        name, autonomy, trust = agent_id, "", ""
        for line in text.splitlines():
            mt = _TITLE.match(line)
            if mt and name == agent_id:
                name = mt.group(1).strip()
            mr = _ROW.match(line)
            if mr:
                key, val = mr.group(1).strip(), mr.group(2).strip()
                if "autonomie" in key.lower():
                    autonomy = val.split()[0] if val else ""
                elif "confiance" in key.lower():
                    trust = val.split()[0] if val else ""
        return Agent(id=agent_id, name=name, autonomy=autonomy, trust=trust)

    def register_first(self) -> List[Agent]:
        for aid in self._config.first_agents:
            if aid not in self._agents:
                self._agents[aid] = self._load_fiche(aid)
        return self.agents()

    def agents(self) -> List[Agent]:
        return [self._agents[k] for k in sorted(self._agents)]

    def to_list(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.agents()]


__all__ = ["Agent", "AgentRegistry"]
