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
import stat
import tempfile
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, Stores, _bound_diag, consult_intent, converse_intent, need_intent,
    realize_intent, resume_intent)
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
from scc_brainai_bootstrap.builder.testing import TestResultStore
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


def propose_learning() -> Dict[str, Any]:
    """Raccord explicite Memory-11 → Learning-12 ; propositions uniquement."""
    from brainai_app.learning import propose_from_deliveries
    return propose_from_deliveries(_state_root())

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
        # Seam consult — enveloppe d'invocation reflétée telle quelle (None pour les parcours historiques).
        "invocation": getattr(outcome, "invocation", None),
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


# --------------------------------------------------------------------- #
# R-07 (rev5) — Publication SANS remplacement du transit `consult` vers son chemin déterministe.
# Primitives EXCLUSIVES relatives aux descripteurs de répertoire (linkat/mkdirat) : non-remplacement AU MOMENT
# de l'opération (FileExistsError si la cible existe déjà), sans redirection possible d'un parent. Types RÉELLEMENT
# admis par le parcours consult : fichiers réguliers (*.jsonl) et répertoires (workspace `exec` éventuel). Aucun
# lien symbolique ni type spécial n'est produit par consult ; en rencontrer un ⇒ refus explicite (jamais suivi/
# recopié). Ce n'est PAS un copieur universel : uniquement la finalisation de consult.
# --------------------------------------------------------------------- #
class _UnexpectedTransitEntry(Exception):
    """Entrée de transit d'un type NON admis par consult (lien symbolique ou type spécial) — refus explicite."""


# Opérations requises en mode "relatif à un descripteur" (évite la redirection d'un parent au moment de l'op).
# ``os.stat(..., follow_symlinks=False)`` (fstatat) est utilisé au lieu de ``os.lstat`` : sur macOS 3.9, ``os.lstat``
# n'est pas dans ``supports_dir_fd`` alors que ``os.stat`` l'est (avec ``supports_follow_symlinks``).
_DIRFD_OPS = {os.link, os.mkdir, os.unlink, os.rmdir, os.stat, os.open}
# R07-C : références CAPTURÉES À L'IMPORT (objets originaux). La garde de disponibilité teste ces objets, jamais un
# attribut ``os.link``/``os.stat`` re-résolu — un monkeypatch de test sur ``os.link`` ne fausse donc plus la garde
# (l'ancienne forme ``os.link in os.supports_follow_symlinks`` renvoyait à tort ``mecanisme_indisponible``).
_FOLLOW_OPS = {os.link, os.stat}
_O_DIR_NOFOLLOW = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _publish_dir_contents(src_fd: int, dst_fd: int, published: List[str], removed: List[str],
                          prefix: str = "") -> None:
    """Publie le CONTENU du répertoire ouvert ``src_fd`` dans ``dst_fd`` (nôtre, fraîchement créé, vide) par
    primitives EXCLUSIVES relatives aux descripteurs. ``os.link`` (linkat, ``follow_symlinks=False``) et ``os.mkdir``
    (mkdirat) lèvent ``FileExistsError`` si la cible existe déjà ⇒ **jamais de remplacement**. Un lien physique ne
    duplique pas les octets. R07-B : ``published`` reçoit le chemin DÈS que le lien + l'identité (inode/dev) sont
    établis à destination — AVANT toute tentative de ``os.unlink`` — ; ``removed`` ne le reçoit qu'APRÈS le retrait
    réussi de l'ancien nom source. Si ``os.unlink`` échoue, le fichier reste sous LES DEUX noms : il figure dans
    ``published`` mais PAS dans ``removed`` (état honnête, jamais faux par omission). Types admis : réguliers +
    répertoires ; tout autre ⇒ ``_UnexpectedTransitEntry`` (jamais suivi/recopié)."""
    for name in sorted(os.listdir(src_fd)):
        st = os.stat(name, dir_fd=src_fd, follow_symlinks=False)   # fstatat, NE SUIT PAS un lien
        rel = prefix + name
        if stat.S_ISREG(st.st_mode):
            os.link(name, name, src_dir_fd=src_fd, dst_dir_fd=dst_fd,
                    follow_symlinks=False)                     # EEXIST si présent à destination ; ne suit pas un lien
            ds = os.stat(name, dir_fd=dst_fd, follow_symlinks=False)   # identité établie à destination
            if not (stat.S_ISREG(ds.st_mode) and ds.st_ino == st.st_ino and ds.st_dev == st.st_dev):
                raise OSError("identité du fichier publié non établie: " + rel)   # aucun published/unlink dans ce cas
            published.append(rel)                              # PUBLIÉ à destination (avant toute tentative d'unlink)
            os.unlink(name, dir_fd=src_fd)                     # retrait de l'ancien nom (peut échouer ⇒ double nom)
            removed.append(rel)                                # ancien nom RÉELLEMENT retiré
        elif stat.S_ISDIR(st.st_mode):
            os.mkdir(name, dir_fd=dst_fd)                      # création EXCLUSIVE (EEXIST-safe)
            sub_src = os.open(name, _O_DIR_NOFOLLOW, dir_fd=src_fd)   # O_NOFOLLOW : refuse un répertoire aliasé par lien
            try:
                sub_dst = os.open(name, _O_DIR_NOFOLLOW, dir_fd=dst_fd)
                try:
                    _publish_dir_contents(sub_src, sub_dst, published, removed, rel + "/")
                finally:
                    os.close(sub_dst)
            finally:
                os.close(sub_src)
            os.rmdir(name, dir_fd=src_fd)                      # sous-répertoire source vidé (rmdir ≠ rmtree)
        else:
            raise _UnexpectedTransitEntry(rel)                # lien symbolique / type spécial : refus explicite


