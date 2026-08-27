"""Hiérarchie d'exceptions du bootstrap BrainAI."""

from __future__ import annotations


class BootstrapError(Exception):
    """Erreur de base du démarrage BrainAI."""


class ConfigError(BootstrapError):
    """Configuration absente, illisible ou invalide."""


class ComponentError(BootstrapError):
    """Un composant réutilisé est introuvable ou ne s'initialise pas."""


class SessionStateError(BootstrapError):
    """État de session présent mais illisible/incohérent (L2 store-safety).

    Fail-closed : un ``session.json`` présent mais illisible, JSON invalide, non-``dict``
    ou sans ``session_id`` non vide ne doit **jamais** être traité comme une absence
    (aucun reset silencieux de l'identité/compteurs). Seule une **absence réelle** du
    fichier autorise la création d'un nouvel état."""


__all__ = ["BootstrapError", "ConfigError", "ComponentError", "SessionStateError"]
