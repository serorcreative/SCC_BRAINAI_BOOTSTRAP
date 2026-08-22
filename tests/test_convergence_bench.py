"""Banc de non-régression déterministe (Étage 1) — COGNITIVE-IDENTITY-001 post-campagne (C8/C9/C5-minimal).

**Coût 0 $, fakes déterministes.** Prouve la couche STRUCTURELLE : schéma C9, normalisation legacy (D3),
gardes A4-2 et C8, séparation besoin/solutions et invariance du besoin fondamental (C9), continuité C5-minimal
après simulation de redémarrage, rétrocompatibilité des faits historiques sans réécriture, et absence de tout
terme/scénario métier interdit dans la correction.

Limite de preuve honnête : ce banc **ne prouve pas** la cognition (désaccord argumenté, calibration réelle du
seuil de maturité) — cela relève de l'Étage 2 (mini-campagne réelle). Les cas T6/T7/T4-like ici ne testent que
la **mécanique** qui permet de router et persister la réponse, jamais la qualité cognitive.
"""

from __future__ import annotations

import hashlib
import json

from scc_brainai_bootstrap.builder import conversation as C
from scc_brainai_bootstrap.builder.cognitive_identity import COGNITIVE_IDENTITY, CONDENSED_IDENTITY
from scc_brainai_bootstrap.builder.confirmations import ConfirmationStore, build_confirmation, declared_actor
from scc_brainai_bootstrap.builder.conversation import (
    build_turn,
    element_source,
    matured_need_present,
    matured_need_to_need_text,
    normalize_matured_need,
)
from scc_brainai_bootstrap.builder.turns import TurnStore


def _env(result_obj, *, ok=True, cost=0.02):
    return {"type": "result", "subtype": "success" if ok else "error_max_turns", "is_error": not ok,
            "api_error_status": None, "num_turns": 1,
            "result": result_obj if isinstance(result_obj, str) else json.dumps(result_obj, ensure_ascii=False),
            "total_cost_usd": cost, "usage": {"input_tokens": 10, "output_tokens": 20}}


def _turn(obj):
    return build_turn(message="m", prompt="p", capability="conversation", adapter="claude_code",
                      model="fake", envelope=_env(obj), exit_code=0, timed_out=False,
                      as_of="2026-08-19T00:00:00+00:00", argv=["claude"], stdout="o", stderr="",
                      pursuit_ref="pursuit_bench")


def _matured(besoin, sols=(), inconnues=(), hyps=()):
    return {"besoin_fondamental": besoin,
            "solutions_privilegiees": [{"statement": s} for s in sols],
            "inconnues_nommees": [{"statement": s} for s in inconnues],
            "hypotheses_actives": [{"statement": s} for s in hyps]}


# ===================================================================== #
# D3 — normalisation legacy (rétrocompat)
# ===================================================================== #
def test_bench_normalize_legacy_none_and_structured():
    assert normalize_matured_need(None) is None
    assert normalize_matured_need("   ") is None
    assert normalize_matured_need({"besoin_fondamental": "", "solutions_privilegiees": [],
                                   "inconnues_nommees": [], "hypotheses_actives": []}) is None
    # chaîne legacy → structure C9
    assert normalize_matured_need("un besoin brut") == _matured("un besoin brut")
    # structure conservée
    m = _matured("besoin", sols=["piste"], inconnues=["ouvert"], hyps=["supposé"])
    assert normalize_matured_need(m) == m


def test_bench_matured_present_helper_not_dict_truthiness():
    assert matured_need_present(_matured("besoin défini")) is True
    assert matured_need_present(_matured("")) is False           # dict non vide MAIS besoin vide → absent
    assert matured_need_present("legacy") is True
    assert matured_need_present(None) is False


# ===================================================================== #
# A4-2 + C8 — gardes de cohérence
# ===================================================================== #
def test_bench_a4_2_continue_with_matured_is_valid_and_kept():
    # A4-2 CORRIGÉE (défaut du test produit réel) : continue + matured_need COEXISTENT — tour valide/proposed,
    # matured_need CONSERVÉ, conversation continue. La réalisation reste gouvernée par ready + realize (A4-1/D3).
    f = _turn({"reply": "r", "readiness": "continue", "matured_need": _matured("besoin")})
    assert f["status"] == "proposed" and f["readiness"] == "continue"
    assert f["matured_need"] == _matured("besoin") and f["error"] is None   # jamais perdu, jamais nulled


