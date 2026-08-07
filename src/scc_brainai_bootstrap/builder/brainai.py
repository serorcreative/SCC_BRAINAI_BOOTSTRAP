"""**BrainAI** — première incarnation gouvernée (ARC-PROPOSE-001, Tâche 1 : contrat seul).

BrainAI est un **objet unique et persistant**. Il reçoit une **intention**, décide du parcours, orchestre des
**capacités louées interchangeables**, et transporte budget, provenance, faits, arrêt-au-premier-échec et
invariants de gouvernance. Sa **première faculté** (enseignée par ce chantier) est le parcours ``Need →
Understanding → Specification → Build``. Les chantiers futurs enseigneront de nouvelles facultés (Validation,
Exécution, Observation, Apprentissage) **au même objet**, **sans changer son identité publique**.

**Pursuit = unité durable de cognition.** Une poursuite possède une identité stable ``pursuit_id`` (adressée au
contenu, frappée **une seule fois** à la création via :func:`new_pursuit_id`, **jamais** re-frappée à la reprise).
L':class:`Outcome` est la **photographie non terminale** de la Pursuit à un tour donné. Le couple *(pursuit_id
stable + Outcome non terminal + Intention neutre)* suffit, au niveau du contrat, à reconstruire/continuer/reprendre
une Pursuit **demain** sans store ni changement d'API (aucune persistance ici).

**Entrée = Intention neutre (H1).** ``BrainAI.pursue(intent, *, context) -> Outcome`` : ``intent`` est une
:class:`Intent` **agnostique aux facultés** (``kind`` **ouvert**). Cette version supporte ``need`` (besoin initial,
**première intention**) et ``resume`` (reprise d'une poursuite existante par sa référence). Un ``payload`` neutre et
optionnel porte la **matière du tour suivant** (clarification, décision de gouvernance, continuation) — la structure
fine de cette matière n'est **pas** conçue ici. Les genres non supportés sont refusés **avant toute frontière**.

**Création ≠ reprise (invariant).** :func:`new_pursuit_id` frappe l'identité d'une **nouvelle** Pursuit et **refuse**
une intention ``resume``. Une reprise réutilise **exactement** le ``pursuit_ref`` reçu : aucune ambiguïté possible.

**Continuer ≠ reprendre.** « Continuer » (mouvement dans une Pursuit encore chaude) et « reprendre » (retour à une
Pursuit interrompue, pouvant exiger re-compréhension) seront **deux genres d'intention distincts** sur la **même**
signature — l'API ne les fusionne pas. Aucune méthode ``continue()`` n'est nécessaire ni ajoutée.

**État ≠ raison d'attente (H2, non-prolifération).** L':class:`Outcome` distingue le **lifecycle** ``state`` ∈
:data:`PURSUIT_STATES` (``active`` / ``awaiting`` / ``terminal``) d'un ``wait_reason`` optionnel (vocabulaire
**ouvert** : ``governance``, ``clarification``…) — une nouvelle raison d'attente n'ajoute **aucun** statut racine.
Un arc réussi n'est **pas** terminal : il est ``awaiting`` (``governance``). **BrainAI peut proposer une clôture ;
il ne s'auto-déclare jamais quitte** (le ``terminal`` n'est atteint que par refus/échec, ou — futur — clôture humaine).

**Capacités** louées interchangeables et injectées (R8) ; direction stricte ``BrainAI → capacités``. BrainAI vit dans
le **plan builder**, n'importe **aucun** module du noyau (frontière S9), ne modifie **aucun** état officiel (R5).

**Tâche 1 = contrat seul** : identité publique, objets, validations et refus **avant toute frontière** — **aucune**
orchestration, **aucun** appel réel, **aucune** matérialisation, **aucun** fait produit. Invariants portés par l'objet :
identité stable · **non-auto-autorité** (résultat toujours non autoritatif) · capacité ≠ outil (R8) · coût honnête (R2)
· aucun retry (R6) · arrêt au premier échec · append-only · budget avant frontière · confinement. Stdlib + ``core``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from scc_brainai_bootstrap.builder.build import BuildCapability
from scc_brainai_bootstrap.builder.specification import SpecificationCapability
from scc_brainai_bootstrap.builder.understanding import NeedUnderstandingCapability
from scc_brainai_bootstrap.core.clock import short_id


# --------------------------------------------------------------------- #
# Erreurs — refus gouvernés, levés AVANT toute frontière externe
# --------------------------------------------------------------------- #
class BrainAIError(ValueError):
    """Base des refus gouvernés de BrainAI (levés **avant** tout appel/effet)."""


class CapabilityInjectionError(BrainAIError):
    """Capacité injectée absente ou ne satisfaisant pas son Protocol (R8)."""


class IntentError(BrainAIError):
    """Intention invalide, mal formée, ou non supportée par ce contrat."""


class NeedError(BrainAIError):
    """Contenu de besoin invalide (absent, non-chaîne, ou vide)."""


class GovernanceError(BrainAIError):
    """Contexte d'exécution invalide (budget non positif, workspace/journaux/projet absents)."""


