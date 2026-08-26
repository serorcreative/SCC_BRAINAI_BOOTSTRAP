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
    converse_intent,
    need_intent,
    new_pursuit_id,
    realize_intent,
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
    validate_intent(converse_intent("bonjour"))                     # 1er tour : sans pursuit_ref
    validate_intent(converse_intent("suite", pursuit_ref="pursuit_x"))
    validate_intent(realize_intent("pursuit_x"))
    validate_intent(resume_intent("pursuit_x"))
    for bad in ("pas une intention", Intent(kind=""), Intent(kind="observe"),
                Intent(kind="resume", pursuit_ref=""),
                Intent(kind="realize", pursuit_ref=""),             # réalisation sans identité
                Intent(kind="converse", payload=None),              # message absent
                Intent(kind="converse", payload={"message": "   "}),  # message vide
                Intent(kind="converse", payload={"message": "ok"}, pursuit_ref="  ")):  # ref vide
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
    with pytest.raises(IntentError):
        new_pursuit_id(realize_intent("pursuit_X"), "proj", "t")  # ni une réalisation


def test_converse_first_turn_mints_a_pursuit_identity():
    # Le dialogue EST une Pursuit : le premier message frappe une identité (aucun conversation_id séparé).
    d = new_pursuit_id(converse_intent("bonjour"), "proj", "2026-08-07T00:00:00+00:00")
    d2 = new_pursuit_id(converse_intent("bonjour"), "proj", "2026-08-07T00:00:00+00:00")
    d3 = new_pursuit_id(converse_intent("autre"), "proj", "2026-08-07T00:00:00+00:00")
    assert d.startswith("pursuit_") and d == d2 and d != d3       # adressé au message


def test_resume_keeps_the_same_pursuit_identity():
    pid = new_pursuit_id(need_intent("besoin"), "proj", "2026-08-07T00:00:00+00:00")
    again = resume_intent(pid)
    assert again.pursuit_ref == pid                              # la Pursuit reste la même


# ===================================================================== #
# Conversation = même Pursuit : message dans payload, jamais dans need
# ===================================================================== #
def test_converse_intent_carries_message_in_payload_not_need():
    i = converse_intent("  Je veux réfléchir à un projet  ")
    assert i.kind == "converse"
    assert i.payload == {"message": "Je veux réfléchir à un projet"}  # message nettoyé, dans payload
    assert i.need is None                                             # need reste réservé au genre 'need'
    assert i.pursuit_ref is None                                      # 1er tour : identité pas encore frappée
    j = converse_intent("suite", pursuit_ref="  pursuit_abc  ")
    assert j.pursuit_ref == "pursuit_abc" and j.payload == {"message": "suite"}
    with pytest.raises(IntentError):                                 # message vide ⇒ IntentError (pas NeedError)
        converse_intent("   ")


def test_realize_intent_targets_the_same_pursuit():
    r = realize_intent("  pursuit_abc  ")
    assert r.kind == "realize" and r.pursuit_ref == "pursuit_abc" and r.need is None
    with pytest.raises(IntentError):
        realize_intent("")


def test_dialogue_then_realization_share_one_pursuit_identity():
    # Doctrine : Pursuit = unité de cognition. Le dialogue mûrit puis la réalisation s'exécute sur la MÊME identité.
    pid = new_pursuit_id(converse_intent("un besoin flou"), "proj", "2026-08-07T00:00:00+00:00")
    assert converse_intent("précision", pursuit_ref=pid).pursuit_ref == pid
    assert realize_intent(pid).pursuit_ref == pid                    # aucune seconde identité cognitive


def test_outcome_can_carry_reply_and_proposal_without_authorizing():
    # Tour conversationnel : reply + proposal (appréciation) — jamais autoritatif, pursuit_id toujours requis.
    out = Outcome(state="awaiting", wait_reason="clarification", project_id="p", pursuit_id="pursuit_x",
                  as_of="t", reply="Peux-tu préciser la cible ?",
                  proposal={"readiness": "continue"})
    assert out.reply.startswith("Peux-tu") and out.proposal["readiness"] == "continue"
    ready = Outcome(state="awaiting", wait_reason="governance", project_id="p", pursuit_id="pursuit_x",
                    as_of="t", proposal={"readiness": "ready", "matured_need": "Gérer un refuge"})
    assert ready.proposal["matured_need"] == "Gérer un refuge"       # proposition, PAS une autorisation
    with pytest.raises(TypeError):                                   # pursuit_id reste obligatoire
        Outcome(state="active", project_id="p", as_of="t")           # noqa: no pursuit_id


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


