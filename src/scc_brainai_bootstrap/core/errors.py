"""Hiérarchie d'exceptions du bootstrap BrainAI."""

from __future__ import annotations


class BootstrapError(Exception):
    """Erreur de base du démarrage BrainAI."""


class ConfigError(BootstrapError):
    """Configuration absente, illisible ou invalide."""


class ComponentError(BootstrapError):
    """Un composant réutilisé est introuvable ou ne s'initialise pas."""


__all__ = ["BootstrapError", "ConfigError", "ComponentError"]
