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

from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from scc_brainai_bootstrap.builder.adapter_contract import require_contract
from scc_brainai_bootstrap.builder.brainai import Capabilities
from scc_brainai_bootstrap.builder.solution_architecture import (
    ClaudeCodeArchitectureAdapter, SolutionArchitectureCapability)
from scc_brainai_bootstrap.builder.build import ClaudeCodeBuildAdapter
from scc_brainai_bootstrap.builder.conversation import ClaudeCodeConversationAdapter
from scc_brainai_bootstrap.builder.gemini_understanding import GeminiUnderstandingAdapter
from scc_brainai_bootstrap.builder.openai_understanding import OpenAIUnderstandingAdapter
from scc_brainai_bootstrap.builder.site import ClaudeCodeSiteAdapter
from scc_brainai_bootstrap.builder.local_site import LocalDeterministicSiteAdapter, PROVIDER_NAME as LOCAL_BUILDER
from scc_brainai_bootstrap.builder.git_read import (
    LocalGitReadAdapter, GitReadHandle, PROVIDER_NAME as LOCAL_GIT,
    GIT_STATUS, GIT_DIFF, GIT_BRANCHES, GIT_READ_CAPABILITIES)
from scc_brainai_bootstrap.builder.git_write import (
    LocalGitWriteAdapter, GitWriteHandle,
    GIT_BRANCH_CREATE, GIT_COMMIT, GIT_WRITE_CAPABILITIES)
from scc_brainai_bootstrap.builder.specification import ClaudeCodeSpecificationAdapter
from scc_brainai_bootstrap.builder.understanding import ClaudeCodeUnderstandingAdapter
from scc_brainai_bootstrap.builder.observability_read import (
    LocalControlPlaneReadAdapter, ObservabilityReadHandle, PROVIDER_NAME as LOCAL_CONTROL_PLANE,
    OBS_HEALTH, OBSERVABILITY_READ_CAPABILITIES)
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
# 2ᵉ fournisseur de cognition **réel** (L6A) — interchangeable derrière la MÊME capacité (INV-PROVIDER-INTERCHANGEABLE).
OPENAI = "openai"
# 3ᵉ fournisseur de cognition **réel** (L6B) — même abstraction, même registre (INV-PROVIDER-INTERCHANGEABLE).
GEMINI = "gemini"
# Fournisseurs de cognition **admis** pour la sélection explicite (fail-closed hors de cet ensemble).
COGNITION_PROVIDERS = (CLAUDE_CODE, OPENAI, GEMINI)

# L9 — **BuildProviders** admis pour la capacité d'exécution ``build.site`` (construction réelle). ``claude_code``
# reste le **défaut historique** (inchangé) ; ``deterministic_local`` (:data:`LOCAL_BUILDER`) est un 2ᵉ exécutant
# **explicitement sélectionnable** (jamais un fallback automatique). Fail-closed hors de cet ensemble.
BUILD_PROVIDERS = (CLAUDE_CODE, LOCAL_BUILDER)

# L10.1 — GitReadProviders admis pour les capacités de LECTURE git (classe R). ``local_git`` : exécutant local
# déterministe (aucune remote, aucune credential ; network_required=false). Fail-closed hors de cet ensemble.
GIT_READ_PROVIDERS = (LOCAL_GIT,)

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


