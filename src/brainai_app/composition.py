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
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, Stores, converse_intent, need_intent, realize_intent)
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.builder.turns import TurnStore
from scc_brainai_bootstrap.builder.workspace import Workspace

from brainai_app.contract import CONTRACT_VERSION

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


def real_capabilities() -> Capabilities:
    """Capacités **réelles** (facturables) — activées explicitement (mode réel)."""
    from scc_brainai_bootstrap.builder.build import ClaudeCodeBuildAdapter
    from scc_brainai_bootstrap.builder.conversation import ClaudeCodeConversationAdapter
    from scc_brainai_bootstrap.builder.specification import ClaudeCodeSpecificationAdapter
    from scc_brainai_bootstrap.builder.understanding import ClaudeCodeUnderstandingAdapter
    return Capabilities(
        understanding=ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        specification=ClaudeCodeSpecificationAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        build=ClaudeCodeBuildAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        # Conversation réelle en **sonnet** (A6) : la voix dialogique justifie la capacité supérieure ;
        # timeout 180 (R6 interdit le retry — un timeout serré fabriquerait des échecs évitables). Plafond
        # coût par appel inchangé (0,50 $). Understanding/Specification/Build restent en haiku.
        conversation=ClaudeCodeConversationAdapter(model="sonnet", max_budget_usd=0.50, timeout=180))


def _capabilities(mode: str) -> Capabilities:
    if mode == "real":
        return real_capabilities()
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


def run_pursuit(need: str, *, mode: str = "demo", budget_usd: float = 2.0) -> Dict[str, Any]:
    """**Chemin unique application → moteur** : construit le contexte (hors ``data/``), appelle **uniquement**
    ``BrainAI.pursue`` et renvoie le ViewModel. En mode ``demo`` : 0 €. En mode ``real`` : facturable."""
    caps = _capabilities(mode)
    root = Path(tempfile.mkdtemp(prefix="brainai_ui_"))          # session éphémère, HORS data/ et dépôt
    stores = Stores(proposals=ProposalStore(root / "prop.jsonl"),
                    specifications=SpecificationStore(root / "spec.jsonl"),
                    builds=BuildStore(root / "build.jsonl"))
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
    """Contexte pointé au répertoire stable, **avec** le journal des tours (``turns``) requis par le dialogue."""
    stores = Stores(proposals=ProposalStore(root / "prop.jsonl"),
                    specifications=SpecificationStore(root / "spec.jsonl"),
                    builds=BuildStore(root / "build.jsonl"),
                    turns=TurnStore(root / "turns.jsonl"))
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


def realize(pursuit_ref: str, *, mode: str = "demo", budget_usd: float = 2.0) -> Dict[str, Any]:
    """**Confirmation humaine** : poursuit la **même** Pursuit vers l'arc. Le besoin (``matured_need``) est relu
    **côté moteur** depuis les tours ; l'UI n'en fournit aucun."""
    caps = _capabilities(mode)
    root = _session_dir(pursuit_ref)
    ctx = _session_context(root, budget_usd=budget_usd)
    brain = BrainAI(caps)
    t0 = time.monotonic()
    outcome = brain.pursue(realize_intent(pursuit_ref), context=ctx)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    root = _settle_dir(root, outcome.pursuit_id)                 # no-op hors transit (realize a toujours un pursuit_ref)
    _remember(outcome.pursuit_id, root)
    return to_viewmodel(outcome, need=None, mode=mode, budget_usd=budget_usd, elapsed_ms=elapsed_ms)


__all__ = ["demo_capabilities", "real_capabilities", "to_viewmodel", "run_pursuit", "converse", "realize"]
