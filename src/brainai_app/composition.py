"""Composition root — **câble** BrainAI et **projette** l'``Outcome`` vers un ViewModel. Aucune logique métier.

Responsabilités (et rien de plus) : construire BrainAI, **injecter** ses capacités (démo factices 0 € / réelles
facturables), bâtir Stores / RunContext / Workspace **hors ``data/``**, appeler **exclusivement**
``BrainAI.pursue(...)``, puis **refléter** l'``Outcome`` en ViewModel. Le ViewModel est **piloté par ce que
BrainAI renvoie** (``Outcome.steps``) : **aucune** liste de facultés codée en dur (libellé inconnu → nom brut).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, Stores, converse_intent, need_intent, realize_intent)
from scc_brainai_bootstrap.builder.arbitrations import ArbitrationStore
from scc_brainai_bootstrap.builder.build_authorization import (
    BuildAuthorizationStore, authorization_status, build_authorization_fact, resolve_cost_gate)
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.confirmations import ConfirmationStore
from scc_brainai_bootstrap.builder.cost_estimate import CostEstimateStore
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.solution_architecture import SolutionArchitectureStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.turns import TurnStore
from scc_brainai_bootstrap.builder.workspace import Workspace
from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.delivered import DeliveredStore
from brainai_app.delivery.memory import (MemoryUnavailable, open_memory_store, report_memory_ids,
                                          write_delivery_memory)
from brainai_app.delivery.runner import BuildRunStore
from brainai_app.delivery.service import run_delivery
from brainai_app.delivery.verify import VerificationStore

from brainai_app.contract import CONTRACT_VERSION
from brainai_app.delivery.budget_config import load_delivery_budget

# Budget de livraison — **gouverné** (RS-047) : plus de constante câblée. Résolution explicite > env > défaut,
# source tracée. Plafond USD = best-effort borné (RS-039) ; plafond d'appels = garde dure. Voir ``budget_config``.

# Jalon du moteur exposé à l'UI (informationnel) — première faculté : Need→Understanding→Specification→Build.
BRAINAI_VERSION = "arc-propose-001"

# Libellés lisibles des livrables — **avec repli** sur le nom de faculté (agnostique au nombre de facultés).
_LABELS = {"understanding": "Brief", "specification": "Specification", "build": "Manifest"}
# Verbe d'action « en cours » pour l'affichage vivant — même repli sur le nom de faculté.
_PROGRESS = {"understanding": "Compréhension", "specification": "Spécification", "build": "Construction"}


# --------------------------------------------------------------------- #
# Mode DÉMO — capacités factices, 0 €. Vivent dans l'APPLICATION, jamais dans le moteur.
# --------------------------------------------------------------------- #
_DEMO_BRIEF = {"objective": "Gérer un refuge animalier", "context": "Petite structure associative",
               "actors": ["Personnel", "Adoptant"], "scope": ["Animaux", "Adoptants", "Rendez-vous"],
               "assumptions": ["Usage web interne"], "open_questions": ["Multi-refuge ?"],
               "constraints": ["Budget limité"]}
_DEMO_SPEC = {"product_objective": "Application de gestion d'un refuge animalier.",
              "users_and_roles": ["Personnel", "Adoptant"], "functional_scope": ["Animaux", "Adoptants", "RDV"],
              "features": ["Fiche animal", "Recherche adoptant", "Planning RDV"],
              "entities_and_data": ["Animal", "Adoptant", "RendezVous"],
              "key_journeys": ["Enregistrer un animal", "Planifier une visite"],
              "constraints": ["Budget limité"], "acceptance_criteria": ["Un animal peut être créé et retrouvé"],
              "assumptions": ["Un seul refuge en V1"], "open_questions": ["Notifications ?"],
              "out_of_scope": ["Paiement en ligne"]}
_DEMO_MANIFEST = {"name": "Gestion Refuge Animalier",
                  "summary": "Application unifiant animaux, adoptants et rendez-vous d'un refuge.",
                  "users": ["Personnel", "Adoptant"], "features": ["Fiche animal", "Planning RDV"],
                  "entities": ["Animal", "Adoptant", "RendezVous"]}


def _demo_envelope(result_obj: Any) -> Dict[str, Any]:
    return {"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
            "num_turns": 1, "result": json.dumps(result_obj, ensure_ascii=False),
            "total_cost_usd": 0.0, "usage": {"input_tokens": 10, "output_tokens": 20}}


class _DemoCapability:
    """Capacité louée **factice** conforme au Protocol (0 €). Renvoie un résultat canned, sans appel réel."""

    def __init__(self, capability: str, envelope: Dict[str, Any]):
        self.capability = capability
        self.name = "demo"
        self.model = "demo"
        self._env = envelope

    def propose(self, _payload: Any, *, cwd: Any, budget_remaining_usd: float) -> Dict[str, Any]:
        return {"called": True, "envelope": self._env, "exit_code": 0, "timed_out": False,
                "prompt": "(démo)", "argv": ["demo"], "stdout": "", "stderr": ""}


class _DemoConversation:
    """Capacité de **dialogue** factice **honnête** conforme au Protocol (0 €) — COGNITIVE-IDENTITY-001 T4/A3.

    Le mode démo ne **simule jamais** une compréhension : ``readiness='continue'`` **toujours**, **aucun**
    ``matured_need``, **aucune** affirmation de compréhension (« c'est clair pour moi » proscrit). La réponse
    déclare franchement qu'aucune cognition n'est active. Conséquence assumée : la démo n'ouvre **jamais** de
    porte de gouvernance — le parcours ready→realize ne s'exerce qu'en mode **réel** (ou via une fake dédiée
    au test). Les fakes déterministes vivent dans les tests, pas dans la démo produit."""

    capability = "conversation"; name = "demo"; model = "demo"

    def propose(self, message: str, *, history: List[Dict[str, Any]], cwd: Any,
                budget_remaining_usd: float) -> Dict[str, Any]:
        obj = {"reply": "Mode démo — aucune cognition active ; réponses pré-écrites, aucune compréhension "
                        "réelle de votre besoin. Passez en mode réel pour un véritable dialogue.",
               "readiness": "continue"}
        return {"called": True, "envelope": _demo_envelope(obj), "exit_code": 0, "timed_out": False,
                "prompt": "(démo)", "argv": ["demo"], "stdout": "", "stderr": ""}


def demo_capabilities() -> Capabilities:
    """Capacités **démo** (0 €) — pour développer/exercer l'interface sans dépense."""
    return Capabilities(
        understanding=_DemoCapability("understanding", _demo_envelope(_DEMO_BRIEF)),
        specification=_DemoCapability("specification", _demo_envelope(_DEMO_SPEC)),
        build=_DemoCapability("build", _demo_envelope(_DEMO_MANIFEST)),
        conversation=_DemoConversation())


def real_capabilities(understanding_provider: Optional[str] = None, *,
                      understanding_providers: Optional[List[str]] = None,
                      arbitration_policy: Optional[Any] = None) -> Capabilities:
    """Capacités **réelles** (facturables) — **résolues via le Capability Registry**. Aucun nom de fournisseur,
    aucun import d'adaptateur concret ici : la sélection ``capacité → fournisseur → adaptateur`` vit dans la
    couche d'infrastructure :mod:`brainai_app.providers` (découplage structurel du fournisseur, I9).

    ``understanding_provider`` / ``understanding_providers`` sont des **sélecteurs opaques** transmis tels quels à
    l'infrastructure — ce module n'en connaît **aucune** valeur nominale. L7 : ``understanding_providers`` (liste)
    permet un **fan-out explicite** derrière la même capacité ; ``arbitration_policy`` (optionnelle) est
    provider-neutral. La sémantique exacte (single/défaut/cohorte, fail-closed) est résolue **uniquement** dans
    :mod:`brainai_app.providers`."""
    from brainai_app import providers
    return providers.real_capabilities(understanding_provider=understanding_provider,
                                       understanding_providers=understanding_providers,
                                       arbitration_policy=arbitration_policy)


def _capabilities(mode: str, understanding_provider: Optional[str] = None, *,
                  understanding_providers: Optional[List[str]] = None,
                  arbitration_policy: Optional[Any] = None) -> Capabilities:
    if mode == "real":
        return real_capabilities(understanding_provider=understanding_provider,
                                 understanding_providers=understanding_providers,
                                 arbitration_policy=arbitration_policy)
    return demo_capabilities()


# --------------------------------------------------------------------- #
# Projection Outcome -> ViewModel (mapping pur, aucune décision)
# --------------------------------------------------------------------- #
def _reply(outcome: Any) -> str:
    """Reflet **lisible** de l'Outcome (déterministe, sans cognition)."""
    if outcome.state == "awaiting" and outcome.wait_reason == "governance":
        labels = [_LABELS.get(s.get("faculty"), s.get("faculty"))
                  for s in outcome.steps if s.get("status") == "proposed"]
        return ("J'ai produit : " + ", ".join(labels) +
                ". J'ai terminé — en attente de votre validation.")
    if outcome.refused:
        return "Poursuite arrêtée : " + str(outcome.refused) + "."
    failed = [s for s in outcome.steps if s.get("status") == "failed"]
    if failed:
        return "Poursuite arrêtée à l'étape « " + str(failed[-1].get("faculty")) + " » (échec)."
    return "Poursuite terminée (état : " + str(outcome.state) + ")."


def to_viewmodel(outcome: Any, *, need: Optional[str], mode: str, budget_usd: float,
                 elapsed_ms: int) -> Dict[str, Any]:
    """Projette un ``Outcome`` en ViewModel de transport. **Piloté par ``Outcome.steps``** — aucun nombre de
    facultés codé en dur ; un libellé inconnu retombe sur le nom de faculté. Tour de **dialogue** : ``reply`` =
    la réponse du moteur (``outcome.reply``) et ``proposal`` (appréciation ``readiness``/``matured_need``) sont
    reflétés tels quels ; l'arc, lui, n'a pas de ``reply`` propre → repli sur la synthèse lisible ``_reply``."""
    steps: List[Dict[str, Any]] = [
        {"faculty": s.get("faculty"), "status": s.get("status"),
         "label": _LABELS.get(s.get("faculty"), s.get("faculty")),
         "progress_label": _PROGRESS.get(s.get("faculty"), s.get("faculty")),
         "fact_id": s.get("fact_id")}
        for s in outcome.steps
    ]
    deliverables = [{"label": st["label"], "fact_id": st["fact_id"]}
                    for st in steps if st["status"] == "proposed"]
    reply = outcome.reply if getattr(outcome, "reply", None) is not None else _reply(outcome)
    return {
        "conversation": {"need": need, "reply": reply},
        "pursuit": {
            "pursuit_id": outcome.pursuit_id, "state": outcome.state, "wait_reason": outcome.wait_reason,
            "proposal": getattr(outcome, "proposal", None),         # appréciation, jamais autorisation
            "cost": outcome.cost_total, "budget_usd": budget_usd, "elapsed_ms": elapsed_ms,
            "mode": mode, "as_of": outcome.as_of, "refused": outcome.refused,
            "brainai_version": BRAINAI_VERSION, "contract_version": CONTRACT_VERSION,
        },
        "steps": steps,
        "deliverables": deliverables,
    }


def run_pursuit(need: str, *, mode: str = "demo", budget_usd: float = 2.0,
                understanding_provider: Optional[str] = None,
                understanding_providers: Optional[List[str]] = None,
                arbitration_policy: Optional[Any] = None) -> Dict[str, Any]:
    """**Chemin unique application → moteur** : construit le contexte (hors ``data/``), appelle **uniquement**
    ``BrainAI.pursue`` et renvoie le ViewModel. En mode ``demo`` : 0 €. En mode ``real`` : facturable.

    ``understanding_provider`` / ``understanding_providers`` sont des **sélecteurs opaques** de la capacité
    ``understand.need`` — transmis tels quels à l'infrastructure, jamais interprétés ici (aucune règle single/cohorte
    dans ce module). L7 : le câblage du journal d'arbitrage (``ArbitrationStore``, obligatoire côté moteur pour une
    cohorte) est décidé **uniquement** d'après l'état déjà résolu par :mod:`brainai_app.providers`
    (``caps.understanding_cohort``). Sans cohorte : chemin single-provider historique **strictement inchangé**
    (aucun ``ArbitrationStore``)."""
    caps = _capabilities(mode, understanding_provider=understanding_provider,
                         understanding_providers=understanding_providers,
                         arbitration_policy=arbitration_policy)
    root = Path(tempfile.mkdtemp(prefix="brainai_ui_"))          # session éphémère, HORS data/ et dépôt
    # Source de vérité = état provider-neutral déjà résolu (providers.py décide seul single vs cohorte).
    fan_out = bool(getattr(caps, "understanding_cohort", ()))
    # L8 actif (capacité architecture présente ⇒ mode réel) ⇒ journaux architecture/estimations/autorisations
    # requis (l'arc refuse fail-closed une architecture sans journaux). Démo : architecture absente ⇒ None (chemin
    # single-provider historique strictement inchangé, aucun store L8).
    l8 = getattr(caps, "architecture", None) is not None
    stores = Stores(proposals=ProposalStore(root / "prop.jsonl"),
                    specifications=SpecificationStore(root / "spec.jsonl"),
                    builds=BuildStore(root / "build.jsonl"),
                    arbitrations=ArbitrationStore(root / "arb.jsonl") if fan_out else None,
                    solution_architectures=SolutionArchitectureStore(root / "architectures.jsonl") if l8 else None,
                    cost_estimates=CostEstimateStore(root / "cost_estimates.jsonl") if l8 else None,
                    build_authorizations=BuildAuthorizationStore(root / "build_authorizations.jsonl") if l8 else None)
    ctx = RunContext(budget_usd=budget_usd, project_id="session",
                     workspace=Workspace(root / "exec", "session"), stores=stores)
    brain = BrainAI(caps)
    t0 = time.monotonic()
    outcome = brain.pursue(need_intent(need), context=ctx)       # SEUL point d'appel du moteur
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return to_viewmodel(outcome, need=need, mode=mode, budget_usd=budget_usd, elapsed_ms=elapsed_ms)


# --------------------------------------------------------------------- #
# Session (C5-minimal, A1) — CONTINUITÉ DURABLE d'une Pursuit après redémarrage de processus.
# Les nouvelles Pursuits vivent sous une racine d'état STABLE, à un chemin DÉTERMINISTE de leur ``pursuit_id`` :
# ``<state_root>/pursuits/<pursuit_id>/`` (y compris le répertoire de transit du 1ᵉʳ tour, créé SOUS cette
# racine — jamais dans le temp système). Elles ne dépendent donc plus du temp et **survivent** au redémarrage :
# le chemin est **recalculable**, aucun index nominal requis. ``_SESSIONS`` n'est plus qu'un cache mémoire
# (accélérateur) ; la source de vérité reste le disque (``turns.jsonl``). Un index de compat existe UNIQUEMENT
# pour d'anciens répertoires (legacy) — seule réserve restante : une Pursuit legacy encore **physiquement** dans
# le temp système reste, elle, exposée au nettoyage (non les nouvelles Pursuits).
# --------------------------------------------------------------------- #
_SESSIONS: Dict[str, Path] = {}
_SESSIONS_LOCK = threading.Lock()


def _state_root() -> Path:
    """Racine d'état applicative **stable et configurable** (``BRAINAI_STATE_ROOT``), distincte du temp système
    et du ``data/`` du noyau. Défaut : ``~/.brainai/state``."""
    env = os.environ.get("BRAINAI_STATE_ROOT")
    return Path(env) if env else (Path.home() / ".brainai" / "state")


def _pursuits_root() -> Path:
    return _state_root() / "pursuits"


def _pursuit_dir(pursuit_id: str) -> Path:
    """Chemin **déterministe** d'une Pursuit à partir de son identité (A1) — recalculable après redémarrage,
    sans index. Ce déterminisme remplace l'ancien mapping mémoire comme source de continuité."""
    return _pursuits_root() / pursuit_id


def _legacy_index_path() -> Path:
    return _state_root() / "legacy_sessions.json"


def _legacy_lookup(pursuit_ref: str) -> Optional[Path]:
    """Correspondance de **compat** pour un ancien répertoire hors racine déterministe (ex. campagne T1→T8).
    Réservé au legacy — jamais le chemin nominal."""
    try:
        data = json.loads(_legacy_index_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    path = data.get(pursuit_ref) if isinstance(data, dict) else None
    return Path(path) if isinstance(path, str) else None


def _legacy_register(pursuit_ref: str, root: Path) -> None:
    """Enregistre un répertoire **legacy** (hors racine déterministe) pour pouvoir encore le retrouver, sans
    réécrire ses faits. N'appartient pas au chemin nominal des nouvelles Pursuits."""
    p = _legacy_index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    data[pursuit_ref] = str(root)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _session_dir(pursuit_ref: Optional[str]) -> Path:
    """Répertoire d'une Pursuit. **Connue** → chemin déterministe recalculé (survit au redémarrage) ; le cache
    ``_SESSIONS`` n'est qu'un accélérateur ; un ancien répertoire hors racine passe par l'index de compat. **1ᵉʳ
    tour** (identité pas encore frappée) → répertoire de **transit**, déplacé vers son chemin déterministe après
    la frappe (voir :func:`_settle_dir`)."""
    if pursuit_ref:
        with _SESSIONS_LOCK:
            cached = _SESSIONS.get(pursuit_ref)
        if cached is not None:
            return cached
        det = _pursuit_dir(pursuit_ref)
        if det.exists():
            return det
        legacy = _legacy_lookup(pursuit_ref)
        if legacy is not None:
            return legacy
        det.mkdir(parents=True, exist_ok=True)       # connue mais dossier absent : matérialise le chemin nominal
        return det
    _pursuits_root().mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".staging-", dir=str(_pursuits_root())))   # transit, déplacé après frappe


