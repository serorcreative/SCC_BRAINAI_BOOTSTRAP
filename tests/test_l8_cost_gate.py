"""L8 — Solution Architecture + Cost Gate — déterministe, 0 $, fakes only, aucun provider réel, aucun réseau.

Prouve, sans aucune clé ni appel réel :
- **modèle de coût** (``cost_estimate``) : montant par SOURCE fail-closed ; ``unknown`` ≠ 0 ; ``n_a`` ≠ ``unknown`` ;
  devise jamais fabriquée ; ``internal_deterministic`` exclu de la complétude provider ; complétude calculée ;
- **comparaison BrainAI** (``compare_architectures``) : construction one-time et récurrent JAMAIS additionnés ;
  dominance de Pareto seulement si réellement comparable ; sinon tradeoff/non-comparable → repli structurel ;
  inconnu ≠ avantage ; option unique auditable ;
- **fingerprint** (``gate_fingerprint``) : sources uniques = ``comparison_options`` + ``comparison_estimates`` ;
  couvre TOUTES les options comparées ⇒ modification matérielle d'une alternative **même non sélectionnée**
  (architecture OU coût OU hypothèse matérielle) ⇒ nouveau fingerprint ; wording/ordre/commentaire hors empreinte ;
  fail-closed (ids incohérents, vide, option sélectionnée absente, hypothèses contradictoires) ;
- **resolve_cost_gate** : reconstruit depuis les faits PERSISTÉS, ancré sur le spec_sha256 COURANT ;
  ``absent`` ; fingerprint stable + reproductible (``fp_arc == fp_deliver``) ; dépendances réelles ;
- **authorization_status** : ``none``/``approved``/``declined`` ; fingerprint obsolète ⇒ ``none`` ; ``declined``
  postérieur annule un ``approved`` ;
- **composition.authorize** : USER GO inerte (aucune construction) ; ``presented_spec_ref`` +
  ``presented_gate_fingerprint`` obligatoires ; lookup EXACT ; fingerprint ≠ recomputé ⇒ refus SANS écriture ;
  dépendances réelles de l'option retenue (jamais ``[]`` fabriqué) ;
- **composition._deliver** (frontière réelle) : NO VALID CURRENT USER GO = NO SIGNIFICANT CONSTRUCTION —
  la frontière ``providers.real_delivery()`` n'est atteinte qu'après un GO exact (A..F) ;
- **wiring serveur** : ``kind == "authorize"`` sous ``/v1/pursue`` (même endpoint) ; validation de forme TYPE-stricte
  (400) ; refus métier gouverné renvoyé en 200 ; ``authorize`` ne déclenche aucune livraison.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from brainai_app import composition, providers
from brainai_app import server
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.build_authorization import (
    BuildAuthorizationStore, authorization_status, build_authorization_fact,
    canonical_material_assumptions, gate_fingerprint, resolve_cost_gate)
from scc_brainai_bootstrap.builder.cost_estimate import (
    COMPLETE, HAS_UNKNOWNS, INTERNAL_DETERMINISTIC, KNOWN, N_A, PROVIDER_CALL, UNKNOWN,
    CostEstimateStore, amount, build_cost_estimate, completeness, estimate_costs, has_unknown,
    is_provider_incomplete, line_item, provider_real_value)
from scc_brainai_bootstrap.builder.solution_architecture import (
    SolutionArchitectureStore, compare_architectures)
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.core.clock import digest


# --------------------------------------------------------------------- #
# Fixtures / helpers — spec 11 champs, options valides, faits persistés (tout en temp, 0 $)
# --------------------------------------------------------------------- #
SPEC = {
    "product_objective": "Gestion d'un refuge animalier.",
    "users_and_roles": ["Personnel", "Adoptant"],
    "functional_scope": ["Animaux", "Adoptants", "RDV"],
    "features": ["Fiche animal", "Planning RDV"],
    "entities_and_data": ["Animal", "Adoptant", "RendezVous"],
    "key_journeys": ["Enregistrer un animal"],
    "constraints": ["Budget limité"],
    "acceptance_criteria": ["Un animal peut être créé et retrouvé"],
    "assumptions": ["Un seul refuge en V1"],
    "open_questions": ["Notifications ?"],
    "out_of_scope": ["Paiement en ligne"],
}
_AS_OF = "2026-01-01T00:00:00+00:00"


def _option(oid, *, components=None, external_services=None, dependencies=None, risks=None,
            summary="s", scalability="moyenne", maintainability="bonne"):
    return {"id": oid, "summary": summary,
            "components": list(components or ["web"]),
            "external_services": list(external_services or []),
            "dependencies": list(dependencies or ["python"]),
            "risks": list(risks or ["r"]),
            "scalability": scalability, "maintainability": maintainability}


_OPTIONS = [
    _option("opt_a", components=["web", "db"], external_services=[], dependencies=["python"], risks=["scaling"]),
    _option("opt_b", components=["web", "db", "worker"], external_services=["queue"],
            dependencies=["python", "redis"], risks=["ops", "cost"]),
]


def _known_estimate(option_id, *, construction, recurring, currency="USD"):
    """Estimation MATÉRIELLEMENT connue (COMPLETE) : construction one-time connue + récurrent 'expected' connu.
    Le récurrent au niveau ligne est ``n_a`` (porté au niveau scénario) — n_a ≠ inconnu, jamais 0."""
    li = line_item(category="c", construction=amount(kind=KNOWN, value=construction, currency=currency),
                   recurring=amount(kind=N_A))
    scen = {"expected": {"recurring_total": amount(kind=KNOWN, value=recurring, currency=currency, period="month"),
                         "assumptions": []}}
    est = build_cost_estimate(pursuit_ref="p", architecture_ref="a", option_ref=option_id, as_of=_AS_OF,
                              line_items=[li], scenarios=scen, currency=currency)
    assert est["cost_completeness"] == COMPLETE            # garde-fou du helper (comparabilité réelle)
    return est


@pytest.fixture()
def l8_env(tmp_path, monkeypatch):
    """Racine d'état TEMPORAIRE + cache session neuf. Renvoie un seeder qui matérialise les faits persistés d'une
    Pursuit à son chemin déterministe (spec/build/architecture/estimations) et retourne
    ``(root, spec_id, build_id, spec_fact, gate_fp)``. Aucune écriture hors ``tmp_path``."""
    monkeypatch.setenv("BRAINAI_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setattr(composition, "_SESSIONS", {})     # cache mémoire neuf (isolation inter-tests)

    def seed(pursuit_id, *, build_spec_ref=None):
        root = composition._pursuit_dir(pursuit_id)
        root.mkdir(parents=True, exist_ok=True)
        spec_sha = digest(SPEC)
        spec_fact = SpecificationStore(root / "spec.jsonl").record({
            "fact_type": "specification", "status": "proposed", "specification": SPEC,
            "brief_ref": "brief_x", "brief_sha256": "x", "model": "demo", "adapter": "demo", "as_of": _AS_OF})
        spec_id = spec_fact["specification_id"]
        build_fact = BuildStore(root / "build.jsonl").record({
            "fact_type": "build", "status": "proposed", "artefact": {"file": "manifest.json"},
            "spec_ref": build_spec_ref if build_spec_ref is not None else spec_id, "spec_sha256": spec_sha,
            "model": "demo", "adapter": "demo", "as_of": _AS_OF})
        build_id = build_fact["build_id"]
        arch_store = SolutionArchitectureStore(root / "architectures.jsonl")
        arch_fact = arch_store.record({
            "fact_type": "solution_architecture", "status": "proposed", "pursuit_ref": pursuit_id,
            "cost_source": PROVIDER_CALL, "spec_ref": spec_id, "spec_sha256": spec_sha,
            "options": _OPTIONS, "as_of": _AS_OF})
        arch_id = arch_fact["architecture_id"]
        est_store = CostEstimateStore(root / "cost_estimates.jsonl")
        for opt in _OPTIONS:
            est_store.record(estimate_costs(opt, pursuit_ref=pursuit_id, architecture_ref=arch_id, as_of=_AS_OF))
        gate = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                                 pursuit_ref=pursuit_id, current_spec=spec_fact)
        assert gate["status"] == "resolved", gate
        return root, spec_id, build_id, spec_fact, gate["gate"]["gate_fingerprint"]

    return seed


class _Boundary(Exception):
    """Levée par le sentinel remplaçant ``providers.real_delivery`` — prouve l'atteinte de la frontière sans
    exécuter aucun build réel (0 $)."""


class _Sentinel:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        raise _Boundary("frontière providers.real_delivery() atteinte")


@pytest.fixture()
def boundary(monkeypatch):
    """Remplace la frontière de livraison par un sentinel : aucun provider réel, aucun réseau, 0 $."""
    s = _Sentinel()
    monkeypatch.setattr(providers, "real_delivery", s)
    return s


class FakeOutcome:
    """Fake Outcome — surface exacte lue par ``_deliver`` (steps/pursuit_id/proposal/as_of/need)."""
    state = "awaiting"
    wait_reason = "governance"
    refused = None
    need = None

    def __init__(self, pursuit_id, spec_id, build_id, gate_fp):
        self.pursuit_id = pursuit_id
        self.as_of = _AS_OF
        self.steps = [{"faculty": "specification", "status": "proposed", "fact_id": spec_id},
                      {"faculty": "build", "status": "proposed", "fact_id": build_id}]
        self.proposal = None if gate_fp is None else {"cost_gate": {"gate_fingerprint": gate_fp}}


# ===================================================================== #
# 1. MODÈLE DE COÛT — montants qualifiés, sources, complétude (fonctions pures)
# ===================================================================== #
def test_amount_fail_closed_unknown_and_na_never_carry_value():
    assert amount(kind=UNKNOWN)["value"] is None
    assert amount(kind=N_A)["value"] is None
    with pytest.raises(ValueError):
        amount(kind=UNKNOWN, value=0)                     # un inconnu n'est JAMAIS 0
    with pytest.raises(ValueError):
        amount(kind=N_A, value=0)                         # non applicable ≠ 0
    with pytest.raises(ValueError):
        amount(kind=KNOWN)                                # known exige une valeur numérique
    with pytest.raises(ValueError):
        amount(kind=KNOWN, value=-1)                      # jamais négatif
    with pytest.raises(ValueError):
        amount(kind="invente")                            # kind hors contrat


def test_amount_currency_never_fabricated():
    assert amount(kind=UNKNOWN)["currency"] is None       # devise non déterminée, jamais fabriquée en USD
    assert amount(kind=KNOWN, value=10)["currency"] is None
    assert amount(kind=KNOWN, value=10, currency="USD")["currency"] == "USD"


def test_cost_source_semantics_fail_closed_and_internal_excluded():
    prov_real = {"kind": "real", "value": 0.02}
    assert is_provider_incomplete(prov_real, source=PROVIDER_CALL) is False
    assert provider_real_value(prov_real, source=PROVIDER_CALL) == 0.02
    # internal_deterministic (calcul BrainAI) : jamais un coût fournisseur, exclu de la complétude provider
    assert is_provider_incomplete({"kind": "n_a"}, source=INTERNAL_DETERMINISTIC) is False
    assert provider_real_value({"kind": "real", "value": 9}, source=INTERNAL_DETERMINISTIC) is None
    # provider sans USD réel → incomplet (unavailable)
    assert is_provider_incomplete({"kind": "unavailable"}, source=PROVIDER_CALL) is True
    with pytest.raises(ValueError):
        is_provider_incomplete(prov_real, source="source_inconnue")   # fail-closed sur source inconnue
    with pytest.raises(ValueError):
        provider_real_value(prov_real, source="source_inconnue")


def test_completeness_complete_when_all_amounts_known():
    # Cas COMPLETE : estimation construite EXPLICITEMENT sans aucun montant unknown (construction connue +
    # récurrent n_a au niveau ligne, récurrent 'expected' connu au niveau scénario). n_a ≠ inconnu, jamais 0.
    li = line_item(category="c", construction=amount(kind=KNOWN, value=100, currency="USD"),
                   recurring=amount(kind=N_A))
    scen = {"expected": {"recurring_total": amount(kind=KNOWN, value=10, currency="USD", period="month"),
                         "assumptions": []}}
    est_complete = build_cost_estimate(pursuit_ref="p", architecture_ref="a", option_ref="opt_a", as_of=_AS_OF,
                                       line_items=[li], scenarios=scen, currency="USD")
    assert has_unknown(est_complete) is False
    assert completeness(est_complete) == COMPLETE


def test_completeness_flags_unknown_estimate():
    # Cas UNKNOWN : estimate_costs sur une option sans prix connus ⇒ montants unknown ⇒ HAS_UNKNOWNS
    # (jamais 0, jamais fabriqué). Source = internal_deterministic (BrainAI calcule, aucun coût fournisseur).
    est_unknown = estimate_costs(_OPTIONS[0], pursuit_ref="p", architecture_ref="a", as_of=_AS_OF)
    assert est_unknown["cost_source"] == INTERNAL_DETERMINISTIC
    assert has_unknown(est_unknown) is True
    assert completeness(est_unknown) == HAS_UNKNOWNS


# ===================================================================== #
# 2. COMPARAISON BRAINAI — Pareto / tradeoff / non-comparable / dimensions séparées
# ===================================================================== #
def test_compare_single_option_auditable():
    res = compare_architectures([_OPTIONS[0]], {})
    assert res["selected_id"] == "opt_a"
    assert res["cost_decisive"] is False
    assert res["decisive_criteria"] == ["single_option"]


def test_compare_pareto_domination_picks_cheaper_on_both_dims():
    ests = {"opt_a": _known_estimate("opt_a", construction=100, recurring=10),
            "opt_b": _known_estimate("opt_b", construction=200, recurring=20)}
    res = compare_architectures(_OPTIONS, ests)
    assert res["selected_id"] == "opt_a"                  # ≤ construction ET ≤ récurrent, strictement meilleure
    assert res["cost_decisive"] is True
    assert not res["cost_unknowns"]
    # DEUX dimensions SÉPARÉES exposées, jamais additionnées : aucune clé de total global
    card_a = next(c for c in res["comparison"] if c["id"] == "opt_a")
    assert card_a["construction_total"] == 100 and card_a["expected_recurring_total"] == 10
    assert "total" not in card_a and "tco" not in card_a


def test_compare_tradeoff_no_domination_falls_back_structural():
    ests = {"opt_a": _known_estimate("opt_a", construction=100, recurring=20),   # moins cher en construction
            "opt_b": _known_estimate("opt_b", construction=200, recurring=10)}   # moins cher en récurrent
    res = compare_architectures(_OPTIONS, ests)
    assert res["cost_decisive"] is False                  # tradeoff sans horizon → coût NON décisif
    assert "tradeoff" in res["selection_rationale"]
    assert res["decisive_criteria"] == ["external_services", "risks", "dependencies"]


def test_compare_unknown_is_never_an_advantage():
    ests = {"opt_a": _known_estimate("opt_a", construction=100, recurring=10),
            "opt_b": estimate_costs(_OPTIONS[1], pursuit_ref="p", architecture_ref="a", as_of=_AS_OF)}  # inconnu
    res = compare_architectures(_OPTIONS, ests)
    assert "opt_b" in res["cost_unknowns"]                # inconnu → non comparable (jamais 0 ni avantage)
    assert res["cost_decisive"] is False


def test_compare_fail_closed_requires_valid_option():
    with pytest.raises(ValueError):
        compare_architectures([], {})


# ===================================================================== #
# 3. FINGERPRINT — sources uniques, couverture de TOUTES les options, invariances, fail-closed
# ===================================================================== #
def _fp(options, selected, *, cost_unknowns=None):
    ests = {o["id"]: estimate_costs(o, pursuit_ref="p", architecture_ref="a", as_of=_AS_OF) for o in options}
    return gate_fingerprint(spec_sha256="sha", selected_option_id=selected, comparison_options=options,
                            comparison_estimates=ests, cost_unknowns=cost_unknowns or [],
                            paid_providers=[], paid_external_services=[])


def test_fingerprint_stable_and_permutation_invariant():
    fp1 = _fp(_OPTIONS, "opt_a")
    fp2 = _fp(list(reversed(_OPTIONS)), "opt_a")          # ordre des options inversé
    assert fp1 == fp2 and fp1.startswith("fp_")


def test_fingerprint_changes_on_material_change_of_NON_selected_option():
    fp_ref = _fp(_OPTIONS, "opt_a")                       # sélectionnée = opt_a
    opt_b2 = _option("opt_b", components=["web", "db", "worker", "cache"],   # matière STRUCTURELLE modifiée
                     external_services=["queue"], dependencies=["python", "redis"], risks=["ops", "cost"])
    fp_mut = _fp([_OPTIONS[0], opt_b2], "opt_a")
    assert fp_ref != fp_mut                               # alternative NON retenue modifiée ⇒ nouveau fingerprint


def test_fingerprint_changes_on_material_assumption_but_not_on_wording():
    ests = {o["id"]: estimate_costs(o, pursuit_ref="p", architecture_ref="a", as_of=_AS_OF) for o in _OPTIONS}
    base = gate_fingerprint(spec_sha256="sha", selected_option_id="opt_a", comparison_options=_OPTIONS,
                            comparison_estimates=ests, cost_unknowns=[], paid_providers=[],
                            paid_external_services=[])
    # wording pur (assumptions descriptives) → MÊME fingerprint
    ests_word = {k: {**v, "assumptions": v["assumptions"] + ["commentaire libre"]} for k, v in ests.items()}
    fp_word = gate_fingerprint(spec_sha256="sha", selected_option_id="opt_a", comparison_options=_OPTIONS,
                               comparison_estimates=ests_word, cost_unknowns=[], paid_providers=[],
                               paid_external_services=[])
    assert fp_word == base
    # hypothèse MATÉRIELLE (volumétrie) → fingerprint DIFFÉRENT
    ests_mat = {k: {**v, "material_assumptions": [{"key": "active_users", "value": 1000}]} for k, v in ests.items()}
    fp_mat = gate_fingerprint(spec_sha256="sha", selected_option_id="opt_a", comparison_options=_OPTIONS,
                              comparison_estimates=ests_mat, cost_unknowns=[], paid_providers=[],
                              paid_external_services=[])
    assert fp_mat != base


def test_fingerprint_fail_closed_ids_and_selected():
    ests = {o["id"]: estimate_costs(o, pursuit_ref="p", architecture_ref="a", as_of=_AS_OF) for o in _OPTIONS}
    with pytest.raises(ValueError):                       # option sélectionnée absente des options comparées
        gate_fingerprint(spec_sha256="sha", selected_option_id="opt_absente", comparison_options=_OPTIONS,
                         comparison_estimates=ests, cost_unknowns=[])
    with pytest.raises(ValueError):                       # comparison_options vide
        gate_fingerprint(spec_sha256="sha", selected_option_id="opt_a", comparison_options=[],
                         comparison_estimates=ests, cost_unknowns=[])
    with pytest.raises(ValueError):                       # ids options ≠ ids estimations
        gate_fingerprint(spec_sha256="sha", selected_option_id="opt_a", comparison_options=_OPTIONS,
                         comparison_estimates={"opt_a": ests["opt_a"]}, cost_unknowns=[])


def test_canonical_material_assumptions_fail_closed():
    assert canonical_material_assumptions([{"key": "u", "value": 10, "unit": "n"}]) == \
        [{"key": "u", "value": 10, "unit": "n"}]
    # dédup de clés strictement identiques
    assert canonical_material_assumptions([{"key": "u", "value": 10}, {"key": "u", "value": 10}]) == \
        [{"key": "u", "value": 10, "unit": None}]
    with pytest.raises(ValueError):                       # value None interdite (un inconnu se dit inconnu ailleurs)
        canonical_material_assumptions([{"key": "u", "value": None}])
    with pytest.raises(ValueError):                       # élément non-dict
        canonical_material_assumptions(["pas_un_dict"])
    with pytest.raises(ValueError):                       # même clé, valeurs contradictoires
        canonical_material_assumptions([{"key": "u", "value": 10}, {"key": "u", "value": 99}])


# ===================================================================== #
# 4. RESOLVE_COST_GATE — reconstruction depuis faits persistés, ancrage spec courante, reproductibilité
# ===================================================================== #
def test_resolve_cost_gate_reproducible_and_dependencies_real(l8_env):
    root, spec_id, build_id, spec_fact, fp = l8_env("p_resolve")
    arch_store = SolutionArchitectureStore(root / "architectures.jsonl")
    est_store = CostEstimateStore(root / "cost_estimates.jsonl")
    g1 = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                           pursuit_ref="p_resolve", current_spec=spec_fact)
    g2 = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                           pursuit_ref="p_resolve", current_spec=spec_fact)
    assert g1["status"] == "resolved" and g1["gate"]["gate_fingerprint"] == g2["gate"]["gate_fingerprint"] == fp
    assert g1["gate"]["dependencies"], "dépendances réelles de l'option retenue (jamais [] fabriqué)"
    assert g1["gate"]["dependencies"] == ["python"]       # opt_a (repli structurel) → deps réelles


def test_resolve_cost_gate_absent_when_no_persisted_architecture(l8_env, tmp_path):
    _root, _sid, _bid, spec_fact, _fp = l8_env("p_absent")
    empty_arch = SolutionArchitectureStore(tmp_path / "empty_arch.jsonl")
    empty_est = CostEstimateStore(tmp_path / "empty_est.jsonl")
    res = resolve_cost_gate(architecture_store=empty_arch, cost_estimate_store=empty_est,
                            pursuit_ref="p_absent", current_spec=spec_fact)
    assert res["status"] == "absent" and res["gate"] is None


def test_resolve_cost_gate_anchored_on_current_spec_sha(l8_env):
    root, _sid, _bid, spec_fact, _fp = l8_env("p_anchor")
    arch_store = SolutionArchitectureStore(root / "architectures.jsonl")
    est_store = CostEstimateStore(root / "cost_estimates.jsonl")
    # spec matériellement différente (autre objectif) ⇒ autre spec_sha256 ⇒ aucune architecture ancrée ⇒ absent
    other = {**spec_fact, "specification": {**SPEC, "product_objective": "TOUT AUTRE PRODUIT"}}
    res = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                            pursuit_ref="p_anchor", current_spec=other)
    assert res["status"] == "absent"                      # ancien Outcome ne peut pas réactiver via une autre matière


# ===================================================================== #
# 5. AUTHORIZATION_STATUS — autorité unique, fingerprint exact, declined annule approved
# ===================================================================== #
def test_authorization_status_latest_and_obsolete(tmp_path):
    store = BuildAuthorizationStore(tmp_path / "auth.jsonl")
    assert authorization_status(store, pursuit_ref="p", gate_fingerprint="fp_x") == "none"
    assert authorization_status(None, pursuit_ref="p", gate_fingerprint="fp_x") == "none"
    store.record(build_authorization_fact(pursuit_ref="p", spec_ref="s", architecture_ref="a",
                 selected_option_id="opt_a", estimate_refs=["e1"], gate_fingerprint="fp_x", decision="approved",
                 as_of="2026-01-01T00:00:00+00:00", dependencies=["python"]))
    assert authorization_status(store, pursuit_ref="p", gate_fingerprint="fp_x") == "approved"
    assert authorization_status(store, pursuit_ref="p", gate_fingerprint="fp_autre") == "none"   # obsolète ⇒ none
    store.record(build_authorization_fact(pursuit_ref="p", spec_ref="s", architecture_ref="a",
                 selected_option_id="opt_a", estimate_refs=["e1"], gate_fingerprint="fp_x", decision="declined",
                 as_of="2026-01-02T00:00:00+00:00", dependencies=["python"]))
    assert authorization_status(store, pursuit_ref="p", gate_fingerprint="fp_x") == "declined"   # postérieur annule


# ===================================================================== #
# 6. COMPOSITION.AUTHORIZE — USER GO inerte, lookup exact, fail-closed, dépendances réelles
# ===================================================================== #
def test_authorize_approved_records_inert_with_real_dependencies(l8_env, boundary):
    root, spec_id, build_id, spec_fact, fp = l8_env("p_auth_ok")
    rec = composition.authorize("p_auth_ok", presented_spec_ref=spec_id, presented_gate_fingerprint=fp,
                                decision="approved", actor="tester")
    assert rec["status"] == "recorded" and rec["decision"] == "approved" and rec["gate_fingerprint"] == fp
    assert boundary.calls == 0                            # authorize ne déclenche AUCUNE construction
    facts = BuildAuthorizationStore(root / "build_authorizations.jsonl").read_all()
    assert len(facts) == 1 and facts[0]["decision"] == "approved"
    assert facts[0]["dependencies"] == ["python"]         # dépendances réelles de l'option retenue (jamais [])


def test_authorize_obsolete_fingerprint_refused_without_write(l8_env):
    root, spec_id, build_id, spec_fact, fp = l8_env("p_auth_obs")
    rec = composition.authorize("p_auth_obs", presented_spec_ref=spec_id,
                                presented_gate_fingerprint="fp_obsolete", decision="approved", actor="t")
    assert rec["status"] == "refused" and rec["reason"] == "fingerprint_present_obsolete"
    # AUCUNE écriture : le journal d'autorisations reste vide (lecture explicite, pas seulement absence de fichier)
    assert BuildAuthorizationStore(root / "build_authorizations.jsonl").read_all() == []


def test_authorize_fail_closed_inputs(l8_env):
    root, spec_id, build_id, spec_fact, fp = l8_env("p_auth_form")
    assert composition.authorize("p_auth_form", presented_spec_ref=spec_id,
                                 presented_gate_fingerprint=fp, decision="peut-etre")["status"] == "refused"
    assert composition.authorize("p_auth_form", presented_spec_ref="   ",
                                 presented_gate_fingerprint=fp, decision="approved")["status"] == "refused"
    # spec présentée introuvable ⇒ refus (aucun parcours arbitraire de l'historique)
    r = composition.authorize("p_auth_form", presented_spec_ref="spec_inconnue",
                              presented_gate_fingerprint=fp, decision="approved")
    assert r["status"] == "refused" and r["reason"] == "specification_presentee_introuvable_ou_ambigue"
    # aucun de ces refus n'a écrit une autorisation
    assert BuildAuthorizationStore(root / "build_authorizations.jsonl").read_all() == []


# ===================================================================== #
# 7. COMPOSITION._DELIVER — frontière réelle (A..F) : NO VALID CURRENT GO = NO SIGNIFICANT CONSTRUCTION
# ===================================================================== #
def test_deliver_A_no_go_refuses(l8_env, boundary):
    root, sid, bid, _s, fp = l8_env("p_A")
    res = composition._deliver(root, FakeOutcome("p_A", sid, bid, fp), actor="t", budget_usd=1.0)
    assert res["status"] == "refused" and res["reason"] == "no_valid_current_go"
    assert res["significant_construction"] is False and boundary.calls == 0


def test_deliver_B_declined_refuses(l8_env, boundary):
    root, sid, bid, _s, fp = l8_env("p_B")
    composition.authorize("p_B", presented_spec_ref=sid, presented_gate_fingerprint=fp, decision="declined")
    res = composition._deliver(root, FakeOutcome("p_B", sid, bid, fp), actor="t", budget_usd=1.0)
    assert res["status"] == "refused" and res["authorization"] == "declined"
    assert res["significant_construction"] is False and boundary.calls == 0


def test_deliver_D_stale_outcome_fingerprint_refuses(l8_env, boundary):
    root, sid, bid, _s, fp = l8_env("p_D")
    composition.authorize("p_D", presented_spec_ref=sid, presented_gate_fingerprint=fp, decision="approved")
    res = composition._deliver(root, FakeOutcome("p_D", sid, bid, "fp_wrong"), actor="t", budget_usd=1.0)
    assert res["status"] == "refused" and res["reason"] == "cost_gate_fingerprint_present_incoherent"
    assert res["significant_construction"] is False and boundary.calls == 0   # snapshot jamais l'autorité


def test_deliver_E_build_not_attached_refuses(l8_env, boundary):
    root, sid, bid, _s, fp = l8_env("p_E", build_spec_ref="spec_autre")
    composition.authorize("p_E", presented_spec_ref=sid, presented_gate_fingerprint=fp, decision="approved")
    res = composition._deliver(root, FakeOutcome("p_E", sid, bid, fp), actor="t", budget_usd=1.0)
    assert res["status"] == "refused" and res["reason"] == "manifeste_non_attache_a_la_spec_courante"
    assert res["significant_construction"] is False and boundary.calls == 0


def test_deliver_F_valid_go_reaches_boundary(l8_env, boundary):
    root, sid, bid, _s, fp = l8_env("p_F")
    composition.authorize("p_F", presented_spec_ref=sid, presented_gate_fingerprint=fp, decision="approved")
    with pytest.raises(_Boundary):                         # frontière ATTEINTE seulement après GO exact
        composition._deliver(root, FakeOutcome("p_F", sid, bid, fp), actor="t", budget_usd=1.0)
    assert boundary.calls == 1


# ===================================================================== #
# 8. WIRING SERVEUR — kind == "authorize" sous /v1/pursue (même endpoint), forme TYPE-stricte, refus métier 200
# ===================================================================== #
def _req(url, *, method="GET", token=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-BrainAI-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


@pytest.fixture()
def live_server():
    httpd = server.make_server("127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", server.SESSION_TOKEN
    finally:
        httpd.shutdown()


def test_server_authorize_form_validation_type_strict(live_server):
    base, token = live_server

    def post(body):
        return _req(base + "/v1/pursue", method="POST", token=token, body=body)[0]

    valid = {"kind": "authorize", "pursuit_ref": "p", "presented_spec_ref": "s",
             "presented_gate_fingerprint": "f", "decision": "approved"}
    # champ requis absent
    assert post({k: v for k, v in valid.items() if k != "pursuit_ref"}) == 400
    # pursuit_ref non-string (jamais de coercition silencieuse)
    assert post({**valid, "pursuit_ref": 123}) == 400
    # presented_spec_ref non-string
    assert post({**valid, "presented_spec_ref": 123}) == 400
    # presented_gate_fingerprint non-string
    assert post({**valid, "presented_gate_fingerprint": 123}) == 400
    # decision invalide
    assert post({**valid, "decision": "peut-etre"}) == 400
    # kind invalide → message mis à jour mentionnant authorize
    code, body = _req(base + "/v1/pursue", method="POST", token=token, body={"kind": "inconnu"})
    assert code == 400 and "authorize" in body["error"]


def test_server_authorize_business_refusal_is_200(l8_env, live_server):
    root, spec_id, build_id, spec_fact, fp = l8_env("p_srv_ref")
    base, token = live_server
    # forme valide mais fingerprint obsolète : refus MÉTIER gouverné ⇒ 200 (enveloppe), jamais 400
    code, body = _req(base + "/v1/pursue", method="POST", token=token,
                      body={"kind": "authorize", "pursuit_ref": "p_srv_ref", "presented_spec_ref": spec_id,
                            "presented_gate_fingerprint": "fp_obsolete", "decision": "approved"})
    assert code == 200
    assert body["data"]["status"] == "refused" and body["data"]["reason"] == "fingerprint_present_obsolete"


def test_server_authorize_approved_records(l8_env, live_server, boundary):
    root, spec_id, build_id, spec_fact, fp = l8_env("p_srv_ok")
    base, token = live_server
    code, body = _req(base + "/v1/pursue", method="POST", token=token,
                      body={"kind": "authorize", "pursuit_ref": "p_srv_ok", "presented_spec_ref": spec_id,
                            "presented_gate_fingerprint": fp, "decision": "approved", "actor": "humain"})
    assert code == 200 and body["data"]["status"] == "recorded" and body["data"]["decision"] == "approved"
    assert boundary.calls == 0                              # aucun déclenchement de livraison via authorize
