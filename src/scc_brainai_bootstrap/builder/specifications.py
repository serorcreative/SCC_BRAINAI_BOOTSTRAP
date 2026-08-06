"""Faits **Specification** — proposition produite par une capacité de spécification (JALON-ZERO).

Un modèle de langage **propose** (une Spécification structurée à partir d'un Brief) ; il ne modifie
**aucun** état officiel BrainAI (R5), et **ne modifie jamais** le Brief source. Chaque appel produit
**un fait immuable** distinct du fait Brief, avec type de fait, référence + empreinte du Brief source,
modèle, prompt (empreinte), paramètres, réponse, **usage** et **coût** (``real`` / ``unavailable`` —
**jamais fabriqués**), horodatage et ``status`` (``proposed`` en succès, ``failed`` sinon, avec
diagnostic RV-1). Store JSONL **append-only**, relu du disque, **hors** du vrai ``data/`` (injecté).
Déterministe (``as_of`` figé côté unités / réel côté appel, id adressé-contenu). Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.core.clock import short_id


class SpecificationStore:
    """Journal append-only des spécifications, dans un fichier hors ``data/`` (injecté)."""

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
        """Ajoute un fait spécification immuable (déjà construit par :func:`build_specification`).

        **Le store adresse lui-même l'identifiant** à partir du **fait complet sans identifiant** : tout
        ``specification_id`` fourni par l'appelant est **ignoré** (retiré puis recalculé). L'identifiant
        dépend du **statut**, du **contenu** (``specification`` en succès, ``diagnostic`` en échec), de la
        **source** (``brief_ref`` + ``brief_sha256``), du **modèle**, de l'**adaptateur** et de
        l'**horodatage** — deux contenus distincts issus des mêmes Brief/prompt/as_of donnent **deux
        identifiants distincts**."""
        stored = {k: v for k, v in fact.items() if k != "specification_id"}  # id appelant ignoré
        specification_id = short_id("spec", {
            "status": stored.get("status"),
            "specification": stored.get("specification"),
            "diagnostic": stored.get("diagnostic"),
            "brief_ref": stored.get("brief_ref"),
            "brief_sha256": stored.get("brief_sha256"),
            "model": stored.get("model"),
            "adapter": stored.get("adapter"),
            "as_of": stored.get("as_of"),
        })
        stored = {"specification_id": specification_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["SpecificationStore"]
