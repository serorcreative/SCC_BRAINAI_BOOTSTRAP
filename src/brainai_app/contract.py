"""Contrat de l'application BrainAI — **axe** versionné (ADR-UI-010), servi verbatim par le transport.

Une seule opération métier : ``pursue`` (``action``), plus ``contract`` (``read``, introspection). Réplique le
**patron d'enveloppe** de la couche de présentation du noyau, sans en dépendre. Le transport liste-blanche les
opérations contre :data:`OPERATIONS` et renvoie l'enveloppe **verbatim** (Doctrine n°6 : exposer un contrat,
jamais une implémentation)."""

from __future__ import annotations

from typing import Any, Dict

CONTRACT_VERSION = "brainai-app/v1"

OPERATIONS: Dict[str, Dict[str, str]] = {
    "contract": {"kind": "read", "summary": "Introspection du contrat (describe)"},
    "pursue": {"kind": "action", "summary": "Poursuivre un besoin : BrainAI.pursue(intent, context)"},
}


def envelope(operation: str, data: Any, as_of: str) -> Dict[str, Any]:
    """Enveloppe canonique : version + opération + genre + horodatage + données (ViewModel)."""
    kind = OPERATIONS.get(operation, {}).get("kind", "read")
    return {"contract_version": CONTRACT_VERSION, "operation": operation, "kind": kind,
            "generated_as_of": as_of, "data": data}


def describe() -> Dict[str, Any]:
    """Sérialisation du contrat (source de vérité pour un futur client généré)."""
    return {"contract_version": CONTRACT_VERSION, "operations": OPERATIONS}


__all__ = ["CONTRACT_VERSION", "OPERATIONS", "envelope", "describe"]
