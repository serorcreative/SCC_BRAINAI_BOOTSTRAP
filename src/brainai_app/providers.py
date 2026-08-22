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

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

from scc_brainai_bootstrap.builder.adapter_contract import require_contract
from scc_brainai_bootstrap.builder.brainai import Capabilities
from scc_brainai_bootstrap.builder.build import ClaudeCodeBuildAdapter
from scc_brainai_bootstrap.builder.conversation import ClaudeCodeConversationAdapter
from scc_brainai_bootstrap.builder.site import ClaudeCodeSiteAdapter
from scc_brainai_bootstrap.builder.specification import ClaudeCodeSpecificationAdapter
from scc_brainai_bootstrap.builder.understanding import ClaudeCodeUnderstandingAdapter
from scc_brainai_bootstrap.core.config import BrainAIConfig
from brainai_app.delivery.preview_capability import LocalPreviewAdapter
from brainai_app.delivery.watchdog_config import load_call_watchdog
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

# Capacités de **livraison** (J2) — build réel d'un site + preview locale substituable.
BUILD_SITE = "build.site"
PREVIEW_LOCAL = "preview.local"
# Capacité **différée** (jamais réalisée en J2) — le déploiement public est consigné RS-2/J3+ (RS-041).
DEPLOY_PUBLIC = "deploy.public"

# Fournisseur actuel (seule occurrence du slug dans tout le chemin produit).
CLAUDE_CODE = "claude_code"
# Fournisseur de preview locale (surface loopback interne, distincte du fournisseur de cognition).
LOCAL_LOOPBACK = "local_loopback"

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
    """Binder ``(fournisseur, capacité) → fabrique d'adaptateur``. Understanding/specification/build en haiku ;
    conversation en sonnet ; plafond par appel 0,50 $. Le **timeout** n'est plus le cutoff cognitif figé (180 s) :
    c'est le **watchdog de sécurité gouverné** (``watchdog_config`` : défaut 3600 s / env / explicite) — un fusible
    anti-zombie, jamais une limite de réflexion (RS-059 = vraie distinction activité/blocage à venir)."""
    wd = load_call_watchdog().timeout_s
    return {
        (CLAUDE_CODE, UNDERSTAND_NEED): lambda: ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50, timeout=wd),
        (CLAUDE_CODE, SPECIFY): lambda: ClaudeCodeSpecificationAdapter(model="haiku", max_budget_usd=0.50, timeout=wd),
        (CLAUDE_CODE, BUILD_SOFTWARE): lambda: ClaudeCodeBuildAdapter(model="haiku", max_budget_usd=0.50, timeout=wd),
        (CLAUDE_CODE, CONVERSE): lambda: ClaudeCodeConversationAdapter(model="sonnet", max_budget_usd=0.50, timeout=wd),
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
    fournisseur ici : tout vient des descriptors/binder). **Rejet structurel** (T2) : tout adaptateur résolu dont le
    contrat est incomplet est refusé via ``require_contract`` (aucune capacité non déclarée sur le chemin produit)."""
    resolved: Dict[str, Any] = {}
    for slug in CAPABILITY_SLUGS:
        impl = resolve_capability(slug, descriptors, binders)
        require_contract(impl)                              # contrat d'adaptateur complet exigé (T2)
        resolved[_CAPABILITY_TO_FIELD[slug]] = impl
    return Capabilities(**resolved)


def real_capabilities() -> Capabilities:
    """Capacités **réelles** (facturables) du chemin produit, obtenues par résolution de capacités."""
    return resolve_capabilities(default_descriptors(), default_binders())


# --------------------------------------------------------------------- #
# Capacités de LIVRAISON (J2) — build réel de site + preview locale, résolues via le MÊME registre
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class DeliveryCapabilities:
    """Capacités de la **livraison réelle** (post-``realize``), résolues par le registre (jamais câblées dans la
    logique métier) : ``site_build`` (le fournisseur écrit de vrais fichiers) et ``preview`` (surface locale
    substituable). ``deploy.public`` reste **différé** (RS-2/J3+) — non résolu ici."""

    site_build: Any
    preview: Any


def delivery_descriptors() -> List[AgentDescriptor]:
    """Descriptors de livraison : ``build.site`` → ``claude_code`` ; ``preview.local`` → ``local_loopback``.
    ``cost`` reste **None** (le budget réel vit dans le ``BudgetLedger`` du run, pas dans le descriptor)."""
    return [
        AgentDescriptor(id=f"brainai.{CLAUDE_CODE}.{BUILD_SITE.replace('.', '_')}", namespace="brainai",
                        name=f"{CLAUDE_CODE}:{BUILD_SITE}", capabilities=[BUILD_SITE], state=AgentState.ACTIVE,
                        provider=CLAUDE_CODE, availability="available", cost=None, priority=0),
        AgentDescriptor(id=f"brainai.{LOCAL_LOOPBACK}.{PREVIEW_LOCAL.replace('.', '_')}", namespace="brainai",
                        name=f"{LOCAL_LOOPBACK}:{PREVIEW_LOCAL}", capabilities=[PREVIEW_LOCAL],
                        state=AgentState.ACTIVE, provider=LOCAL_LOOPBACK, availability="available",
                        cost=None, priority=0),
    ]


def deferred_deploy_public_descriptor() -> AgentDescriptor:
    """Descriptor **différé** du déploiement public (Q4 : différé RS-2/J3+). Déclaré ``availability=unavailable``
    et non lié : il **prouve** que la capacité ``deploy.public`` pourra un jour **remplacer** ``preview.local``
    par simple résolution — **sans** être réalisée en J2 (aucun déploiement public réel)."""
    return AgentDescriptor(id=f"brainai.public.{DEPLOY_PUBLIC.replace('.', '_')}", namespace="brainai",
                           name=f"public:{DEPLOY_PUBLIC}", capabilities=[DEPLOY_PUBLIC],
                           state=AgentState.PROPOSED, provider="public", availability="unavailable",
                           cost=None, priority=0)


def delivery_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(fournisseur, capacité) → fabrique`` pour la livraison. Site en **haiku** par défaut (plafond par
    appel 0,50 $ ; **watchdog de sécurité gouverné**, pas un cutoff cognitif) ; preview locale sans coût.
    Substituable : changer la fabrique substitue l'impl."""
    wd = load_call_watchdog().timeout_s          # watchdog de sécurité gouverné (défaut 3600 s), pas un cutoff cognitif
    return {
        (CLAUDE_CODE, BUILD_SITE): lambda: ClaudeCodeSiteAdapter(model="haiku", max_budget_usd=0.50, timeout=wd),
        (LOCAL_LOOPBACK, PREVIEW_LOCAL): lambda: LocalPreviewAdapter(),
    }