# --------------------------------------------------------------------- #
# Intention — entrée publique NEUTRE (H1), extensible
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class Intent:
    """**Intention** agnostique aux facultés. ``kind`` (ouvert) identifie le genre. Cette version supporte ``need``
    (``need`` = besoin en langage naturel) et ``resume`` (``pursuit_ref`` = ``pursuit_id`` d'une poursuite à
    reprendre). ``payload`` : matière **neutre et optionnelle** du tour suivant (clarification, décision de
    gouvernance, continuation) — sa structure fine n'est pas conçue ici. Construire via :func:`need_intent` /
    :func:`resume_intent`."""

    kind: str
    need: Optional[str] = None
    pursuit_ref: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


def need_intent(text: str) -> Intent:
    """Première intention supportée : un **besoin** en langage naturel (nettoyé, non vide)."""
    return Intent(kind="need", need=validate_need(text))


def resume_intent(pursuit_id: str, *, payload: Optional[Dict[str, Any]] = None) -> Intent:
    """Intention de **reprise** d'une poursuite existante (référence son ``pursuit_id``). ``payload`` optionnel :
    matière du tour suivant (p. ex. clarification humaine ou référence d'une décision de gouvernance)."""
    if not isinstance(pursuit_id, str) or not pursuit_id.strip():
        raise IntentError("pursuit_id (chaîne non vide) requis pour une intention 'resume'")
    return Intent(kind="resume", pursuit_ref=pursuit_id.strip(), payload=payload)


# --------------------------------------------------------------------- #
# Capacités injectées — facultés louées interchangeables (R8)
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class Capabilities:
    """Conteneur d'**injection** des capacités louées. Chacune doit satisfaire son **Protocol** (vérifié à la
    construction) — n'importe quelle implémentation conforme est acceptée (interchangeabilité, R8)."""

    understanding: NeedUnderstandingCapability
    specification: SpecificationCapability
    build: BuildCapability

    def __post_init__(self) -> None:
        for role, value, protocol in (
            ("understanding", self.understanding, NeedUnderstandingCapability),
            ("specification", self.specification, SpecificationCapability),
            ("build", self.build, BuildCapability),
        ):
            if value is None or not isinstance(value, protocol):
                raise CapabilityInjectionError(
                    f"capacité '{role}' absente ou non conforme à {protocol.__name__}")

    def roles(self) -> Tuple[str, ...]:
        """Rôles (facultés louées) injectés, dans l'ordre du parcours courant."""
        return ("understanding", "specification", "build")


# --------------------------------------------------------------------- #
# Contexte d'exécution d'une poursuite — enveloppe de gouvernance (par pursuit)
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class RunContext:
    """Enveloppe de gouvernance d'**une** poursuite. ``budget_usd`` : budget **total de la Pursuit** — les futurs
    budgets *d'appel* et *de réflexion* pourront s'ajouter comme champs **sans rupture**. ``workspace`` confiné et
    ``stores`` (journaux append-only) : leur forme précise est fixée en Tâche 2 ; ici seule leur **présence** est
    requise."""

    budget_usd: float
    project_id: str
    workspace: Any
    stores: Any


