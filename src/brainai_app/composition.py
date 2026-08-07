"""Composition root — **câble** BrainAI et **projette** l'``Outcome`` vers un ViewModel. Aucune logique métier.

Responsabilités (et rien de plus) : construire BrainAI, **injecter** ses capacités (démo factices 0 € / réelles
facturables), bâtir Stores / RunContext / Workspace **hors ``data/``**, appeler **exclusivement**
``BrainAI.pursue(...)``, puis **refléter** l'``Outcome`` en ViewModel. Le ViewModel est **piloté par ce que
BrainAI renvoie** (``Outcome.steps``) : **aucune** liste de facultés codée en dur (libellé inconnu → nom brut).
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.builder.brainai import BrainAI, Capabilities, RunContext, Stores, need_intent
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
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


def demo_capabilities() -> Capabilities:
    """Capacités **démo** (0 €) — pour développer/exercer l'interface sans dépense."""
    return Capabilities(
        understanding=_DemoCapability("understanding", _demo_envelope(_DEMO_BRIEF)),
        specification=_DemoCapability("specification", _demo_envelope(_DEMO_SPEC)),
        build=_DemoCapability("build", _demo_envelope(_DEMO_MANIFEST)))


def real_capabilities() -> Capabilities:
    """Capacités **réelles** (facturables) — activées explicitement (mode réel)."""
    from scc_brainai_bootstrap.builder.build import ClaudeCodeBuildAdapter
    from scc_brainai_bootstrap.builder.specification import ClaudeCodeSpecificationAdapter
    from scc_brainai_bootstrap.builder.understanding import ClaudeCodeUnderstandingAdapter
    return Capabilities(
        understanding=ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        specification=ClaudeCodeSpecificationAdapter(model="haiku", max_budget_usd=0.50, timeout=180),
        build=ClaudeCodeBuildAdapter(model="haiku", max_budget_usd=0.50, timeout=180))


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


def to_viewmodel(outcome: Any, *, need: str, mode: str, budget_usd: float, elapsed_ms: int) -> Dict[str, Any]:
    """Projette un ``Outcome`` en ViewModel de transport. **Piloté par ``Outcome.steps``** — aucun nombre de
    facultés codé en dur ; un libellé inconnu retombe sur le nom de faculté."""
    steps: List[Dict[str, Any]] = [
        {"faculty": s.get("faculty"), "status": s.get("status"),
         "label": _LABELS.get(s.get("faculty"), s.get("faculty")),
         "progress_label": _PROGRESS.get(s.get("faculty"), s.get("faculty")),
         "fact_id": s.get("fact_id")}
        for s in outcome.steps
    ]
    deliverables = [{"label": st["label"], "fact_id": st["fact_id"]}
                    for st in steps if st["status"] == "proposed"]
    return {
        "conversation": {"need": need, "reply": _reply(outcome)},
        "pursuit": {
            "pursuit_id": outcome.pursuit_id, "state": outcome.state, "wait_reason": outcome.wait_reason,
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


__all__ = ["demo_capabilities", "real_capabilities", "to_viewmodel", "run_pursuit"]
