"""Tests du routeur de demandes (decisionnel → decide ; sinon → kernel)."""

from __future__ import annotations

import pytest

from scc_brainai_bootstrap.router import route


@pytest.mark.parametrize("query", [
    "Faut-il publier l API maintenant ou différer ?",
    "Doit-on migrer vers le nouveau schéma ?",
    "Quelle option choisir pour le déploiement ?",
    "Vaut-il mieux réécrire ou refactorer ?",
    "Publier maintenant ou bien attendre la revue ?",
    "Comment trancher entre les deux architectures ?",
])
def test_decisional_routes_to_decide(query):
    assert route(query) == "decide"


@pytest.mark.parametrize("query", [
    "Quelles doctrines gouvernent la gouvernance ?",
    "Explique l architecture du Runtime.",
    "Liste les agents enregistrés.",
    "Résume la mémoire de la dernière session.",
])
def test_informational_routes_to_kernel(query):
    assert route(query) == "kernel"


def test_forced_route_overrides_lexical():
    assert route("Faut-il publier ?", forced="kernel") == "kernel"
    assert route("Explique l architecture.", forced="decide") == "decide"


def test_invalid_forced_falls_back_to_lexical():
    assert route("Faut-il publier ?", forced="auto") == "decide"


def test_empty_and_none_route_to_kernel():
    assert route("") == "kernel"
    assert route(None) == "kernel"


def test_route_is_deterministic():
    q = "Faut-il choisir l option A ou l option B ?"
    assert route(q) == route(q) == "decide"
