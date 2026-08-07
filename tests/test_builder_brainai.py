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
        "BrainAI", "Capabilities", "RunContext", "Stores", "Outcome", "Intent", "PURSUIT_STATES",
        "BrainAIError", "CapabilityInjectionError", "IntentError", "NeedError", "GovernanceError",
        "need_intent", "resume_intent", "validate_need", "validate_intent", "validate_run_context",
        "new_pursuit_id",
    }


# ===================================================================== #
# TÂCHE 2 — orchestration réelle de l'arc Need → Understanding → Specification → Build
# ===================================================================== #
import json  # noqa: E402
from scc_brainai_bootstrap.builder.brainai import Stores  # noqa: E402
from scc_brainai_bootstrap.builder.proposals import ProposalStore  # noqa: E402
from scc_brainai_bootstrap.builder.specifications import SpecificationStore  # noqa: E402
from scc_brainai_bootstrap.builder.builds import BuildStore  # noqa: E402
from scc_brainai_bootstrap.builder.workspace import Workspace  # noqa: E402

_BRIEF = {"objective": "Gérer un refuge", "context": "Assoc", "actors": ["A"], "scope": ["S"],
          "assumptions": ["H"], "open_questions": ["Q ?"], "constraints": ["C"]}
_SPEC = {"product_objective": "App refuge", "users_and_roles": ["U"], "functional_scope": ["F"],
         "features": ["Fiche"], "entities_and_data": ["Animal"], "key_journeys": ["J"],
         "constraints": ["C"], "acceptance_criteria": ["AC"], "assumptions": ["H"],
         "open_questions": ["Q ?"], "out_of_scope": ["Hors"]}
_MANIFEST = {"name": "Refuge", "summary": "Résumé du produit refuge.", "users": ["U"],
             "features": ["Fiche"], "entities": ["Animal"]}


def _env(result_obj, *, ok=True, cost=0.02):
    return {"type": "result", "subtype": "success" if ok else "error_max_turns", "is_error": not ok,
            "api_error_status": None, "num_turns": 1,
            "result": result_obj if isinstance(result_obj, str) else json.dumps(result_obj, ensure_ascii=False),
            "total_cost_usd": cost, "usage": {"input_tokens": 10, "output_tokens": 20}}


class _ArcCap:
    """Adaptateur factice paramétrable (compte les appels ; garde budget)."""

    def __init__(self, capability, envelope, *, budget_floor=0.50, cost=0.02, model="fake-model"):
        self.capability = capability; self.name = "claude_code"; self.model = model
        self._env = envelope; self._floor = budget_floor; self._cost = cost; self.calls = 0

    def propose(self, _payload, *, cwd, budget_remaining_usd):
        self.calls += 1
        if budget_remaining_usd < self._floor:
            return {"called": False, "refused": "budget insuffisant", "envelope": None, "exit_code": None,
                    "timed_out": False, "prompt": "p", "argv": ["claude"], "stdout": None, "stderr": None}
        return {"called": True, "envelope": self._env, "exit_code": 0, "timed_out": False, "prompt": "p",
                "argv": ["claude", "-p", "x"], "stdout": "out", "stderr": ""}


def _caps_arc(*, u_env=None, s_env=None, b_env=None, u_cost=0.02, s_cost=0.02, b_cost=0.02, floor=0.50):
    u = _ArcCap("understanding", u_env if u_env is not None else _env(_BRIEF, cost=u_cost), budget_floor=floor, cost=u_cost)
    s = _ArcCap("specification", s_env if s_env is not None else _env(_SPEC, cost=s_cost), budget_floor=floor, cost=s_cost)
    b = _ArcCap("build", b_env if b_env is not None else _env(_MANIFEST, cost=b_cost), budget_floor=floor, cost=b_cost)
    return Capabilities(understanding=u, specification=s, build=b)


def _run_context(tmp_path, *, budget_usd=5.0):
    stores = Stores(proposals=ProposalStore(tmp_path / "prop.jsonl"),
                    specifications=SpecificationStore(tmp_path / "spec.jsonl"),
                    builds=BuildStore(tmp_path / "build.jsonl"))
    ws = Workspace(tmp_path / "exec-root", "refuge-demo")
    return RunContext(budget_usd=budget_usd, project_id="refuge-demo", workspace=ws, stores=stores)


def _brain_arc(caps):
    return BrainAI(caps, clock=lambda: "2026-08-07T00:00:00+00:00")


