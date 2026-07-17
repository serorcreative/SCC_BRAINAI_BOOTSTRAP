"""Tests de la couche de présentation (contrat, délégation, frontière, garde-fous)."""

from __future__ import annotations

import copy
import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.presentation import (
    CONTRACT_VERSION,
    OPERATIONS,
    Presentation,
    describe,
)


def _present(boot):
    return Presentation(bootstrap=boot)


# --------------------------------------------------------------------- #
# Contrat
# --------------------------------------------------------------------- #
def test_contract_describe_shape():
    d = describe()
    assert d["contract_version"] == CONTRACT_VERSION
    assert set(d["operations"]) == set(OPERATIONS)
    for meta in d["operations"].values():
        assert meta["kind"] in ("read", "action")
        assert meta["summary"]


def test_contract_lists_expected_operations():
    reads = {k for k, v in OPERATIONS.items() if v["kind"] == "read"}
    actions = {k for k, v in OPERATIONS.items() if v["kind"] == "action"}
    assert {"overview", "doctor", "session", "agents", "capabilities",
            "resolve", "status", "learnings", "events", "inputs", "input"} <= reads
    assert {"run", "decide", "plan", "validate_decision", "execute_decision",
            "learn", "validate_learning", "start", "record_input"} <= actions


def test_envelope_shape(boot):
    env = _present(boot).overview()
    assert env["contract_version"] == CONTRACT_VERSION
    assert env["operation"] == "overview"
    assert env["kind"] == "read"
    assert env["generated_as_of"] == boot.config.as_of
    assert "data" in env


# --------------------------------------------------------------------- #
# Délégation fidèle (aucune duplication, aucune transformation)
# --------------------------------------------------------------------- #
def test_read_delegates_verbatim(boot):
    present = _present(boot)
    assert present.overview()["data"] == boot.overview()
    assert present.session()["data"] == boot.session_summary()
    assert present.agents()["data"] == boot.agents_catalog()
    assert present.capabilities()["data"] == boot.capability_index()
    assert present.status()["data"] == boot.status_summary()


def test_resolve_delegates(boot):
    env = _present(boot).resolve("memory.recall")
    assert env["kind"] == "read"
    assert env["data"]["selected"] == "brainai-memory"


def test_action_run_forwards(boot):
    env = _present(boot).run("Quelles doctrines gouvernent la gouvernance ?")
    assert env["operation"] == "run" and env["kind"] == "action"
    assert env["data"]["ok"] is True
    assert env["data"]["route"] in ("kernel", "decide")


def test_action_decide_forwards_without_deciding_itself(boot):
    # la couche transfère ; c'est le moteur Decision qui décide (statut proposé).
    env = _present(boot).decide("Faut-il publier ou différer ?")
    assert env["kind"] == "action"
    assert env["data"]["status"] == "proposed"
    assert env["data"]["needs_human_validation"] is True


def test_events_read_and_journal_helper(boot):
    present = _present(boot)
    assert present.journal_exists() is False           # rien avant démarrage
    present.start()
    assert present.journal_exists() is True
    env = present.events()
    assert env["kind"] == "read" and env["data"]["count"] > 0


# --------------------------------------------------------------------- #
# Garde-fous : sens de dépendance & lecture seule
# --------------------------------------------------------------------- #
def test_bootstrap_does_not_depend_on_presentation():
    import scc_brainai_bootstrap.bootstrap as bmod
    src = open(bmod.__file__, encoding="utf-8").read()
    assert "presentation" not in src                   # le cerveau ignore ses visages


def test_reads_do_not_start_or_write(config):
    present = Presentation(bootstrap=BrainAIBootstrap(config=config))
    present.overview(); present.agents(); present.capabilities(); present.status(); present.session()
    boot = present.bootstrap
    assert boot._booted is False
    assert not boot.events_path.exists()
    assert not boot.session.path.exists()


def test_describe_covers_all_public_read_and_action_methods():
    # chaque opération du contrat correspond à une méthode de Presentation.
    for op in OPERATIONS:
        assert callable(getattr(Presentation, op))


# --------------------------------------------------------------------- #
# Le CLI passe exclusivement par la couche
# --------------------------------------------------------------------- #
def test_cli_module_uses_presentation_only():
    import scc_brainai_bootstrap.cli as clim
    src = open(clim.__file__, encoding="utf-8").read()
    assert "_present" in src
    assert "BrainAIBootstrap" not in src               # plus d'accès direct au cerveau


# --------------------------------------------------------------------- #
# Déterminisme
# --------------------------------------------------------------------- #
def test_presentation_overview_deterministic(config):
    def ov(name):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir.parent / name
        return Presentation(bootstrap=BrainAIBootstrap(config=cfg)).overview()
    a, b = ov("pa"), ov("pb")
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)