def _settle_dir(root: Path, pursuit_id: str) -> Path:
    """Après frappe de l'identité au 1ᵉʳ tour : déplace le répertoire de **transit** vers son chemin
    **déterministe** ``pursuits/<pursuit_id>/`` (A1). Idempotent : sans transit, ne fait rien."""
    target = _pursuit_dir(pursuit_id)
    if root == target or not root.name.startswith(".staging-"):
        return root
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():                               # collision quasi impossible (id déterministe) : garder la cible
        shutil.rmtree(root, ignore_errors=True)
        return target
    shutil.move(str(root), str(target))
    return target


def _remember(pursuit_id: str, root: Path) -> None:
    with _SESSIONS_LOCK:
        _SESSIONS[pursuit_id] = root


def _session_context(root: Path, *, budget_usd: float) -> RunContext:
    """Contexte pointé au répertoire stable, **avec** le journal des tours (``turns``) requis par le dialogue et
    les journaux **L8 persistants** (architecture / estimations / autorisations) — nécessaires pour que le Cost
    Gate présenté survive au flux converse → realize → USER GO → realize, et que ``_deliver`` puisse recomputer
    le fingerprint depuis les faits persistés (frontière réelle, CHOIX 2)."""
    stores = Stores(proposals=ProposalStore(root / "prop.jsonl"),
                    specifications=SpecificationStore(root / "spec.jsonl"),
                    builds=BuildStore(root / "build.jsonl"),
                    turns=TurnStore(root / "turns.jsonl"),
                    confirmations=ConfirmationStore(root / "confirmations.jsonl"),
                    solution_architectures=SolutionArchitectureStore(root / "architectures.jsonl"),
                    cost_estimates=CostEstimateStore(root / "cost_estimates.jsonl"),
                    build_authorizations=BuildAuthorizationStore(root / "build_authorizations.jsonl"))
    return RunContext(budget_usd=budget_usd, project_id="session",
                      workspace=Workspace(root / "exec", "session"), stores=stores)


