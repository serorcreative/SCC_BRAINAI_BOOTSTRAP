"""Contrat de présentation — la frontière **stable** entre le cerveau et ses visages.

Ce module fige le **contrat** : le nom des opérations, leur genre (lecture / action) et
la forme de l'**enveloppe** de réponse. Toute interface (CLI, Web, Desktop, Mobile, API)
consomme ce contrat, jamais les moteurs internes. Le contrat est **versionné** : une
évolution incompatible incrémente ``CONTRACT_VERSION``.

Aucune logique métier ici : uniquement la description du contrat et l'emballage.
"""

from __future__ import annotations

from typing import Any, Dict

# Version du contrat de présentation (incrémentée à toute rupture de compatibilité).
CONTRACT_VERSION = "1.0"

# Opérations exposées : nom -> {genre, résumé}. `read` = vue sans effet de bord sur le
# domaine ; `action` = transfert vers un appel public du Bootstrap (jamais une décision
# propre à la couche). L'ordre est stable (déterminisme de `describe()`).
OPERATIONS: Dict[str, Dict[str, str]] = {
    "overview": {"kind": "read", "summary": "Instantané agrégé (ViewModel officiel)"},
    "doctor": {"kind": "read", "summary": "Diagnostic complet"},
    "session": {"kind": "read", "summary": "État de la session persistée"},
    "agents": {"kind": "read", "summary": "Catalogue déclaratif des agents"},
    "capabilities": {"kind": "read", "summary": "Index capacité → fournisseur(s)"},
    "resolve": {"kind": "read", "summary": "Résolution d'une capacité"},
    "status": {"kind": "read", "summary": "Patrimoine et disponibilité"},
    "learnings": {"kind": "read", "summary": "Apprentissages proposés / validés"},
    "events": {"kind": "read", "summary": "Journal d'événements"},
    "inputs": {"kind": "read", "summary": "Entrées perçues (liste projetée)"},
    "input": {"kind": "read", "summary": "Détail d'une Entrée par identifiant"},
    "input_history": {"kind": "read", "summary": "Histoire événementielle d'une Entrée"},
    "input_analysis": {"kind": "read", "summary": "Analyse revisitable d'une Entrée (délibération persistée)"},
    "start": {"kind": "action", "summary": "Démarrer BrainAI"},
    "run": {"kind": "action", "summary": "Traiter une demande (routage auto)"},
    "decide": {"kind": "action", "summary": "Formaliser une décision candidate"},
    "plan": {"kind": "action", "summary": "Planifier un objectif"},
    "validate_decision": {"kind": "action", "summary": "Valider une décision (humain)"},
    "execute_decision": {"kind": "action", "summary": "Exécuter une décision validée"},
    "learn": {"kind": "action", "summary": "Apprendre du vécu"},
    "validate_learning": {"kind": "action", "summary": "Valider un apprentissage (humain)"},
    "record_input": {"kind": "action", "summary": "Enregistrer une Entrée texte"},
    "analyze_input": {"kind": "action", "summary": "Analyser une Entrée (Reasoning)"},
    "input_decide": {"kind": "action", "summary": "Proposer une décision à partir de l'analyse d'une Entrée"},
}


def envelope(operation: str, data: Any, as_of: str) -> Dict[str, Any]:
    """Emballe une réponse dans l'enveloppe stable du contrat."""
    kind = OPERATIONS.get(operation, {}).get("kind", "read")
    return {
        "contract_version": CONTRACT_VERSION,
        "operation": operation,
        "kind": kind,
        "generated_as_of": as_of,
        "data": data,
    }


def describe() -> Dict[str, Any]:
    """Le contrat lui-même : version + opérations (pour l'introspection d'un UI)."""
    return {"contract_version": CONTRACT_VERSION,
            "operations": {k: dict(v) for k, v in OPERATIONS.items()}}


__all__ = ["CONTRACT_VERSION", "OPERATIONS", "envelope", "describe"]
