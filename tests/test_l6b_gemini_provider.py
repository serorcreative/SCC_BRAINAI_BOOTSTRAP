"""L6B — Gemini comme 3ᵉ provider réel : INTERCHANGEABILITÉ RÉELLE, déterministe, 0 $.

Strict miroir de la preuve L6A, provider distinct. Prouve, sans aucune clé ni appel réel (client injecté
déterministe) : l'adaptateur Gemini satisfait le MÊME contrat de capacité que Claude Code / OpenAI ; le Core résout
explicitement ``gemini`` derrière la même capacité ``understand.need`` via le MÊME registre ; fournisseur inconnu /
clé absente / budget insuffisant = fail-closed ; réponse et erreur normalisées ; aucun secret ne fuit ; aucun
fan-out/arbitrage ; Claude Code et OpenAI non régressés ; aucun couplage L4/L5 / Memory-11 / Learning-12 / 13 / 15.
Le test réel Gemini est GATED (jamais exécuté en CI par défaut).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from brainai_app import providers as P
from brainai_app.composition import demo_capabilities
from scc_brainai_bootstrap.builder.adapter_contract import require_contract, validate_contract
from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, Stores, need_intent)
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.gemini_understanding import (
    GeminiUnderstandingAdapter, build_generate_request)
from scc_brainai_bootstrap.builder.openai_understanding import OpenAIUnderstandingAdapter
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.builder.understanding import (
    BRIEF_SCHEMA, NeedUnderstandingCapability, ClaudeCodeUnderstandingAdapter, build_proposal)
from scc_brainai_bootstrap.builder.workspace import Workspace

_BRIEF = {"objective": "o", "context": "c", "actors": ["a"], "scope": ["s"],
          "assumptions": ["h"], "open_questions": ["q"], "constraints": ["k"]}


class _FakeResponder:
    """Client structuré déterministe (aucun réseau, aucun SDK) — renvoie un Brief conforme."""

    def __init__(self, *, brief=None, usage=None, raises=None):
        self._brief = brief if brief is not None else _BRIEF
        self._usage = usage
        self._raises = raises
        self.calls = []

    def respond(self, *, prompt, schema, model, timeout):
        self.calls.append({"prompt": prompt, "model": model, "timeout": timeout})
        if self._raises is not None:
            raise self._raises
        return {"text": json.dumps(self._brief), "usage": self._usage}


# 1. Même contrat de capacité (Protocol + contrat T2 complet) ------------------------------------------
def test_gemini_adapter_satisfies_capability_contract():
    ad = GeminiUnderstandingAdapter(client=_FakeResponder())
    assert isinstance(ad, NeedUnderstandingCapability)          # même Protocol que Claude Code / OpenAI
    assert ad.capability == "understanding" and ad.name == "gemini"
    assert validate_contract(ad.contract()) == []              # contrat complet (T2)
    require_contract(ad)                                        # ne lève pas
    c = ad.contract().to_dict()
    assert c["auth_channel"]["kind"] == "api_key" and c["auth_channel"]["leaks_identity"] is False
    assert c["auth_channel"]["token_var"] == "GEMINI_API_KEY"
    assert c["cost_report"]["mode"] == "unavailable"           # I6 : coût jamais fabriqué
    assert c["native_budget"]["call_cap"] == "enforced_by_brainai"


# 2 & 3. Résolution explicite gemini derrière la MÊME capacité ----------------------------------------
def test_resolve_understanding_gemini():
    impl = P.resolve_understanding("gemini")
    assert isinstance(impl, GeminiUnderstandingAdapter) and impl.name == "gemini"
    assert isinstance(impl, NeedUnderstandingCapability)


# 4. Fournisseur inconnu => fail-closed (gemini est désormais admis, mistral non) ---------------------
def test_unknown_provider_fail_closed():
    with pytest.raises(LookupError):
        P.resolve_understanding("mistral")                     # pas encore admis (lot suivant)


# 5. Clé absente => fail-closed UNIQUEMENT à l'appel réel demandé (client réel) -----------------------
def test_missing_api_key_fail_closed_on_real_call(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ad = GeminiUnderstandingAdapter()                          # client None => chemin réel
    out = ad.propose("besoin", cwd=tmp_path, budget_remaining_usd=10.0)
    assert out["called"] is False and out["envelope"] is None
    assert "GEMINI_API_KEY absent" in out["refused"]


# 7. Budget insuffisant => aucun appel ----------------------------------------------------------------
def test_budget_refused_no_call():
    fake = _FakeResponder()
    ad = GeminiUnderstandingAdapter(client=fake, max_budget_usd=0.50)
    out = ad.propose("besoin", cwd=Path("."), budget_remaining_usd=0.10)
    assert out["called"] is False and out["refused"] == "budget insuffisant"
    assert fake.calls == []                                    # le client n'a jamais été appelé


# 8. Réponse normalisée dans l'enveloppe attendue (amont agnostique de Gemini) ------------------------
def test_response_normalized_into_envelope_and_brief():
    fake = _FakeResponder(usage={"prompt_token_count": 12, "candidates_token_count": 34})
    ad = GeminiUnderstandingAdapter(client=fake, max_budget_usd=0.50)
    out = ad.propose("un site pour mon club", cwd=Path("."), budget_remaining_usd=10.0)
    assert out["called"] is True and out["timed_out"] is False and out["argv"] is None
    env = out["envelope"]
    assert env["subtype"] == "success" and env["is_error"] is False
    assert env["usage"] == {"prompt_token_count": 12, "candidates_token_count": 34}
    assert "total_cost_usd" not in env                        # Gemini ne renvoie pas de coût USD => unavailable (I6)
    # L'amont (build_proposal) construit un fait 'proposed' sans rien connaître de Gemini :
    fact = build_proposal(need="un site", prompt=out["prompt"], capability="understanding",
                          adapter=ad.name, model=ad.model, envelope=env, exit_code=out["exit_code"],
                          timed_out=out["timed_out"], as_of="t0")
    assert fact["status"] == "proposed" and fact["brief"] == _BRIEF
    assert fact["cost"] == {"value": None, "kind": "unavailable"}   # honnête (I6)


# 9. Erreur API normalisée + AUCUN secret ne fuit -----------------------------------------------------
def test_api_error_normalized_no_secret_leak():
    fake = _FakeResponder(raises=ValueError("boom AIzaSyABCDEFGH12345678 leaked"))
    ad = GeminiUnderstandingAdapter(client=fake, max_budget_usd=0.50)
    out = ad.propose("besoin", cwd=Path("."), budget_remaining_usd=10.0)
    assert out["called"] is True
    env = out["envelope"]
    assert env["is_error"] is True and env["subtype"] == "api_error"
    assert env["api_error_status"] == "ValueError"            # classe seule, jamais le message
    assert "AIzaSyABCDEFGH12345678" not in json.dumps(out)    # aucune fuite de secret dans tout le retour


# 6. Aucun secret journalisé/persisté : la valeur de clé n'apparaît jamais dans le retour -------------
def test_api_key_value_never_in_output(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyREALSECRETVALUE0000")
    fake = _FakeResponder()
    ad = GeminiUnderstandingAdapter(client=fake)              # client injecté => clé jamais lue
    out = ad.propose("besoin", cwd=Path("."), budget_remaining_usd=10.0)
    assert "AIzaSyREALSECRETVALUE0000" not in json.dumps(out)
    assert "GEMINI_API_KEY" == ad.api_key_var                # seul le NOM est manipulé


# 10. Claude Code ET OpenAI non régressés -------------------------------------------------------------
def test_claude_and_openai_providers_not_regressed():
    claude = P.resolve_understanding("claude_code")
    assert validate_contract(claude.contract()) == []
    assert claude.contract().to_dict()["auth_channel"]["kind"] == "keychain_home"   # comportement historique
    openai = P.resolve_understanding("openai")
    assert isinstance(openai, OpenAIUnderstandingAdapter) and openai.name == "openai"


# 14. Aucun fan-out / arbitrage accidentel : la résolution rend UN adaptateur, pas une collection -----
def test_no_fanout_single_impl():
    impl = P.resolve_understanding("gemini")
    assert not isinstance(impl, (list, tuple, set, dict))
    assert hasattr(impl, "propose") and callable(impl.propose)


# 11/12/13. Aucun couplage L4/L5 / Memory-11 / Learning-12 / Reasoning-13 / Decision-15 ---------------
def test_adapter_has_no_forbidden_couplings():
    import scc_brainai_bootstrap.builder.gemini_understanding as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("scc_brainai_memory", "scc_brainai_learning",
                      "scc_brainai_reasoning", "scc_brainai_decision"):
        assert forbidden not in src                            # CONNECTER un provider, pas recâbler la cognition


# --- Phase K : PREUVE DU CHEMIN PURSUIT CANONIQUE ($0) ----------------------------------------------
def test_canonical_real_capabilities_default_is_claude():
    """Construction canonique par défaut : understanding = Claude Code (comportement inchangé)."""
    caps = P.real_capabilities()                               # défaut = claude_code
    assert isinstance(caps.understanding, ClaudeCodeUnderstandingAdapter)
    assert caps.understanding.name == "claude_code"


def test_canonical_real_capabilities_gemini_only_understanding():
    """Construction canonique avec provider explicite gemini : SEULE l'understanding bascule ; les autres
    capacités restent claude_code (aucune bascule automatique)."""
    caps = P.real_capabilities(understanding_provider="gemini")
    assert isinstance(caps.understanding, GeminiUnderstandingAdapter)
    assert caps.understanding.name == "gemini"
    assert caps.specification.name == "claude_code"           # inchangé
    assert caps.build.name == "claude_code"                   # inchangé
    assert caps.conversation.name == "claude_code"            # inchangé


def test_canonical_real_capabilities_unknown_provider_fail_closed():
    with pytest.raises(LookupError):
        P.real_capabilities(understanding_provider="mistral")


def _ctx(tmp_path, budget_usd=2.0):
    stores = Stores(proposals=ProposalStore(tmp_path / "prop.jsonl"),
                    specifications=SpecificationStore(tmp_path / "spec.jsonl"),
                    builds=BuildStore(tmp_path / "build.jsonl"))
    return RunContext(budget_usd=budget_usd, project_id="session",
                      workspace=Workspace(tmp_path / "exec", "session"), stores=stores)


def test_pursue_consumes_selected_gemini_understanding(tmp_path):
    """BrainAI.pursue consomme EFFECTIVEMENT l'adaptateur Gemini sélectionné pour understand.need — pas un
    resolver isolé. Understanding = Gemini(fake client, $0) ; les autres capacités = démo (0 €) pour rester
    exécutable en CI sans clé. Prouve que le fait 'brief' porte adapter='gemini'."""
    fake = _FakeResponder()
    demo = demo_capabilities()
    caps = Capabilities(understanding=GeminiUnderstandingAdapter(client=fake, max_budget_usd=0.50),
                        specification=demo.specification, build=demo.build, conversation=demo.conversation)
    outcome = BrainAI(caps).pursue(need_intent("un site pour mon club"), context=_ctx(tmp_path))
    assert fake.calls, "pursue n'a pas consommé l'understanding Gemini"
    und_steps = [s for s in outcome.steps if s.get("faculty") == "understanding"]
    assert und_steps and und_steps[0]["status"] == "proposed"
    # Le fait 'brief' persisté par l'arc porte bien l'adaptateur Gemini (provenance) :
    briefs = [json.loads(l) for l in (tmp_path / "prop.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert any(b.get("adapter") == "gemini" and b.get("fact_type") == "brief" for b in briefs)


# --- Phase L : forme EXACTE de l'appel Structured Outputs (generate_content), sans réseau ------------
def test_generate_request_uses_response_json_schema():
    """Structured Outputs Gemini pour un JSON Schema standard : le schéma vit sous ``config.response_json_schema``
    (et NON ``config.response_schema``, réservé aux objets OpenAPI/Pydantic), avec ``response_mime_type``.
    Fonction pure — banc de contrat des arguments, 0 $."""
    req = build_generate_request("PROMPT", BRIEF_SCHEMA, "gemini-x")
    assert req["model"] == "gemini-x" and req["contents"] == "PROMPT"
    cfg = req["config"]
    assert cfg["response_mime_type"] == "application/json"
    assert cfg["response_json_schema"] == BRIEF_SCHEMA
    assert "response_schema" not in cfg                        # pas la forme OpenAPI/Pydantic
    assert "text" not in req and "response_format" not in cfg  # ni OpenAI (text.format) ni Chat Completions


# 15 / Phase G. Test réel GATED — jamais exécuté en CI par défaut ($0). --------------------------------
@pytest.mark.skipif(
    os.environ.get("BRAINAI_L6B_REAL") != "1" or not os.environ.get("GEMINI_API_KEY"),
    reason="test réel Gemini : nécessite BRAINAI_L6B_REAL=1 ET GEMINI_API_KEY (GO-secrets propriétaire)")
def test_gemini_real_call_gated(tmp_path):  # pragma: no cover - exécuté seulement sur activation explicite
    ad = P.resolve_understanding("gemini")                     # client réel (SDK + clé)
    out = ad.propose("un site vitrine pour un club de sport", cwd=tmp_path, budget_remaining_usd=10.0)
    assert out["called"] is True
    env = out["envelope"]
    assert env is not None and env["is_error"] is False
    brief = json.loads(env["result"]) if isinstance(env["result"], str) else env["result"]
    assert all(k in brief for k in ("objective", "context", "actors", "scope",
                                    "assumptions", "open_questions", "constraints"))