def test_pursue_full_arc_success_awaiting_governance_with_provenance(tmp_path):
    caps = _caps_arc(); brain = _brain_arc(caps); ctx = _run_context(tmp_path)
    out = brain.pursue(need_intent("Une application pour un refuge animalier"), context=ctx)
    # succès complet, NON autoritatif : en attente de gouvernance humaine
    assert out.state == "awaiting" and out.wait_reason == "governance"
    assert out.pursuit_id.startswith("pursuit_") and out.artefact is not None
    # steps ordonnés understanding → specification → build, tous proposed
    assert [s["faculty"] for s in out.steps] == ["understanding", "specification", "build"]
    assert all(s["status"] == "proposed" for s in out.steps)
    # un seul appel par rung (aucun retry)
    assert caps.understanding.calls == 1 and caps.specification.calls == 1 and caps.build.calls == 1
    # provenance chaînée reconstructible via les faits enregistrés
    brief = ctx.stores.proposals.read_all()[0]
    spec = ctx.stores.specifications.read_all()[0]
    build = ctx.stores.builds.read_all()[0]
    assert brief["pursuit_ref"] == out.pursuit_id                    # Brief ancré à la Pursuit
    assert spec["brief_ref"] == brief["proposal_id"]                 # Spéc → Brief
    assert build["spec_ref"] == spec["specification_id"]             # Build → Spéc
    assert build["artefact"]["relative_path"] == "manifest.json"
    assert (ctx.workspace.path / "manifest.json").exists()          # artefact matérialisé (confiné)
    # coût total = somme honnête des réels
    assert out.cost_total["kind"] == "real" and abs(out.cost_total["value"] - 0.06) < 1e-9


def test_pursue_stops_at_first_failure_understanding(tmp_path):
    caps = _caps_arc(u_env=_env("pas du JSON"))                      # Brief invalide → failed
    brain = _brain_arc(caps); ctx = _run_context(tmp_path)
    out = brain.pursue(need_intent("besoin"), context=ctx)
    assert out.state == "terminal"
    assert [s["faculty"] for s in out.steps] == ["understanding"]
    assert out.steps[0]["status"] == "failed"
    assert caps.specification.calls == 0 and caps.build.calls == 0   # STOP au 1er échec, aval non appelé
    assert ctx.stores.specifications.read_all() == [] and ctx.stores.builds.read_all() == []
    assert not (ctx.workspace.path / "manifest.json").exists()


def test_pursue_stops_at_first_failure_specification(tmp_path):
    caps = _caps_arc(s_env=_env("pas du JSON"))                      # Spéc invalide → failed
    brain = _brain_arc(caps); ctx = _run_context(tmp_path)
    out = brain.pursue(need_intent("besoin"), context=ctx)
    assert out.state == "terminal"
    assert [s["faculty"] for s in out.steps] == ["understanding", "specification"]
    assert out.steps[0]["status"] == "proposed" and out.steps[1]["status"] == "failed"
    assert caps.build.calls == 0                                     # build non appelé
    assert ctx.stores.builds.read_all() == []


def test_pursue_budget_stops_mid_arc(tmp_path):
    # budget couvre le rung 1 (coût 0.30) mais pas le plafond du rung 2 (0.50).
    caps = _caps_arc(u_cost=0.30, floor=0.50)
    brain = _brain_arc(caps); ctx = _run_context(tmp_path, budget_usd=0.60)
    out = brain.pursue(need_intent("besoin"), context=ctx)
    assert out.state == "terminal" and out.refused == "budget insuffisant"
    assert [s["faculty"] for s in out.steps] == ["understanding", "specification"]
    assert out.steps[1]["status"] == "refused"
    assert caps.specification.calls == 1 and caps.build.calls == 0   # spec a refusé AVANT frontière (called=False), build jamais
    assert ctx.stores.specifications.read_all() == []               # aucun fait spéc


def test_pursue_budget_refused_before_any_real_call(tmp_path):
    caps = _caps_arc(floor=0.50)
    brain = _brain_arc(caps); ctx = _run_context(tmp_path, budget_usd=0.10)  # < plafond rung 1
    out = brain.pursue(need_intent("besoin"), context=ctx)
    assert out.state == "terminal" and out.refused == "budget insuffisant"
    assert [s["faculty"] for s in out.steps] == ["understanding"] and out.steps[0]["status"] == "refused"
    assert ctx.stores.proposals.read_all() == []                    # aucun fait produit
    assert caps.specification.calls == 0 and caps.build.calls == 0


def test_cost_total_partial_when_a_rung_cost_unavailable(tmp_path):
    env_no_cost = _env(_BRIEF); del env_no_cost["total_cost_usd"]    # coût understanding unavailable
    caps = _caps_arc(u_env=env_no_cost)
    brain = _brain_arc(caps); ctx = _run_context(tmp_path)
    out = brain.pursue(need_intent("besoin"), context=ctx)
    assert out.state == "awaiting"
    assert out.cost_total["kind"] == "partial"                      # honnête : un coût manquant → partiel
    assert abs(out.cost_total["value"] - 0.04) < 1e-9               # somme des réels (spec+build)


def test_pursue_never_official_and_no_data_touch(tmp_path):
    # aucun état officiel : facts dans stores injectés (tmp), artefact dans workspace (tmp) ; data/ gardé par conftest.
    caps = _caps_arc(); brain = _brain_arc(caps); ctx = _run_context(tmp_path)
    out = brain.pursue(need_intent("besoin"), context=ctx)
    assert out.state == "awaiting"                                  # jamais 'official'/'validated'
    produced = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    assert produced == ["build.jsonl", "manifest.json", "prop.jsonl", "spec.jsonl"]  # rien hors tmp injecté
