"""Banc **Étage 1** — raccord UI de **reprise d'une pursuit existante** (Option A), déterministe, 0 €, 0 LLM.

Le serveur/moteur supporte déjà la reprise (``converse``/``realize`` transmettent ``pursuit_ref`` ; l'historique
vit côté serveur et est relu par le moteur). Ce banc verrouille le fait que l'**UI** :
* expose un contrôle de reprise (``#resume-id`` + ``#resume-btn``) ;
* ré-attache l'identifiant en assignant ``currentPursuitId`` depuis l'input (aucune fabrication d'historique) ;
* n'introduit **aucun** appel backend nouveau (les appels réseau restent ``converse``/``realize`` via ``pursuit_ref``).

Test purement **statique** (lecture du HTML/JS livré) — ni serveur ni cognition.
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


def test_resume_adds_no_new_backend_call(html: str):
    # aucune nouvelle route/opération : un SEUL primitif réseau (fetch), vers /v1/pursue ; kinds inchangés.
    assert html.count("fetch(") == 1                                      # un unique point d'appel réseau
    assert 'fetch("/v1/pursue"' in html                                   # toujours le même endpoint
    kinds = set(re.findall(r'kind:\s*"([a-z]+)"', html))
    assert kinds <= {"converse", "realize"}                               # aucun kind nouveau introduit


def test_resume_does_not_auto_realize(html: str):
    # la reprise retire toute proposition héritée et n'appelle jamais la réalisation
    handler = html.split('resume-btn")')[1].split("});")[0]
    assert "removeRealizeAction()" in handler
    assert "runRealize" not in handler and "realize" not in handler
