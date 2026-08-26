"""Build runner asynchrone — worker in-process, ``BuildStep`` append-only, ordonnancement Kahn (JALON 2, T2/A2).

Orchestre les étapes d'une **livraison** (build réel → vérification) dans un **worker in-process** (thread). Les
faits de run et d'étape sont **append-only** (``BuildRunStore``) ; les états reprennent le vocabulaire de
``16_EXECUTION`` (run : ``prepared``/``running``/``succeeded``/``failed``/``cancelled``/``interrupted`` ; étape :
``pending``/``running``/``succeeded``/``failed``/``skipped``) — aucune prolifération de statuts.

Garde-fous :

* **ordonnancement** par le vrai Kahn de ``14_PLANNING`` (via :mod:`.planning`), jamais recopié ;
* **budget** borné (:class:`BudgetLedger`) : pré-garde AVANT toute étape facturable ; ``budget_exhausted`` ⇒
  arrêt réel ;
* **timeout** réel (déjà appliqué par ``run_confined`` au niveau outil ; le run n'invente pas d'état) ;
* **annulation** à **ordre honnête** (A2) : (1) l'acte humain émet un fait d'annulation ; (2) l'étape en vol
  **termine réellement** et enregistre son fait terminal ; (3) le run est ensuite marqué ``cancelled`` ;
* **jamais de retry silencieux** : une étape ``failed`` arrête le run ;
* **run interrompu** (A2) : au démarrage, tout run laissé non terminal (worker mort avec l'app) est **constaté**
  par un fait ``run_interrupted`` (jamais de reprise/disparition/échec silencieux) ; la reprise est un **nouveau
  run** référençant le précédent (``prev_run_ref``), gouvernée par l'appelant.

Réserve consignée (T1/T2) : le worker **in-process** suffit à J2 ; un **process OS séparé** (survie à la mort de
l'app) est une dette RS-2 (RS-040). Stdlib pur ; ce module vit hors ``builder/`` (peut raccorder ``14_PLANNING``).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id
from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.planning import PlanningUnavailable, order_steps
# Vocabulaire d'états **enveloppé** du vrai 16_EXECUTION (source unique) — voir :mod:`.vocab`.
from brainai_app.delivery.vocab import (
    RUN_CANCELLED, RUN_FAILED, RUN_INTERRUPTED, RUN_PREPARED, RUN_RUNNING, RUN_SUCCEEDED, RUN_TERMINAL,
    STEP_FAILED, STEP_PENDING, STEP_RUNNING, STEP_SKIPPED, STEP_SUCCEEDED, STEP_TERMINAL)

_RUN_TERMINAL = RUN_TERMINAL
_STEP_TERMINAL = STEP_TERMINAL


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepResult:
    """Résultat **réel** d'une étape (renvoyé par son exécuteur). ``cost`` = coût réel ``{value,kind}`` ou None."""
    status: str                                   # succeeded | failed
    detail: str = ""
    refs: Dict[str, Any] = field(default_factory=dict)   # ex. {"build_id":…, "verification_id":…}
    cost: Optional[Dict[str, Any]] = None


@dataclass
class Step:
    """Étape de build. ``run`` : exécuteur réel (aucune décision hors de lui). ``billable`` : franchit la
    frontière payante (⇒ pré-garde budget). ``max_usd`` : enveloppe max de l'appel (garde 1), si connue."""
    name: str
    kind: str                                     # "build" | "verify" | …
    run: Callable[[], StepResult]
    billable: bool = False
    max_usd: Optional[float] = None
    prerequisites: List[str] = field(default_factory=list)


class BuildRunStore:
    """Journal **append-only** des faits run/étape (fichier injecté). Un fait par transition — rien n'écrase."""

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def append(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(fact, ensure_ascii=False) + "\n")
        return fact