def test_bench_c8_ready_requires_besoin_but_allows_named_unknowns():
    # ready sans besoin fondamental → failed
    empty = _turn({"reply": "r", "readiness": "ready", "matured_need": _matured("")})
    assert empty["status"] == "failed" and empty["error"] == "ready sans besoin fondamental"
    # ready AVEC besoin + inconnues non bloquantes → proposed, inconnues conservées (C8)
    ok = _turn({"reply": "r", "readiness": "ready",
                "matured_need": _matured("besoin défini", inconnues=["un point encore ouvert"])})
    assert ok["status"] == "proposed" and ok["readiness"] == "ready"
    assert ok["matured_need"]["inconnues_nommees"] == [{"statement": "un point encore ouvert"}]


# ===================================================================== #
# C9 — séparation besoin/solutions + invariance du besoin fondamental
# ===================================================================== #
def test_bench_c9_structural_separation_in_fact_and_text():
    m = _matured("Rendre un service accessible", sols=["une approche A"], hyps=["public large"],
                 inconnues=["modalité à choisir"])
    f = _turn({"reply": "restitution", "readiness": "ready", "matured_need": m})
    # champs distincts dans le fait
    assert f["matured_need"]["besoin_fondamental"] == "Rendre un service accessible"
    assert f["matured_need"]["solutions_privilegiees"] == [{"statement": "une approche A"}]
    # le texte dérivé conserve la fonction de chaque élément en toutes lettres (A2)
    txt = matured_need_to_need_text(m)
    assert "BESOIN FONDAMENTAL" in txt and "SOLUTIONS PRIVILÉGIÉES" in txt
    assert "HYPOTHÈSES ACTIVES" in txt and "INCONNUES NOMMÉES" in txt
    # le besoin n'est pas noyé sous une rubrique solution
    assert txt.index("BESOIN FONDAMENTAL") < txt.index("SOLUTIONS PRIVILÉGIÉES")
    assert "une approche A" not in txt.split("SOLUTIONS PRIVILÉGIÉES")[0]   # la solution n'apparaît pas avant sa rubrique


def test_bench_c9_solution_change_keeps_besoin_fondamental_invariant():
    besoin = "Permettre l'accès collectif à un service coûteux"
    f1 = _turn({"reply": "r1", "readiness": "ready", "matured_need": _matured(besoin, sols=["solution X"])})
    f2 = _turn({"reply": "r2", "readiness": "ready", "matured_need": _matured(besoin, sols=["solution Y révisée"])})
    assert f1["status"] == "proposed" and f2["status"] == "proposed"
    # la solution privilégiée change, le besoin fondamental NON (séparation structurelle, C9)
    assert f1["matured_need"]["besoin_fondamental"] == f2["matured_need"]["besoin_fondamental"] == besoin
    assert f1["matured_need"]["solutions_privilegiees"] != f2["matured_need"]["solutions_privilegiees"]


# ===================================================================== #
# T6/T7/T4-like — mécanique de routage/persistance (PAS la cognition)
# ===================================================================== #
def test_bench_t6_like_ambiguous_assent_stays_continue():
    f = _turn({"reply": "je note votre accord, mais je manque encore de matière", "readiness": "continue"})
    assert f["status"] == "proposed" and f["readiness"] == "continue" and f["matured_need"] is None


def test_bench_t7_like_defined_need_with_non_blocking_unknowns_matures():
    f = _turn({"reply": "voici ce que j'ai compris…", "readiness": "ready",
               "matured_need": _matured("besoin fondamental défini", inconnues=["détail non bloquant"])})
    assert f["status"] == "proposed" and f["readiness"] == "ready"
    assert f["matured_need"]["inconnues_nommees"]              # inconnues conservées


def test_bench_t4_like_only_mechanics_not_cognitive_disagreement():
    # PREUVE STRUCTURELLE UNIQUEMENT : on vérifie que la mécanique persiste une réponse de désaccord en
    # ``continue`` — le CARACTÈRE argumenté du désaccord n'est PAS prouvé ici (Étage 2 réel).
    f = _turn({"reply": "je ne suis pas d'accord avec cette hypothèse, voici pourquoi …", "readiness": "continue"})
    assert f["status"] == "proposed" and f["readiness"] == "continue"


# ===================================================================== #
# Anti-surapprentissage — aucun terme/scénario métier de la campagne
# ===================================================================== #
def test_bench_no_forbidden_domain_terms_in_injected_text():
    forbidden = ("immobil", "crowdfunding", "scpi", "psfp", "homunity", "fundimmo", "anaxago",
                 "financement participatif", "plus-value", "promoteur")
    corpus = (COGNITIVE_IDENTITY + "\n" + CONDENSED_IDENTITY + "\n" + C._CONVERSATION_MISSION).lower()
    leaked = [t for t in forbidden if t in corpus]
    assert leaked == [], f"terme de domaine interdit dans le texte injecté : {leaked}"