def converse(message: str, *, pursuit_ref: Optional[str] = None, mode: str = "demo",
             budget_usd: float = 2.0) -> Dict[str, Any]:
    """Un tour de **dialogue** au sein d'une Pursuit. 1ᵉʳ tour (``pursuit_ref=None``) : le moteur frappe
    l'identité ; suivants : reprise du **même** répertoire (historique relu **côté moteur**, jamais par l'UI)."""
    caps = _capabilities(mode)
    root = _session_dir(pursuit_ref)
    ctx = _session_context(root, budget_usd=budget_usd)
    brain = BrainAI(caps)
    t0 = time.monotonic()
    outcome = brain.pursue(converse_intent(message, pursuit_ref=pursuit_ref), context=ctx)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    root = _settle_dir(root, outcome.pursuit_id)                 # 1ᵉʳ tour : transit → chemin déterministe (A1)
    _remember(outcome.pursuit_id, root)                          # cache mémoire (accélérateur, non source de vérité)
    return to_viewmodel(outcome, need=message, mode=mode, budget_usd=budget_usd, elapsed_ms=elapsed_ms)


def _spec_fact_for(stores: Stores, outcome: Any) -> Optional[Dict[str, Any]]:
    """Retrouve le **fait Spécification** proposé par l'arc (source du build réel), par son ``fact_id``."""
    spec_id = None
    for s in outcome.steps:
        if s.get("faculty") == "specification" and s.get("status") == "proposed":
            spec_id = s.get("fact_id")
    if not spec_id:
        return None
    for f in stores.specifications.read_all():
        if f.get("specification_id") == spec_id:
            return f
    return None


