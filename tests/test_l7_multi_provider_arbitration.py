"""L7 — Fan-out multi-provider / contradiction / arbitrage BrainAI / convergence — déterministe, 0 $.

Prouve, sans aucune clé ni appel réel (adaptateurs fakes injectés) :
- sélection provider : absent → défaut single historique ; 1 nom → ce fournisseur seul (jamais remplacé) ;
  ≥2 → cohorte ; liste vide/doublon → ValueError ; inconnu → LookupError ; deux sélecteurs → ValueError ;
- wiring réel ``server → composition → BrainAI.pursue`` : opt-in via champ ``providers`` (transmis 1 fois) ;
- fan-out : cohorte vide ⇒ 1 propose() ; cohorte N ⇒ N propose() (jamais N+1) ; contributions séparées +
  provenance conservée ; arbitrage BrainAI provider-neutral ; convergence → brief convergé alimente le Rung 2 ;
- classification : consensus / complémentarité / divergence / contradiction / insuffisant ;
- canonicalisation invariante par permutation ; policy injectable ; contradiction TOUJOURS fail-closed (policy
  jamais consultée) ; fan-out sans ArbitrationStore ⇒ fail-closed avant tout appel ;
- frontières : aucun nom de provider dans le moteur d'arbitrage ; aucun couplage bridge/base44/reasoning/decision.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from brainai_app import providers as P
from brainai_app import server
from brainai_app.composition import demo_capabilities
from scc_brainai_bootstrap.builder import understanding_arbitration as ARB
from scc_brainai_bootstrap.builder.arbitrations import ArbitrationStore
from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, Stores, need_intent)
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.builder.understanding import NeedUnderstandingCapability
from scc_brainai_bootstrap.builder.workspace import Workspace
from scc_brainai_bootstrap.builder.understanding_arbitration import (
    ArbitrationPolicy, PreserveOrFailClosed, converge, normalize)


# --------------------------------------------------------------------- #
# Helpers — briefs, fake understanding adapter (0 $), contextes
# --------------------------------------------------------------------- #
def _brief(**over):
    b = {"objective": "o", "context": "c", "actors": ["a"], "scope": ["s"],
         "assumptions": ["h"], "open_questions": ["q"], "constraints": ["k"]}
    b.update(over)
    return b


class _FakeUnderstanding:
    """Adaptateur understanding **fake** conforme au Protocol (0 $, aucun réseau). Capacité = constante canonique
    ``understand.need`` (réutilisée de la couche providers) ; ``name`` libre (label), brief configurable ; peut
    simuler refus (budget/clé), erreur d'appel, ou réponse invalide."""

    capability = P.UNDERSTAND_NEED

    def __init__(self, *, name, brief=None, max_budget_usd=0.50,
                 refused=None, is_error=False, invalid=False):
        self.name = name
        self.model = None
        self.max_budget_usd = max_budget_usd
        self._brief = brief if brief is not None else _brief()
        self._refused = refused
        self._is_error = is_error
        self._invalid = invalid
        self.calls = 0

    def propose(self, need, *, cwd, budget_remaining_usd):
        self.calls += 1
        base = {"called": True, "prompt": "(fake)", "argv": None, "stdout": None, "stderr": None,
                "exit_code": 0, "timed_out": False}
        if self._refused is not None or budget_remaining_usd < self.max_budget_usd:
            return {"called": False, "envelope": None, "exit_code": None, "timed_out": False,
                    "prompt": "(fake)", "argv": None, "stdout": None, "stderr": None,
                    "refused": self._refused or "budget insuffisant"}
        if self._is_error:
            return {**base, "envelope": {"subtype": "api_error", "is_error": True, "result": None,
                                         "api_error_status": "boom"}}
        if self._invalid:
            return {**base, "envelope": {"subtype": "success", "is_error": False,
                                         "result": "pas-du-json", "api_error_status": None}}
        return {**base, "envelope": {"subtype": "success", "is_error": False,
                                     "result": json.dumps(self._brief), "usage": None,
                                     "api_error_status": None}}