def real_capabilities(understanding_provider: Optional[str] = None, *,
                      understanding_providers: Optional[List[str]] = None,
                      arbitration_policy: Optional[Any] = None,
                      architecture: Optional[SolutionArchitectureCapability] = None) -> Capabilities:
    """Capacités **réelles** (facturables) du chemin produit, obtenues par résolution de capacités.

    Sélection EXPLICITE du/des fournisseur(s) de la capacité d'entrée ``understand.need`` — **un seul sélecteur à
    la fois** (fail-closed si les deux sont fournis, aucune priorité implicite) :
    - ``understanding_providers`` **absent** (``None``) ⇒ sélection **single** historique via
      ``understanding_provider`` (``None`` ⇒ défaut :data:`CLAUDE_CODE`, résolu **ici seulement**, I9 ;
      comportement **strictement inchangé**) ;
    - ``understanding_providers`` = **1 nom** ⇒ sélection **single explicite** de ce fournisseur (jamais remplacé
      par le défaut) ;
    - ``understanding_providers`` = **≥2 noms distincts admis** ⇒ **fan-out L7** : cohorte résolue, ``understanding``
      ancré sur le 1ᵉʳ membre, ``understanding_cohort`` renseignée, ``arbitration_policy`` optionnelle transmise ;
      ``specification``/``build``/``conversation`` restent ``claude_code``.
    Liste vide / doublon ⇒ ``ValueError`` ; fournisseur hors :data:`COGNITION_PROVIDERS` ⇒ ``LookupError`` — dans
    tous les cas **fail-closed** (aucune capacité construite)."""
    if understanding_provider is not None and understanding_providers is not None:
        raise ValueError("sélecteurs incompatibles : 'understanding_provider' (single) ET "
                         "'understanding_providers' (liste) fournis simultanément — un seul à la fois")
    # L8 — capacité architecture (``architect.solution``, provider-assistée) injectée dans TOUTES les capacités
    # réelles : le mode réel active le Cost Gate (Architecture → Estimate → GATE) ; la construction significative
    # reste gouvernée par le USER GO (frontière ``composition._deliver``). ``architecture`` INJECTABLE
    # (provider-neutral) ; ``None`` ⇒ défaut ``claude_code``. Contrat complet exigé (T2) ; le Protocol est revérifié
    # par ``Capabilities.__post_init__``. CONNECTER, PAS RECONSTRUIRE (L9 = généralisation ExecutionProvider).
    arch_cap = architecture if architecture is not None else \
        ClaudeCodeArchitectureAdapter(max_budget_usd=0.50, timeout=load_call_watchdog().timeout_s)
    require_contract(arch_cap)
    if understanding_providers is not None:
        provs = list(understanding_providers)
        if not provs:
            raise ValueError("understanding_providers vide (liste non vide requise)")
        if len(set(provs)) != len(provs):
            raise ValueError(f"understanding_providers contient des doublons : {provs!r}")
        if len(provs) == 1:
            understanding_provider = provs[0]                                    # single explicite (jamais défaut)
        else:
            cohort = resolve_understanding_cohort(provs)                         # fan-out L7 (fail-closed inclus)
            dd, db = default_descriptors(), default_binders()                    # autres capacités restent claude_code
            resolved: Dict[str, Any] = {"understanding": cohort[0]}             # ancre back-compat (1ᵉʳ membre)
            for slug in (SPECIFY, BUILD_SOFTWARE, CONVERSE):
                impl = resolve_capability(slug, dd, db)
                require_contract(impl)
                resolved[_CAPABILITY_TO_FIELD[slug]] = impl
            return Capabilities(understanding_cohort=cohort, arbitration_policy=arbitration_policy,
                                architecture=arch_cap, **resolved)
    # --- Chemin single-provider (historique). ``claude_code`` (défaut OU explicite) → chemin inchangé, JAMAIS
    #     capturé par le LookupError (la branche ``== CLAUDE_CODE`` précède la garde 'inconnu').
    if understanding_provider is None:
        understanding_provider = CLAUDE_CODE                                     # défaut résolu UNIQUEMENT ici (I9)
    if understanding_provider == CLAUDE_CODE:
        return replace(resolve_capabilities(default_descriptors(), default_binders()),
                       architecture=arch_cap)                                    # défaut/claude + L8 architecture
    if understanding_provider not in COGNITION_PROVIDERS:
        raise LookupError(f"fournisseur de cognition inconnu : {understanding_provider!r} "
                          f"(attendu ∈ {COGNITION_PROVIDERS})")
    dd, db = default_descriptors(), default_binders()                            # specification/build/conversation restent claude_code
    resolved = {"understanding": resolve_understanding(understanding_provider)}
    for slug in (SPECIFY, BUILD_SOFTWARE, CONVERSE):
        impl = resolve_capability(slug, dd, db)
        require_contract(impl)
        resolved[_CAPABILITY_TO_FIELD[slug]] = impl
    return Capabilities(architecture=arch_cap, **resolved)


