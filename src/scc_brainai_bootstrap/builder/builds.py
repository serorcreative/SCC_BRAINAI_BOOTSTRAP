"""Faits **Build** — proposition produite par une capacité de build (JALON-ZERO).

Un modèle de langage **propose** (le contenu d'un manifeste à partir d'une Spécification) ; il ne modifie
**aucun** état officiel BrainAI (R5), et **ne modifie jamais** la Spécification source. Chaque tentative
produit **un fait immuable** distinct, avec type de fait, référence + empreinte de la Spéc source, modèle,
empreinte du prompt, paramètres, **métadonnées d'artefact** (chemin relatif imposé, ``sha256`` des octets
réellement écrits, taille) sur succès — ou ``None`` sur échec, usage, **coût** (``real``/``unavailable`` —
**jamais fabriqués**), horodatage et ``status`` (``proposed`` en succès, ``failed`` sinon avec diagnostic
RV-1). Store JSONL **append-only**, relu du disque, **hors** du vrai ``data/`` (injecté). Id **adressé au
contenu** et **calculé par le store**. Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.core.clock import short_id


class BuildStore:
    """Journal append-only des builds, dans un fichier hors ``data/`` (injecté)."""

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
        """Ajoute un fait build immuable (déjà construit par :func:`build_build`).

        **Le store adresse lui-même l'identifiant** à partir du **fait complet sans identifiant** : tout
        ``build_id`` fourni par l'appelant est **ignoré** (retiré puis recalculé). L'identifiant dépend du
        **statut**, du **contenu** (``artefact`` en succès, ``diagnostic`` en échec), de la **source**
        (``spec_ref`` + ``spec_sha256``), du **modèle**, de l'**adaptateur** et de l'**horodatage** — deux
        artefacts distincts (ou deux échecs distincts) donnent **deux identifiants distincts**."""
        stored = {k: v for k, v in fact.items() if k != "build_id"}  # id appelant ignoré
        build_id = short_id("build", {
            "status": stored.get("status"),
            "artefact": stored.get("artefact"),
            "diagnostic": stored.get("diagnostic"),
            "spec_ref": stored.get("spec_ref"),
            "spec_sha256": stored.get("spec_sha256"),
            "model": stored.get("model"),
            "adapter": stored.get("adapter"),
            "as_of": stored.get("as_of"),
        })
        stored = {"build_id": build_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["BuildStore"]