def _ctx(tmp_path, *, arbitrations=False, budget_usd=2.0):
    kw = dict(proposals=ProposalStore(tmp_path / "prop.jsonl"),
              specifications=SpecificationStore(tmp_path / "spec.jsonl"),
              builds=BuildStore(tmp_path / "build.jsonl"))
    if arbitrations:
        kw["arbitrations"] = ArbitrationStore(tmp_path / "arb.jsonl")
    return RunContext(budget_usd=budget_usd, project_id="session",
                      workspace=Workspace(tmp_path / "exec", "session"), stores=Stores(**kw))


def _caps_cohort(cohort, *, policy=None):
    demo = demo_capabilities()
    return Capabilities(understanding=cohort[0], specification=demo.specification, build=demo.build,
                        conversation=demo.conversation, understanding_cohort=tuple(cohort),
                        arbitration_policy=policy)


def _read_props(tmp_path):
    p = tmp_path / "prop.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def _read_arbs(tmp_path):
    return ArbitrationStore(tmp_path / "arb.jsonl").read_all()


# ===================================================================== #
# 1. MOTEUR D'ARBITRAGE — pur, déterministe, provider-neutral
# ===================================================================== #
def test_engine_has_no_concrete_provider_name():
    src = Path(ARB.__file__).read_text(encoding="utf-8")
    for name in ("claude_code", "openai", "gemini"):
        assert name not in src, f"nom de provider concret interdit dans le moteur : {name}"


def test_consensus_arrays_and_scalars():
    briefs = [_brief(), _brief()]
    res = converge(briefs)
    assert res["status"] == "converged"
    assert res["brief"] == _brief()
    assert res["rationale"]["objective"]["category"] == "consensus"
    assert res["rationale"]["actors"]["category"] == "consensus"


def test_complementarity_union_arrays():
    b1 = _brief(scope=["Animaux"])
    b2 = _brief(scope=["Adoptants"])
    res = converge([b1, b2])
    assert res["status"] == "converged"
    assert res["brief"]["scope"] == ["Adoptants", "Animaux"]           # union canonique triée
    assert res["rationale"]["scope"]["category"] == "complementarity"


def test_divergence_scalar_without_policy_is_failclosed():
    b1 = _brief(objective="gérer un club")
    b2 = _brief(objective="gérer une association")
    res = converge([b1, b2])                                           # défaut = PreserveOrFailClosed
    assert res["status"] == "unresolved"
    assert "objective" in res["unresolved_fields"]


def test_divergence_scalar_with_policy_resolves():
    calls = []

    class _Pol:
        def resolve(self, *, field, candidates):
            calls.append((field, candidates))
            return {"value": "DECISION BRAINAI", "justification": "règle neutre"}

    b1 = _brief(objective="gérer un club")
    b2 = _brief(objective="gérer une association")
    res = converge([b1, b2], policy=_Pol())
    assert res["status"] == "converged"
    assert res["brief"]["objective"] == "DECISION BRAINAI"
    assert calls and calls[0][0] == "objective"
    # candidats canoniques triés (order-invariant), pas de nom de provider
    assert calls[0][1] == ("gérer un club", "gérer une association")


def test_contradiction_array_is_failclosed():
    b1 = _brief(constraints=["notifications"])
    b2 = _brief(constraints=["pas de notifications"])
    res = converge([b1, b2])
    assert res["status"] == "unresolved"
    assert "constraints" in res["unresolved_fields"]


def test_contradiction_scalar_never_calls_policy_and_failcloses():
    called = {"n": 0}

    class _Spy:
        def resolve(self, *, field, candidates):
            called["n"] += 1
            return {"value": "X", "justification": "j"}

    b1 = _brief(objective="notifications")
    b2 = _brief(objective="pas de notifications")                      # négation explicite → contradiction
    res = converge([b1, b2], policy=_Spy())
    assert res["status"] == "unresolved"
    assert "objective" in res["unresolved_fields"]
    assert called["n"] == 0, "la policy ne doit JAMAIS être consultée sur une contradiction"