# --------------------------------------------------------------------- #
# L6A — INTERCHANGEABILITÉ RÉELLE d'un fournisseur de cognition sur la capacité d'entrée
# (``understand.need``). Sélection EXPLICITE d'un provider derrière la MÊME capacité, via le MÊME registre —
# aucun fan-out / débat / vote / arbitrage / consensus (lot suivant). Le défaut reste ``claude_code`` (inchangé).
# --------------------------------------------------------------------- #
def understanding_descriptors(provider: str = CLAUDE_CODE) -> List[AgentDescriptor]:
    """Descriptor de la capacité ``understand.need`` pour un fournisseur **explicite** admis
    (:data:`COGNITION_PROVIDERS` : ``claude_code`` / ``openai`` / ``gemini``). Changer ``provider`` **substitue**
    l'implémentation par simple résolution (aucun code métier touché)."""
    return [
        AgentDescriptor(id=f"brainai.{provider}.{UNDERSTAND_NEED.replace('.', '_')}", namespace="brainai",
                        name=f"{provider}:{UNDERSTAND_NEED}", capabilities=[UNDERSTAND_NEED], state=AgentState.ACTIVE,
                        provider=provider, availability="available", cost=None, priority=0),
    ]


def understanding_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(fournisseur, understand.need) → fabrique`` pour les TROIS fournisseurs réels. Claude Code inchangé
    (haiku, plafond 0,50 $, watchdog gouverné). OpenAI / Gemini : modèle configurable (défaut adaptateur), même
    plafond d'appel **enforced_by_brainai**, client réel construit seulement à l'appel (clé lue via
    ``OPENAI_API_KEY`` / ``GEMINI_API_KEY`` respectivement)."""
    wd = load_call_watchdog().timeout_s
    return {
        (CLAUDE_CODE, UNDERSTAND_NEED): lambda: ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50, timeout=wd),
        (OPENAI, UNDERSTAND_NEED): lambda: OpenAIUnderstandingAdapter(max_budget_usd=0.50, timeout=wd),
        (GEMINI, UNDERSTAND_NEED): lambda: GeminiUnderstandingAdapter(max_budget_usd=0.50, timeout=wd),
    }


def resolve_understanding(provider: str = CLAUDE_CODE) -> Any:
    """Résout la capacité ``understand.need`` vers l'implémentation du **fournisseur explicite** demandé, via le
    registre (l'appelant ne connaît jamais le fournisseur). **Fail-closed** : un fournisseur hors
    :data:`COGNITION_PROVIDERS` est refusé sans résolution. Rejet structurel T2 (contrat complet) via
    ``require_contract``. Ne réalise **aucun** appel — retourne l'adaptateur invocable."""
    if provider not in COGNITION_PROVIDERS:
        raise LookupError(f"fournisseur de cognition inconnu : {provider!r} (attendu ∈ {COGNITION_PROVIDERS})")
    impl = resolve_capability(UNDERSTAND_NEED, understanding_descriptors(provider), understanding_binders())
    require_contract(impl)                          # contrat d'adaptateur complet exigé (T2) — quel que soit le provider
    return impl


def resolve_understanding_cohort(providers: List[str]) -> Tuple[Any, ...]:
    """Résout une **cohorte** de fournisseurs ``understand.need`` (L7, fan-out) en **réutilisant** strictement
    :func:`resolve_understanding` pour chaque nom — **aucune nouvelle logique de provider**. Retourne les adaptateurs
    résolus **dans l'ordre demandé** (l'ordre n'induit aucune préférence : l'arbitrage est provider-neutral).
    **Fail-closed** : liste vide ⇒ ``ValueError`` ; doublon ⇒ ``ValueError`` ; fournisseur hors
    :data:`COGNITION_PROVIDERS` ⇒ ``LookupError`` (via :func:`resolve_understanding`)."""
    provs = list(providers)
    if not provs:
        raise ValueError("cohorte de cognition vide (au moins un fournisseur requis)")
    if len(set(provs)) != len(provs):
        raise ValueError(f"cohorte de cognition avec doublons : {provs!r}")
    return tuple(resolve_understanding(p) for p in provs)   # fail-closed par fournisseur (LookupError si inconnu)


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


# --------------------------------------------------------------------- #
# L9 — INTERCHANGEABILITÉ RÉELLE du **BuildProvider** (capacité d'exécution ``build.site``).
# Sélection EXPLICITE d'un exécutant derrière la MÊME capacité, via le MÊME registre — aucun fan-out, aucun
# fallback automatique. Le défaut reste ``claude_code`` (inchangé). Miroir strict de ``resolve_understanding`` (L6A).
# --------------------------------------------------------------------- #
def build_site_descriptors(provider: str = CLAUDE_CODE) -> List[AgentDescriptor]:
    """Descriptor de la capacité ``build.site`` pour un **BuildProvider explicite** admis
    (:data:`BUILD_PROVIDERS` : ``claude_code`` / ``deterministic_local``). Changer ``provider`` **substitue**
    l'exécutant par simple résolution (aucun code métier touché)."""
    return [
        AgentDescriptor(id=f"brainai.{provider}.{BUILD_SITE.replace('.', '_')}", namespace="brainai",
                        name=f"{provider}:{BUILD_SITE}", capabilities=[BUILD_SITE], state=AgentState.ACTIVE,
                        provider=provider, availability="available", cost=None, priority=0),
    ]


def build_site_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(BuildProvider, build.site) → fabrique`` pour les exécutants admis. ``claude_code`` : adaptateur
    Claude Code (haiku, plafond 0,50 $, watchdog gouverné) — **inchangé**. ``deterministic_local`` : exécutant
    local déterministe (aucun LLM/réseau/subprocess, coût ``unavailable``)."""
    wd = load_call_watchdog().timeout_s
    return {
        (CLAUDE_CODE, BUILD_SITE): lambda: ClaudeCodeSiteAdapter(model="haiku", max_budget_usd=0.50, timeout=wd),
        (LOCAL_BUILDER, BUILD_SITE): lambda: LocalDeterministicSiteAdapter(),
    }


def resolve_build_site(provider: str = CLAUDE_CODE) -> Any:
    """Résout la capacité ``build.site`` vers l'exécutant du **BuildProvider explicite** demandé, via le registre
    (l'appelant ne connaît jamais le provider). **Fail-closed** : un provider hors :data:`BUILD_PROVIDERS` est
    refusé **sans résolution** (``LookupError``) — **aucun fallback silencieux**. Rejet structurel T2 (contrat
    complet) via ``require_contract``. Ne réalise **aucune** construction : retourne l'adaptateur invocable."""
    if provider not in BUILD_PROVIDERS:
        raise LookupError(f"BuildProvider inconnu : {provider!r} (attendu ∈ {BUILD_PROVIDERS})")
    impl = resolve_capability(BUILD_SITE, build_site_descriptors(provider), build_site_binders())
    require_contract(impl)                          # contrat d'adaptateur complet exigé (T2) — quel que soit le provider
    return impl


def real_delivery(build_provider: Optional[str] = None) -> DeliveryCapabilities:
    """Capacités de livraison **réelles** (site + preview locale). ``build_provider`` = **sélecteur opaque** L9 du
    BuildProvider de ``build.site`` :
    - **absent** (``None``) ⇒ chemin **historique strictement inchangé** (défaut ``claude_code``) ;
    - **1 nom admis** ⇒ sélection **explicite** de cet exécutant (jamais remplacé, **aucun fallback**) ;
    - **nom hors** :data:`BUILD_PROVIDERS` ⇒ ``LookupError`` (fail-closed).
    La preview reste ``local_loopback`` dans tous les cas."""
    if build_provider is None:
        return resolve_delivery(delivery_descriptors(), delivery_binders())    # historique inchangé
    site_build = resolve_build_site(build_provider)                            # sélection explicite (fail-closed)
    preview = resolve_capability(PREVIEW_LOCAL, delivery_descriptors(), delivery_binders())
    require_contract(preview)
    return DeliveryCapabilities(site_build=site_build, preview=preview)


# --------------------------------------------------------------------- #
# L10.1 — Capacités Git en LECTURE SEULE (classe R). Résolution EXPLICITE via le MÊME registre (I9 : les noms
# d'exécutant ne vivent qu'ici). Aucune mutation, aucune remote. Miroir strict de ``resolve_build_site`` (L9).
# --------------------------------------------------------------------- #
def git_read_descriptors(provider: str = LOCAL_GIT, capability: str = GIT_STATUS) -> List[AgentDescriptor]:
    """Descriptor d'une capacité git-read (``git.status`` / ``git.diff`` / ``git.branches.list``) pour un
    GitReadProvider admis. Un descriptor = une capacité (résolution par ``(provider, capability)``)."""
    return [
        AgentDescriptor(id=f"brainai.{provider}.{capability.replace('.', '_')}", namespace="brainai",
                        name=f"{provider}:{capability}", capabilities=[capability], state=AgentState.ACTIVE,
                        provider=provider, availability="available", cost=None, priority=0),
    ]


def git_read_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(GitReadProvider, capacité) → fabrique`` pour les trois lectures git. ``local_git`` : exécutant
    local déterministe (aucun LLM/réseau/credential, coût ``unavailable``)."""
    return {
        (LOCAL_GIT, GIT_STATUS): lambda: LocalGitReadAdapter(),
        (LOCAL_GIT, GIT_DIFF): lambda: LocalGitReadAdapter(),
        (LOCAL_GIT, GIT_BRANCHES): lambda: LocalGitReadAdapter(),
    }


def resolve_git_read(capability: str, provider: str = LOCAL_GIT) -> GitReadHandle:
    """Résout une capacité git-read (classe R) et renvoie un :class:`~scc_brainai_bootstrap.builder.git_read.GitReadHandle`
    — **voie d'exécution publique unique** (F-6.1) : jamais l'adaptateur exécutable nu. **Fail-closed** : provider
    hors :data:`GIT_READ_PROVIDERS` **ou** capacité hors :data:`GIT_READ_CAPABILITIES` ⇒ ``LookupError`` (aucun
    fallback). Rejet structurel T2 via ``require_contract`` sur l'implémentation interne **avant** wrapping."""
    if provider not in GIT_READ_PROVIDERS:
        raise LookupError(f"GitReadProvider inconnu : {provider!r} (attendu ∈ {GIT_READ_PROVIDERS})")
    if capability not in GIT_READ_CAPABILITIES:
        raise LookupError(f"capacité git-read inconnue : {capability!r} (attendu ∈ {GIT_READ_CAPABILITIES})")
    impl = resolve_capability(capability, git_read_descriptors(provider, capability), git_read_binders())
    require_contract(impl)                          # T2 exigé AVANT wrapping (sur l'implémentation interne)
    return GitReadHandle(impl, capability)          # F-6.1 : voie publique = handle (read), jamais l'adaptateur nu


# --------------------------------------------------------------------- #
# L10.2 — Capacités Git en MUTATION LOCALE (classe M). Résolution EXPLICITE via le MÊME registre (I9 : les noms
# d'exécutant ne vivent qu'ici). Miroir strict de resolve_git_read (L10.1) ; provider unique local_git ; le handle
# renvoyé est la voie publique unique (F-6.1), le gate N2 vit dans produce_git_write (jamais contournable ici).
# --------------------------------------------------------------------- #
GIT_WRITE_PROVIDERS = (LOCAL_GIT,)


def git_write_descriptors(provider: str = LOCAL_GIT, capability: str = GIT_BRANCH_CREATE) -> List[AgentDescriptor]:
    """Descriptor d'une capacité git-write (``git.branch.create`` / ``git.commit``) pour un GitWriteProvider admis.
    Un descriptor = une capacité (résolution par ``(provider, capability)``)."""
    return [
        AgentDescriptor(id=f"brainai.{provider}.{capability.replace('.', '_')}", namespace="brainai",
                        name=f"{provider}:{capability}", capabilities=[capability], state=AgentState.ACTIVE,
                        provider=provider, availability="available", cost=None, priority=0),
    ]


def git_write_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(GitWriteProvider, capacité) → fabrique`` pour les deux mutations git locales. ``local_git`` :
    exécutant local déterministe (aucun LLM/réseau/credential ; gate N2 gouverne toute mutation dans le seam)."""
    return {
        (LOCAL_GIT, GIT_BRANCH_CREATE): lambda: LocalGitWriteAdapter(),
        (LOCAL_GIT, GIT_COMMIT): lambda: LocalGitWriteAdapter(),
    }


def resolve_git_write(capability: str, provider: str = LOCAL_GIT) -> GitWriteHandle:
    """Résout une capacité git-write (classe M) et renvoie un
    :class:`~scc_brainai_bootstrap.builder.git_write.GitWriteHandle` — **voie d'exécution publique unique** (F-6.1) :
    jamais l'adaptateur mutant nu. **Fail-closed** : provider hors :data:`GIT_WRITE_PROVIDERS` **ou** capacité hors
    :data:`GIT_WRITE_CAPABILITIES` ⇒ ``LookupError`` (aucun fallback). Rejet structurel T2 via ``require_contract``
    sur l'implémentation interne **avant** wrapping. Le gate N2 est appliqué dans ``produce_git_write`` (seam)."""
    if provider not in GIT_WRITE_PROVIDERS:
        raise LookupError(f"GitWriteProvider inconnu : {provider!r} (attendu ∈ {GIT_WRITE_PROVIDERS})")
    if capability not in GIT_WRITE_CAPABILITIES:
        raise LookupError(f"capacité git-write inconnue : {capability!r} (attendu ∈ {GIT_WRITE_CAPABILITIES})")
    impl = resolve_capability(capability, git_write_descriptors(provider, capability), git_write_binders())
    require_contract(impl)                          # T2 exigé AVANT wrapping (sur l'implémentation interne)
    return GitWriteHandle(impl, capability)          # F-6.1 : voie publique = handle (write), jamais l'adaptateur nu


# --------------------------------------------------------------------- #
# L10 (Variante MIN) — Capacité OBSERVABILITÉ en LECTURE SEULE (classe R). Résolution EXPLICITE via le MÊME
# registre (I9 : les noms d'exécutant ne vivent qu'ici). CONNECTER, PAS RECONSTRUIRE : consomme la façade
# existante 09_CONTROL_PLANE (INCHANGÉE). Miroir strict de resolve_git_read (L10.1). Aucune mutation, aucun réseau.
# --------------------------------------------------------------------- #
OBSERVABILITY_READ_PROVIDERS = (LOCAL_CONTROL_PLANE,)


def observability_read_descriptors(provider: str = LOCAL_CONTROL_PLANE, capability: str = OBS_HEALTH) -> List[AgentDescriptor]:
    """Descriptor de la capacité observability-read (``observability.health``) pour un provider admis. Un descriptor
    = une capacité (résolution par ``(provider, capability)``)."""
    return [
        AgentDescriptor(id=f"brainai.{provider}.{capability.replace('.', '_')}", namespace="brainai",
                        name=f"{provider}:{capability}", capabilities=[capability], state=AgentState.ACTIVE,
                        provider=provider, availability="available", cost=None, priority=0),
    ]


def observability_read_binders() -> Dict[Tuple[str, str], Callable[[], Any]]:
    """Binder ``(provider, capacité) → fabrique`` pour la lecture d'observabilité. ``local_control_plane`` :
    exécutant local déterministe (aucun LLM/réseau/credential ; façade ControlPlane, adaptateur INERTE)."""
    return {
        (LOCAL_CONTROL_PLANE, OBS_HEALTH): lambda: LocalControlPlaneReadAdapter(),
    }


def resolve_observability_read(capability: str, provider: str = LOCAL_CONTROL_PLANE) -> ObservabilityReadHandle:
    """Résout la capacité observability-read (classe R) et renvoie un ``ObservabilityReadHandle`` — voie d'exécution
    publique unique (F-6.1) : jamais l'adaptateur nu. Fail-closed : provider hors OBSERVABILITY_READ_PROVIDERS OU
    capacité hors OBSERVABILITY_READ_CAPABILITIES => LookupError (aucun fallback). require_contract avant wrapping."""
    if provider not in OBSERVABILITY_READ_PROVIDERS:
        raise LookupError(f"ObservabilityReadProvider inconnu : {provider!r} (attendu in {OBSERVABILITY_READ_PROVIDERS})")
    if capability not in OBSERVABILITY_READ_CAPABILITIES:
        raise LookupError(f"capacité observability-read inconnue : {capability!r} (attendu in {OBSERVABILITY_READ_CAPABILITIES})")
    impl = resolve_capability(capability, observability_read_descriptors(provider, capability), observability_read_binders())
    require_contract(impl)
    return ObservabilityReadHandle(impl, capability)


__all__ = ["OBS_HEALTH", "OBSERVABILITY_READ_CAPABILITIES", "LOCAL_CONTROL_PLANE", "OBSERVABILITY_READ_PROVIDERS", "observability_read_descriptors", "observability_read_binders", "resolve_observability_read", "UNDERSTAND_NEED", "SPECIFY", "BUILD_SOFTWARE", "CONVERSE", "CAPABILITY_SLUGS", "CLAUDE_CODE",
           "OPENAI", "GEMINI", "COGNITION_PROVIDERS",
           "BUILD_SITE", "PREVIEW_LOCAL", "DEPLOY_PUBLIC", "LOCAL_LOOPBACK",
           "LOCAL_BUILDER", "BUILD_PROVIDERS",
           "default_descriptors", "default_binders", "resolve_capability", "resolve_capabilities",
           "real_capabilities", "understanding_descriptors", "understanding_binders", "resolve_understanding",
           "resolve_understanding_cohort",
           "DeliveryCapabilities", "delivery_descriptors", "delivery_binders",
           "deferred_deploy_public_descriptor", "resolve_delivery", "real_delivery",
           "build_site_descriptors", "build_site_binders", "resolve_build_site",
           "LOCAL_GIT", "GIT_READ_PROVIDERS", "GIT_STATUS", "GIT_DIFF", "GIT_BRANCHES", "GIT_READ_CAPABILITIES",
           "git_read_descriptors", "git_read_binders", "resolve_git_read",
           "GIT_WRITE_PROVIDERS", "GIT_BRANCH_CREATE", "GIT_COMMIT", "GIT_WRITE_CAPABILITIES",
           "git_write_descriptors", "git_write_binders", "resolve_git_write"]
