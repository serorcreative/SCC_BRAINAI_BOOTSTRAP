"""Banc **Étage 1** — raccord UI du **mode d'exécution** (Voie B), **déterministe, 0 €**, aucun appel LLM.

Le serveur supporte déjà ``mode ∈ {demo, real}`` (``server.py``) ; ce banc verrouille le fait que l'**UI** :
* expose un **sélecteur** de mode (``#mode-select``) avec **demo** (défaut) ET **real** sélectionnable ;
* ne code **plus aucun** ``mode`` en dur dans les appels réseau (``converse`` **et** ``realize``) ;
* transmet le **mode réellement sélectionné** via un unique point (``selectedMode()``).

Test purement **statique** (lecture du HTML/JS livré) — il ne lance ni serveur ni cognition.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_INDEX = Path(__file__).resolve().parents[1] / "src" / "brainai_app" / "static" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return _INDEX.read_text(encoding="utf-8")


def test_mode_selector_present_with_demo_and_real(html: str):
    assert 'id="mode-select"' in html                                  # le contrôle existe
    assert re.search(r'<option value="demo"[^>]*>', html)              # démo conservée
    assert re.search(r'<option value="real"[^>]*>', html)              # réel sélectionnable
    # démo reste le défaut (option marquée selected) — aucun coût par surprise
    assert re.search(r'<option value="demo"[^>]*\bselected\b', html)


def test_selected_mode_helper_defined(html: str):
    assert "selectedMode" in html
    assert re.search(r"const\s+selectedMode\s*=", html)                # point unique de lecture du mode


def test_no_hardcoded_mode_in_network_calls(html: str):
    # plus aucune valeur de mode figée dans les appels : ni "demo" ni "real" en dur
    assert 'mode: "demo"' not in html and "mode: 'demo'" not in html
    assert 'mode: "real"' not in html and "mode: 'real'" not in html


def test_converse_and_realize_send_selected_mode(html: str):
    # les deux appels que l'UI émet réellement transmettent le mode SÉLECTIONNÉ
    converse = re.search(r'kind:\s*"converse".*?mode:\s*selectedMode\(\)', html, re.S)
    realize = re.search(r'kind:\s*"realize".*?mode:\s*selectedMode\(\)', html, re.S)
    assert converse, "l'appel converse doit transmettre selectedMode()"
    assert realize, "l'appel realize doit transmettre selectedMode()"


def test_every_post_mode_is_dynamic(html: str):
    """Tout ``mode:`` présent dans un appel du script est dynamique (``selectedMode()``), jamais une constante."""
    for m in re.finditer(r"mode:\s*([^,}\s]+)", html):
        assert m.group(1).startswith("selectedMode"), f"mode non dynamique détecté : {m.group(0)!r}"