# --------------------------------------------------------------------- #
# A2 — constat des runs interrompus (worker mort avec l'app), au démarrage
# --------------------------------------------------------------------- #
def detect_interrupted_runs(store: BuildRunStore, *, clock: Callable[[], str] = _system_clock,
                            pursuit_ref: Optional[str] = None) -> List[Dict[str, Any]]:
    """Constate tout run laissé **non terminal** (dernier fait run ∈ {prepared, running}) : émet **un** fait
    ``run_interrupted`` append-only (jamais de reprise/échec/disparition silencieux). Idempotent : un run déjà
    constaté ``interrupted`` n'est pas reconstatté. Retourne les faits émis."""
    facts = store.read_all()
    last_run_status: Dict[str, str] = {}
    run_meta: Dict[str, Dict[str, Any]] = {}
    step_last: Dict[str, Dict[str, str]] = {}
    already_constated: set = set()          # runs déjà constatés interrompus (idempotence)
    for f in facts:
        if f.get("fact_type") == "build_run":
            rid = f.get("run_id")
            last_run_status[rid] = f.get("status")
            run_meta.setdefault(rid, f)
        elif f.get("fact_type") == "build_step":
            rid = f.get("run_ref")
            step_last.setdefault(rid, {})[f.get("step")] = f.get("status")
        elif f.get("fact_type") == "run_interrupted":
            already_constated.add(f.get("run_ref"))

    emitted: List[Dict[str, Any]] = []
    for rid, status in last_run_status.items():
        if status in _RUN_TERMINAL or rid in already_constated:   # jamais reconstaté (append-only honnête)
            continue
        meta = run_meta.get(rid, {})
        if pursuit_ref is not None and meta.get("pursuit_ref") != pursuit_ref:
            continue
        non_terminal_steps = sorted(s for s, st in step_last.get(rid, {}).items() if st not in _STEP_TERMINAL)
        as_of = clock()
        fact = {"fact_type": "run_interrupted", "run_ref": rid,
                "pursuit_ref": meta.get("pursuit_ref"), "interrupted_steps": non_terminal_steps,
                "last_run_status": status, "as_of": as_of}
        fact["event_id"] = short_id("runx", {"run_ref": rid, "as_of": as_of})
        emitted.append(store.append(fact))
    return emitted