# --------------------------------------------------------------------- #
# Cycle de vie d'une Pursuit — état ≠ raison d'attente (non-prolifération des statuts)
# --------------------------------------------------------------------- #
# Lifecycle de la Pursuit. Une raison d'attente n'ajoute JAMAIS un statut racine : elle vit dans ``wait_reason``.
PURSUIT_STATES = ("active", "awaiting", "terminal")


@dataclass(frozen=True)
class Outcome:
    """**Photographie non terminale** d'une Pursuit à un tour. Porte l'identité stable ``pursuit_id``. ``state`` ∈
    :data:`PURSUIT_STATES` (``active`` vivante / ``awaiting`` suspendue / ``terminal`` refus·échec·clôture) ;
    ``wait_reason`` (ouvert : ``governance``/``clarification``…) est **requis si et seulement si** ``state ==
    'awaiting'``. ``steps`` : résultats par faculté, ordonnés, **extensibles**. Aucun champ autoritatif : BrainAI ne
    s'auto-déclare jamais quitte.

    Réserve consignée (M2, hors périmètre) : ``need`` (optionnel) et ``artefact`` sont **spécifiques à la première
    faculté** ; ils rejoindront ``steps`` lors d'un nettoyage ultérieur, sans changer la signature de ``pursue``."""

    state: str
    project_id: str
    pursuit_id: str
    as_of: str
    need: Optional[str] = None
    wait_reason: Optional[str] = None
    steps: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    artefact: Optional[Dict[str, Any]] = None
    cost_total: Dict[str, Any] = field(default_factory=lambda: {"value": None, "kind": "unavailable"})
    refused: Optional[str] = None

    def __post_init__(self) -> None:
        if self.state not in PURSUIT_STATES:
            raise ValueError(f"state inconnu : {self.state!r} (attendu ∈ {PURSUIT_STATES})")
        if self.state == "awaiting":
            if not isinstance(self.wait_reason, str) or not self.wait_reason.strip():
                raise ValueError("wait_reason (non vide) requis quand state == 'awaiting'")
        elif self.wait_reason is not None:
            raise ValueError("wait_reason interdit hors de l'état 'awaiting'")


# --------------------------------------------------------------------- #
# Validations & primitives — déterministes, avant toute frontière
# --------------------------------------------------------------------- #
def validate_need(need: Any) -> str:
    """Valide un contenu de besoin et renvoie sa forme nettoyée — ou lève :class:`NeedError`. Chaîne **non vide**."""
    if not isinstance(need, str) or not need.strip():
        raise NeedError("besoin requis : chaîne non vide")
    return need.strip()


def validate_intent(intent: Any) -> None:
    """Valide une intention — ou lève. Refuse **avant toute frontière** : non-:class:`Intent`, ``kind`` vide, genre
    non supporté (:class:`IntentError`) ; besoin vide pour ``need`` (:class:`NeedError`) ; ``pursuit_ref`` vide pour
    ``resume`` (:class:`IntentError`). ``payload`` est opaque (non contraint ici)."""
    if not isinstance(intent, Intent):
        raise IntentError("intention (Intent) requise")
    if not isinstance(intent.kind, str) or not intent.kind.strip():
        raise IntentError("intent.kind requis (chaîne non vide)")
    if intent.kind == "need":
        validate_need(intent.need)
    elif intent.kind == "resume":
        if not isinstance(intent.pursuit_ref, str) or not intent.pursuit_ref.strip():
            raise IntentError("intention 'resume' : référence de poursuite (pursuit_id) requise")
    else:
        raise IntentError(f"intention non supportée par ARC-PROPOSE-001 : kind={intent.kind!r}")


