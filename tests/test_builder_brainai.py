"""ARC-PROPOSE-001 — Tâche 1 : contrat public de BrainAI (revue de gel).

Prouve à **0 €** le contrat seul : Intention neutre (H1), Pursuit identifiable/suspendable (H2), création ≠ reprise,
état de Pursuit ≠ raison d'attente, Outcome non terminal, matière de tour suivant (payload), injection interchangeable,
identité publique stable. **Aucune** orchestration, appel réel, matérialisation : une entrée valide atteint un seuil
`NotImplementedError` sans appeler aucune capacité.
"""

from __future__ import annotations

import pytest

from scc_brainai_bootstrap.builder import brainai as BA
from scc_brainai_bootstrap.builder.brainai import (
    PURSUIT_STATES,
    BrainAI,
    Capabilities,
    CapabilityInjectionError,
    GovernanceError,
    Intent,
    IntentError,
    NeedError,
    Outcome,
    RunContext,
    need_intent,
    new_pursuit_id,
    resume_intent,
    validate_intent,
    validate_need,
    validate_run_context,
)


# --- Fakes conformes aux Protocols (interchangeabilité, R8) — comptent leurs appels. ---
class _FakeUnderstanding:
    capability = "understanding"
    name = "fake"

    def __init__(self):
        self.calls = 0

    def propose(self, need, *, cwd, budget_remaining_usd):
        self.calls += 1
        return {"called": True}


class _FakeSpecification:
    capability = "specification"
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = 0

    def propose(self, brief, *, cwd, budget_remaining_usd):
        self.calls += 1
        return {"called": True}


class _FakeBuild:
    capability = "build"
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = 0

    def propose(self, spec, *, cwd, budget_remaining_usd):
        self.calls += 1
        return {"called": True}


def _caps():
    return Capabilities(understanding=_FakeUnderstanding(),
                        specification=_FakeSpecification(),
                        build=_FakeBuild())


def _ctx(**over):
    base = dict(budget_usd=5.0, project_id="refuge-demo", workspace=object(), stores=object())
    base.update(over)
    return RunContext(**base)


def _all_calls(caps):
    return caps.understanding.calls + caps.specification.calls + caps.build.calls


# ===================================================================== #
# H1 — Intention neutre : construction, payload, validation
# ===================================================================== #
def test_need_intent_is_the_first_supported_intention():
    i = need_intent("  Gérer un refuge animalier  ")
    assert i.kind == "need" and i.need == "Gérer un refuge animalier"
    assert i.pursuit_ref is None and i.payload is None
    with pytest.raises(NeedError):
        need_intent("")


def test_resume_intent_references_a_pursuit_and_can_carry_payload():
    i = resume_intent("pursuit_abc123")
    assert i.kind == "resume" and i.pursuit_ref == "pursuit_abc123" and i.need is None
    # matière du tour suivant (clarification / décision de gouvernance) portée par payload
    j = resume_intent("pursuit_abc123", payload={"clarification": "plutôt Y"})
    assert j.payload == {"clarification": "plutôt Y"}
    with pytest.raises(IntentError):
        resume_intent("")


def test_validate_intent_accepts_supported_and_rejects_others():
    validate_intent(need_intent("un besoin"))
    validate_intent(resume_intent("pursuit_x"))
    for bad in ("pas une intention", Intent(kind=""), Intent(kind="observe"),
                Intent(kind="resume", pursuit_ref="")):
        with pytest.raises(IntentError):
            validate_intent(bad)
    with pytest.raises(NeedError):
        validate_intent(Intent(kind="need", need=""))


# ===================================================================== #
# Point 2 — création ≠ reprise : aucune ambiguïté
# ===================================================================== #
def test_new_pursuit_id_mints_for_new_and_refuses_resume():
    a = new_pursuit_id(need_intent("besoin"), "proj", "2026-08-07T00:00:00+00:00")
    b = new_pursuit_id(need_intent("besoin"), "proj", "2026-08-07T00:00:00+00:00")
    c = new_pursuit_id(need_intent("AUTRE"), "proj", "2026-08-07T00:00:00+00:00")
    assert a.startswith("pursuit_") and a == b and a != c        # déterministe, adressé au contenu
    with pytest.raises(IntentError):
        new_pursuit_id(resume_intent("pursuit_X"), "proj", "t")  # une reprise ne crée JAMAIS d'identité


