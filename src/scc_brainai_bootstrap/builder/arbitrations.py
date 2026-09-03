"""Faits **understanding_arbitration** — trace d'un arbitrage BrainAI multi-provider (L7).

CONNECTER, PAS RECONSTRUIRE. Même patron *trace-shaped* append-only que :class:`ConfirmationStore` /
:class:`TurnStore` (id adressé-contenu, ``as_of`` figé, ``pursuit_ref``). **Aucune mémoire parallèle** : ce
journal est un store additif injecté via :class:`Stores`, au même titre que ``turns``/``confirmations``.

Le fait ne **décide rien** par lui-même (*record ≠ decision*) : il **trace** ce que BrainAI a arbitré —
contributions consultées (``contributor_proposal_ids``), classification, ``status`` (``converged`` /
``unresolved`` / ``insufficient``), ``converged_proposal_id`` éventuel, et ``rationale`` provider-neutral. La
provenance ``adapter`` de chaque contribution vit dans les faits ``ProposalStore`` référencés — pas ici, et
jamais comme critère de décision. Lecture **fail-closed** (une ligne invalide fait échouer explicitement).
Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id


def build_arbitration_fact(*, pursuit_ref: str, contributor_proposal_ids: List[str],
                           classification: Any, status: str, rationale: Any,
                           as_of: str, converged_proposal_id: Optional[str] = None,
                           reason: Optional[str] = None,
                           unresolved_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Construit un fait ``understanding_arbitration`` immuable. ``status`` ∈ {``converged``, ``unresolved``,
    ``insufficient``}. ``converged_proposal_id`` renseigné uniquement en convergence. Ne mute aucun fait ; ne
    déclenche rien. ``contributor_proposal_ids`` est **trié** pour une trace déterministe indépendante de l'ordre
    de consultation."""
    return {
        "fact_type": "understanding_arbitration",
        "pursuit_ref": pursuit_ref,
        "contributor_proposal_ids": sorted(contributor_proposal_ids),
        "status": status,
        "reason": reason,
        "unresolved_fields": sorted(unresolved_fields) if unresolved_fields else [],
        "converged_proposal_id": converged_proposal_id,
        "classification": classification,
        "rationale": rationale,
        "as_of": as_of,
    }


class ArbitrationStore:
    """Journal **append-only** des arbitrages d'understanding (fichier injecté, hors ``data/``)."""

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _load_all(self) -> List[Dict[str, Any]]:
        """Relit le journal du disque **fail-closed** : toute ligne non vide illisible en JSON lève une erreur
        explicite (aucun ``continue`` silencieux ne masque une corruption)."""
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for i, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"ArbitrationStore: ligne {i} JSON invalide ({exc}) — lecture fail-closed") from exc
        return out

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait arbitrage immuable ; **le store adresse lui-même l'identifiant** (id appelant ignoré)
        à partir du **fait complet** (hors ``arbitration_id``) — ``classification``, ``rationale``, ``reason`` et
        ``unresolved_fields`` contribuent donc à l'identité (content-addressed). N'exécute **aucune** action."""
        stored = {k: v for k, v in fact.items() if k != "arbitration_id"}
        arbitration_id = short_id("arb", stored)
        stored = {"arbitration_id": arbitration_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["ArbitrationStore", "build_arbitration_fact"]
