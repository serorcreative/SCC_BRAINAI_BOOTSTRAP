"""Faits **Proposal** — proposition produite par une capacité de compréhension (JALON-ZERO, Preuve B).

Un modèle de langage **propose** (un Brief structuré à partir d'un besoin en langage naturel) ; il ne
modifie **aucun** état officiel BrainAI (R5). Chaque appel produit **un fait immuable** avec modèle,
prompt (empreinte), paramètres, réponse, **usage** et **coût** (``real`` / ``estimated`` /
``unavailable`` — **jamais fabriqués**), horodatage et ``status`` (``proposed`` en succès, ``failed``
si la réponse est invalide). Store JSONL **append-only**, relu du disque. Déterministe (``as_of``
figé, id adressé-contenu). Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.core.clock import short_id


class ProposalStore:
    """Journal append-only des propositions, dans un fichier hors ``data/`` (injecté)."""

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
        """Ajoute un fait proposition immuable (déjà construit par :func:`build_proposal`).

        **Le store adresse lui-même l'identifiant** à partir du **fait complet sans identifiant** : tout
        ``proposal_id`` fourni par l'appelant est **ignoré** (retiré puis recalculé). L'identifiant dépend
        du **statut**, du **contenu** (``brief`` en succès, ``diagnostic`` en échec), de la **capacité**, de
        l'**adaptateur**, du **modèle**, de l'empreinte du **prompt**, du **``pursuit_ref``** (appartenance
        à la Pursuit) et de l'**horodatage** — deux faits distincts, ou deux Pursuits produisant le même
        Brief, donnent **deux identifiants distincts**."""
        stored = {k: v for k, v in fact.items() if k != "proposal_id"}  # id appelant ignoré
        proposal_id = short_id("prop", {
            "status": stored.get("status"),
            "brief": stored.get("brief"),
            "diagnostic": stored.get("diagnostic"),
            "capability": stored.get("capability"),
            "adapter": stored.get("adapter"),
            "model": stored.get("model"),
            "prompt_sha256": stored.get("prompt_sha256"),
            "pursuit_ref": stored.get("pursuit_ref"),
            "as_of": stored.get("as_of"),
        })
        stored = {"proposal_id": proposal_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["ProposalStore"]