def validate_run_context(context: Any) -> None:
    """Valide l'enveloppe de gouvernance — ou lève :class:`GovernanceError`. Refuse **avant tout appel** : budget
    non numérique/≤ 0, ``project_id`` non-chaîne/vide, ``workspace`` absent, ``stores`` absent."""
    if not isinstance(context, RunContext):
        raise GovernanceError("contexte d'exécution (RunContext) requis")
    if not isinstance(context.budget_usd, (int, float)) or context.budget_usd <= 0:
        raise GovernanceError("budget_usd doit être un nombre strictement positif")
    if not isinstance(context.project_id, str) or not context.project_id.strip():
        raise GovernanceError("project_id requis : chaîne non vide")
    if context.workspace is None:
        raise GovernanceError("workspace confiné requis")
    if context.stores is None:
        raise GovernanceError("stores (journaux append-only) requis")


def new_pursuit_id(intent: Intent, project_id: str, as_of: str) -> str:
    """Frappe l'identité **stable et adressée au contenu** d'une **nouvelle** Pursuit (préfixe ``pursuit_``).
    **Refuse** une intention ``resume`` : une reprise ne crée jamais d'identité (réutiliser ``pursuit_ref``).
    Déterministe : mêmes intention/projet/horodatage → même ``pursuit_id``."""
    if not isinstance(intent, Intent):
        raise IntentError("intention (Intent) requise")
    if intent.kind == "resume":
        raise IntentError("une reprise ne crée pas d'identité de Pursuit ; réutiliser intent.pursuit_ref")
    return short_id("pursuit", {"kind": intent.kind, "need": intent.need,
                                "project_id": project_id, "as_of": as_of})


def _system_clock() -> str:
    """Horloge réelle : instant UTC ISO 8601. Injectable (paramètre ``clock`` de :class:`BrainAI`)."""
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------- #
# BrainAI — l'objet
# --------------------------------------------------------------------- #
class BrainAI:
    """**BrainAI** — objet unique, persistant, gouverné. Reçoit une **intention**, décide du parcours, orchestre les
    capacités injectées, transporte budget/provenance/faits/arrêt-au-premier-échec. Première faculté : l'arc
    ``Need→Understanding→Specification→Build`` (orchestration enseignée en Tâche 2)."""

    def __init__(self, capabilities: Capabilities, *, clock: Callable[[], str] = _system_clock):
        if not isinstance(capabilities, Capabilities):
            raise CapabilityInjectionError("capabilities (Capabilities) requis")
        self._capabilities = capabilities
        self._clock = clock

    @property
    def capabilities(self) -> Capabilities:
        return self._capabilities

    @property
    def clock(self) -> Callable[[], str]:
        return self._clock

    @property
    def faculties(self) -> Tuple[str, ...]:
        """Parcours **courant** de BrainAI (ordre des facultés). Extensible sans changer l'identité publique."""
        return self._capabilities.roles()

    def pursue(self, intent: Intent, *, context: RunContext) -> Outcome:
        """**Identité publique stable** : poursuivre une **intention** sous gouvernance et renvoyer un
        :class:`Outcome` **non autoritatif** et **identifié** (``pursuit_id``). Cette signature **ne changera pas**
        quand de nouvelles facultés ou de nouveaux genres d'intention (``resume``, futur ``continue``…) seront
        enseignés.

        **Tâche 1 (contrat)** : valide l'intention et le contexte, **refuse avant toute frontière** en cas
        d'invalidité (:class:`IntentError` / :class:`NeedError` / :class:`GovernanceError`), puis **délègue à la
        faculté d'orchestration** — **non encore enseignée** (Tâche 2). Aucun appel réel, aucune matérialisation,
        aucun fait produit."""
        validate_intent(intent)
        validate_run_context(context)
        raise NotImplementedError(
            "ARC-PROPOSE-001 · Tâche 2 : la faculté d'orchestration (Need→Understanding→Specification→Build, "
            "et la reprise gouvernée) n'est pas encore enseignée (contrat seul en Tâche 1)")


__all__ = ["BrainAI", "Capabilities", "RunContext", "Outcome", "Intent", "PURSUIT_STATES",
           "BrainAIError", "CapabilityInjectionError", "IntentError", "NeedError", "GovernanceError",
           "need_intent", "resume_intent", "validate_need", "validate_intent", "validate_run_context",
           "new_pursuit_id"]