# --------------------------------------------------------------------- #
# Le runner
# --------------------------------------------------------------------- #
class BuildRunner:
    """Worker **in-process** exécutant les étapes ordonnancées d'une livraison. ``run()`` synchrone (bloquant) ou
    ``start()`` asynchrone (thread) + ``wait()``/``status()`` (polling). Annulation coopérative à ordre honnête."""

    def __init__(self, store: BuildRunStore, budget: BudgetLedger, *,
                 pursuit_ref: str, clock: Callable[[], str] = _system_clock,
                 config: Any = None, prev_run_ref: Optional[str] = None):
        self._store = store
        self._budget = budget
        self._pursuit_ref = pursuit_ref
        self._clock = clock
        self._config = config
        self._prev_run_ref = prev_run_ref
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._run_id: Optional[str] = None
        self._final: Optional[Dict[str, Any]] = None

    # -- faits ----------------------------------------------------------- #
    def _run_fact(self, status: str, *, steps: Optional[List[str]] = None,
                  detail: str = "") -> Dict[str, Any]:
        as_of = self._clock()
        fact = {"fact_type": "build_run", "run_id": self._run_id, "pursuit_ref": self._pursuit_ref,
                "status": status, "detail": detail, "as_of": as_of, "prev_run_ref": self._prev_run_ref}
        if steps is not None:
            fact["steps"] = list(steps)
        fact["event_id"] = short_id("runev", {"run_id": self._run_id, "status": status, "as_of": as_of})
        return self._store.append(fact)

    def _step_fact(self, step: str, kind: str, status: str, *, detail: str = "",
                   refs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        as_of = self._clock()
        fact = {"fact_type": "build_step", "run_ref": self._run_id, "step": step, "kind": kind,
                "status": status, "detail": detail, "refs": dict(refs or {}), "as_of": as_of}
        fact["event_id"] = short_id("stepev", {"run_id": self._run_id, "step": step,
                                              "status": status, "as_of": as_of})
        return self._store.append(fact)

    def _cancel_fact(self) -> Dict[str, Any]:
        as_of = self._clock()
        fact = {"fact_type": "cancellation_requested", "run_ref": self._run_id,
                "pursuit_ref": self._pursuit_ref, "as_of": as_of}
        fact["event_id"] = short_id("cancel", {"run_id": self._run_id, "as_of": as_of})
        return self._store.append(fact)

    # -- pilotage -------------------------------------------------------- #
    def request_cancel(self) -> Dict[str, Any]:
        """Acte **humain** d'annulation : émet **immédiatement** un fait ``cancellation_requested`` (append-only).
        L'étape en vol terminera réellement avant que le run ne soit marqué ``cancelled`` (ordre honnête, A2)."""
        self._cancel.set()
        return self._cancel_fact()

    def status(self) -> Optional[str]:
        """Dernier statut de **ce** run lu depuis le journal (source de vérité = disque), ou None."""
        last = None
        for f in self._store.read_all():
            if f.get("fact_type") == "build_run" and f.get("run_id") == self._run_id:
                last = f.get("status")
        return last

    def start(self, steps: List[Step]) -> "BuildRunner":
        self._thread = threading.Thread(target=self._execute, args=(steps,), daemon=True)
        self._thread.start()
        return self

    def wait(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        if self._thread is not None:
            self._thread.join(timeout)
        return self._final or {"status": self.status(), "steps": []}

    def run(self, steps: List[Step]) -> Dict[str, Any]:
        """Exécute **synchrone** (bloquant). Renvoie ``{status, steps:[…], refs, budget_exhausted?}``."""
        return self._execute(steps)

    # -- cœur ------------------------------------------------------------ #
    def _ordered(self, steps: List[Step]) -> List[Step]:
        by_name = {s.name: s for s in steps}
        prereqs = {s.name: list(s.prerequisites) for s in steps}
        order_names, blockers = order_steps(list(by_name), prereqs, config=self._config)
        if blockers:
            raise PlanningUnavailable(f"ordonnancement bloqué : {blockers}")
        return [by_name[n] for n in order_names]

    def _execute(self, steps: List[Step]) -> Dict[str, Any]:
        # Identité du run : contenu (pursuit + étapes + horodatage de préparation).
        prepared_at = self._clock()
        self._run_id = short_id("run", {"pursuit_ref": self._pursuit_ref,
                                        "steps": [s.name for s in steps], "as_of": prepared_at})
        try:
            ordered = self._ordered(steps)
        except PlanningUnavailable as exc:
            self._run_fact(RUN_PREPARED, steps=[s.name for s in steps])
            fact = self._run_fact(RUN_FAILED, detail=str(exc))
            self._final = {"status": RUN_FAILED, "steps": [], "detail": str(exc)}
            return self._final

        self._run_fact(RUN_PREPARED, steps=[s.name for s in ordered])
        self._run_fact(RUN_RUNNING, steps=[s.name for s in ordered])
        for s in ordered:
            self._step_fact(s.name, s.kind, STEP_PENDING)

        step_reports: List[Dict[str, Any]] = []
        all_refs: Dict[str, Any] = {}
        for s in ordered:
            # Annulation observée AVANT de lancer une nouvelle étape (l'étape en vol, elle, n'est pas interrompue).
            if self._cancel.is_set():
                self._step_fact(s.name, s.kind, STEP_SKIPPED, detail="annulation demandée")
                step_reports.append({"step": s.name, "status": STEP_SKIPPED})
                continue
            # Pré-garde budget pour une étape facturable (A4) : AVANT tout appel.
            if s.billable:
                ok, reason = self._budget.can_start_call(s.max_usd)
                if not ok:
                    self._budget.record_exhausted(reason or "budget")
                    self._step_fact(s.name, s.kind, STEP_SKIPPED, detail=f"budget_exhausted: {reason}")
                    fact = self._run_fact(RUN_FAILED, detail=f"budget_exhausted: {reason}")
                    self._final = {"status": RUN_FAILED, "steps": step_reports,
                                   "budget_exhausted": reason, "refs": all_refs}
                    return self._final
            self._step_fact(s.name, s.kind, STEP_RUNNING)
            result = s.run()                                  # exécution réelle (l'étape en vol termine)
            if s.billable:
                self._budget.record_charge(result.cost, invocation_ref=result.refs.get("tool_ref"),
                                           label=s.name)
            terminal = STEP_SUCCEEDED if result.status == STEP_SUCCEEDED else STEP_FAILED
            self._step_fact(s.name, s.kind, terminal, detail=result.detail, refs=result.refs)
            step_reports.append({"step": s.name, "status": terminal, "refs": result.refs})
            all_refs.update(result.refs)
            if terminal == STEP_FAILED:                       # jamais de retry silencieux
                self._run_fact(RUN_FAILED, detail=f"étape « {s.name} » en échec : {result.detail}")
                self._final = {"status": RUN_FAILED, "steps": step_reports, "refs": all_refs}
                return self._final
            # Après le fait terminal réel de l'étape : si une annulation est arrivée en vol, run cancelled (ordre honnête).
            if self._cancel.is_set():
                self._run_fact(RUN_CANCELLED, detail="annulation après étape en vol")
                self._final = {"status": RUN_CANCELLED, "steps": step_reports, "refs": all_refs}
                return self._final

        final_status = RUN_CANCELLED if self._cancel.is_set() else RUN_SUCCEEDED
        self._run_fact(final_status)
        self._final = {"status": final_status, "steps": step_reports, "refs": all_refs}
        return self._final


__all__ = ["StepResult", "Step", "BuildRunStore", "BuildRunner", "detect_interrupted_runs",
           "RUN_PREPARED", "RUN_RUNNING", "RUN_SUCCEEDED", "RUN_FAILED", "RUN_CANCELLED", "RUN_INTERRUPTED",
           "STEP_PENDING", "STEP_RUNNING", "STEP_SUCCEEDED", "STEP_FAILED", "STEP_SKIPPED"]
