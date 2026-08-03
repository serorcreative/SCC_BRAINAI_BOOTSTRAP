"""Fixtures du bootstrap BrainAI (data en tmp ; scc_root réel pour les composants)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.core.config import BOOTSTRAP_ROOT, load_config

# Vrai répertoire de données du dépôt — aucune suite ne doit jamais l'écrire (isolation stricte).
REAL_DATA_DIR = BOOTSTRAP_ROOT / "data"


def _data_fingerprint(root: Path) -> dict[str, str]:
    """Empreinte {chemin relatif → sha256} de tous les fichiers sous ``root`` (vide si absent).

    Capte ajout, suppression et modification : un fichier ajouté/retiré change l'ensemble des
    clés, un contenu modifié change son hash — aucune altération ne peut être masquée."""
    if not root.exists():
        return {}
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="session", autouse=True)
def _guard_real_data_dir_unchanged():
    """Garde-fou anti-pollution : échoue si une suite modifie le vrai ``data/`` du dépôt.

    Peu coûteux (empreinte du seul ``data/`` réel, quelques fichiers), pris avant la session et
    revérifié après. Compatible avec le ``data_dir`` temporaire (fixture ``config``) : un run sain
    ne touche jamais le vrai ``data/``, donc l'empreinte est identique."""
    before = _data_fingerprint(REAL_DATA_DIR)
    yield
    after = _data_fingerprint(REAL_DATA_DIR)
    assert after == before, (
        "POLLUTION du vrai data/ détectée pendant la suite — "
        f"différences : { {k: (before.get(k, '∅'), after.get(k, '∅')) for k in set(before) ^ set(after) | {k for k in before if before.get(k) != after.get(k)}} }"
    )


@pytest.fixture
def config(tmp_path):
    cfg = load_config()               # scc_root réel (config par défaut)
    cfg.data_dir = tmp_path / "data"
    return cfg


@pytest.fixture
def boot(config):
    return BrainAIBootstrap(config=config)


@pytest.fixture
def report(boot):
    return boot.run()
