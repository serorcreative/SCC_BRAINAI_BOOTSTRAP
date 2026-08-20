"""COGNITIVE-IDENTITY-001 T1 — l'actif cognitif déposé dans le moteur.

Le module :mod:`cognitive_identity` est une **traduction** de l'héritage v0.2 : une *nature* injectée
en tête des facultés louées, jamais une liste de consignes. Ces tests vérifient le **contrat de dépôt** :
import propre, constantes non vides, ordre identité → mission de :func:`compose_prompt`, et **isolation
cognitive** (doctrine 15) — aucune syntaxe ni aucun nom de fournisseur dans les constantes injectées.
Aucun appel réel, aucun coût.
"""

from __future__ import annotations

from scc_brainai_bootstrap.builder.cognitive_identity import (
    COGNITIVE_IDENTITY,
    CONDENSED_IDENTITY,
    compose_prompt,
)


def test_module_exposes_two_identities_and_composer():
    # Import propre + surface publique attendue (les deux voix + l'assembleur).
    from scc_brainai_bootstrap.builder import cognitive_identity as ci
    assert set(ci.__all__) == {"COGNITIVE_IDENTITY", "CONDENSED_IDENTITY", "compose_prompt"}


def test_identities_are_non_empty_substantive_constants():
    # Constantes non vides — la voix complète est nettement plus riche que l'essence condensée.
    assert isinstance(COGNITIVE_IDENTITY, str) and COGNITIVE_IDENTITY.strip()
    assert isinstance(CONDENSED_IDENTITY, str) and CONDENSED_IDENTITY.strip()
    assert len(COGNITIVE_IDENTITY) > len(CONDENSED_IDENTITY) > 200
    # Marqueurs de la nature héritée (pentagone) présents dans la voix complète.
    for sommet in ("COMPRENDRE", "STRUCTURER", "ARBITRER", "ORCHESTRER", "LIVRER"):
        assert sommet.lower() in COGNITIVE_IDENTITY.lower()


def test_compose_prompt_orders_identity_before_mission_as_nature():
    # L'identité précède TOUJOURS la mission : la nature d'abord, la tâche ensuite.
    out = compose_prompt("<<IDENTITÉ>>", "<<MISSION>>")
    assert out.index("<<IDENTITÉ>>") < out.index("<<MISSION>>")
    assert "ta nature" in out.lower()                 # cadrage « c'est ta nature », pas « voici tes consignes »
    # Idempotent / déterministe : même entrée → même sortie.
    assert compose_prompt("<<IDENTITÉ>>", "<<MISSION>>") == out
    # Ordre préservé avec les vraies constantes.
    real = compose_prompt(COGNITIVE_IDENTITY, "MISSION_DU_TOUR")
    assert real.index(COGNITIVE_IDENTITY[:40]) < real.index("MISSION_DU_TOUR")


def test_cognitive_isolation_no_provider_leaks_in_injected_constants():
    # Doctrine 15 — ISOLATION COGNITIVE : les constantes INJECTÉES ne nomment aucun fournisseur ni
    # syntaxe de moteur. Si tous les moteurs changent demain, ce texte reste valable ; l'adaptateur
    # traduit, l'identité ignore le moteur. (Les commentaires du module, eux, peuvent situer l'héritage.)
    forbidden = ("claude", "anthropic", "openai", "gpt", "gemini", "haiku",
                 "sonnet", "opus", "codex", "cursor", "mistral", "llm")
    for identity in (COGNITIVE_IDENTITY, CONDENSED_IDENTITY):
        low = identity.lower()
        leaked = [name for name in forbidden if name in low]
        assert leaked == [], f"fournisseur/moteur nommé dans une constante d'identité : {leaked}"
