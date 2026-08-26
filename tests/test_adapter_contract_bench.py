"""Banc **Étage 1** — contrat d'adaptateur, **déterministe, 0 $**. JALON 3 T2.

Vérifie : rejet **structurel** d'une déclaration incomplète ; **conformité des 6 adaptateurs** existants ; canaux
auth/entrants explicites (RV-2) ; coût ``real``/``unavailable`` jamais fabriqué (I6) ; nature du plafond fournisseur
déclarée honnêtement (RS-039 : jamais « hard » quand ce n'est qu'un arrêt agrégé) ; confinement déclaré ; I9 (jamais
la Pursuit entière dans un canal) ; **AM6** (le test valide un principe, pas une techno) ; budget gouverné (RS-047).
"""

from __future__ import annotations

import pytest

from scc_brainai_bootstrap.builder.adapter_contract import (
    AdapterContract, IncompleteContractError, is_conformant, require_contract, validate_contract)
from scc_brainai_bootstrap.builder.build import ClaudeCodeBuildAdapter
from scc_brainai_bootstrap.builder.conversation import ClaudeCodeConversationAdapter
from scc_brainai_bootstrap.builder.site import ClaudeCodeSiteAdapter
from scc_brainai_bootstrap.builder.specification import ClaudeCodeSpecificationAdapter
from scc_brainai_bootstrap.builder.understanding import ClaudeCodeUnderstandingAdapter
from brainai_app.delivery.preview_capability import LocalPreviewAdapter

ALL_ADAPTERS = [
    ClaudeCodeUnderstandingAdapter(), ClaudeCodeSpecificationAdapter(), ClaudeCodeBuildAdapter(),
    ClaudeCodeConversationAdapter(), ClaudeCodeSiteAdapter(), LocalPreviewAdapter(),
]


# --------------------------------------------------------------------- #
# Rejet structurel d'une déclaration incomplète
# --------------------------------------------------------------------- #
def test_adapter_without_contract_is_rejected():
    class _NoContract:
        name = "sans_contrat"
    with pytest.raises(IncompleteContractError):
        require_contract(_NoContract())


def test_incomplete_declaration_is_rejected():
    class _Incomplete:
        name = "incomplet"
        def contract(self):
            return {"capabilities_served": ["x"]}          # tout le reste manque
    errs = validate_contract(_Incomplete().contract())
    assert errs                                            # non vide → rejeté
    with pytest.raises(IncompleteContractError):
        require_contract(_Incomplete())
    assert is_conformant(_Incomplete()) is False


def test_fabricated_cost_is_rejected():
    """I6 : un contrat déclarant un coût **fabriqué** est structurellement rejeté."""
    c = {"capabilities_served": ["x"], "auth_channel": {"kind": "k", "explicit": True, "leaks_identity": False},
         "inbound_channels": [], "cost_report": {"mode": "real_from_envelope", "fabricated": True},
         "native_budget": {"usd_cap": "aggregate_stop", "call_cap": "enforced_by_brainai"},
         "confinement": {"workspace": True, "tools_allowed": [], "tools_disallowed": [], "permission_mode": "d"}}
    errs = validate_contract(c)
    assert any("I6" in e or "fabricated" in e for e in errs)


def test_whole_pursuit_channel_is_rejected():
    """I9 : un canal entrant portant la Pursuit entière est rejeté."""
    c = {"capabilities_served": ["x"], "auth_channel": {"kind": "k", "explicit": True, "leaks_identity": False},
         "inbound_channels": [{"channel": "x", "pursuit_scoped": True, "carries_whole_pursuit": True}],
         "cost_report": {"mode": "real_from_envelope", "fabricated": False},
         "native_budget": {"usd_cap": "aggregate_stop", "call_cap": "enforced_by_brainai"},
         "confinement": {"workspace": True, "tools_allowed": [], "tools_disallowed": [], "permission_mode": "d"}}
    assert any("I9" in e for e in validate_contract(c))


def test_bad_native_budget_kind_rejected():
    c = {"capabilities_served": ["x"], "auth_channel": {"kind": "k", "explicit": True, "leaks_identity": False},
         "inbound_channels": [], "cost_report": {"mode": "real_from_envelope", "fabricated": False},
         "native_budget": {"usd_cap": "magique", "call_cap": "enforced_by_brainai"},
         "confinement": {"workspace": True, "tools_allowed": [], "tools_disallowed": [], "permission_mode": "d"}}
    assert any("native_budget" in e for e in validate_contract(c))


# --------------------------------------------------------------------- #
# Conformité des 6 adaptateurs existants
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.capability)
def test_existing_adapters_are_conformant(adapter):
    assert is_conformant(adapter) is True
    contract = require_contract(adapter)                   # ne lève pas
    assert validate_contract(contract) == []


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.capability)
def test_each_adapter_declares_auth_and_inbound(adapter):
    c = require_contract(adapter).to_dict()
    assert "kind" in c["auth_channel"] and isinstance(c["auth_channel"]["leaks_identity"], bool)
    assert isinstance(c["inbound_channels"], list)         # RV-2 étendue déclarée (peut être vide pour la preview)


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.capability)
def test_cost_report_never_fabricated(adapter):
    assert require_contract(adapter).to_dict()["cost_report"]["fabricated"] is False   # I6


def test_provider_adapters_declare_usd_cap_honestly_not_hard():
    """RS-039 : les adaptateurs Claude déclarent ``aggregate_stop`` (arrêt agrégé), **jamais** ``hard`` — le plafond
    dur est le **compteur d'appels**, pas le plafond USD."""
    for adapter in ALL_ADAPTERS[:5]:                       # les 5 adaptateurs fournisseur (pas la preview locale)
        nb = require_contract(adapter).to_dict()["native_budget"]
        assert nb["usd_cap"] == "aggregate_stop"           # honnête : pas « hard »
        assert nb["call_cap"] == "enforced_by_brainai"


