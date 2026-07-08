"""Tests unitaires du registre d'agents déclaratif & orienté capacités."""

from __future__ import annotations

import json

import pytest

from scc_brainai_bootstrap.core.config import load_config
from scc_brainai_bootstrap.registry import (
    AdapterRegistry,
    AgentDescriptor,
    AgentRegistry,
    AgentState,
    CapabilityResolver,
    ManifestSource,
    capability_domain,
    invalid_capabilities,
    is_valid_capability,
)


# --------------------------------------------------------------------- #
# Capacités (validation légère du format, vocabulaire ouvert)
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("slug", [
    "memory.recall", "learning.analyze", "planning.propose",
    "vision.describe", "security.audit", "github.pull-request", "a.b.c",
])
def test_valid_capabilities(slug):
    assert is_valid_capability(slug)


@pytest.mark.parametrize("slug", [
    "memory", "Memory.Recall", "memory.", ".recall", "memory recall", "", None, 42,
])
def test_invalid_capabilities(slug):
    assert not is_valid_capability(slug)


def test_capability_domain_and_report():
    assert capability_domain("vision.describe") == "vision"
    assert invalid_capabilities(["ok.slug", "BAD", "memory.recall"]) == ["BAD"]


# --------------------------------------------------------------------- #
# Descripteur (données pures, déterminisme, forward-compatibilité)
# --------------------------------------------------------------------- #
def test_descriptor_generates_id_and_hash():
    d = AgentDescriptor(name="X", role="r", capabilities=["b.y", "a.x"]).finalize("2026-07-06T00:00:00+00:00")
    assert d.id.startswith("agent_") and d.id_generated
    assert d.hash
    assert d.capabilities == ["a.x", "b.y"]           # trié


def test_descriptor_declared_id_preserved():
    d = AgentDescriptor(id="brainai-x").finalize()
    assert d.id == "brainai-x" and d.id_generated is False


def test_descriptor_roundtrip_and_extra_absorbs_unknown():
    d = AgentDescriptor.from_dict({"id": "z", "capabilities": ["a.b"],
                                   "future_field": {"k": 1}})
    assert d.extra["future_field"] == {"k": 1}         # schéma futur préservé
    d2 = AgentDescriptor.from_dict(d.to_dict())
    assert d2.extra["future_field"] == {"k": 1}


def test_descriptor_hash_stable_ignores_source():
    a = AgentDescriptor(id="x", capabilities=["a.b"], source="fiche:1.md").finalize()
    b = AgentDescriptor(id="x", capabilities=["a.b"], source="manifest:2.json").finalize()
    assert a.hash == b.hash                            # provenance hors empreinte


# --------------------------------------------------------------------- #
# Sources & registre
# --------------------------------------------------------------------- #
class _StaticSource:
    def __init__(self, descs):
        self._descs = descs

    def descriptors(self):
        return list(self._descs)


def _registry(*descs):
    cfg = load_config()
    return AgentRegistry(cfg, sources=[_StaticSource(list(descs))]).load()


def test_manifest_source_loads_cognitive_agents():
    cfg = load_config()
    src = ManifestSource(cfg.agents_registry_dir, name="brainai")
    ids = {d.id for d in src.descriptors()}
    assert {"brainai-memory", "brainai-learning", "brainai-planning",
            "brainai-decision", "brainai-execution"} <= ids


def test_registry_indexes_by_capability_many_to_many():
    reg = _registry(
        AgentDescriptor(id="p1", capabilities=["vision.describe"], state=AgentState.ACTIVE),
        AgentDescriptor(id="p2", capabilities=["vision.describe"], state=AgentState.ACTIVE),
        AgentDescriptor(id="m", capabilities=["memory.recall"], state=AgentState.ACTIVE),
    )
    providers = reg.by_capability("vision.describe")
    assert {d.id for d in providers} == {"p1", "p2"}   # 1 capacité → N agents
    assert reg.capabilities()["vision.describe"] == ["p1", "p2"]


def test_registry_by_capability_prefers_priority_then_reliability():
    reg = _registry(
        AgentDescriptor(id="low", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=1),
        AgentDescriptor(id="high", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=9),
        AgentDescriptor(id="mid", capabilities=["vision.describe"], state=AgentState.ACTIVE,
                        priority=5, reliability=0.9),
    )
    order = [d.id for d in reg.by_capability("vision.describe")]
    assert order == ["high", "mid", "low"]


