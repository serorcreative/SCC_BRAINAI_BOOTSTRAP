"""Faits **convergence_confirmed** — confirmation HUMAINE d'une convergence (EPISTEMIC-PROVENANCE, D3/RS-005).

``readiness='ready'`` reste une **appréciation cognitive** du modèle — **jamais** une confirmation humaine. La
confirmation est un **fait append-only SÉPARÉ** : il ne mute **aucun** ``matured_need`` historique (I5), il
n'ajoute qu'une trace immuable attribuée à un **acteur DÉCLARÉ et NON VÉRIFIÉ** (l'identité authentifiée n'existe
pas encore — dette RS-029). Le fait **ne déclenche rien par lui-même** : *record ≠ decision*.

Même patron *trace-shaped* que :class:`TurnStore` (id adressé-contenu, ``as_of`` figé, ``pursuit_ref``). Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id


def declared_actor(actor: Any) -> Dict[str, Any]:
    """Normalise un acteur en identité **DÉCLARÉE / NON VÉRIFIÉE**. Ne crée JAMAIS une garantie d'identité que
    l'architecture ne possède pas : ``verified`` est **toujours** ``False`` et ``attribution`` **toujours**
    ``"declared"`` (RS-029), quelle que soit l'entrée. Accepte une chaîne (id déclaré) ou un dict ``{id: …}`` ;
    défaut : ``"humain"``."""
    if isinstance(actor, str) and actor.strip():
        aid = actor.strip()
    elif isinstance(actor, dict) and isinstance(actor.get("id"), str) and actor["id"].strip():
        aid = actor["id"].strip()
    else:
        aid = "humain"
    return {"id": aid, "attribution": "declared", "verified": False}


def build_confirmation(*, pursuit_ref: str, turn_ref: Optional[str], as_of: str,
                       actor: Any = None) -> Dict[str, Any]:
    """Construit un fait ``convergence_confirmed`` immuable : la convergence mûrie du tour ``turn_ref`` (un tour
    ``ready``) a été **confirmée** par un acte humain, attribuée à un acteur déclaré/non vérifié. Ne mute aucun
    fait ; ne déclenche rien."""
    return {
        "fact_type": "convergence_confirmed",
        "pursuit_ref": pursuit_ref,
        "turn_ref": turn_ref,
        "actor": declared_actor(actor),
        "as_of": as_of,
    }


class ConfirmationStore:
    """Journal **append-only** des confirmations de convergence (fichier injecté, hors ``data/``)."""

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _load_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait confirmation immuable ; **le store adresse lui-même l'identifiant** (id appelant ignoré)
        à partir du contenu (``pursuit_ref``/``turn_ref``/``actor``/``as_of``). N'exécute **aucune** action."""
        stored = {k: v for k, v in fact.items() if k != "confirmation_id"}
        confirmation_id = short_id("conf", {
            "fact_type": stored.get("fact_type"),
            "pursuit_ref": stored.get("pursuit_ref"),
            "turn_ref": stored.get("turn_ref"),
            "actor": stored.get("actor"),
            "as_of": stored.get("as_of"),
        })
        stored = {"confirmation_id": confirmation_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["ConfirmationStore", "build_confirmation", "declared_actor"]