def test_preview_is_local_surface_no_provider_auth():
    c = require_contract(LocalPreviewAdapter()).to_dict()
    assert c["auth_channel"]["kind"] == "none" and c["cost_report"]["mode"] == "unavailable"


def test_conversation_history_is_pursuit_scoped_i9():
    c = require_contract(ClaudeCodeConversationAdapter()).to_dict()
    hist = [ch for ch in c["inbound_channels"] if "history" in ch.get("channel", "")]
    assert hist and hist[0]["pursuit_scoped"] is True and hist[0].get("carries_whole_pursuit") is False


def test_site_declares_write_tool_confinement():
    c = require_contract(ClaudeCodeSiteAdapter()).to_dict()["confinement"]
    assert "Write" in c["tools_allowed"] and "Bash" in c["tools_disallowed"]
    assert c["permission_mode"] == "acceptEdits" and c["workspace"] is True


def test_text_adapters_disallow_all_file_tools():
    for adapter in (ClaudeCodeUnderstandingAdapter(), ClaudeCodeSpecificationAdapter(),
                    ClaudeCodeBuildAdapter(), ClaudeCodeConversationAdapter()):
        conf = require_contract(adapter).to_dict()["confinement"]
        assert conf["tools_allowed"] == [] and "Write" in conf["tools_disallowed"]


# --------------------------------------------------------------------- #
# AM6 — le contrat valide un PRINCIPE, pas une technologie
# --------------------------------------------------------------------- #
def test_contract_is_technology_independent():
    """Un adaptateur **hypothétique** d'un autre fournisseur (clé API, OAuth de service…) passe le contrat dès lors
    qu'il déclare *auth explicite + canaux + coût honnête + confinement* — le validateur n'impose aucune techno."""
    other = AdapterContract(
        capabilities_served=("some.capability",),
        auth_channel={"kind": "api_key", "explicit": True, "leaks_identity": False},
        inbound_channels=({"channel": "http:body", "carries": "mission bornée", "pursuit_scoped": True},),
        cost_report={"mode": "real_from_envelope", "fabricated": False},
        native_budget={"usd_cap": "hard", "call_cap": "enforced_by_brainai"},   # un fournisseur PEUT offrir un dur
        confinement={"workspace": True, "tools_allowed": [], "tools_disallowed": [], "permission_mode": "sandbox"})
    assert validate_contract(other) == []                  # techno différente, contrat valide


# --------------------------------------------------------------------- #
# RS-047 — budget de livraison gouverné (plus de constante câblée)
# --------------------------------------------------------------------- #
def test_delivery_budget_default_and_source(monkeypatch):
    from brainai_app.delivery import budget_config as bc
    monkeypatch.delenv(bc.ENV_CEILING, raising=False)
    monkeypatch.delenv(bc.ENV_MAX_CALLS, raising=False)
    cfg = bc.load_delivery_budget()
    assert cfg.ceiling_usd == bc.DEFAULT_CEILING_USD and cfg.max_calls == bc.DEFAULT_MAX_CALLS
    assert cfg.ceiling_source == "default" and cfg.max_calls_source == "default"
    assert cfg.call_guarantee == "hard" and cfg.usd_guarantee == "best_effort_bounded"   # RS-039 honnête


def test_delivery_budget_env_override(monkeypatch):
    from brainai_app.delivery import budget_config as bc
    monkeypatch.setenv(bc.ENV_MAX_CALLS, "1")
    monkeypatch.setenv(bc.ENV_CEILING, "1.5")
    cfg = bc.load_delivery_budget()
    assert cfg.max_calls == 1 and cfg.max_calls_source == "env"
    assert cfg.ceiling_usd == 1.5 and cfg.ceiling_source == "env"


def test_real_path_enforces_contract_conformance():
    """Le chemin produit réel ne rend que des adaptateurs **conformes** (rejet structurel intégré)."""
    from brainai_app import providers
    caps = providers.real_capabilities()
    for a in (caps.understanding, caps.specification, caps.build, caps.conversation):
        assert is_conformant(a)
    delivery = providers.real_delivery()
    assert is_conformant(delivery.site_build) and is_conformant(delivery.preview)


def test_resolve_capabilities_rejects_nonconformant_binder():
    """Rejet **structurel** : un binder liant un adaptateur sans contrat fait échouer la résolution du chemin produit."""
    from brainai_app import providers
    descriptors = providers.default_descriptors()
    binders = dict(providers.default_binders())
    binders[(providers.CLAUDE_CODE, providers.UNDERSTAND_NEED)] = lambda: object()   # sans contract()
    with pytest.raises(IncompleteContractError):
        providers.resolve_capabilities(descriptors, binders)


def test_delivery_budget_env_ceiling_capped_to_safety(monkeypatch):
    """Une valeur env ne peut pas dépasser le plafond de sûreté (défaut) sans acte explicite."""
    from brainai_app.delivery import budget_config as bc
    monkeypatch.setenv(bc.ENV_CEILING, "999")
    cfg = bc.load_delivery_budget()
    assert cfg.ceiling_usd == bc.DEFAULT_CEILING_USD       # borné
    # un plafond explicite plus haut est respecté mais tracé
    cfg2 = bc.load_delivery_budget(ceiling_usd=5.0)
    assert cfg2.ceiling_usd == 5.0 and cfg2.ceiling_source == "explicit"
