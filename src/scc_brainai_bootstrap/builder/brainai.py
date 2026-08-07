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

from scc_brainai_bootstrap.builder.build import BuildCapability, produce_build
from scc_brainai_bootstrap.builder.conversation import ConversationCapability
from scc_brainai_bootstrap.builder.specification import SpecificationCapability, produce_specification
from scc_brainai_bootstrap.builder.understanding import NeedUnderstandingCapability, build_proposal
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
    """**Intention** agnostique aux facultés. ``kind`` (ouvert) identifie le genre. Genres supportés : ``need``
    (``need`` = besoin en langage naturel), ``converse`` (un **message** de dialogue, porté par
    ``payload['message']`` — jamais par ``need``), ``realize`` (demander la **réalisation** d'une Pursuit mûrie,
    ``pursuit_ref`` = son ``pursuit_id``) et ``resume`` (``pursuit_ref`` = ``pursuit_id`` d'une poursuite à
    reprendre). ``converse``/``realize`` **restent la même Pursuit** : le dialogue et la future réalisation
    partagent un ``pursuit_id`` (via ``pursuit_ref``) — il n'y a **pas** de seconde identité cognitive. ``payload``
    : matière **neutre et optionnelle** du tour (message, clarification, décision de gouvernance, continuation) —
    sa structure fine n'est pas conçue ici. Construire via :func:`need_intent` / :func:`converse_intent` /
    :func:`realize_intent` / :func:`resume_intent`."""

    kind: str
    need: Optional[str] = None
    pursuit_ref: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


def need_intent(text: str) -> Intent:
    """Première intention supportée : un **besoin** en langage naturel (nettoyé, non vide)."""
    return Intent(kind="need", need=validate_need(text))


def converse_intent(message: str, *, pursuit_ref: Optional[str] = None) -> Intent:
    """Intention de **dialogue** : un message en langage naturel. Le message est porté par ``payload['message']``
    (jamais par ``need``, réservé au genre ``need``). ``pursuit_ref`` optionnel : ``pursuit_id`` de la **même**
    Pursuit à poursuivre (absent au premier tour ; le moteur frappera alors l'identité)."""
    if not isinstance(message, str) or not message.strip():
        raise IntentError("message (chaîne non vide) requis pour une intention 'converse'")
    ref = pursuit_ref.strip() if isinstance(pursuit_ref, str) and pursuit_ref.strip() else None
    return Intent(kind="converse", pursuit_ref=ref, payload={"message": message.strip()})


def realize_intent(pursuit_id: str) -> Intent:
    """Intention de **réalisation** d'une Pursuit mûrie : lance l'arc (Brief→Spéc→Manifeste) sur la **même**
    Pursuit (référence son ``pursuit_id``). Émise **après** confirmation humaine — l'appréciation ``readiness``
    du dialogue ne l'émet jamais d'elle-même (BrainAI propose, l'humain autorise)."""
    if not isinstance(pursuit_id, str) or not pursuit_id.strip():
        raise IntentError("pursuit_id (chaîne non vide) requis pour une intention 'realize'")
    return Intent(kind="realize", pursuit_ref=pursuit_id.strip())


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
    conversation: Optional[ConversationCapability] = None

    def __post_init__(self) -> None:
        for role, value, protocol in (
            ("understanding", self.understanding, NeedUnderstandingCapability),
            ("specification", self.specification, SpecificationCapability),
            ("build", self.build, BuildCapability),
        ):
            if value is None or not isinstance(value, protocol):
                raise CapabilityInjectionError(
                    f"capacité '{role}' absente ou non conforme à {protocol.__name__}")
        # Capacité de dialogue : **optionnelle** (additive) — validée seulement si injectée ; son absence ne
        # rompt pas l'arc historique. ``roles()`` reste inchangé (le dialogue n'est pas une étape du parcours).
        if self.conversation is not None and not isinstance(self.conversation, ConversationCapability):
            raise CapabilityInjectionError(
                "capacité 'conversation' non conforme à ConversationCapability")

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


