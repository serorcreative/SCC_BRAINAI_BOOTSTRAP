"""Contrôles statiques de reprise UI : requête authentifiée, rattachement après
confirmation serveur, aucun appel automatique de réalisation. Les scénarios
exécutés sont dans test_runtime_interface et test_runtime_browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_INDEX = Path(__file__).resolve().parents[1] / "src" / "brainai_app" / "static" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return _INDEX.read_text(encoding="utf-8")


def test_resume_control_present(html: str):
    assert 'id="resume-id"' in html and 'id="resume-btn"' in html


def test_resume_reattaches_current_pursuit_id_from_input(html: str):
    # le handler assigne currentPursuitId à partir de la valeur saisie (ré-attachement, pas de rejeu)
    assert re.search(r'resume-btn"\)\.addEventListener\("click"', html)
    assert re.search(r"currentPursuitId\s*=\s*id\b", html)
    assert re.search(r'\$\("resume-id"\)\.value', html)


def test_resume_uses_authenticated_workflow_on_same_endpoint(html: str):
    # Le nouveau workflow réutilise le même endpoint et le même primitif authentifié.
    assert html.count("fetch(") == 1                                      # un unique point d'appel réseau
    assert 'fetch("/v1/pursue"' in html                                   # toujours le même endpoint
    kinds = set(re.findall(r'kind:\s*"([a-z]+)"', html))
    assert kinds == {"converse", "workflow", "realize"}
    assert 'kind:"realize", pursuit_ref:currentPursuitId, mode:selectedMode()' in html
    assert 'action: "resume"' in html
    assert 'env.data.status !== "resumed"' in html


def test_resume_does_not_auto_realize(html: str):
    # la reprise retire toute proposition héritée et n'appelle jamais la réalisation
    handler = html.split('resume-btn")')[1].split('$("approve-btn")')[0]
    assert "removeRealizeAction()" in handler
    assert "runRealize" not in handler