def test_conversation_capability_is_optional_additive_and_validated():
    from scc_brainai_bootstrap.builder.conversation import ConversationCapability

    class _FakeConversation:                          # conforme au Protocol de dialogue
        capability = "conversation"; name = "fake"; model = "fake-model"
        def propose(self, message, *, history, cwd, budget_remaining_usd):
            return {"called": False, "envelope": None}

    assert isinstance(_FakeConversation(), ConversationCapability)
    bare = _caps()                                    # absente ⇒ arc historique intact
    assert bare.conversation is None and bare.roles() == ("understanding", "specification", "build")
    withconv = Capabilities(understanding=_FakeUnderstanding(), specification=_FakeSpecification(),
                            build=_FakeBuild(), conversation=_FakeConversation())
    assert withconv.conversation is not None
    assert withconv.roles() == ("understanding", "specification", "build")  # le dialogue n'est pas une étape
    with pytest.raises(CapabilityInjectionError):     # présente mais non conforme ⇒ refus
        Capabilities(understanding=_FakeUnderstanding(), specification=_FakeSpecification(),
                     build=_FakeBuild(), conversation=object())


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
# pursue — resume reste au seuil (non encore orchestré) ; converse/realize : voir section CONVERSATION T2
# ===================================================================== #
def test_pursue_valid_resume_is_accepted_and_reaches_seam():
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
        "need_intent", "converse_intent", "realize_intent", "resume_intent", "validate_need",
        "validate_intent", "validate_run_context", "new_pursuit_id",
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


# ===================================================================== #
# TÂCHE 2 — CONVERSATION : une conversation EST une Pursuit (dialogue → réalisation, même identité)
# ===================================================================== #
from scc_brainai_bootstrap.builder.turns import TurnStore  # noqa: E402


class _ConvCap:
    """Capacité de dialogue **factice** : consomme une enveloppe par tour, mémorise l'historique reçu et
    garde le budget (comme l'adaptateur réel : refus AVANT frontière si le reste ne couvre pas le plafond)."""

    capability = "conversation"; name = "claude_code"; model = "fake-model"

    def __init__(self, envelopes, *, floor=0.50):
        self._envelopes = list(envelopes); self._floor = floor
        self.calls = 0; self.seen_history = []

    def propose(self, message, *, history, cwd, budget_remaining_usd):
        self.calls += 1
        self.seen_history.append(list(history))
        if budget_remaining_usd < self._floor:
            return {"called": False, "refused": "budget insuffisant", "envelope": None, "exit_code": None,
                    "timed_out": False, "prompt": "p:" + message, "argv": ["claude"],
                    "stdout": None, "stderr": None}
        env = self._envelopes[min(self.calls - 1, len(self._envelopes) - 1)]
        return {"called": True, "envelope": env, "exit_code": 0, "timed_out": False,
                "prompt": "p:" + message, "argv": ["claude", "-p", message], "stdout": "out", "stderr": ""}


def _turn_env(reply, readiness, matured=None):
    obj = {"reply": reply, "readiness": readiness}
    if matured is not None:
        obj["matured_need"] = matured
    return _env(obj)


def _caps_conv(conv, **arc):
    base = _caps_arc(**arc)
    return Capabilities(understanding=base.understanding, specification=base.specification,
                        build=base.build, conversation=conv)


def _conv_context(tmp_path, *, budget_usd=5.0):
    stores = Stores(proposals=ProposalStore(tmp_path / "prop.jsonl"),
                    specifications=SpecificationStore(tmp_path / "spec.jsonl"),
                    builds=BuildStore(tmp_path / "build.jsonl"),
                    turns=TurnStore(tmp_path / "turns.jsonl"))
    ws = Workspace(tmp_path / "exec-root", "refuge-demo")
    return RunContext(budget_usd=budget_usd, project_id="refuge-demo", workspace=ws, stores=stores)


def _arc_calls(caps):
    return caps.understanding.calls + caps.specification.calls + caps.build.calls


