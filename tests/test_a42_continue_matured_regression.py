"""Non-régression — défaut **A4-2** révélé par le test produit RÉEL (``pursuit_e4b6033b3b08``, tour 8).

Déterministe, **0 €, aucun appel LLM**. Prouve que ``readiness='continue'`` + ``matured_need`` **COEXISTENT** :
la conception/challenge continue librement après maturation, le ``matured_need`` **n'est jamais perdu**, le
message **reste dans l'historique** relu, et la **RÉALISATION reste impossible** sans ``ready`` + acte humain
``realize`` (garde A4-1 + confirmation D3). Aucun ``matured_need`` n'est transformé en ``ready`` ; aucune
réalisation n'est lancée automatiquement.
"""

from __future__ import annotations

import json

from scc_brainai_bootstrap.builder import brainai as E
from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, Stores, converse_intent, realize_intent)
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.confirmations import ConfirmationStore
from scc_brainai_bootstrap.builder.conversation import build_turn
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.builder.turns import TurnStore
from scc_brainai_bootstrap.builder.workspace import Workspace


def _env(obj, *, ok=True):
    return {"type": "result", "subtype": "success" if ok else "error", "is_error": not ok,
            "api_error_status": None, "num_turns": 1, "result": json.dumps(obj, ensure_ascii=False),
            "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "output_tokens": 1}}


def _matured(besoin="besoin défini"):
    return {"besoin_fondamental": besoin, "solutions_privilegiees": [],
            "inconnues_nommees": [], "hypotheses_actives": []}


def _turn(obj):
    return build_turn(message="m", prompt="p", capability="conversation", adapter="fake", model="fake",
                      envelope=_env(obj), exit_code=0, timed_out=False, as_of="2026-08-22T00:00:00+00:00",
                      argv=["x"], stdout="", stderr="", pursuit_ref="pursuit_regr")


# --------------------------------------------------------------------- #
# Niveau build_turn — les 3 formes + la forme EXACTE qui a cassé la pursuit
# --------------------------------------------------------------------- #
def test_a_continue_with_matured_is_proposed_and_kept():
    f = _turn({"reply": "je continue", "readiness": "continue", "matured_need": _matured()})
    assert f["status"] == "proposed" and f["readiness"] == "continue"
    assert f["matured_need"] == _matured() and f["error"] is None      # conservé, jamais perdu


def test_b_ready_with_matured_unchanged():
    f = _turn({"reply": "prêt", "readiness": "ready", "matured_need": _matured()})
    assert f["status"] == "proposed" and f["readiness"] == "ready" and f["matured_need"] == _matured()


def test_c_continue_without_matured_unchanged():
    f = _turn({"reply": "on continue", "readiness": "continue"})
    assert f["status"] == "proposed" and f["readiness"] == "continue" and f["matured_need"] is None


def test_f_exact_broken_case_now_proposed_non_regression():
    # Reproduction EXACTE de la forme du tour 8 réel : continue + matured_need — jadis 'failed'/terminal,
    # désormais 'proposed' (matured conservé, aucune erreur).
    f = _turn({"reply": "concevons la V1 complète avant toute réalisation", "readiness": "continue",
               "matured_need": _matured("représentation mûre du besoin")})
    assert f["status"] == "proposed" and f["error"] is None
    assert f["matured_need"]["besoin_fondamental"] == "représentation mûre du besoin"


# --------------------------------------------------------------------- #
# Niveau MOTEUR — conception continue après ready, message en historique, réalisation gouvernée
# --------------------------------------------------------------------- #
class _ConvReadyThenContinue:
    """Fake piloté par l'historique : 1ᵉʳ tour (vide) → ready+matured ; suivants → continue+matured."""
    capability = "conversation"; name = "fake"; model = "fake"

    def propose(self, message, *, history, cwd, budget_remaining_usd):
        if not history:
            obj = {"reply": "voici ma compréhension mûre", "readiness": "ready", "matured_need": _matured()}
        else:
            obj = {"reply": "je continue la conception avec vous", "readiness": "continue",
                   "matured_need": _matured()}
        return {"called": True, "envelope": _env(obj), "exit_code": 0, "timed_out": False,
                "prompt": "p", "argv": ["x"], "stdout": "", "stderr": ""}


class _Arc:
    def __init__(self, cap):
        self.capability = cap; self.name = "fake"; self.model = "fake"

    def propose(self, payload, *, cwd, budget_remaining_usd):
        body = {
            "understanding": {"objective": "o", "context": "c", "actors": [], "scope": [],
                              "assumptions": [], "open_questions": [], "constraints": []},
            "specification": {k: ([] if k != "product_objective" else "o") for k in
                              ("product_objective", "users_and_roles", "functional_scope", "features",
                               "entities_and_data", "key_journeys", "constraints", "acceptance_criteria",
                               "assumptions", "open_questions", "out_of_scope")},
            "build": {"name": "n", "summary": "s", "users": [], "features": [], "entities": []},
        }[self.capability]
        return {"called": True, "envelope": _env(body), "exit_code": 0, "timed_out": False,
                "prompt": "p", "argv": ["x"], "stdout": "", "stderr": ""}


def _brain_ctx(tmp_path):
    caps = Capabilities(understanding=_Arc("understanding"), specification=_Arc("specification"),
                        build=_Arc("build"), conversation=_ConvReadyThenContinue())
    stores = Stores(proposals=ProposalStore(tmp_path / "p.jsonl"),
                    specifications=SpecificationStore(tmp_path / "s.jsonl"),
                    builds=BuildStore(tmp_path / "b.jsonl"), turns=TurnStore(tmp_path / "t.jsonl"),
                    confirmations=ConfirmationStore(tmp_path / "c.jsonl"))
    ctx = RunContext(budget_usd=5.0, project_id="p", workspace=Workspace(tmp_path / "exec", "p"), stores=stores)
    return BrainAI(caps), ctx, stores


def test_e_continue_after_ready_keeps_pursuit_alive_and_message_in_history(tmp_path):
    brain, ctx, stores = _brain_ctx(tmp_path)
    # 1) tour ready (proposition de maturité) — aucune réalisation lancée (steps vides).
    out1 = brain.pursue(converse_intent("mon besoin initial"), context=ctx)
    pid = out1.pursuit_id
    assert out1.state == "awaiting" and out1.wait_reason == "confirmation" and out1.steps == ()
    # 2) message « continue la conception, ne réalise pas » → continue+matured : la pursuit RESTE VIVANTE.
    out2 = brain.pursue(converse_intent("concevons la V1 avant toute réalisation", pursuit_ref=pid), context=ctx)
    assert out2.pursuit_id == pid
    assert out2.state == "active" and out2.refused is None            # PAS terminal, PAS d'arrêt (bug corrigé)
    # le tour est persisté 'proposed' (message conservé) et RELU dans l'historique côté moteur
    turns = [t for t in stores.turns.read_all() if t.get("pursuit_ref") == pid]
    assert len(turns) == 2 and all(t["status"] == "proposed" for t in turns)
    hist = brain._history(stores.turns, pid)
    assert any("concevons la V1" in h["content"] for h in hist)       # message visible dans l'historique relu
    # 3) réalisation refusée : dernier tour 'continue' → convergence évoluée, aucun arc, aucune construction.
    out3 = brain.pursue(realize_intent(pid, actor="frederique"), context=ctx)
    assert out3.state == "terminal" and out3.refused == E._REALIZE_REFUSED_EVOLVED
    assert stores.confirmations.read_all() == []                      # aucune confirmation, aucune réalisation


def test_d_no_realization_without_explicit_realize_intent(tmp_path):
    brain, ctx, stores = _brain_ctx(tmp_path)
    out1 = brain.pursue(converse_intent("besoin"), context=ctx)       # atteint ready
    assert out1.state == "awaiting" and out1.steps == ()              # converse ne construit RIEN
    assert stores.builds.read_all() == [] and stores.confirmations.read_all() == []
    # seule une intention humaine explicite 'realize' sur un dernier tour ready lance l'arc :
    out2 = brain.pursue(realize_intent(out1.pursuit_id, actor="frederique"), context=ctx)
    assert out2.state == "awaiting" and out2.wait_reason == "governance"   # arc exécuté (proposition complète)
    assert len(stores.confirmations.read_all()) == 1                  # confirmation D3 sur acte humain
