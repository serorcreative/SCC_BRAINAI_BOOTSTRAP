"""Fixtures du bootstrap BrainAI (data en tmp ; scc_root réel pour les composants)."""

from __future__ import annotations

import pytest

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.core.config import load_config


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