def test_converse_first_turn_dialogues_persists_and_never_realizes(tmp_path):
    conv = _ConvCap([_turn_env("Peux-tu préciser la cible ?", "continue")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    out = brain.pursue(converse_intent("Je veux un truc pour mon refuge"), context=ctx)
    assert out.state == "active" and out.wait_reason is None          # dialogue vivant
    assert out.pursuit_id.startswith("pursuit_")
    assert out.reply == "Peux-tu préciser la cible ?"
    assert out.proposal == {"readiness": "continue"}
    assert _arc_calls(caps) == 0 and ctx.stores.proposals.read_all() == []  # l'arc n'est JAMAIS lancé
    turns = ctx.stores.turns.read_all()                               # un fait tour persisté, rattaché à la Pursuit
    assert len(turns) == 1 and turns[0]["pursuit_ref"] == out.pursuit_id
    assert turns[0]["status"] == "proposed" and turns[0]["fact_type"] == "turn"
    assert turns[0]["message"] == "Je veux un truc pour mon refuge"
    assert conv.seen_history[0] == []                                 # 1er tour : aucun historique


def test_converse_second_turn_reuses_identity_and_reads_history_server_side(tmp_path):
    conv = _ConvCap([_turn_env("ok, et le périmètre ?", "continue"),
                     _turn_env("c'est clair", "ready", matured="Gérer un refuge animalier")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    out1 = brain.pursue(converse_intent("premier message"), context=ctx)
    pid = out1.pursuit_id
    out2 = brain.pursue(converse_intent("deuxième message", pursuit_ref=pid), context=ctx)
    assert out2.pursuit_id == pid                                     # MÊME Pursuit (aucune 2e identité)
    assert out2.state == "awaiting" and out2.wait_reason == "confirmation"
    assert out2.reply == "c'est clair"
    # matured_need STRUCTURÉ (C9) : la chaîne legacy émise par la fake est normalisée en structure (D3).
    assert out2.proposal["readiness"] == "ready"
    assert out2.proposal["matured_need"] == {"besoin_fondamental": "Gérer un refuge animalier",
                                             "solutions_privilegiees": [], "inconnues_nommees": [],
                                             "hypotheses_actives": []}
    hist2 = conv.seen_history[1]                                      # historique relu CÔTÉ MOTEUR au 2e tour
    assert {"role": "user", "content": "premier message"} in hist2
    assert {"role": "assistant", "content": "ok, et le périmètre ?"} in hist2
    turns = ctx.stores.turns.read_all()
    assert len(turns) == 2 and all(t["pursuit_ref"] == pid for t in turns)


def test_realize_reads_matured_need_and_runs_arc_on_same_pursuit(tmp_path):
    conv = _ConvCap([_turn_env("compris", "ready", matured="Une application pour un refuge")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    out1 = brain.pursue(converse_intent("besoin encore flou"), context=ctx)
    pid = out1.pursuit_id
    assert out1.wait_reason == "confirmation" and _arc_calls(caps) == 0   # rien lancé sans confirmation
    out2 = brain.pursue(realize_intent(pid), context=ctx)             # CONFIRMATION humaine
    assert out2.pursuit_id == pid                                     # MÊME identité, aucun nouveau pursuit_id
    assert out2.state == "awaiting" and out2.wait_reason == "governance"
    assert [s["faculty"] for s in out2.steps] == ["understanding", "specification", "build"]
    brief = ctx.stores.proposals.read_all()[0]
    assert brief["pursuit_ref"] == pid                               # Brief ancré à la MÊME Pursuit
    # besoin de l'arc = matured_need relu côté moteur, APLATI en texte typé (A2) : le besoin fondamental y figure.
    assert "Une application pour un refuge" in brief["need"] and "BESOIN FONDAMENTAL" in brief["need"]
    assert realize_intent(pid).payload is None                       # le besoin ne vient JAMAIS de l'UI


def test_realize_without_matured_proposal_refuses_without_running_arc(tmp_path):
    conv = _ConvCap([_turn_env("continue à explorer", "continue")])   # jamais 'ready'
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    out1 = brain.pursue(converse_intent("flou"), context=ctx)
    out2 = brain.pursue(realize_intent(out1.pursuit_id), context=ctx)
    assert out2.state == "terminal" and out2.refused == "Aucun besoin mûri disponible."   # aucune convergence
    assert out2.pursuit_id == out1.pursuit_id and _arc_calls(caps) == 0
    out3 = brain.pursue(realize_intent("pursuit_inconnu"), context=ctx)  # Pursuit sans aucun tour
    assert out3.state == "terminal" and out3.refused == "Aucun besoin mûri disponible."


# --------------------------------------------------------------------- #
# Garde de convergence A4-1 — realize ne part que depuis la DERNIÈRE convergence encore valide.
# Le moteur ne lit jamais le contenu des messages : il applique l'invariant sur les faits ``turn`` persistés.
# --------------------------------------------------------------------- #
def _drive_converse(brain, ctx, message, pursuit_ref=None):
    return brain.pursue(converse_intent(message, pursuit_ref=pursuit_ref), context=ctx)


def test_convergence_cas1_ready_then_realize_runs_arc(tmp_path):
    # Cas 1 : ready ↓ realize ⇒ OK (le dernier tour EST la convergence mûrie).
    conv = _ConvCap([_turn_env("compris", "ready", matured="Une application pour un refuge")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    pid = _drive_converse(brain, ctx, "besoin flou").pursuit_id
    out = brain.pursue(realize_intent(pid), context=ctx)
    assert out.state == "awaiting" and out.wait_reason == "governance"
    assert [s["faculty"] for s in out.steps] == ["understanding", "specification", "build"]
    assert "Une application pour un refuge" in ctx.stores.proposals.read_all()[0]["need"]


def test_convergence_cas2_ready_then_continue_refuses_as_evolved(tmp_path):
    # Cas 2 : ready ↓ continue ↓ realize ⇒ refus (la convergence n'est plus la dernière). Aucun arc.
    conv = _ConvCap([_turn_env("compris", "ready", matured="X"),
                     _turn_env("on continue d'explorer", "continue")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    pid = _drive_converse(brain, ctx, "t1").pursuit_id
    _drive_converse(brain, ctx, "t2", pursuit_ref=pid)                    # tour continue POSTÉRIEUR
    out = brain.pursue(realize_intent(pid), context=ctx)
    assert out.state == "terminal" and _arc_calls(caps) == 0
    assert out.refused.startswith("La conversation a évolué depuis la dernière convergence.")


def test_convergence_cas3_ready_then_failed_refuses_as_failed(tmp_path):
    # Cas 3 : ready ↓ failed ↓ realize ⇒ refus (dernier tour illisible), quel que soit le contenu. Aucun arc.
    conv = _ConvCap([_turn_env("compris", "ready", matured="X"),
                     _env("pas du JSON")])                                # tour suivant → failed
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    pid = _drive_converse(brain, ctx, "t1").pursuit_id
    _drive_converse(brain, ctx, "t2", pursuit_ref=pid)                    # tour failed POSTÉRIEUR
    assert ctx.stores.turns.read_all()[-1]["status"] == "failed"         # le fait failed est bien le dernier
    out = brain.pursue(realize_intent(pid), context=ctx)
    assert out.state == "terminal" and _arc_calls(caps) == 0
    assert out.refused.startswith("Votre dernier message n'a pas pu être traité.")


def test_convergence_cas4_revalidation_after_failed_runs_arc(tmp_path):
    # Cas 4 : ready ↓ failed ↓ converse ↓ ready ↓ realize ⇒ OK (revalidation de convergence).
    conv = _ConvCap([_turn_env("c1", "ready", matured="Ancien besoin"),
                     _env("pas du JSON"),                                 # failed intercalé
                     _turn_env("c2", "ready", matured="Nouveau besoin révisé")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    pid = _drive_converse(brain, ctx, "t1").pursuit_id
    _drive_converse(brain, ctx, "t2", pursuit_ref=pid)                    # failed
    _drive_converse(brain, ctx, "t3", pursuit_ref=pid)                    # nouvelle convergence
    out = brain.pursue(realize_intent(pid), context=ctx)
    assert out.state == "awaiting" and out.wait_reason == "governance" and _arc_calls(caps) == 3
    assert "Nouveau besoin révisé" in ctx.stores.proposals.read_all()[0]["need"]  # besoin = DERNIÈRE convergence


def test_convergence_cas5_realization_facts_never_invalidate_convergence(tmp_path):
    # Cas 5 : ready ↓ realize ↓ Brief/Spec/Manifest ; la garde ne considère QUE les faits turn — les faits de
    # réalisation ne suspendent jamais la convergence. Preuve : un second realize repart de la même convergence.
    conv = _ConvCap([_turn_env("compris", "ready", matured="Une application pour un refuge")])
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    pid = _drive_converse(brain, ctx, "besoin").pursuit_id
    out1 = brain.pursue(realize_intent(pid), context=ctx)
    assert out1.state == "awaiting" and out1.wait_reason == "governance"  # arc produit (Brief/Spec/Manifest)
    turns_before = ctx.stores.turns.read_all()
    out2 = brain.pursue(realize_intent(pid), context=ctx)                 # aucun nouveau tour entre-temps
    assert out2.state == "awaiting" and out2.wait_reason == "governance"  # convergence toujours courante
    assert ctx.stores.turns.read_all() == turns_before                   # la réalisation n'ajoute AUCUN fait turn


def test_convergence_cas6_a6_correction_after_confirmation_suspends_and_confirmation_inert(tmp_path):
    # A6 (JALON 2) : une correction POSTÉRIEURE à un fait ``convergence_confirmed`` **périme** la convergence.
    # Le gate re-vérifie la chronologie des tours ; le fait de confirmation est **inert** (ne re-déclenche rien,
    # append-only). Séquence : ready ↓ realize (confirme + arc) ↓ correction ↓ realize ⇒ REFUS ``EVOLVED``.
    from scc_brainai_bootstrap.builder.confirmations import ConfirmationStore
    conv = _ConvCap([_turn_env("compris", "ready", matured="Une application pour un refuge"),
                     _turn_env("finalement, change tout", "continue")])   # correction postérieure
    caps = _caps_conv(conv); brain = _brain_arc(caps)
    stores = Stores(proposals=ProposalStore(tmp_path / "prop.jsonl"),
                    specifications=SpecificationStore(tmp_path / "spec.jsonl"),
                    builds=BuildStore(tmp_path / "build.jsonl"),
                    turns=TurnStore(tmp_path / "turns.jsonl"),
                    confirmations=ConfirmationStore(tmp_path / "conf.jsonl"))
    ctx = RunContext(budget_usd=5.0, project_id="refuge-demo",
                     workspace=Workspace(tmp_path / "exec-root", "refuge-demo"), stores=stores)
    pid = _drive_converse(brain, ctx, "besoin").pursuit_id
    out1 = brain.pursue(realize_intent(pid, actor="Frédérique"), context=ctx)   # confirmation humaine → arc
    assert out1.state == "awaiting" and out1.wait_reason == "governance"
    assert len(stores.confirmations.read_all()) == 1                     # UN fait convergence_confirmed
    _drive_converse(brain, ctx, "t2", pursuit_ref=pid)                    # CORRECTION postérieure (continue)
    out2 = brain.pursue(realize_intent(pid, actor="Frédérique"), context=ctx)   # 2e realize
    assert out2.state == "terminal"                                      # convergence périmée → refus
    assert out2.refused.startswith("La conversation a évolué depuis la dernière convergence.")
    assert len(stores.confirmations.read_all()) == 1                     # inert : AUCUN nouveau fait, append-only


def test_converse_budget_refused_before_frontier_leaves_no_fact(tmp_path):
    conv = _ConvCap([_turn_env("x", "continue")], floor=0.50)
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path, budget_usd=0.10)
    out = brain.pursue(converse_intent("bonjour"), context=ctx)
    assert out.state == "terminal" and out.refused == "budget insuffisant"
    assert ctx.stores.turns.read_all() == []                         # aucun fait tour (refus avant frontière)


def test_converse_failed_turn_is_terminal_but_traced(tmp_path):
    conv = _ConvCap([_env("pas du JSON")])                           # tour illisible → failed
    caps = _caps_conv(conv); brain = _brain_arc(caps); ctx = _conv_context(tmp_path)
    out = brain.pursue(converse_intent("bonjour"), context=ctx)
    assert out.state == "terminal" and out.refused == "format tour invalide"
    turns = ctx.stores.turns.read_all()
    assert len(turns) == 1 and turns[0]["status"] == "failed"        # échec conservé comme trace
    # un tour raté n'entre pas dans l'historique ni ne fournit de matured_need
    assert brain._history(ctx.stores.turns, out.pursuit_id) == []


def test_converse_requires_conversation_capability(tmp_path):
    brain = _brain_arc(_caps_arc()); ctx = _conv_context(tmp_path)   # aucune capacité 'conversation'
    with pytest.raises(CapabilityInjectionError):
        brain.pursue(converse_intent("bonjour"), context=ctx)


def test_conversational_intents_require_turns_store(tmp_path):
    conv = _ConvCap([_turn_env("x", "continue")])
    brain = _brain_arc(_caps_conv(conv))
    ctx_noturns = _run_context(tmp_path)                             # Stores sans 'turns'
    with pytest.raises(GovernanceError):
        brain.pursue(converse_intent("bonjour"), context=ctx_noturns)
    with pytest.raises(GovernanceError):
        brain.pursue(realize_intent("pursuit_x"), context=ctx_noturns)
    assert conv.calls == 0                                           # refus avant tout appel