def resolve_delivery(descriptors: List[AgentDescriptor],
                     binders: Dict[Tuple[str, str], Callable[[], Any]]) -> DeliveryCapabilities:
    """Résout les capacités de livraison **via le registre** (aucun fournisseur connu de l'appelant). **Rejet
    structurel** (T2) des adaptateurs à contrat incomplet via ``require_contract``."""
    site_build = resolve_capability(BUILD_SITE, descriptors, binders)
    preview = resolve_capability(PREVIEW_LOCAL, descriptors, binders)
    require_contract(site_build)
    require_contract(preview)
    return DeliveryCapabilities(site_build=site_build, preview=preview)


def real_delivery() -> DeliveryCapabilities:
    """Capacités de livraison **réelles** (site facturable + preview locale), par résolution de capacités."""
    return resolve_delivery(delivery_descriptors(), delivery_binders())


__all__ = ["UNDERSTAND_NEED", "SPECIFY", "BUILD_SOFTWARE", "CONVERSE", "CAPABILITY_SLUGS", "CLAUDE_CODE",
           "BUILD_SITE", "PREVIEW_LOCAL", "DEPLOY_PUBLIC", "LOCAL_LOOPBACK",
           "default_descriptors", "default_binders", "resolve_capability", "resolve_capabilities",
           "real_capabilities", "DeliveryCapabilities", "delivery_descriptors", "delivery_binders",
           "deferred_deploy_public_descriptor", "resolve_delivery", "real_delivery"]
