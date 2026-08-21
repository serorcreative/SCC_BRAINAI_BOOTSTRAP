"""Fait ``delivered`` — clôture honnête d'une livraison réelle (JALON 2, T5).

Émis **uniquement** quand la chaîne réelle a abouti : artefact bâti, vérifié (``verdict=passed`` lié au hash),
preview servie. Append-only, adressé au contenu. Champs : ``pursuit_ref``, ``artifact_ref`` (point d'entrée +
sha256), ``preview_ref`` (reflet non secret de la surface locale — jamais le jeton), ``verification_ref``,
``as_of``. Ne déclenche rien, ne rend rien « officiel » de lui-même : c'est un **constat** gouvernable. Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id


def build_delivered(*, pursuit_ref: str, artifact_ref: Any, preview_ref: Any,
                    verification_ref: str, as_of: str, build_ref: Optional[str] = None) -> Dict[str, Any]:
    """Construit un fait ``delivered`` immuable (pur, testable)."""
    return {
        "fact_type": "delivered",
        "pursuit_ref": pursuit_ref,
        "build_ref": build_ref,
        "artifact_ref": artifact_ref,
        "preview_ref": preview_ref,
        "verification_ref": verification_ref,
        "as_of": as_of,
    }


class DeliveredStore:
    """Journal **append-only** des faits ``delivered`` (fichier injecté, hors ``data/``)."""

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
        """Ajoute un fait ``delivered`` ; **le store adresse l'``id``** (id appelant ignoré) depuis le contenu."""
        stored = {k: v for k, v in fact.items() if k != "delivered_id"}
        did = short_id("deliv", {"pursuit_ref": stored.get("pursuit_ref"),
                                 "verification_ref": stored.get("verification_ref"),
                                 "as_of": stored.get("as_of")})
        stored = {"delivered_id": did, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["build_delivered", "DeliveredStore"]