def _deliver(root: Path, outcome: Any, *, actor: Any, budget_usd: float) -> Optional[Dict[str, Any]]:
    """Livraison **réelle** post-arc (JALON 2) : build confiné du site → preview locale → vérification HTTP 200
    (liée au hash) → fait ``delivered`` → **écriture mémoire minimale** (T5, depuis l'app uniquement). Ne s'exécute
    qu'après un arc **réussi** (``awaiting``/``governance``). Renvoie un résumé, ou ``None`` si non applicable."""
    from brainai_app import providers                              # résolution de capacités (aucun fournisseur ici)

    stores = Stores(proposals=ProposalStore(root / "prop.jsonl"),
                    specifications=SpecificationStore(root / "spec.jsonl"),
                    builds=BuildStore(root / "build.jsonl"))
    spec_fact = _spec_fact_for(stores, outcome)
    if spec_fact is None:
        return None
    current_spec_id = spec_fact.get("specification_id")

    # --- L8 : VERROU RÉEL de la construction significative (CHOIX 2). ``produce_build`` (manifeste confiné) a pu
    # s'exécuter, mais AUCUNE construction significative réelle sans USER GO valide. Ordre fail-closed strict :
    # (2) le manifeste Build réellement destiné à la livraison est attaché à la Spécification COURANTE ;
    # (3) reconstruire le Cost Gate depuis les faits L8 PERSISTÉS, ancré sur la spec réellement exécutée ;
    # (4) le snapshot Outcome prouve que CE gate a été présenté (jamais une autorité) : son fingerprint doit
    #     EXACTEMENT égaler le fingerprint recomputé ; (5)+(6) l'autorité UNIQUE est ``authorization_status`` relu
    # sur le store à l'instant de l'exécution, ``approved`` exact requis. Tout écart ⇒ REFUS. NO VALID CURRENT GO
    # = NO SIGNIFICANT CONSTRUCTION.
    build_ids = [s.get("fact_id") for s in outcome.steps
                 if s.get("faculty") == "build" and s.get("status") == "proposed" and s.get("fact_id")]
    if len(build_ids) != 1:
        return {"status": "refused", "reason": "build_absent_ou_ambigu", "significant_construction": False}
    build_facts = [f for f in stores.builds.read_all() if f.get("build_id") == build_ids[0]]
    if len(build_facts) != 1:
        return {"status": "refused", "reason": "build_introuvable_ou_ambigu", "significant_construction": False}
    if build_facts[0].get("spec_ref") != current_spec_id:
        return {"status": "refused", "reason": "manifeste_non_attache_a_la_spec_courante",
                "significant_construction": False}

    arch_store = SolutionArchitectureStore(root / "architectures.jsonl")
    est_store = CostEstimateStore(root / "cost_estimates.jsonl")
    auth_store = BuildAuthorizationStore(root / "build_authorizations.jsonl")
    gate = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                             pursuit_ref=outcome.pursuit_id, current_spec=spec_fact)
    if gate["status"] != "resolved":
        return {"status": "refused", "reason": "cost_gate_" + gate["status"],
                "detail": gate.get("reason"), "significant_construction": False}
    current_fp = gate["gate"]["gate_fingerprint"]

    # (4) Snapshot Outcome = PREUVE que CE gate a été présenté avant GO (jamais une autorité).
    snap = getattr(outcome, "proposal", None)
    snap_gate = snap.get("cost_gate") if isinstance(snap, dict) else None
    if not isinstance(snap_gate, dict):
        return {"status": "refused", "reason": "cost_gate_non_presente_dans_outcome",
                "significant_construction": False}
    snap_fp = snap_gate.get("gate_fingerprint")
    if not isinstance(snap_fp, str) or not snap_fp or snap_fp != current_fp:
        return {"status": "refused", "reason": "cost_gate_fingerprint_present_incoherent",
                "presented": snap_fp, "current": current_fp, "significant_construction": False}

    # (5)+(6) Autorité UNIQUE : relecture du store à l'instant de l'exécution ; ``approved`` exact requis.
    auth = authorization_status(auth_store, pursuit_ref=outcome.pursuit_id, gate_fingerprint=current_fp)
    if auth != "approved":                                        # none / declined / (fingerprint obsolète ⇒ none)
        return {"status": "refused", "reason": "no_valid_current_go", "authorization": auth,
                "gate_fingerprint": current_fp, "significant_construction": False}
    # (7) USER GO valide pour le fingerprint MATÉRIEL courant → construction significative réelle autorisée.

    delivery_caps = providers.real_delivery()                     # site_build + preview, résolus via le registre
    # Budget **gouverné** (RS-047) : env > défaut, source tracée ; ``budget_usd`` (réalisation) borne le plafond.
    budget_cfg = load_delivery_budget()
    ceiling = min(float(budget_usd), budget_cfg.ceiling_usd) if budget_usd else budget_cfg.ceiling_usd
    workspace = Workspace(root / "delivery_exec", "site")          # workspace dédié à la livraison (confiné)
    report = run_delivery(
        spec_source=spec_fact, workspace=workspace, project_id="site", pursuit_ref=outcome.pursuit_id,
        site_build=delivery_caps.site_build, preview=delivery_caps.preview,
        budget=BudgetLedger(root / "budget.jsonl", ceiling_usd=ceiling, max_calls=budget_cfg.max_calls),
        build_store=BuildStore(root / "site_build.jsonl"),
        tool_store=ToolInvocationStore(root / "tinv.jsonl"),
        run_store=BuildRunStore(root / "run_events.jsonl"),
        verification_store=VerificationStore(root / "verifications.jsonl"),
        delivered_store=DeliveredStore(root / "delivered.jsonl"))
    report["budget_config"] = budget_cfg.to_dict()                # traçabilité gouvernée (RS-047)

    # T5 — écriture mémoire minimale, DEPUIS l'app uniquement, sur succès (écriture seule, aucune récupération).
    if report.get("status") == "delivered":
        try:
            store = open_memory_store(_state_root() / "memory")
            entry = write_delivery_memory(
                store, pursuit_ref=outcome.pursuit_id, project="site",
                result=spec_fact.get("specification", {}).get("product_objective", ""),
                decisions=["convergence confirmée (humain)", "build réel confiné", "vérification HTTP 200 (hash)"],
                artifact_ref=report.get("build", {}).get("artefact"), preview_ref=report.get("preview_ref"),
                provenance_ids=report.get("provenance", {}), as_of=outcome.as_of,
                need=getattr(outcome, "need", None), status=report.get("status"))   # L3 : origine durable + statut réel livré
            report.update(report_memory_ids(entry))       # memory_11_id (canonique) + memory_id (alias égal)
        except MemoryUnavailable as exc:
            report["memory_error"] = str(exc)                     # honnête : jamais silencieux
    return report


