"""Couche officielle de présentation de BrainAI.

Frontière unique et **stable** entre le Bootstrap (cerveau) et toutes les interfaces
futures. Elle présente les opérations déjà publiques sous un contrat versionné — sans
logique métier, sans dépendance UI/réseau. ``Presentation`` dépend du Bootstrap ; jamais
l'inverse. Cf. :mod:`scc_brainai_bootstrap.presentation.contract` pour le contrat.
"""

from __future__ import annotations

from scc_brainai_bootstrap.presentation.contract import (
    CONTRACT_VERSION,
    OPERATIONS,
    describe,
    envelope,
)
from scc_brainai_bootstrap.presentation.presenter import Presentation

__all__ = ["Presentation", "CONTRACT_VERSION", "OPERATIONS", "describe", "envelope"]