def test_insufficient_single_brief():
    res = converge([_brief()])
    assert res["status"] == "unresolved" and res["reason"] == "insufficient_contributions"


def test_permutation_invariance():
    b1 = _brief(scope=["A"], assumptions=["x"])
    b2 = _brief(scope=["B"], assumptions=["y"])
    b3 = _brief(scope=["C"], assumptions=["z"])
    r1 = converge([b1, b2, b3])
    r2 = converge([b3, b1, b2])
    r3 = converge([b2, b3, b1])
    assert r1["status"] == "converged"
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(r2, sort_keys=True, ensure_ascii=False)
    assert json.dumps(r1, sort_keys=True, ensure_ascii=False) == json.dumps(r3, sort_keys=True, ensure_ascii=False)


def test_canonicalisation_nfc_whitespace_case_dedup():
    # NFC + trim + collapse + casefold-dedup : formes variées de "Café" fusionnent en un seul item.
    b1 = _brief(actors=["  Café  ", "café"])
    b2 = _brief(actors=["Café"])                          # 'e' + accent combinant → NFC 'é'
    res = converge([b1, b2])
    assert res["status"] == "converged"
    assert res["brief"]["actors"] == ["Café"]                         # une seule valeur canonique
    assert normalize("  a   b ") == "a b"


# ===================================================================== #
# 2. SÉLECTION PROVIDER — providers.py (fail-closed, non-régression)
# ===================================================================== #
def test_absent_selector_defaults_to_claude():
    caps = P.real_capabilities()
    assert caps.understanding.name == "claude_code"
    assert caps.understanding_cohort == ()                            # aucun fan-out


def test_list_single_claude_only():
    caps = P.real_capabilities(understanding_providers=["claude_code"])
    assert caps.understanding.name == "claude_code" and caps.understanding_cohort == ()


def test_list_single_openai_not_replaced_by_default():
    caps = P.real_capabilities(understanding_providers=["openai"])
    assert caps.understanding.name == "openai" and caps.understanding_cohort == ()


def test_list_single_gemini_only():
    caps = P.real_capabilities(understanding_providers=["gemini"])
    assert caps.understanding.name == "gemini" and caps.understanding_cohort == ()


def test_cohort_three_providers():
    caps = P.real_capabilities(understanding_providers=["claude_code", "openai", "gemini"])
    assert [a.name for a in caps.understanding_cohort] == ["claude_code", "openai", "gemini"]
    assert caps.understanding is caps.understanding_cohort[0]         # ancre = 1ᵉʳ membre
    assert caps.specification.name == "claude_code"                  # autres capacités inchangées
    assert caps.build.name == "claude_code" and caps.conversation.name == "claude_code"


def test_empty_list_fail_closed():
    with pytest.raises(ValueError):
        P.real_capabilities(understanding_providers=[])


def test_duplicate_list_fail_closed():
    with pytest.raises(ValueError):
        P.real_capabilities(understanding_providers=["openai", "openai"])


def test_unknown_provider_lookuperror():
    with pytest.raises(LookupError):
        P.real_capabilities(understanding_providers=["mistral", "openai"])
    with pytest.raises(LookupError):
        P.resolve_understanding_cohort(["mistral"])


def test_both_selectors_fail_closed():
    with pytest.raises(ValueError):
        P.real_capabilities(understanding_provider="openai", understanding_providers=["openai", "gemini"])


def test_resolve_cohort_reuses_resolve_understanding_ordered():
    cohort = P.resolve_understanding_cohort(["claude_code", "openai", "gemini"])
    assert [a.name for a in cohort] == ["claude_code", "openai", "gemini"]
    with pytest.raises(ValueError):
        P.resolve_understanding_cohort([])
    with pytest.raises(ValueError):
        P.resolve_understanding_cohort(["openai", "openai"])


