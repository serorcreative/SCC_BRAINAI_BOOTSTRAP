"""Banc **Étage 1** — watchdog de sécurité gouverné (palier immédiat), **déterministe, 0 LLM**.

Prouve : (1) le cutoff cognitif figé de 180 s a disparu ; (2) le plafond est un **watchdog de sécurité gouverné**
(défaut 3600 s / env / explicite, source tracée) ; (3) ``run_confined`` **honore** réellement ce plafond
(sous-processus locaux inoffensifs — ``sleep``/``true``/``false``, aucun LLM) ; (4) un dépassement est étiqueté
``safety_watchdog_exceeded``, **distinct** d'un process mort (``exit_code != 0``), lui capté immédiatement.
"""

from __future__ import annotations

import json

import pytest

from scc_brainai_bootstrap.builder import build as B
from scc_brainai_bootstrap.builder import conversation as C
from scc_brainai_bootstrap.builder.tool_runner import (
    DEFAULT_WATCHDOG_S, SAFETY_WATCHDOG_EXCEEDED, run_confined)
from brainai_app.delivery.watchdog_config import ENV_WATCHDOG_S, load_call_watchdog


# --------------------------------------------------------------------- #
# Constantes — le watchdog est de 1 h par défaut (fusible), motif explicite
# --------------------------------------------------------------------- #
def test_default_watchdog_is_one_hour_and_reason_is_explicit():
    assert DEFAULT_WATCHDOG_S == 3600.0
    assert SAFETY_WATCHDOG_EXCEEDED == "safety_watchdog_exceeded"


# --------------------------------------------------------------------- #
# Config gouvernée : défaut / env / explicite, source tracée ; ≤0 ignoré
# --------------------------------------------------------------------- #
def test_watchdog_default(monkeypatch):
    monkeypatch.delenv(ENV_WATCHDOG_S, raising=False)
    cfg = load_call_watchdog()
    assert cfg.timeout_s == 3600.0 and cfg.timeout_source == "default"
    assert cfg.cognition_deadline is False and cfg.role == "last_resort_safety_watchdog"


def test_watchdog_env_override(monkeypatch):
    monkeypatch.setenv(ENV_WATCHDOG_S, "7200")
    cfg = load_call_watchdog()
    assert cfg.timeout_s == 7200.0 and cfg.timeout_source == "env"


def test_watchdog_explicit_wins(monkeypatch):
    monkeypatch.setenv(ENV_WATCHDOG_S, "7200")
    cfg = load_call_watchdog(timeout_s=1800)
    assert cfg.timeout_s == 1800.0 and cfg.timeout_source == "explicit"


def test_watchdog_nonpositive_or_garbage_falls_back(monkeypatch):
    monkeypatch.setenv(ENV_WATCHDOG_S, "-5")
    assert load_call_watchdog().timeout_source == "default"          # ≤0 ignoré
    monkeypatch.setenv(ENV_WATCHDOG_S, "pas-un-nombre")
    assert load_call_watchdog().timeout_source == "default"          # illisible ignoré
    monkeypatch.delenv(ENV_WATCHDOG_S, raising=False)
    assert load_call_watchdog(timeout_s=0).timeout_source == "default"   # explicite ≤0 ignoré


# --------------------------------------------------------------------- #
# Les binders passent le watchdog gouverné (plus de 180 figé)
# --------------------------------------------------------------------- #
def test_binders_use_governed_watchdog_not_180(monkeypatch):
    from brainai_app import providers
    monkeypatch.delenv(ENV_WATCHDOG_S, raising=False)
    binders = providers.default_binders()
    for key in ((providers.CLAUDE_CODE, providers.CONVERSE), (providers.CLAUDE_CODE, providers.UNDERSTAND_NEED),
                (providers.CLAUDE_CODE, providers.SPECIFY), (providers.CLAUDE_CODE, providers.BUILD_SOFTWARE)):
        adapter = binders[key]()
        assert adapter.timeout == 3600.0 and adapter.timeout != 180   # cutoff cognitif figé supprimé
    site = providers.delivery_binders()[(providers.CLAUDE_CODE, providers.BUILD_SITE)]()
    assert site.timeout == 3600.0


def test_binders_honor_env_override(monkeypatch):
    from brainai_app import providers
    monkeypatch.setenv(ENV_WATCHDOG_S, "600")
    conv = providers.default_binders()[(providers.CLAUDE_CODE, providers.CONVERSE)]()
    assert conv.timeout == 600.0                                      # gouvernance env réellement propagée


# --------------------------------------------------------------------- #
# run_confined HONORE réellement le plafond (sous-processus locaux, aucun LLM)
# --------------------------------------------------------------------- #
def test_run_confined_kills_after_watchdog(tmp_path):
    # un process qui dort au-delà du plafond → timed_out True, exit_code None (fusible actif)
    r = run_confined(["/bin/sleep", "5"], cwd=tmp_path, timeout=0.2)
    assert r["timed_out"] is True and r["exit_code"] is None


def test_run_confined_lets_fast_process_finish(tmp_path):
    # un process rapide bien en-deçà du plafond → aboutit normalement (le watchdog ne coupe PAS le travail sain)
    r = run_confined(["/usr/bin/true"], cwd=tmp_path, timeout=30)
    assert r["timed_out"] is False and r["exit_code"] == 0


def test_run_confined_dead_process_is_immediate_and_separate(tmp_path):
    # process mort (exit != 0) → capté immédiatement, SANS timeout (indépendant du watchdog)
    r = run_confined(["/usr/bin/false"], cwd=tmp_path, timeout=30)
    assert r["timed_out"] is False and r["exit_code"] != 0


# --------------------------------------------------------------------- #
# Sémantique distincte au niveau adaptateur : watchdog vs process mort
# --------------------------------------------------------------------- #
def _env(obj, *, ok=True, exit_ok=True):
    return {"type": "result", "subtype": "success" if ok else "error", "is_error": not ok,
            "api_error_status": None, "num_turns": 1,
            "result": json.dumps(obj, ensure_ascii=False), "total_cost_usd": 0.0,
            "usage": {"input_tokens": 1, "output_tokens": 1}}


def test_adapter_labels_watchdog_distinctly_from_dead_process():
    # dépassement watchdog (timed_out) → 'safety_watchdog_exceeded'
    timed = C.build_turn(message="m", prompt="p", capability="conversation", adapter="fake", model="fake",
                         envelope=None, exit_code=None, timed_out=True, as_of="2026-08-22T00:00:00+00:00",
                         argv=["x"], stdout="", stderr="", pursuit_ref="pursuit_w")
    assert timed["status"] == "failed" and timed["error"] == SAFETY_WATCHDOG_EXCEEDED
    # process MORT (exit != 0, pas de timeout) → motif DISTINCT ('exit non nul'), jamais le watchdog
    dead = B._failure_reason(_env({"name": "n"}, ok=True), exit_code=1, timed_out=False)
    assert dead is not None and "exit non nul" in dead and dead != SAFETY_WATCHDOG_EXCEEDED
    # et le watchdog via _failure_reason (arc/site) :
    assert B._failure_reason(None, exit_code=None, timed_out=True) == SAFETY_WATCHDOG_EXCEEDED
