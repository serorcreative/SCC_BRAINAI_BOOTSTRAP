"""Workspace confiné d'un Projet (BRAINAI-JALON-ZERO-001, plan d'exécution réelle).

Frontière **logique** entre la Cognition (le cerveau) et l'Exécution (le plan qui provoque des
effets réels). Un **Workspace** est un répertoire **isolé par Projet** — ``<root>/workspaces/
<project_id>/`` — situé **hors** de ``data/`` et **hors** des dépôts BrainAI (``root`` injecté,
jamais le dépôt). Il garantit qu'aucune écriture d'outil ne peut **échapper** au Projet :

* ``project_id`` **strictement validé** (aucune traversée, aucun séparateur, aucun ``..``) ;
* ``resolve_within`` **résout puis vérifie** que le chemin cible est contenu dans la racine — tout
  chemin absolu, ``..`` ou symlink qui échappe est **refusé avant tout effet**.

Ce module ne dépend d'**aucun** outil réel (R8) : il n'exécute rien, il **délimite**. Stdlib pur.
"""

from __future__ import annotations

import re
from pathlib import Path

# Un project_id sûr : minuscules/chiffres, tiret/underscore internes, 1..64 caractères. Jamais de
# ``.``, ``/``, ``\\`` ni ``..`` — l'identifiant ne peut pas exprimer un chemin.
_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class WorkspaceError(ValueError):
    """Identifiant de Projet invalide ou chemin échappant au Workspace."""


class Workspace:
    """Répertoire confiné d'un Projet. ``root`` est la **base d'exécution** (hors dépôts/data)."""

    def __init__(self, root: Path, project_id: str):
        if not isinstance(project_id, str) or not _PROJECT_ID_RE.match(project_id):
            raise WorkspaceError(f"project_id invalide : {project_id!r}")
        self._root = Path(root).resolve() / "workspaces" / project_id
        self.project_id = project_id

    @property
    def path(self) -> Path:
        return self._root

    def ensure(self) -> Path:
        """Crée le répertoire du Workspace (idempotent) et le renvoie."""
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    def resolve_within(self, relative_path: str) -> Path:
        """Résout ``relative_path`` **dans** le Workspace, ou lève :class:`WorkspaceError`.

        **Refuse avant tout effet** : chemin vide, absolu, contenant un octet nul, ou dont la forme
        **résolue** échappe à la racine (``..``, symlink). Le résultat est toujours un chemin dont la
        racine du Workspace est un ancêtre (ou la racine elle-même)."""
        if not relative_path or not isinstance(relative_path, str):
            raise WorkspaceError("chemin relatif requis")
        if relative_path.startswith("/") or "\x00" in relative_path:
            raise WorkspaceError(f"chemin non confiné : {relative_path!r}")
        root = self._root.resolve()
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise WorkspaceError(f"chemin hors workspace : {relative_path!r}")
        return candidate


__all__ = ["Workspace", "WorkspaceError"]
