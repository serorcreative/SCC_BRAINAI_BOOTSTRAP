"""Sources de descripteurs — **pluggables** et lecture seule.

Le catalogue est alimenté par des sources indépendantes ; en ajouter une (un nouveau
projet SCC, un référentiel distant…) n'impacte ni le registre ni le Bootstrap.

Deux sources livrées :

* ``ManifestSource`` — descripteurs **déclaratifs** en JSON (`registry/agents/*.json`).
  C'est la voie normale : *ajouter un agent = ajouter un fichier de description.*
* ``FicheSource`` — **adapte** les fiches Markdown existantes (`00_SYSTEM/agents`) en
  descripteurs, sans les modifier, pour cataloguer les agents SCC déjà décrits.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from scc_brainai_bootstrap.registry.descriptor import AgentDescriptor, AgentState


class DescriptorSource:
    """Protocole : fournit une liste de descripteurs (non finalisés)."""

    name: str = "source"

    def descriptors(self) -> List[AgentDescriptor]:   # pragma: no cover - interface
        raise NotImplementedError


class ManifestSource(DescriptorSource):
    """Descripteurs déclaratifs en JSON. Chaque fichier contient un objet descripteur,
    ou une liste d'objets. Robuste : un fichier illisible est ignoré."""

    def __init__(self, directory: Path, name: str = "manifest"):
        self._dir = Path(directory)
        self.name = name

    def descriptors(self) -> List[AgentDescriptor]:
        if not self._dir.exists():
            return []
        out: List[AgentDescriptor] = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                if not isinstance(item, dict):
                    continue
                desc = AgentDescriptor.from_dict(item)
                desc.source = f"{self.name}:{path.name}"
                out.append(desc)
        return out


# -- Adaptation des fiches Markdown SCC --------------------------------- #
_TITLE = re.compile(r"^#\s+(.*)")
_ROW = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$")


class FicheSource(DescriptorSource):
    """Adapte des fiches ``SCC-AGENT-XXXX-*.md`` en descripteurs (lecture seule).

    Extrait ce que la fiche contient (nom, rôle/famille, autonomie A*, confiance T*,
    version). Les fiches n'expriment pas encore de capacités ``domaine.action`` : le
    descripteur est catalogué sans capacités (le routage par capacité s'appuie sur les
    agents qui en déclarent). Les références de capacités SCC brutes sont conservées
    dans ``extra`` pour un mappage ultérieur."""

    name = "fiche"

    def __init__(self, agents_dir: Path, ids: Iterable[str], namespace: str = "scc"):
        self._dir = Path(agents_dir)
        self._ids = list(ids)
        self._namespace = namespace

    def descriptors(self) -> List[AgentDescriptor]:
        return [self._one(aid) for aid in self._ids]

    def _one(self, agent_id: str) -> AgentDescriptor:
        matches = sorted(self._dir.glob(f"{agent_id}-*.md")) if self._dir.exists() else []
        if not matches:
            return AgentDescriptor(id=agent_id, namespace=self._namespace,
                                   name="(fiche absente)", state=AgentState.PROPOSED,
                                   source=f"{self.name}:absent", tags=["fiche", "missing"])
        path = matches[0]
        text = path.read_text(encoding="utf-8")
        fields: Dict[str, str] = {}
        name = agent_id
        for line in text.splitlines():
            mt = _TITLE.match(line)
            if mt and name == agent_id:
                name = mt.group(1).strip()
            mr = _ROW.match(line)
            if mr:
                fields[mr.group(1).strip().lower()] = mr.group(2).strip()

        def pick(*keys: str) -> str:
            for k in fields:
                if any(term in k for term in keys):
                    return fields[k]
            return ""

        autonomy = pick("autonomie").split()[0] if pick("autonomie") else ""
        trust = pick("confiance").split()[0] if pick("confiance") else ""
        raw_caps = re.findall(r"SCC-CAP-\d+", text)
        return AgentDescriptor(
            id=agent_id, namespace=self._namespace, name=name,
            role=pick("famille"), version=pick("version") or "1.0",
            description=self._mission(text),
            state=AgentState.ACTIVE, autonomy=autonomy or "suggest", trust=trust,
            source=f"{self.name}:{path.name}", tags=["fiche", "scc"],
            extra={"raw_capabilities": sorted(set(raw_caps))} if raw_caps else {},
        )

    @staticmethod
    def _mission(text: str) -> str:
        m = re.search(r"\*\*Mission\.\*\*\s*(.+)", text)
        return re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else ""


__all__ = ["DescriptorSource", "ManifestSource", "FicheSource"]