def test_registry_active_only_filter():
    reg = _registry(
        AgentDescriptor(id="on", capabilities=["x.y"], state=AgentState.ACTIVE),
        AgentDescriptor(id="off", capabilities=["x.y"], state=AgentState.DEPRECATED),
    )
    assert [d.id for d in reg.by_capability("x.y")] == ["on"]
    assert [d.id for d in reg.by_capability("x.y", active_only=False)] == ["off", "on"]


def test_registry_light_capability_guard_non_blocking():
    reg = _registry(AgentDescriptor(id="bad", capabilities=["NOTVALID"], state=AgentState.ACTIVE))
    assert reg.get("bad") is not None                  # non bloquant : l'agent existe
    assert reg.malformed and reg.malformed[0]["agent"] == "bad"
    assert reg.audit()["ok"] is False


# --------------------------------------------------------------------- #
# Gouvernance (cycle de vie)
# --------------------------------------------------------------------- #
def test_governance_activate_and_guarded_transitions():
    reg = _registry(AgentDescriptor(id="a", state=AgentState.PROPOSED))
    assert reg.transition("a", AgentState.ACTIVE, "frederique")["ok"] is True
    assert reg.get("a").state == AgentState.ACTIVE
    # transition interdite active → proposed
    assert reg.transition("a", AgentState.PROPOSED, "frederique")["ok"] is False
    # approbateur requis
    reg2 = _registry(AgentDescriptor(id="b", state=AgentState.PROPOSED))
    assert reg2.transition("b", AgentState.ACTIVE, "")["ok"] is False


def test_governance_retired_is_terminal():
    reg = _registry(AgentDescriptor(id="a", state=AgentState.ACTIVE))
    assert reg.transition("a", AgentState.RETIRED, "frederique")["ok"] is True
    assert reg.transition("a", AgentState.ACTIVE, "frederique")["ok"] is False


# --------------------------------------------------------------------- #
# Adaptateurs & résolution (liaison paresseuse)
# --------------------------------------------------------------------- #
def test_adapter_binds_lazily():
    calls = []

    def binder():
        calls.append(1)
        return object()

    adapters = AdapterRegistry()
    adapters.register("x", binder)
    desc = AgentDescriptor(id="x", state=AgentState.ACTIVE).finalize()
    adapter = adapters.adapter_for(desc)
    assert calls == []                                 # rien n'est chargé à la création
    assert adapter.available() is True
    assert calls == [1]                                # chargé à la première liaison


def test_adapter_unavailable_when_binder_returns_none():
    adapters = AdapterRegistry()
    adapters.register("x", lambda: None)
    desc = AgentDescriptor(id="x").finalize()
    assert adapters.adapter_for(desc).available() is False


def test_resolver_selects_highest_priority_available():
    reg = _registry(
        AgentDescriptor(id="gpt", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=1),
        AgentDescriptor(id="gemini", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=9),
        AgentDescriptor(id="claude", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=5),
    )
    adapters = AdapterRegistry()
    for aid in ("gpt", "gemini", "claude"):
        adapters.register(aid, lambda: object())
    resolver = CapabilityResolver(reg, adapters)
    result = resolver.resolve("vision.describe")
    assert result["selected"] == "gemini"              # priorité la plus haute
    assert result["provider_count"] == 3
    assert result["resolved"] is True


def test_resolver_skips_unavailable_provider():
    reg = _registry(
        AgentDescriptor(id="preferred", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=9),
        AgentDescriptor(id="fallback", capabilities=["vision.describe"], state=AgentState.ACTIVE, priority=1),
    )
    adapters = AdapterRegistry()
    adapters.register("preferred", lambda: None)       # indisponible
    adapters.register("fallback", lambda: object())
    result = CapabilityResolver(reg, adapters).resolve("vision.describe")
    assert result["selected"] == "fallback"            # bascule vers le disponible


def test_resolver_no_provider():
    result = CapabilityResolver(_registry(), AdapterRegistry()).resolve("nope.none")
    assert result["resolved"] is False and result["selected"] is None


def test_registry_deterministic_load():
    cfg = load_config()
    a = AgentRegistry(cfg, sources=[ManifestSource(cfg.agents_registry_dir)]).load()
    b = AgentRegistry(cfg, sources=[ManifestSource(cfg.agents_registry_dir)]).load()
    da = json.dumps([d.to_dict() for d in a.all()], sort_keys=True)
    db = json.dumps([d.to_dict() for d in b.all()], sort_keys=True)
    assert da == db