def _finalize_consult_transit(root: Path, target: Path, authorized_anchor: Path) -> Dict[str, Any]:
    """Publie le transit ``root`` (``.staging-``) vers ``target`` (chemin déterministe) SANS remplacement (R-07).
    Renvoie un dict de finalisation SANS ``provenance_durable`` (résolu par l'appelant selon le fait enregistré).
    ``settled=True`` EXIGE une destination réellement établie par le chemin autorisé ; jamais via un alias/lien.

    R07-A (rev7) : ``authorized_anchor`` est l'**origine autorisée DÉCLARÉE par l'appelant** (``consult`` passe la
    racine d'état applicative :func:`_state_root`) — l'autorisation ne vient donc PAS d'un ``parent.parent`` dérivé du
    chemin cible. On EXIGE que le parent (ex. ``pursuits/``) soit **directement sous cet ancrage** ; on ouvre l'ancrage
    par chemin avec ``O_NOFOLLOW`` (son dernier composant ne peut être un lien), puis le PARENT **relativement à
    l'ancrage** (encore ``O_NOFOLLOW``) ; ni l'ancre ni le parent ne sont atteints via un lien redirigé. Revendication
    et ouvertures se font RELATIVEMENT au parent confiné — plus aucun ``os.mkdir(str(target))``/``os.open(str(target))``
    absolu, et **aucun ``mkdir`` de parent par chemin** (le parent existe déjà : le transit vit dedans)."""
    # R07-B : une cible lien symbolique n'est JAMAIS une finalisation (resolve()==resolve() ne suffit pas).
    if target.is_symlink():
        return {"settled": False, "reason": "cible_lien_symbolique", "transit_kept": str(root)}
    # consult standalone passe TOUJOURS par un transit ``.staging-`` ; tout autre point de départ est indéterminé.
    if not root.name.startswith(".staging-"):
        return {"settled": False, "reason": "transit_inattendu", "transit_kept": str(root)}
    # transit et destination doivent partager le même parent (invariant du parcours standalone).
    if root.parent != target.parent:
        return {"settled": False, "reason": "transit_inattendu", "transit_kept": str(root)}
    # R07-A : le parent DOIT être directement sous l'ancrage AUTORISÉ déclaré (autorisation explicite, non dérivée).
    if target.parent.parent != authorized_anchor:
        return {"settled": False, "reason": "ancrage_non_autorise", "transit_kept": str(root)}
    tname = target.name
    rname = root.name
    pname = target.parent.name
    if (not tname) or ("/" in tname) or tname in (".", "..") or (not rname) or ("/" in rname) \
            or (not pname) or ("/" in pname) or pname in (".", ".."):
        return {"settled": False, "reason": "finalisation_impossible", "transit_kept": str(root)}
    # Mécanisme requis : opérations relatives aux descripteurs + lien/stat exclusifs. Indisponible ⇒ échec explicite.
    if not (_DIRFD_OPS <= os.supports_dir_fd and _FOLLOW_OPS <= os.supports_follow_symlinks):
        return {"settled": False, "reason": "mecanisme_indisponible", "transit_kept": str(root)}
    anchor = authorized_anchor                                # origine autorisée DÉCLARÉE (aucun mkdir de parent ici)
    published: List[str] = []
    removed: List[str] = []
    anchor_fd = None
    parent_fd = None
    src_fd = None
    dst_fd = None

    def _partial(reason, exc=None):                            # état HONNÊTE : distingue publié / source retirée / double nom
        info = {"settled": False, "reason": reason, "transit_kept": str(root), "target": str(target),
                "published": list(published), "source_retired": list(removed),
                "both_names": [p for p in published if p not in removed]}
        if exc is not None:
            info["error"] = _bound_diag(str(exc))
        return info

    try:
        # R07-A (rev7) : ANCRAGE autorisé. Le parent (ex. ``pursuits``) et son ancêtre (ex. ``state``) ne doivent pas
        # être atteints via un lien redirigé. On ouvre l'ANCRAGE (grand-parent) par chemin avec ``O_NOFOLLOW`` — son
        # dernier composant ne peut donc être un lien — puis on ouvre le PARENT **relativement à ce descripteur**,
        # encore ``O_NOFOLLOW`` : ni l'ancre ni le parent ne sont suivis comme lien. Revendication et ouvertures se
        # font ensuite RELATIVEMENT au parent confiné. Les composants AU-DESSUS de l'ancrage sont la frontière de
        # confiance applicative (racine d'état). Identité indéterminée / primitive indisponible ⇒ échec explicite.
        try:
            anchor_fd = os.open(str(anchor), _O_DIR_NOFOLLOW)   # ancrage : dernier composant garanti non-lien
        except OSError as exc:
            return {"settled": False, "reason": "finalisation_impossible",
                    "transit_kept": str(root), "error": _bound_diag(str(exc))}
        if not stat.S_ISDIR(os.fstat(anchor_fd).st_mode):
            return {"settled": False, "reason": "finalisation_impossible", "transit_kept": str(root)}
        try:
            parent_fd = os.open(pname, _O_DIR_NOFOLLOW, dir_fd=anchor_fd)   # parent confiné SOUS l'ancrage (non-lien)
        except OSError as exc:
            return {"settled": False, "reason": "finalisation_impossible",
                    "transit_kept": str(root), "error": _bound_diag(str(exc))}
        if not stat.S_ISDIR(os.fstat(parent_fd).st_mode):
            return {"settled": False, "reason": "finalisation_impossible", "transit_kept": str(root)}
        try:
            os.mkdir(tname, dir_fd=parent_fd)                 # REVENDICATION exclusive RELATIVE au parent confiné
        except FileExistsError:
            return {"settled": False, "reason": "destination_existante", "transit_kept": str(root)}
        except OSError as exc:
            return {"settled": False, "reason": "finalisation_impossible",
                    "transit_kept": str(root), "error": _bound_diag(str(exc))}
        try:
            dst_fd = os.open(tname, _O_DIR_NOFOLLOW, dir_fd=parent_fd)   # ouverture RELATIVE, O_NOFOLLOW
            src_fd = os.open(rname, _O_DIR_NOFOLLOW, dir_fd=parent_fd)   # transit sous le MÊME parent épinglé
        except OSError as exc:
            return {"settled": False, "reason": "finalisation_impossible",
                    "transit_kept": str(root), "target": str(target), "error": _bound_diag(str(exc))}
        try:
            _publish_dir_contents(src_fd, dst_fd, published, removed)
        except _UnexpectedTransitEntry as exc:
            info = _partial("type_inattendu", exc); return info
        except FileExistsError as exc:
            info = _partial("collision_au_transfert", exc); return info   # jamais de remplacement
        except OSError as exc:
            info = _partial("finalisation_partielle", exc); return info   # unlink/link/identité : double nom possible
        # transit vidé : suppression NON destructive du répertoire vide, RELATIVE au parent (jamais rmtree)
        try:
            os.rmdir(rname, dir_fd=parent_fd)
        except OSError as exc:
            info = _partial("transit_non_supprimable", exc); return info  # journal SOUS target ; jamais settle faux
    finally:
        for fd in (src_fd, dst_fd, parent_fd, anchor_fd):
            if fd is not None:
                os.close(fd)
    return {"settled": True, "reason": None, "target": str(target),
            "published": list(published), "source_retired": list(removed), "both_names": []}


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