def realize(pursuit_ref: str, *, mode: str = "demo", budget_usd: float = 2.0,
            actor: Any = None) -> Dict[str, Any]:
    """**Confirmation humaine** : poursuit la **même** Pursuit vers l'arc. Le besoin (``matured_need``) est relu
    **côté moteur** depuis les tours ; l'UI n'en fournit aucun. ``actor`` = identité **déclarée** (non vérifiée)
    à l'origine de la confirmation ; enregistrée comme fait ``convergence_confirmed`` séparé (D3). En mode
    **réel**, un arc réussi enchaîne la **livraison réelle** (build → preview → vérification → ``delivered``)."""
    caps = _capabilities(mode)
    root = _session_dir(pursuit_ref)
    ctx = _session_context(root, budget_usd=budget_usd)
    brain = BrainAI(caps)
    t0 = time.monotonic()
    outcome = brain.pursue(realize_intent(pursuit_ref, actor=actor), context=ctx)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    root = _settle_dir(root, outcome.pursuit_id)                 # no-op hors transit (realize a toujours un pursuit_ref)
    _remember(outcome.pursuit_id, root)
    vm = to_viewmodel(outcome, need=None, mode=mode, budget_usd=budget_usd, elapsed_ms=elapsed_ms)
    if mode == "real" and outcome.state == "awaiting" and outcome.wait_reason == "governance":
        delivery = _deliver(root, outcome, actor=actor, budget_usd=budget_usd)
        if delivery is not None:
            vm["delivery"] = delivery
    return vm