# ===================================================================== #
# 3. FAN-OUT via BrainAI.pursue — 0 $ (fakes injectés)
# ===================================================================== #
def test_no_implicit_fanout_single_provider_one_propose(tmp_path):
    fake = _FakeUnderstanding(name="solo")
    demo = demo_capabilities()
    caps = Capabilities(understanding=fake, specification=demo.specification, build=demo.build,
                        conversation=demo.conversation)                # AUCUNE cohorte
    BrainAI(caps).pursue(need_intent("x"), context=_ctx(tmp_path))
    assert fake.calls == 1                                            # exactement 1 propose()


def test_fanout_calls_each_provider_exactly_once_and_converges(tmp_path):
    f1 = _FakeUnderstanding(name="pa", brief=_brief(scope=["A"]))
    f2 = _FakeUnderstanding(name="pb", brief=_brief(scope=["B"]))
    f3 = _FakeUnderstanding(name="pc", brief=_brief(scope=["C"]))
    caps = _caps_cohort([f1, f2, f3])
    out = BrainAI(caps).pursue(need_intent("x"), context=_ctx(tmp_path, arbitrations=True))
    assert (f1.calls, f2.calls, f3.calls) == (1, 1, 1)               # N propose(), jamais N+1
    props = _read_props(tmp_path)
    contribs = [b for b in props if b.get("fact_type") == "brief" and b.get("adapter") in {"pa", "pb", "pc"}]
    assert {b["adapter"] for b in contribs} == {"pa", "pb", "pc"}    # provenance séparée conservée
    conv = [b for b in props if b.get("adapter") == "brainai"]
    assert len(conv) == 1 and conv[0]["status"] == "proposed"        # brief convergé auteur BrainAI
    assert sorted(conv[0]["brief"]["scope"]) == ["A", "B", "C"]      # union canonique
    arbs = _read_arbs(tmp_path)
    assert len(arbs) == 1 and arbs[0]["status"] == "converged"
    assert arbs[0]["converged_proposal_id"] == conv[0]["proposal_id"]
    assert len(arbs[0]["contributor_proposal_ids"]) == 3
    # convergence alimente le Rung 2 EXISTANT → l'arc se poursuit (démo) jusqu'à awaiting/gouvernance.
    assert out.state == "awaiting"


def test_fanout_insufficient_valid_contributions_failclosed(tmp_path):
    f1 = _FakeUnderstanding(name="pa")                                # ok
    f2 = _FakeUnderstanding(name="pb", is_error=True)                 # échec d'appel
    f3 = _FakeUnderstanding(name="pc", invalid=True)                 # réponse invalide
    caps = _caps_cohort([f1, f2, f3])
    out = BrainAI(caps).pursue(need_intent("x"), context=_ctx(tmp_path, arbitrations=True))
    assert (f1.calls, f2.calls, f3.calls) == (1, 1, 1)               # échecs NON masqués (tous consultés)
    arbs = _read_arbs(tmp_path)
    assert len(arbs) == 1 and arbs[0]["status"] == "insufficient"
    assert not any(b.get("adapter") == "brainai" for b in _read_props(tmp_path))
    assert out.state == "terminal"


def test_fanout_unresolved_divergence_failclosed_no_converged_brief(tmp_path):
    f1 = _FakeUnderstanding(name="pa", brief=_brief(objective="gérer un club"))
    f2 = _FakeUnderstanding(name="pb", brief=_brief(objective="gérer une association"))
    caps = _caps_cohort([f1, f2])                                     # pas de policy → divergence scalaire
    out = BrainAI(caps).pursue(need_intent("x"), context=_ctx(tmp_path, arbitrations=True))
    arbs = _read_arbs(tmp_path)
    assert len(arbs) == 1 and arbs[0]["status"] == "unresolved"
    assert "objective" in arbs[0]["unresolved_fields"]
    assert not any(b.get("adapter") == "brainai" for b in _read_props(tmp_path))
    assert out.state == "terminal"                                    # Rung 2 NON alimentée


