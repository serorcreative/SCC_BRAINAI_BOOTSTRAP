"""Infrastructure de **résolution de capacités** (EPISTEMIC-PROVENANCE / Capability Registry, J1).

Couche d'infrastructure — **seul endroit** qui connaît un **nom de fournisseur** (``claude_code``) et importe
les adaptateurs concrets (``ClaudeCode*Adapter``). ``composition`` **demande une capacité** et reçoit une
implémentation invocable **sans jamais connaître le fournisseur** ; ``builder/*`` ne connaît que le Protocol.

On **réutilise le registre existant** (``AgentRegistry`` / ``CapabilityResolver`` / ``AdapterRegistry``) : les
capacités sont déclarées comme **descriptors** (capacité → fournisseur, + ``cost`` = point d'ancrage du budget
J2, **non exécuté ici**), et un **binder** ``(fournisseur, capacité) → fabrique`` fournit l'adaptateur. Changer
le fournisseur d'un descriptor **substitue** l'implémentation sans toucher ``composition`` ni ``builder``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from scc_brainai_bootstrap.builder.brainai import Capabilities
from scc_brainai_bootstrap.builder.build import ClaudeCodeBuildAdapter
from scc_brainai_bootstrap.builder.conversation import ClaudeCodeConversationAdapter
from scc_brainai_bootstrap.builder.specification import ClaudeCodeSpecificationAdapter
from scc_brainai_bootstrap.builder.understanding import ClaudeCodeUnderstandingAdapter
from scc_brainai_bootstrap.core.config import BrainAIConfig
from scc_brainai_bootstrap.registry import AdapterRegistry, AgentDescriptor, AgentRegistry
from scc_brainai_bootstrap.registry.adapter import CapabilityResolver
from scc_brainai_bootstrap.registry.descriptor import AgentState
from scc_brainai_bootstrap.registry.sources import DescriptorSource

# Slugs de capacité (``domaine.action``) — vocabulaire du contrat de capacités.
UNDERSTAND_NEED = "understand.need"
SPECIFY = "specify.product"
BUILD_SOFTWARE = "build.software"
CONVERSE = "converse.dialogue"
CAPABILITY_SLUGS = (UNDERSTAND_NEED, SPECIFY, BUILD_SOFTWARE, CONVERSE)

# Fournisseur actuel (seule occurrence du slug dans tout le chemin produit).
CLAUDE_CODE = "claude_code"

# Ordre des capacités → champ de :class:`Capabilities`.
_CAPABILITY_TO_FIELD = {UNDERSTAND_NEED: "understanding", SPECIFY: "specification",
                        BUILD_SOFTWARE: "build", CONVERSE: "conversation"}


def default_descriptors() -> List[AgentDescriptor]:
    """Descriptors minimaux J1 : 4 capacités → fournisseur ``claude_code``. ``cost`` reste **None** — **point
    d'ancrage** du budget de build (J2), jamais exécuté ici."""
    return [
        AgentDescriptor(id=f"brainai.{CLAUDE_CODE}.{slug.replace('.', '_')}", namespace="brainai",
                        name=f"{CLAUDE_CODE}:{slug}", capabilities=[slug], state=AgentState.ACTIVE,
                        provider=CLAUDE_CODE, availability="available", cost=None, priority=0)
        for slug in CAPABILITY_SLUGS
    ]


def default_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(fournisseur, capacité) → fabrique d'adaptateur``. Paramètres J1 inchangés (understanding/
    specification/build en haiku ; conversation en sonnet ; plafond par appel 0,50 $, timeout 180)."""
    return {
        (CLAUDE_CODE, UNDERSTAND_NEED): lambda: ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        (CLAUDE_CODE, SPECIFY): lambda: ClaudeCodeSpecificationAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        (CLAUDE_CODE, BUILD_SOFTWARE): lambda: ClaudeCodeBuildAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        (CLAUDE_CODE, CONVERSE): lambda: ClaudeCodeConversationAdapter(model="sonnet", max_budget_usd=0.50, timeout=180),
    }


class _StaticSource(DescriptorSource):
    """Source **en mémoire** de descriptors — point d'extension prévu du registre (aucun nouveau registre)."""

    name = "brainai-capabilities"

    def __init__(self, descriptors: List[AgentDescriptor]):
        self._descriptors = list(descriptors)

    def descriptors(self) -> List[AgentDescriptor]:
        return list(self._descriptors)


def resolve_capability(slug: str, descriptors: List[AgentDescriptor],
                       binders: Dict[Tuple[str, str], Callable[[], Any]]) -> Any:
    """Résout une **capacité** vers une implémentation invocable, **via le registre** (``CapabilityResolver``),
    sans que l'appelant connaisse le fournisseur. Le binder est choisi par ``(descriptor.provider, slug)`` :
    changer le ``provider`` du descriptor substitue l'implémentation."""
    registry = AgentRegistry(BrainAIConfig(), sources=[_StaticSource(descriptors)])
    registry.load()
    adapters = AdapterRegistry()
    for desc in descriptors:
        cap = desc.capabilities[0]
        binder = binders.get((desc.provider, cap))
        if binder is not None:
            adapters.register(desc.id, binder)
    resolution = CapabilityResolver(registry, adapters).resolve(slug)
    selected = resolution.get("selected")
    if not selected:
        raise LookupError(f"capacité non résolue : {slug!r} (aucun fournisseur disponible)")
    impl = adapters.adapter_for(registry.get(selected)).bind()
    if impl is None:
        raise LookupError(f"capacité {slug!r} résolue mais non liable (binder absent)")
    return impl


def resolve_capabilities(descriptors: List[AgentDescriptor],
                         binders: Dict[Tuple[str, str], Callable[[], Any]]) -> Capabilities:
    """Assemble les :class:`Capabilities` du chemin produit en **résolvant** chaque capacité (aucun nom de
    fournisseur ici : tout vient des descriptors/binder)."""
    resolved = {_CAPABILITY_TO_FIELD[slug]: resolve_capability(slug, descriptors, binders)
                for slug in CAPABILITY_SLUGS}
    return Capabilities(**resolved)


def real_capabilities() -> Capabilities:
    """Capacités **réelles** (facturables) du chemin produit, obtenues par résolution de capacités."""
    return resolve_capabilities(default_descriptors(), default_binders())


__all__ = ["UNDERSTAND_NEED", "SPECIFY", "BUILD_SOFTWARE", "CONVERSE", "CAPABILITY_SLUGS", "CLAUDE_CODE",
           "default_descriptors", "default_binders", "resolve_capability", "resolve_capabilities",
           "real_capabilities"]
