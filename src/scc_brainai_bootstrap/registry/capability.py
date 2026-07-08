"""Capacités — slugs conventionnés ``domaine.action`` (vocabulaire **ouvert**).

Une capacité décrit *ce que sait faire* un agent, indépendamment de son nom. Le
routage futur raisonne sur les capacités, pas sur les agents. Exemples : ``memory.recall``,
``learning.analyze``, ``planning.propose``, ``decision.evaluate``, ``execution.run``,
``vision.describe``, ``security.audit``.

Garde-fou **léger** : on valide seulement le *format* (au moins ``domaine.action``,
minuscules, segments alphanumériques séparés par ``-``/``_``). Aucun vocabulaire fermé :
un nouveau domaine s'ajoute sans cérémonie. Une même capacité peut être fournie par
plusieurs agents (many-to-many).
"""

from __future__ import annotations

import re
from typing import Iterable, List

# Un segment : commence par une lettre, alphanumérique, tirets/underscores internes.
_SEGMENT = r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*"
# Une capacité : au moins deux segments séparés par des points (domaine.action[.sous]).
_CAPABILITY = re.compile(rf"^{_SEGMENT}(?:\.{_SEGMENT})+$")


def is_valid_capability(slug: object) -> bool:
    """True si le slug respecte la convention ``domaine.action`` (format seulement)."""
    return isinstance(slug, str) and bool(_CAPABILITY.match(slug))


def capability_domain(slug: str) -> str:
    """Domaine d'une capacité (partie avant le premier point), ou ``""``."""
    return slug.split(".", 1)[0] if is_valid_capability(slug) else ""


def invalid_capabilities(caps: Iterable[str]) -> List[str]:
    """Liste des slugs mal formés (pour un signalement non bloquant)."""
    return [c for c in caps if not is_valid_capability(c)]


__all__ = ["is_valid_capability", "capability_domain", "invalid_capabilities"]