def test_fanout_policy_injected_resolves_divergence(tmp_path):
    class _Pol:
        def resolve(self, *, field, candidates):
            return {"value": candidates[0], "justification": "premier candidat canonique (neutre)"}

    f1 = _FakeUnderstanding(name="pa", brief=_brief(objective="gérer un club"))
    f2 = _FakeUnderstanding(name="pb", brief=_brief(objective="gérer une association"))
    caps = _caps_cohort([f1, f2], policy=_Pol())
    out = BrainAI(caps).pursue(need_intent("x"), context=_ctx(tmp_path, arbitrations=True))
    conv = [b for b in _read_props(tmp_path) if b.get("adapter") == "brainai"]
    assert len(conv) == 1 and conv[0]["brief"]["objective"] == "gérer un club"
    assert _read_arbs(tmp_path)[0]["status"] == "converged"
    assert out.state == "awaiting"


def test_fanout_without_arbitration_store_failcloses_before_any_call(tmp_path):
    f1 = _FakeUnderstanding(name="pa")
    f2 = _FakeUnderstanding(name="pb")
    caps = _caps_cohort([f1, f2])
    out = BrainAI(caps).pursue(need_intent("x"), context=_ctx(tmp_path, arbitrations=False))
    assert f1.calls == 0 and f2.calls == 0                           # refus AVANT tout appel provider
    assert out.state == "terminal" and out.refused


def test_arbitration_policy_default_is_preserve_or_failclosed():
    assert isinstance(PreserveOrFailClosed(), ArbitrationPolicy)
    assert PreserveOrFailClosed().resolve(field="objective", candidates=("a", "b")) is None


# ===================================================================== #
# 4. WIRING RÉEL — server → composition → run_pursuit (0 $)
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


def test_server_forwards_providers_to_run_pursuit(monkeypatch, live_server):
    base, token = live_server
    captured = {"n": 0}

    def _stub(need, *, mode="demo", understanding_providers=None, **kw):
        captured["n"] += 1
        captured["need"] = need
        captured["providers"] = understanding_providers
        return {"conversation": {}, "pursuit": {}, "steps": [], "deliverables": []}

    monkeypatch.setattr(server, "run_pursuit", _stub)
    code, _ = _req(base + "/v1/pursue", method="POST", token=token,
                   body={"need": "x", "providers": ["claude_code", "openai"]})
    assert code == 200
    assert captured["n"] == 1                                         # exactement 1 appel run_pursuit
    assert captured["providers"] == ["claude_code", "openai"]


def test_server_absent_providers_forwards_none(monkeypatch, live_server):
    base, token = live_server
    captured = {"n": 0, "providers": "SENTINEL"}

    def _stub(need, *, mode="demo", understanding_providers=None, **kw):
        captured["n"] += 1
        captured["providers"] = understanding_providers
        return {"conversation": {}, "pursuit": {}, "steps": [], "deliverables": []}

    monkeypatch.setattr(server, "run_pursuit", _stub)
    code, _ = _req(base + "/v1/pursue", method="POST", token=token, body={"need": "x"})
    assert code == 200 and captured["n"] == 1 and captured["providers"] is None


def test_server_empty_providers_400(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token, body={"need": "x", "providers": []})
    assert code == 400


def test_server_duplicate_providers_400(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token,
                   body={"need": "x", "providers": ["openai", "openai"]})
    assert code == 400


def test_server_providers_not_a_list_400(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token,
                   body={"need": "x", "providers": "openai"})
    assert code == 400


def test_server_unknown_provider_mapped_to_400(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token,
                   body={"need": "x", "mode": "real", "providers": ["mistral"]})
    assert code == 400                                                # LookupError (résolution) → 400, aucun appel


# ===================================================================== #
# 5. FRONTIÈRES — aucun couplage interdit introduit par L7
# ===================================================================== #
def test_l7_modules_have_no_forbidden_couplings():
    for mod_file in (ARB.__file__, Path(ARB.__file__).with_name("arbitrations.py")):
        src = Path(mod_file).read_text(encoding="utf-8")
        for forbidden in ("seror", "base44", "SEROR", "Base44",
                          "scc_brainai_reasoning", "scc_brainai_decision",
                          "13_BRAINAI_REASONING", "15_BRAINAI_DECISION",
                          "retrieve_pursuit", "Learning-12"):
            assert forbidden not in src, f"couplage interdit : {forbidden} dans {mod_file}"