# ===================================================================== #
# Rétrocompatibilité — fait legacy relisible, aucune réécriture append-only
# ===================================================================== #
def test_bench_legacy_turn_fact_readable_and_never_rewritten(tmp_path):
    # Simule un fait historique d'avant C9 : matured_need = CHAÎNE (comme le T8 de la campagne).
    path = tmp_path / "turns.jsonl"
    legacy_fact = {"fact_type": "turn", "turn_id": "turn_legacy", "pursuit_ref": "pursuit_legacy",
                   "status": "proposed", "readiness": "ready", "reply": "ok",
                   "matured_need": "un besoin mûri legacy sous forme de chaîne", "cost": {"value": 0.1, "kind": "real"}}
    path.write_text(json.dumps(legacy_fact, ensure_ascii=False) + "\n", encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    store = TurnStore(path)
    facts = [t for t in store.read_all() if t.get("pursuit_ref") == "pursuit_legacy"]
    assert len(facts) == 1
    m = normalize_matured_need(facts[0]["matured_need"])                    # lecture normalisée à la volée
    assert m == _matured("un besoin mûri legacy sous forme de chaîne")
    assert matured_need_present(facts[0]["matured_need"]) is True
    assert "un besoin mûri legacy" in matured_need_to_need_text(facts[0]["matured_need"])

    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before                                                 # AUCUNE réécriture (append-only immuable)


# ===================================================================== #
# C5-minimal — continuité d'une Pursuit après simulation de redémarrage
# ===================================================================== #
def test_bench_c5_minimal_continuity_after_process_restart():
    from brainai_app import composition as X

    vm = X.converse("un besoin quelconque, domaine neutre", mode="demo")   # 1er tour : frappe l'identité
    pid = vm["pursuit"]["pursuit_id"]
    det = X._pursuit_dir(pid)
    assert det.exists() and (det / "turns.jsonl").exists()                 # vit au chemin déterministe (A1)
    assert str(det).startswith(str(X._state_root()))                       # sous la racine d'état stable

    with X._SESSIONS_LOCK:                                                  # simule un redémarrage : cache mémoire vidé
        X._SESSIONS.clear()
    resolved = X._session_dir(pid)                                         # recalculé sans remapping manuel
    assert resolved == det and (resolved / "turns.jsonl").exists()

    # tour suivant après « redémarrage » : même Pursuit retrouvée, historique relu
    vm2 = X.converse("un complément", pursuit_ref=pid, mode="demo")
    assert vm2["pursuit"]["pursuit_id"] == pid


def test_bench_c5_legacy_index_only_for_legacy_dirs(tmp_path):
    from brainai_app import composition as X

    legacy_dir = tmp_path / "ancien_repertoire_hors_racine"
    legacy_dir.mkdir()
    X._legacy_register("pursuit_legacy_ext", legacy_dir)
    with X._SESSIONS_LOCK:
        X._SESSIONS.clear()
    assert X._session_dir("pursuit_legacy_ext") == legacy_dir              # retrouvé via l'index de compat


# ===================================================================== #
# EPISTEMIC-PROVENANCE (J1) — provenance émise, « vérifié » inémettable, legacy = inconnu
# ===================================================================== #
def _mel(besoin, sols=(), inconnues=(), hyps=()):
    # matured avec des ÉLÉMENTS dicts (pas des chaînes) — pour porter une provenance ``source``.
    return {"besoin_fondamental": besoin, "solutions_privilegiees": list(sols),
            "inconnues_nommees": list(inconnues), "hypotheses_actives": list(hyps)}


def test_bench_element_source_emitted_persisted_and_read():
    m = _mel("besoin défini",
             sols=[{"statement": "piste A", "source": "deduit"}],
             hyps=[{"statement": "public non expert", "source": "suppose"}])
    f = _turn({"reply": "r", "readiness": "ready", "matured_need": m})
    assert f["status"] == "proposed"
    # provenance émise CONSERVÉE (persistée) et RELUE
    assert f["matured_need"]["solutions_privilegiees"][0]["source"] == "deduit"
    assert element_source(f["matured_need"]["solutions_privilegiees"][0]) == "deduit"
    assert element_source(f["matured_need"]["hypotheses_actives"][0]) == "suppose"


def test_bench_verifie_is_structurally_unemittable_by_model():
    # « vérifié » exclu de l'enum émettable ET dropé par normalize (aucune garde ne peut le promouvoir).
    props = C.CONVERSATION_SCHEMA["properties"]["matured_need"]["properties"]
    enum = props["solutions_privilegiees"]["items"]["properties"]["source"]["enum"]
    assert "verifie" not in enum and "vérifié" not in enum
    m = _mel("b", sols=[{"statement": "x", "source": "verifie"}])   # tentative de « vérifié »
    el = normalize_matured_need(m)["solutions_privilegiees"][0]
    assert "source" not in el                       # dropé
    assert element_source(el) == "inconnu"          # lu comme inconnu, jamais « vérifié »


def _matured_with(besoin, sols=()):
    return {"besoin_fondamental": besoin,
            "solutions_privilegiees": list(sols),
            "inconnues_nommees": [], "hypotheses_actives": []}


def test_bench_legacy_and_absent_source_default_inconnu_no_fabrication():
    # Fait historique : élément SANS source → inconnu ; jamais fabriqué.
    m = _matured_with("besoin legacy", sols=[{"statement": "piste sans source"}])
    el = normalize_matured_need(m)["solutions_privilegiees"][0]
    assert "source" not in el and element_source(el) == "inconnu"
    # chaîne legacy → structure sans source → besoin lu, provenance inconnue par défaut
    assert element_source({}) == "inconnu" and element_source("pas un dict") == "inconnu"


def test_bench_source_labels_rendered_never_verifie():
    m = _mel("b", sols=[{"statement": "s", "source": "fourni_par_utilisateur"}])
    txt = matured_need_to_need_text(m)
    assert "fourni par l'utilisateur" in txt and "vérifié" not in txt


# ===================================================================== #
# D3 — confirmation humaine : fait séparé append-only, acteur déclaré/non vérifié, ne déclenche rien
# ===================================================================== #
def test_bench_declared_actor_never_verified():
    assert declared_actor("alice") == {"id": "alice", "attribution": "declared", "verified": False}
    assert declared_actor(None)["id"] == "humain"
    # même si l'entrée prétend « verified », on ne fabrique JAMAIS de garantie d'identité (RS-029)
    forced = declared_actor({"id": "bob", "verified": True, "attribution": "authenticated"})
    assert forced == {"id": "bob", "attribution": "declared", "verified": False}


def test_bench_convergence_confirmed_is_append_only_and_inert(tmp_path):
    store = ConfirmationStore(tmp_path / "confirmations.jsonl")
    f1 = store.record(build_confirmation(pursuit_ref="pursuit_x", turn_ref="turn_ready_1",
                                         as_of="2026-08-20T00:00:00+00:00", actor="frederique"))
    assert f1["fact_type"] == "convergence_confirmed" and f1["turn_ref"] == "turn_ready_1"
    assert f1["actor"] == {"id": "frederique", "attribution": "declared", "verified": False}
    assert f1["confirmation_id"].startswith("conf_")
    # append-only : un second enregistrement n'efface pas le premier
    store.record(build_confirmation(pursuit_ref="pursuit_x", turn_ref="turn_ready_2",
                                    as_of="2026-08-20T00:01:00+00:00", actor="rose"))
    refs = [c["turn_ref"] for c in store.read_all()]
    assert refs == ["turn_ready_1", "turn_ready_2"]
    # inerte : enregistrer une confirmation ne crée AUCUN autre artefact (record != decision)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["confirmations.jsonl"]


def test_bench_realize_records_confirmation_without_mutating_history(tmp_path):
    # ready → realize : le tour ready n'est PAS muté ; un fait de confirmation séparé apparaît.
    from scc_brainai_bootstrap.builder.brainai import (
        BrainAI, Capabilities, RunContext, Stores, converse_intent, realize_intent)
    from scc_brainai_bootstrap.builder.proposals import ProposalStore
    from scc_brainai_bootstrap.builder.specifications import SpecificationStore
    from scc_brainai_bootstrap.builder.builds import BuildStore
    from scc_brainai_bootstrap.builder.workspace import Workspace
    import json as _json

    def _env2(obj):
        return {"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                "num_turns": 1, "result": _json.dumps(obj, ensure_ascii=False), "total_cost_usd": 0.0,
                "usage": {"input_tokens": 1, "output_tokens": 1}}

    class _Conv:
        capability = "conversation"; name = "fake"; model = "fake"
        def propose(self, message, *, history, cwd, budget_remaining_usd):
            obj = {"reply": "ok", "readiness": "ready",
                   "matured_need": _mel("un besoin défini", sols=[{"statement": "piste", "source": "deduit"}])}
            return {"called": True, "envelope": _env2(obj), "exit_code": 0, "timed_out": False,
                    "prompt": "p", "argv": ["x"], "stdout": "", "stderr": ""}

    class _Arc:
        def __init__(self, cap): self.capability = cap; self.name = "fake"; self.model = "fake"
        def propose(self, payload, *, cwd, budget_remaining_usd):
            body = {"understanding": {"objective":"o","context":"c","actors":[],"scope":[],"assumptions":[],
                                      "open_questions":[],"constraints":[]},
                    "specification": {k: ([] if k!="product_objective" else "o") for k in
                        ("product_objective","users_and_roles","functional_scope","features","entities_and_data",
                         "key_journeys","constraints","acceptance_criteria","assumptions","open_questions","out_of_scope")},
                    "build": {"name":"n","summary":"s","users":[],"features":[],"entities":[]}}[self.capability]
            return {"called": True, "envelope": _env2(body), "exit_code": 0, "timed_out": False,
                    "prompt": "p", "argv": ["x"], "stdout": "", "stderr": ""}

    caps = Capabilities(understanding=_Arc("understanding"), specification=_Arc("specification"),
                        build=_Arc("build"), conversation=_Conv())
    stores = Stores(proposals=ProposalStore(tmp_path/"p.jsonl"), specifications=SpecificationStore(tmp_path/"s.jsonl"),
                    builds=BuildStore(tmp_path/"b.jsonl"), turns=TurnStore(tmp_path/"t.jsonl"),
                    confirmations=ConfirmationStore(tmp_path/"c.jsonl"))
    ctx = RunContext(budget_usd=5.0, project_id="p", workspace=Workspace(tmp_path/"exec","p"), stores=stores)
    brain = BrainAI(caps)
    pid = brain.pursue(converse_intent("besoin"), context=ctx).pursuit_id
    ready_fact = stores.turns.read_all()[-1]
    before = hashlib.sha256((tmp_path/"t.jsonl").read_bytes()).hexdigest()
    brain.pursue(realize_intent(pid, actor="frederique"), context=ctx)          # confirmation humaine
    after = hashlib.sha256((tmp_path/"t.jsonl").read_bytes()).hexdigest()
    assert after == before                                                       # tours NON mutés (I5)
    confs = stores.confirmations.read_all()
    assert len(confs) == 1 and confs[0]["turn_ref"] == ready_fact["turn_id"]      # référence le tour ready
    assert confs[0]["actor"]["verified"] is False                                # déclaré / non vérifié


# ===================================================================== #
# Capability Registry — resolve utilisé, aucun câblage fournisseur, substituabilité
# ===================================================================== #
def test_bench_no_provider_wiring_in_composition_or_business_logic():
    import inspect
    from brainai_app import composition
    from scc_brainai_bootstrap.builder import brainai as engine
    for mod in (composition, engine):
        src = inspect.getsource(mod)
        assert "ClaudeCode" not in src, f"import/nom de fournisseur concret dans {mod.__name__}"
        assert "claude_code" not in src, f"slug fournisseur dans {mod.__name__}"


def test_bench_resolve_capability_used_on_product_path():
    from brainai_app import providers
    caps = providers.real_capabilities()          # chemin produit réel = résolution de capacités
    assert caps.understanding.capability == "understanding"
    assert caps.conversation.capability == "conversation" and caps.conversation.model == "sonnet"


def test_bench_provider_substitutable_by_descriptor_change():
    from brainai_app import providers
    from scc_brainai_bootstrap.registry.descriptor import AgentDescriptor, AgentState

    class _FakeBuild:
        capability = "build"; name = "test_double"; model = "test_double"
        def propose(self, spec, *, cwd, budget_remaining_usd):
            return {"called": True, "envelope": None, "exit_code": 0, "timed_out": False,
                    "prompt": "", "argv": [], "stdout": "", "stderr": ""}

    # Descriptor BUILD_SOFTWARE re-pointé vers un fournisseur « test_double » + binder dédié — SANS toucher
    # composition.py ni builder/*.
    descriptors = [AgentDescriptor(id="brainai.test_double.build_software", namespace="brainai",
                                   capabilities=[providers.BUILD_SOFTWARE], state=AgentState.ACTIVE,
                                   provider="test_double", availability="available")]
    binders = {("test_double", providers.BUILD_SOFTWARE): lambda: _FakeBuild()}
    impl = providers.resolve_capability(providers.BUILD_SOFTWARE, descriptors, binders)
    assert isinstance(impl, _FakeBuild)           # implémentation substituée par le seul changement de descriptor


def test_bench_cost_field_is_present_as_j2_anchor_not_executed():
    from brainai_app import providers
    for d in providers.default_descriptors():
        assert hasattr(d, "cost")                 # ancrage budget J2 présent
        assert d.cost is None                     # AUCUN budget exécuté en J1