@dataclass(frozen=True)
class Stores:
    """Journaux **append-only** des faits produits le long de l'arc (hors ``data/``, **injectés**). Portés par
    :class:`RunContext` (``stores``) : ``proposals`` (Brief), ``specifications`` (Spéc), ``builds`` (Build)."""

    proposals: Any
    specifications: Any
    builds: Any


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
    faculté** ; ils rejoindront ``steps`` lors d'un nettoyage ultérieur, sans changer la signature de ``pursue``.

    Tour **conversationnel** (BRAINAI-CONVERSATION-001, additif) : ``reply`` (réponse de dialogue en langage
    naturel) et ``proposal`` (appréciation de maturité — p. ex. ``{"readiness": "ready", "matured_need": …}``).
    ``proposal`` est une **proposition cognitive, jamais une autorisation** : la réalisation exige une
    confirmation humaine explicite (intention ``realize``). Le même ``pursuit_id`` porte dialogue puis
    réalisation — pas de seconde identité."""

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
    reply: Optional[str] = None
    proposal: Optional[Dict[str, Any]] = None

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
    non supporté (:class:`IntentError`) ; besoin vide pour ``need`` (:class:`NeedError`) ; ``payload['message']``
    vide pour ``converse`` (:class:`IntentError`, **pas** :class:`NeedError` — le message n'est pas un besoin) ;
    ``pursuit_ref`` vide pour ``realize``/``resume`` (:class:`IntentError`). ``payload`` est par ailleurs opaque."""
    if not isinstance(intent, Intent):
        raise IntentError("intention (Intent) requise")
    if not isinstance(intent.kind, str) or not intent.kind.strip():
        raise IntentError("intent.kind requis (chaîne non vide)")
    if intent.kind == "need":
        validate_need(intent.need)
    elif intent.kind == "converse":
        # Le message conversationnel vit dans payload['message'] — jamais dans need (réservé au genre 'need').
        # Message vide ⇒ IntentError (et non NeedError) : ce n'est pas un besoin mais un tour de dialogue.
        message = intent.payload.get("message") if isinstance(intent.payload, dict) else None
        if not isinstance(message, str) or not message.strip():
            raise IntentError("intention 'converse' : payload['message'] (chaîne non vide) requis")
        if intent.pursuit_ref is not None and (
                not isinstance(intent.pursuit_ref, str) or not intent.pursuit_ref.strip()):
            raise IntentError("intention 'converse' : pursuit_ref, si fourni, doit être une chaîne non vide")
    elif intent.kind == "realize":
        if not isinstance(intent.pursuit_ref, str) or not intent.pursuit_ref.strip():
            raise IntentError("intention 'realize' : référence de poursuite (pursuit_id) requise")
    elif intent.kind == "resume":
        if not isinstance(intent.pursuit_ref, str) or not intent.pursuit_ref.strip():
            raise IntentError("intention 'resume' : référence de poursuite (pursuit_id) requise")
    else:
        raise IntentError(f"intention non supportée : kind={intent.kind!r}")


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
    **Refuse** ``resume`` et ``realize`` : ni la reprise ni la réalisation ne créent d'identité — elles réutilisent
    l'identité existante (``pursuit_ref``). ``converse`` **peut** en frapper une (premier tour de dialogue) ; le
    message est alors intégré au contenu adressé. Déterministe : mêmes intention/projet/horodatage → même
    ``pursuit_id``."""
    if not isinstance(intent, Intent):
        raise IntentError("intention (Intent) requise")
    if intent.kind in ("resume", "realize"):
        raise IntentError(
            "une reprise ou une réalisation ne crée pas d'identité de Pursuit ; réutiliser intent.pursuit_ref")
    message = intent.payload.get("message") if isinstance(intent.payload, dict) else None
    return short_id("pursuit", {"kind": intent.kind, "need": intent.need, "message": message,
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
        :class:`Outcome` **non autoritatif** et **identifié** (``pursuit_id``). Signature figée (T1).

        **Tâche 2 — première faculté (``kind="need"``)** : orchestre l'arc ``Need → Understanding →
        Specification → Build`` **à l'intérieur** de BrainAI. Frappe un ``pursuit_id`` stable, ancre le Brief
        (``pursuit_ref``), transmet chaque fait ``proposed`` au rung suivant (``brief_ref``/``spec_ref``),
        **s'arrête au premier échec/refus** (aucun retry, un appel max par rung), transporte le **budget total**
        (chaque rung reçoit le reste ; aucun appel si insuffisant) et **agrège honnêtement** le coût. **Ne valide
        rien, ne rend rien officiel** : un succès complet renvoie ``state="awaiting"`` / ``wait_reason="governance"``.
        Les autres genres (``converse``/``realize``/``resume``) ne sont pas encore orchestrés (Tâche 2)."""
        validate_intent(intent)
        validate_run_context(context)
        if intent.kind != "need":
            raise NotImplementedError(
                "seule l'intention 'need' est orchestrée en Tâche 1 ; converse/realize/resume seront "
                "enseignés en BRAINAI-CONVERSATION-001 · Tâche 2")

        need = intent.need
        project_id = context.project_id
        stores = context.stores
        workspace = context.workspace
        clock = self._clock
        pursuit_id = new_pursuit_id(intent, project_id, clock())
        cwd = workspace.ensure()                 # répertoire confiné (appels texte : aucun fichier écrit)
        remaining = float(context.budget_usd)
        steps: List[Dict[str, Any]] = []
        spent = 0.0
        incomplete_cost = False

        def _account(cost: Any) -> None:         # somme HONNÊTE : n'ajoute que les coûts réels, jamais inventés
            nonlocal spent, remaining, incomplete_cost
            if isinstance(cost, dict) and cost.get("kind") == "real" and isinstance(cost.get("value"), (int, float)):
                spent += float(cost["value"]); remaining -= float(cost["value"])
            else:
                incomplete_cost = True

        def _cost_total() -> Dict[str, Any]:
            return {"value": spent, "kind": "real" if not incomplete_cost else "partial"}

        def _terminal(refused: Optional[str] = None) -> Outcome:
            return Outcome(state="terminal", project_id=project_id, pursuit_id=pursuit_id,
                           as_of=clock(), need=need, steps=tuple(steps),
                           cost_total=_cost_total(), refused=refused)

        # --- Rung 1 : Understanding (Need → Brief). Pas de wrapper produce_* : la garde budget est dans l'adaptateur.
        und = self._capabilities.understanding
        raw = und.propose(need, cwd=cwd, budget_remaining_usd=remaining)
        if not raw.get("called"):
            steps.append({"faculty": "understanding", "status": "refused", "refused": raw.get("refused")})
            return _terminal(refused=raw.get("refused"))
        brief_fact = stores.proposals.record(build_proposal(
            need=need, prompt=raw["prompt"], capability=und.capability, adapter=und.name,
            model=getattr(und, "model", None), envelope=raw["envelope"], exit_code=raw["exit_code"],
            timed_out=raw["timed_out"], as_of=clock(), argv=raw.get("argv"),
            stdout=raw.get("stdout"), stderr=raw.get("stderr"), pursuit_ref=pursuit_id))
        _account(brief_fact.get("cost"))
        steps.append({"faculty": "understanding", "status": brief_fact["status"],
                      "fact_id": brief_fact["proposal_id"], "pursuit_ref": brief_fact.get("pursuit_ref"),
                      "cost": brief_fact.get("cost"), "error": brief_fact.get("error")})
        if brief_fact["status"] != "proposed":
            return _terminal()

        # --- Rung 2 : Specification (Brief proposé → Spéc). Provenance : spec.brief_ref == brief.proposal_id.
        spec_out = produce_specification(brief_source=brief_fact, adapter=self._capabilities.specification,
                                         store=stores.specifications, budget_remaining_usd=remaining,
                                         cwd=cwd, clock=clock)
        if not spec_out["attempted"]:
            steps.append({"faculty": "specification", "status": "refused", "refused": spec_out.get("refused")})
            return _terminal(refused=spec_out.get("refused"))
        spec_fact = spec_out["fact"]
        _account(spec_fact.get("cost"))
        steps.append({"faculty": "specification", "status": spec_fact["status"],
                      "fact_id": spec_fact["specification_id"], "brief_ref": spec_fact.get("brief_ref"),
                      "cost": spec_fact.get("cost"), "error": spec_fact.get("error")})
        if spec_fact["status"] != "proposed":
            return _terminal()

        # --- Rung 3 : Build (Spéc proposée → Manifeste confiné). Provenance : build.spec_ref == spec.specification_id.
        build_out = produce_build(spec_source=spec_fact, adapter=self._capabilities.build,
                                  store=stores.builds, workspace=workspace,
                                  budget_remaining_usd=remaining, cwd=cwd, clock=clock)
        if not build_out["attempted"]:
            steps.append({"faculty": "build", "status": "refused", "refused": build_out.get("refused")})
            return _terminal(refused=build_out.get("refused"))
        build_fact = build_out["fact"]
        _account(build_fact.get("cost"))
        steps.append({"faculty": "build", "status": build_fact["status"],
                      "fact_id": build_fact["build_id"], "spec_ref": build_fact.get("spec_ref"),
                      "artefact": build_fact.get("artefact"), "cost": build_fact.get("cost"),
                      "error": build_fact.get("error")})
        if build_fact["status"] != "proposed":
            return _terminal()

        # --- Succès : proposition complète de la Pursuit, EN ATTENTE de gouvernance humaine (jamais autoritatif).
        return Outcome(state="awaiting", wait_reason="governance", project_id=project_id,
                       pursuit_id=pursuit_id, as_of=clock(), need=need, steps=tuple(steps),
                       artefact=build_fact.get("artefact"), cost_total=_cost_total())


__all__ = ["BrainAI", "Capabilities", "RunContext", "Stores", "Outcome", "Intent", "PURSUIT_STATES",
           "BrainAIError", "CapabilityInjectionError", "IntentError", "NeedError", "GovernanceError",
           "need_intent", "converse_intent", "realize_intent", "resume_intent", "validate_need",
           "validate_intent", "validate_run_context", "new_pursuit_id"]