# ===================================================================== #
# 6. PREUVE RÉELLE GATED — fan-out multi-provider RÉEL (facturable) — jamais exécuté par défaut
# ===================================================================== #
# Prérequis des TROIS providers canoniques (motif SKIP L6A/L6B, aucune clé exposée : seuls les NOMS sont testés) :
#   - gate propriétaire : BRAINAI_L7_REAL=1 ;
#   - claude_code : binaire CLI ``claude`` présent (auth keychain/HOME propriétaire) ;
#   - openai : OPENAI_API_KEY présent ; gemini : GEMINI_API_KEY présent.
# Gate absent OU un prérequis manquant ⇒ SKIP normal (jamais un faux PASS, jamais de fuite de secret).
@pytest.mark.skipif(
    os.environ.get("BRAINAI_L7_REAL") != "1"
    or shutil.which("claude") is None
    or not os.environ.get("OPENAI_API_KEY")
    or not os.environ.get("GEMINI_API_KEY"),
    reason="preuve réelle L7 : nécessite BRAINAI_L7_REAL=1 ET CLI 'claude' ET OPENAI_API_KEY ET GEMINI_API_KEY "
           "(GO-secrets propriétaire ; appels réels facturables aux 3 providers canoniques)")
def test_l7_real_fanout_gated(tmp_path):  # pragma: no cover - exécuté seulement sur activation explicite
    """Preuve RÉELLE de bout en bout : BrainAI consulte réellement les **3 providers canoniques** sur une même
    demande en **une seule** exécution de fan-out (aucun retry), conserve chaque contribution séparément
    (provenance réelle), et produit **exactement un** fait d'arbitrage BrainAI.

    La preuve n'est acquise QUE si les **trois** provenances ``{claude_code, openai, gemini}`` produisent chacune
    une contribution réelle ``proposed`` distincte. Un ``insufficient`` (une contribution réelle manquante) est un
    **échec** de la preuve. Statut d'arbitrage acceptable : ``converged`` (convergence réelle) OU ``unresolved``
    (fail-closed réellement démontré) — jamais forcé."""
    providers = ["claude_code", "openai", "gemini"]
    caps = P.real_capabilities(understanding_providers=providers)
    assert [a.name for a in caps.understanding_cohort] == providers   # cohorte réelle des 3 canoniques
    out = BrainAI(caps).pursue(need_intent("un site vitrine pour un club de sport associatif"),
                               context=_ctx(tmp_path, arbitrations=True, budget_usd=5.0))
    # Preuve des 3 providers : chacun a produit une contribution réelle 'proposed' SÉPARÉE (provenance conservée).
    proposed_by = {b["adapter"] for b in _read_props(tmp_path)
                   if b.get("fact_type") == "brief" and b.get("status") == "proposed"
                   and b.get("adapter") in set(providers)}
    assert proposed_by == {"claude_code", "openai", "gemini"}, \
        f"preuve multi-provider INCOMPLÈTE — provenances 'proposed' réelles obtenues : {sorted(proposed_by)}"
    # Exactement UN fait d'arbitrage (une seule exécution de fan-out, aucun retry).
    arbs = _read_arbs(tmp_path)
    assert len(arbs) == 1
    assert arbs[0]["status"] in ("converged", "unresolved"), \
        f"'insufficient' = échec de la preuve réelle L7 (statut : {arbs[0]['status']})"
    if arbs[0]["status"] == "converged":
        conv = [b for b in _read_props(tmp_path) if b.get("adapter") == "brainai"]
        assert len(conv) == 1 and conv[0]["proposal_id"] == arbs[0]["converged_proposal_id"]
        assert out.state == "awaiting"                               # brief convergé → Rung 2 alimenté
    else:  # unresolved → fail-closed réellement prouvé : aucun brief inventé, Rung 2 non alimentée
        assert out.state == "terminal"
        assert not any(b.get("adapter") == "brainai" for b in _read_props(tmp_path))