def _deliver(root: Path, outcome: Any, *, actor: Any, budget_usd: float,
             build_provider: Optional[str] = None,
             correction_ref: Optional[str] = None) -> Optional[Dict[str, Any]]:
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

    # L9 — BuildProvider **opt-in** : ``build_provider`` (sélecteur OPAQUE) transmis tel quel à l'infrastructure
    # (résolution des noms de fournisseur UNIQUEMENT dans providers.py, I9 — ce module n'en connaît aucun).
    # ``None`` ⇒ appel **strictement historique** ``real_delivery()`` (défaut résolu par l'infrastructure, chemin
    # inchangé) ; sinon sélection explicite (provider inconnu ⇒ ``LookupError`` fail-closed, aucun fallback). Ce
    # sélecteur ne contourne JAMAIS le verrou ci-dessus.
    delivery_caps = (providers.real_delivery() if build_provider is None
                     else providers.real_delivery(build_provider=build_provider))   # site_build + test_run + preview
    # Budget **gouverné** (RS-047) : env > défaut, source tracée ; ``budget_usd`` (réalisation) borne le plafond.
    budget_cfg = load_delivery_budget()
    ceiling = min(float(budget_usd), budget_cfg.ceiling_usd) if budget_usd else budget_cfg.ceiling_usd
    workspace = Workspace(root / "delivery_exec", "site")          # workspace dédié à la livraison (confiné)
    delivery_args = dict(
        spec_source=spec_fact, workspace=workspace, project_id="site", pursuit_ref=outcome.pursuit_id,
        site_build=delivery_caps.site_build, test_run=delivery_caps.test_run,
        preview=delivery_caps.preview,
        budget=BudgetLedger(root / "budget.jsonl", ceiling_usd=ceiling, max_calls=budget_cfg.max_calls),
        build_store=BuildStore(root / "site_build.jsonl"),
        tool_store=ToolInvocationStore(root / "tinv.jsonl"),
        run_store=BuildRunStore(root / "run_events.jsonl"),
        verification_store=VerificationStore(root / "verifications.jsonl"),
        test_result_store=TestResultStore(root / "test_results.jsonl"),
        delivered_store=DeliveredStore(root / "delivered.jsonl"))
    if correction_ref is None:
        report = run_delivery(**delivery_args)
    else:
        from brainai_app.delivery.corrections import CorrectionError, correction_attempt
        try:
            with correction_attempt(root=root, pursuit_ref=outcome.pursuit_id,
                                    correction_id=correction_ref, spec=spec_fact,
                                    gate_fingerprint=current_fp, ceiling_usd=ceiling,
                                    max_calls=budget_cfg.max_calls, build_provider=build_provider) as attempt:
                delivery_args.update(workspace=attempt['workspace'],
                                     parent_run_ref=attempt['parent_run_ref'], correction_ref=correction_ref,
                                     workspace_ref=str(attempt['workspace'].path.relative_to(root.resolve())))
                report = run_delivery(**delivery_args)
                attempt.update(run_ref=report['provenance'].get('run_id'), status=report['status'])
        except CorrectionError as exc:
            return {'status': 'refused', 'reason': str(exc), 'significant_construction': False}
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
            actor: Any = None, build_provider: Optional[str] = None) -> Dict[str, Any]:
    """**Confirmation humaine** : poursuit la **même** Pursuit vers l'arc. Le besoin (``matured_need``) est relu
    **côté moteur** depuis les tours ; l'UI n'en fournit aucun. ``actor`` = identité **déclarée** (non vérifiée)
    à l'origine de la confirmation ; enregistrée comme fait ``convergence_confirmed`` séparé (D3). En mode
    **réel**, un arc réussi enchaîne la **livraison réelle** (build → preview → vérification → ``delivered``).

    L9 : ``build_provider`` est un **sélecteur opaque** du BuildProvider de ``build.site`` — transmis tel quel à
    ``_deliver`` puis à l'infrastructure (résolution des noms UNIQUEMENT dans :mod:`brainai_app.providers`, I9).
    ``None`` ⇒ **défaut historique** résolu par l'infrastructure (comportement inchangé ; ce module ne connaît
    aucun nom de fournisseur, I9) ; provider inconnu ⇒ ``LookupError`` fail-closed (aucun fallback silencieux).
    N'affecte **jamais** le verrou USER GO / Cost Gate de ``_deliver``."""
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
        delivery = _deliver(root, outcome, actor=actor, budget_usd=budget_usd,
                            build_provider=build_provider)
        if delivery is not None:
            vm["delivery"] = delivery
    return vm