def authorize(pursuit_ref: str, *, presented_spec_ref: str, presented_gate_fingerprint: str,
              decision: str, actor: Any = None) -> Dict[str, Any]:
    """**USER GO** (ou refus) du Cost Gate L8 — écrit une ``build_authorization`` **inerte** (record ≠ exécution) ;
    ne déclenche AUCUNE construction (``_deliver`` reste la frontière et relira l'autorisation à l'exécution).

    Le GO est **ancré sur la proposition effectivement présentée** au caller : ``presented_spec_ref`` (la
    Spécification affichée, obligatoire) + ``presented_gate_fingerprint`` (le fingerprint affiché, obligatoire).
    ``authorize`` retrouve **EXACTEMENT** ce fait Spécification (match unique, ``proposed``, appartenant à cette
    Pursuit si le fait porte ``pursuit_ref``), reconstruit le gate depuis les faits **persistés** ancré sur CETTE
    spec, et exige ``fingerprint recomputé == presented_gate_fingerprint``. **Aucune** boucle sur l'historique : un
    ancien gate reproductible n'est PAS le gate courant. Fail-closed : ``decision`` ∈ {``approved``,``declined``} ;
    refs présentées requises ; spec introuvable/ambiguë/non ``proposed`` ⇒ refus ; fingerprint ≠ recomputé ⇒
    ``refused`` **sans écriture** (proposition obsolète/dérivée → NEW COST/GO)."""
    if decision not in ("approved", "declined"):
        return {"status": "refused", "reason": "decision_invalide", "detail": repr(decision)}
    if not isinstance(presented_spec_ref, str) or not presented_spec_ref.strip():
        return {"status": "refused", "reason": "presented_spec_ref_requis"}
    if not isinstance(presented_gate_fingerprint, str) or not presented_gate_fingerprint.strip():
        return {"status": "refused", "reason": "presented_gate_fingerprint_requis"}
    root = _session_dir(pursuit_ref)
    arch_store = SolutionArchitectureStore(root / "architectures.jsonl")
    est_store = CostEstimateStore(root / "cost_estimates.jsonl")
    auth_store = BuildAuthorizationStore(root / "build_authorizations.jsonl")
    # (3)+(4) Retrouver EXACTEMENT la Spécification présentée (match unique, proposed).
    specs = [f for f in SpecificationStore(root / "spec.jsonl").read_all()
             if f.get("specification_id") == presented_spec_ref]
    if len(specs) != 1:
        return {"status": "refused", "reason": "specification_presentee_introuvable_ou_ambigue",
                "presented_spec_ref": presented_spec_ref}
    current_spec = specs[0]
    if current_spec.get("status") != "proposed":
        return {"status": "refused", "reason": "specification_presentee_non_proposed"}
    # (5)+(6) Reconstruire le gate ancré sur CETTE spec et exiger fingerprint recomputé == présenté.
    gate = resolve_cost_gate(architecture_store=arch_store, cost_estimate_store=est_store,
                             pursuit_ref=pursuit_ref, current_spec=current_spec)
    if gate["status"] != "resolved":
        return {"status": "refused", "reason": "cost_gate_" + gate["status"], "detail": gate.get("reason")}
    match = gate["gate"]
    if match["gate_fingerprint"] != presented_gate_fingerprint:
        return {"status": "refused", "reason": "fingerprint_present_obsolete",
                "presented": presented_gate_fingerprint, "current": match["gate_fingerprint"]}
    # (7) Écriture de la BuildAuthorization inerte, avec la matière réelle (dont dépendances de l'option retenue).
    stored = auth_store.record(build_authorization_fact(
        pursuit_ref=pursuit_ref, spec_ref=match["spec_ref"], architecture_ref=match["architecture_ref"],
        selected_option_id=match["selected_option_id"], estimate_refs=match["estimate_refs"],
        gate_fingerprint=match["gate_fingerprint"], decision=decision,
        as_of=datetime.now(timezone.utc).isoformat(), actor=actor,
        material_assumptions=match["material_assumptions"], paid_providers=match["paid_providers"],
        paid_external_services=match["paid_external_services"], dependencies=match["dependencies"],
        cost_unknowns=match["cost_unknowns"]))
    return {"status": "recorded", "decision": decision, "authorization_id": stored["authorization_id"],
            "gate_fingerprint": match["gate_fingerprint"], "pursuit_id": pursuit_ref,
            "selected_option_id": match["selected_option_id"], "actor": stored["actor"]}


__all__ = ["demo_capabilities", "real_capabilities", "to_viewmodel", "run_pursuit", "converse", "realize",
           "authorize"]