def test_resume_keeps_the_same_pursuit_identity():
    pid = new_pursuit_id(need_intent("besoin"), "proj", "2026-08-07T00:00:00+00:00")
    again = resume_intent(pid)
    assert again.pursuit_ref == pid                              # la Pursuit reste la même


# ===================================================================== #
# Point 4/5 — état ≠ raison d'attente ; Outcome non terminal
# ===================================================================== #
def test_pursuit_states_vocabulary():
    assert set(PURSUIT_STATES) == {"active", "awaiting", "terminal"}


def test_outcome_active_awaiting_terminal_and_pursuit_id():
    active = Outcome(state="active", project_id="p", pursuit_id="pursuit_a", as_of="t")
    awaiting = Outcome(state="awaiting", project_id="p", pursuit_id="pursuit_a", as_of="t",
                       wait_reason="governance")
    terminal = Outcome(state="terminal", project_id="p", pursuit_id="pursuit_a", as_of="t",
                       refused="budget insuffisant")
    assert active.state == "active" and active.wait_reason is None
    assert awaiting.state == "awaiting" and awaiting.wait_reason == "governance"
    assert terminal.state == "terminal" and terminal.refused == "budget insuffisant"
    for o in (active, awaiting, terminal):
        assert o.pursuit_id == "pursuit_a" and o.steps == ()
        for forbidden in ("validated", "official", "approved", "executed"):
            assert not hasattr(o, forbidden)                     # jamais autoritatif


def test_outcome_state_and_wait_reason_coupling_is_enforced():
    with pytest.raises(ValueError):
        Outcome(state="observed", project_id="p", pursuit_id="x", as_of="t")   # état inconnu
    with pytest.raises(ValueError):
        Outcome(state="awaiting", project_id="p", pursuit_id="x", as_of="t")   # awaiting sans raison
    with pytest.raises(ValueError):
        Outcome(state="terminal", project_id="p", pursuit_id="x", as_of="t",
                wait_reason="governance")                        # raison hors awaiting


def test_wait_reason_does_not_proliferate_root_statuses():
    # governance ET clarification partagent le MÊME état 'awaiting' — aucun statut racine par raison.
    gov = Outcome(state="awaiting", project_id="p", pursuit_id="x", as_of="t", wait_reason="governance")
    clar = Outcome(state="awaiting", project_id="p", pursuit_id="x", as_of="t", wait_reason="clarification")
    assert gov.state == clar.state == "awaiting" and gov.wait_reason != clar.wait_reason


def test_outcome_need_is_optional_not_required():
    o = Outcome(state="active", project_id="p", pursuit_id="x", as_of="t")   # sans 'need'
    assert o.need is None


# ===================================================================== #
# Point 3 — clarification vs gouvernance : représentable sans nouvelle méthode
# ===================================================================== #
def test_clarification_and_governance_resume_are_representable():
    # Pursuit suspendue en attente humaine ; reprise après GOUVERNANCE et après CLARIFICATION,
    # toutes deux via resume_intent sur la MÊME identité, sans nouvelle méthode publique.
    suspended = Outcome(state="awaiting", project_id="p", pursuit_id="pursuit_zzz", as_of="t",
                        wait_reason="clarification")
    after_clar = resume_intent(suspended.pursuit_id, payload={"clarification": "plutôt Y"})
    after_gov = resume_intent(suspended.pursuit_id, payload={"decision": "validated"})
    assert after_clar.kind == after_gov.kind == "resume"
    assert after_clar.pursuit_ref == after_gov.pursuit_ref == "pursuit_zzz"
    assert after_clar.payload["clarification"] == "plutôt Y" and after_gov.payload["decision"] == "validated"


# ===================================================================== #
# Injection — capacités interchangeables par Protocol (R8)
# ===================================================================== #
def test_capabilities_accepts_protocol_satisfying_fakes():
    assert _caps().roles() == ("understanding", "specification", "build")


def test_capabilities_reject_missing_or_non_conforming():
    with pytest.raises(CapabilityInjectionError):
        Capabilities(understanding=None, specification=_FakeSpecification(), build=_FakeBuild())
    with pytest.raises(CapabilityInjectionError):
        Capabilities(understanding=_FakeUnderstanding(), specification=object(), build=_FakeBuild())
    with pytest.raises(CapabilityInjectionError):
        Capabilities(understanding=_FakeUnderstanding(), specification=_FakeSpecification(), build=object())