def resume(pursuit_ref: str) -> Dict[str, Any]:
    """Ré-attache une Pursuit depuis le disque, sans cognition ni replay de livraison.

    Le dernier dialogue, la continuité Memory-11 et les états d'exécution sont
    distincts. Ce rappel n'émet ni tour, ni confirmation, ni GO, ni nouveau run.
    """
    import re
    from brainai_app.continuity import ReadOnlyCapability, read_delivery_state
    from brainai_app.recall import _resolve_pursuit_dir_readonly, retrieve_pursuit

    if not isinstance(pursuit_ref, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', pursuit_ref):
        return {'status': 'refused', 'reason': 'pursuit_ref_invalide'}
    root = _resolve_pursuit_dir_readonly(pursuit_ref)
    if root is None or not root.is_dir() or root.is_symlink():
        return {'status': 'refused', 'reason': 'session_absente_ou_invalide'}
    guard = ReadOnlyCapability()
    brain = BrainAI(Capabilities(understanding=guard, specification=guard, build=guard))
    outcome = brain.pursue(resume_intent(pursuit_ref), context=_session_context(root, budget_usd=1.0))
    if outcome.continuity is None:
        return {'status': 'refused', 'reason': outcome.refused}
    try:
        delivery = read_delivery_state(root, pursuit_ref)
        memory = retrieve_pursuit(pursuit_ref, strict=True)
    except Exception:
        # Inclut les erreurs typées du composant Memory-11 chargé dynamiquement.
        # Ne pas exposer des chemins/configs/secrets via un message d'exception brut.
        return {'status': 'refused', 'reason': 'preuves_de_continuite_illisibles_ou_incoherentes'}
    return {'status': 'resumed', 'pursuit_ref': pursuit_ref, 'execution_authorized': False,
            'dialogue': {'state': outcome.state, 'wait_reason': outcome.wait_reason,
                         'reply': outcome.reply, 'proposal': outcome.proposal,
                         'refused': outcome.refused, 'continuity': outcome.continuity},
            'memory': memory, 'delivery': delivery}


def propose_delivery_correction(pursuit_ref: str, *, parent_run_ref: str,
                                test_result_ref: str, suggestion: str) -> Dict[str, Any]:
    """Prépare une proposition inerte depuis les preuves d'une session existante.

    Première surface Python du lot correctif ; ne matérialise pas une session
    absente et ne donne aucune permission de reconstruire ou de retester.
    """
    import re
    from brainai_app.delivery.corrections import CorrectionError, propose_correction

    if not isinstance(pursuit_ref, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', pursuit_ref):
        return {"status": "refused", "reason": "pursuit_ref_invalide"}
    with _SESSIONS_LOCK:
        root = _SESSIONS.get(pursuit_ref)
    if root is None:
        root = _pursuit_dir(pursuit_ref)
        if not root.exists():
            root = _legacy_lookup(pursuit_ref)
    if root is None or not root.is_dir():
        return {"status": "refused", "reason": "session_absente"}
    try:
        fact = propose_correction(root=root, pursuit_ref=pursuit_ref,
                                  parent_run_ref=parent_run_ref, test_result_ref=test_result_ref,
                                  suggestion=suggestion)
    except CorrectionError as exc:
        return {"status": "refused", "reason": str(exc)}
    return {"status": "proposed", "correction": fact, "execution_authorized": False}


def authorize_delivery_correction(pursuit_ref: str, *, correction_ref: str,
                                  presented_spec_ref: str, presented_gate_fingerprint: str,
                                  decision: str, budget_usd: float = 2.0,
                                  build_provider: Optional[str] = None, actor: Any = None) -> Dict[str, Any]:
    """Accord correctif inerte, après le GO du Cost Gate, pour une seule tentative.

    Le budget approuvé est le plafond total partagé avec les tentatives passées.
    La spécification corrigée doit déjà avoir été présentée puis autorisée.
    """
    import re
    from brainai_app.delivery.corrections import CorrectionError, authorize_correction
    if not isinstance(pursuit_ref, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', pursuit_ref):
        return {'status': 'refused', 'reason': 'pursuit_ref_invalide'}
    with _SESSIONS_LOCK:
        root = _SESSIONS.get(pursuit_ref)
    if root is None:
        root = _pursuit_dir(pursuit_ref)
        if not root.exists():
            root = _legacy_lookup(pursuit_ref)
    if root is None or not root.is_dir():
        return {'status': 'refused', 'reason': 'session_absente'}
    cfg = load_delivery_budget()
    ceiling = min(float(budget_usd), cfg.ceiling_usd) if budget_usd else cfg.ceiling_usd
    try:
        fact = authorize_correction(root=root, pursuit_ref=pursuit_ref, correction_id=correction_ref,
                                    spec_ref=presented_spec_ref, gate_fingerprint=presented_gate_fingerprint,
                                    decision=decision, ceiling_usd=ceiling, max_calls=cfg.max_calls,
                                    build_provider=build_provider, actor=actor)
    except CorrectionError as exc:
        return {'status': 'refused', 'reason': str(exc)}
    return {'status': 'recorded', 'decision': decision, 'authorization': fact}


def execute_delivery_correction(pursuit_ref: str, *, correction_ref: str,
                                presented_spec_ref: str, presented_gate_fingerprint: str,
                                budget_usd: float = 2.0, build_provider: Optional[str] = None,
                                actor: Any = None) -> Dict[str, Any]:
    """Reconstruit une spec corrigée déjà produite et autorisée, une seule fois.

    Raccord Python explicite : aucun nouvel appel cognitif pour redécouvrir la
    spec autorisée. Les références présentées et les sources persistées sont
    revérifiées ; la livraison et l'écriture Memory-11 restent celles de _deliver.
    """
    import re
    from types import SimpleNamespace
    from brainai_app.delivery.corrections import CorrectionError, correction_target
    if not isinstance(pursuit_ref, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', pursuit_ref):
        return {'status': 'refused', 'reason': 'pursuit_ref_invalide'}
    with _SESSIONS_LOCK:
        root = _SESSIONS.get(pursuit_ref)
    if root is None:
        root = _pursuit_dir(pursuit_ref)
        if not root.exists():
            root = _legacy_lookup(pursuit_ref)
    if root is None or not root.is_dir():
        return {'status': 'refused', 'reason': 'session_absente'}
    try:
        spec, build_ref = correction_target(root, pursuit_ref, presented_spec_ref,
                                            presented_gate_fingerprint)
    except CorrectionError as exc:
        return {'status': 'refused', 'reason': str(exc)}
    # Projection des faits existants, jamais un nouveau manifeste ou un GO synthétique.
    outcome = SimpleNamespace(
        pursuit_id=pursuit_ref, as_of=datetime.now(timezone.utc).isoformat(), need=None,
        steps=[{'faculty': 'specification', 'status': 'proposed', 'fact_id': spec['specification_id']},
               {'faculty': 'build', 'status': 'proposed', 'fact_id': build_ref}],
        proposal={'cost_gate': {'gate_fingerprint': presented_gate_fingerprint}})
    return _deliver(root, outcome, actor=actor, budget_usd=budget_usd,
                    build_provider=build_provider, correction_ref=correction_ref)


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


def consult(capability: str, *, decision_source: str = "explicit_request", mode: str = "demo",
            budget_usd: float = 2.0) -> Dict[str, Any]:
    """Consultation **STANDALONE** d'une capacité typée (seam D-2 ; D-1 : aucun rattachement). Base **démo** dans les
    deux modes (les facultés understanding/specification/build ne sont **jamais** invoquées par ``_consult`` ⇒ aucune
    résolution cognitive facturable, aucun LLM/builder/subprocess) + capacité **observability RÉELLE** injectée
    (Option B). Données réelles (lecture locale) dans les deux modes ; coût ``unavailable``. La provenance
    ``ToolInvocation`` est écrite sous le répertoire **déterministe** de la Pursuit (transit → ``_settle_dir``),
    donc **relisible après redémarrage**. ``Stores``/``RunContext`` inchangés (les stores obligatoires ne sont jamais
    écrits par consult)."""
    from brainai_app import providers                          # résolution de capacité (aucun fournisseur ici, I9)
    root = _session_dir(None)                                  # standalone : répertoire de transit sous pursuits/
    tool_store = ToolInvocationStore(root / "tinv.jsonl")      # provenance de session (lié dans la capacité, Option B)
    caps = replace(demo_capabilities(),
                   observability=providers.resolve_observability_capability(tool_store=tool_store))
    stores = Stores(proposals=ProposalStore(root / "prop.jsonl"),
                    specifications=SpecificationStore(root / "spec.jsonl"),
                    builds=BuildStore(root / "build.jsonl"))   # requis par RunContext ; JAMAIS écrits par consult
    ctx = RunContext(budget_usd=budget_usd, project_id="session",
                     workspace=Workspace(root / "exec", "session"), stores=stores)
    brain = BrainAI(caps)
    t0 = time.monotonic()
    outcome = brain.pursue(consult_intent(capability, decision_source=decision_source), context=ctx)  # SEUL appel moteur
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    vm = to_viewmodel(outcome, need=None, mode=mode, budget_usd=budget_usd, elapsed_ms=elapsed_ms)
    # R-07 (rev5) : publication de `consult` **sans remplacement au moment de l'opération**. La revendication
    # ``os.mkdir(target)`` (exclusive) empêche déjà de remplacer une destination vide/non vide. Mais un
    # ``exists()`` suivi d'un ``os.rename`` ordinaire garderait une fenêtre TOCTOU ; on publie donc le contenu par
    # **primitives exclusives relatives aux descripteurs** — ``linkat`` (fichiers réguliers) et ``mkdirat``
    # (répertoires), toutes deux **``FileExistsError`` si la cible existe déjà** — sans redirection possible d'un
    # parent (voir :func:`_finalize_consult_transit`). Un lien physique **ne duplique pas** les octets : l'ancien
    # nom source n'est retiré qu'APRÈS publication réussie ET identité (inode/dev) établie à destination. Types
    # admis par consult : réguliers + répertoires ; tout **lien/symlink ou type spécial est REFUSÉ** (jamais suivi/
    # recopié). Une cible ``target`` lien symbolique n'est **jamais** une finalisation. Aucun fallback vers rename/
    # replace/copie ; FS différent ou mécanisme indisponible ⇒ **échec explicite, données conservées**. Sur panne
    # tardive : état partiel **honnête** (``published`` = entrées réellement sous ``target`` ; reste sous
    # ``transit_kept``), **aucun** rmtree/rollback/nettoyage/retry, cache **non réaffecté**, jamais ``settled=True``.
    inv = vm.get("invocation") if isinstance(vm.get("invocation"), dict) else {}
    recorded = (inv.get("provenance") == "recorded_and_referenced"
                and isinstance(inv.get("tool_ref"), str) and bool(inv.get("tool_ref")))
    target = _pursuit_dir(outcome.pursuit_id)
    # R07-A : ancrage AUTORISÉ déclaré = racine d'état applicative (le parent ``pursuits/`` doit être directement dessous).
    fin = _finalize_consult_transit(root, target, _state_root())   # publication exclusive sans remplacement (R-07)
    if fin.get("settled"):
        _remember(outcome.pursuit_id, target)                # cache → chemin déterministe UNIQUEMENT sur settle réel
        fin["provenance_durable"] = bool(recorded)           # durable ⇔ fait réellement enregistré ET finalisation affirmée
    else:
        fin["provenance_durable"] = False                    # refus/panne/indétermination : jamais durable ; cache NON réaffecté
    vm["finalization"] = fin
    return vm


__all__ = ["demo_capabilities", "real_capabilities", "to_viewmodel", "run_pursuit", "converse", "realize",
           "authorize", "consult", "resume", "propose_delivery_correction", "authorize_delivery_correction",
           "execute_delivery_correction", "propose_learning"]