def test_two_distinct_conforming_implementations_are_both_accepted():
    class _OtherUnderstanding(_FakeUnderstanding):
        name = "other"
    caps = Capabilities(understanding=_OtherUnderstanding(),
                        specification=_FakeSpecification(), build=_FakeBuild())
    assert caps.understanding.name == "other"


# ===================================================================== #
# Identité publique de BrainAI
# ===================================================================== #
def test_brainai_construction_and_identity():
    caps = _caps(); brain = BrainAI(caps)
    assert brain.capabilities is caps
    assert brain.faculties == ("understanding", "specification", "build")
    assert callable(brain.clock)


def test_brainai_rejects_non_capabilities():
    with pytest.raises(CapabilityInjectionError):
        BrainAI(object())


def test_clock_is_injectable():
    brain = BrainAI(_caps(), clock=lambda: "2099-01-01T00:00:00+00:00")
    assert brain.clock() == "2099-01-01T00:00:00+00:00"


# ===================================================================== #
# pursue — refus AVANT toute frontière (aucune capacité appelée)
# ===================================================================== #
@pytest.mark.parametrize("bad_intent", [
    "un besoin en chaîne brute", {"kind": "need"}, None,
    Intent(kind="need", need=""), Intent(kind="need", need="   "),
    Intent(kind="observe"), Intent(kind="resume", pursuit_ref=""),
])
def test_pursue_refuses_invalid_intent_before_any_call(bad_intent):
    caps = _caps(); brain = BrainAI(caps)
    with pytest.raises((IntentError, NeedError)):
        brain.pursue(bad_intent, context=_ctx())
    assert _all_calls(caps) == 0


@pytest.mark.parametrize("ctx_over", [
    {"budget_usd": 0}, {"budget_usd": -1.0}, {"budget_usd": "5"},
    {"project_id": ""}, {"workspace": None}, {"stores": None},
])
def test_pursue_refuses_invalid_context_before_any_call(ctx_over):
    caps = _caps(); brain = BrainAI(caps)
    with pytest.raises(GovernanceError):
        brain.pursue(need_intent("Un besoin réel"), context=_ctx(**ctx_over))
    assert _all_calls(caps) == 0


def test_pursue_refuses_non_runcontext():
    caps = _caps(); brain = BrainAI(caps)
    with pytest.raises(GovernanceError):
        brain.pursue(need_intent("Un besoin réel"), context={"budget_usd": 5.0})
    assert _all_calls(caps) == 0


# ===================================================================== #
# pursue — entrée valide : seuil Tâche 2 (aucune orchestration en T1)
# ===================================================================== #
def test_pursue_valid_need_reaches_t2_seam_without_calling_capabilities():
    caps = _caps(); brain = BrainAI(caps)
    with pytest.raises(NotImplementedError) as exc:
        brain.pursue(need_intent("Une application pour un refuge animalier"), context=_ctx())
    assert "Tâche 2" in str(exc.value)
    assert _all_calls(caps) == 0


def test_pursue_valid_resume_is_accepted_and_reaches_t2_seam():
    caps = _caps(); brain = BrainAI(caps)
    with pytest.raises(NotImplementedError):
        brain.pursue(resume_intent("pursuit_abc"), context=_ctx())
    assert _all_calls(caps) == 0


# ===================================================================== #
# Validations pures
# ===================================================================== #
def test_validate_need_returns_clean():
    assert validate_need("  besoin  ") == "besoin"
    with pytest.raises(NeedError):
        validate_need("")


def test_validate_run_context_accepts_valid_and_rejects_invalid():
    validate_run_context(_ctx())
    with pytest.raises(GovernanceError):
        validate_run_context(_ctx(budget_usd=0))


# ===================================================================== #
# Surface publique
# ===================================================================== #
def test_public_api_surface():
    assert set(BA.__all__) == {
        "BrainAI", "Capabilities", "RunContext", "Outcome", "Intent", "PURSUIT_STATES",
        "BrainAIError", "CapabilityInjectionError", "IntentError", "NeedError", "GovernanceError",
        "need_intent", "resume_intent", "validate_need", "validate_intent", "validate_run_context",
        "new_pursuit_id",
    }
