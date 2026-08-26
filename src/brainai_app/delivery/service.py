"""Service de **livraison réelle** — assemble build confiné → preview → vérification → ``delivered`` (JALON 2).

Orchestration **post-``realize``** (choix propriétaire : étape post-arc). Le service **ne connaît aucun
fournisseur** : il reçoit des **capacités résolues** (``site_build``, ``preview``) et des journaux append-only.
Il pilote le :class:`BuildRunner` (worker in-process, étapes ordonnancées par le vrai Kahn), applique le budget
réellement borné, puis, en cas de succès, enregistre le fait ``delivered``. L'**écriture mémoire** minimale reste
volontairement **hors** de ce service (déclenchée depuis ``brainai_app``, T5).

Étapes (DAG minimal, ordonné par ``14_PLANNING``) : ``build`` (facturable, écrit le site) → ``verify`` (GET réel
200 sur la preview servie, « vérifié » lié au hash). Arrêt au premier échec (aucun retry) ; ``budget_exhausted``
⇒ arrêt réel ; run interrompu **constaté** au démarrage. Stdlib pur ; vit hors ``builder/``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from scc_brainai_bootstrap.builder.site import SITE_ENTRYPOINT, produce_site_build
from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.delivered import DeliveredStore, build_delivered
from brainai_app.delivery.runner import (
    BuildRunner, BuildRunStore, RUN_SUCCEEDED, STEP_FAILED, STEP_SUCCEEDED, Step, StepResult,
    detect_interrupted_runs)
from brainai_app.delivery.verify import VerificationStore, verify_url


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_delivery(*, spec_source: Dict[str, Any], workspace: Any, project_id: str, pursuit_ref: str,
                 site_build: Any, preview: Any, budget: BudgetLedger,
                 build_store: Any, tool_store: Any, run_store: BuildRunStore,
                 verification_store: VerificationStore, delivered_store: DeliveredStore,
                 config: Any = None, entrypoint: str = SITE_ENTRYPOINT,
                 clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """Livre **réellement** une Spéc confirmée. Renvoie un rapport :
    ``{status, delivered?, provenance{…}, preview_ref?, verification?, build?, run{…}, interrupted[…]}``.

    ``status`` ∈ {delivered, failed, budget_exhausted, interrupted-noted…}. Toute étape passe par des **faits
    append-only** ; le fait ``delivered`` n'est écrit **que** si build+verify réussissent (vérifié lié au hash)."""
    workspace.ensure()
    cwd = workspace.path

    # A2 — constater tout run laissé non terminal (worker mort) AVANT d'en démarrer un nouveau.
    interrupted = detect_interrupted_runs(run_store, pursuit_ref=pursuit_ref, clock=clock)

    # Contexte partagé entre étapes (le runner exécute des closures zéro-arg ; verify lit la sortie de build).
    ctx: Dict[str, Any] = {}

    def _build_step() -> StepResult:
        out = produce_site_build(spec_source=spec_source, adapter=site_build, store=build_store,
                                 tool_store=tool_store, workspace=workspace, project_id=project_id,
                                 budget_remaining_usd=max(0.0, budget.ceiling_usd - budget.spent_real()),
                                 cwd=cwd, clock=clock)
        if not out.get("attempted"):
            return StepResult(status=STEP_FAILED, detail=f"appel refusé : {out.get('refused')}",
                              refs={}, cost=None)
        fact = out["fact"]
        ctx["build_fact"] = fact
        entry = fact.get("artefact") or {}
        ctx["entrypoint_sha"] = entry.get("sha256")
        cost = fact.get("cost")
        refs = {"build_id": fact.get("build_id"), "tool_ref": fact.get("tool_ref")}
        if fact.get("status") != "proposed":
            return StepResult(status=STEP_FAILED, detail=fact.get("error") or "build échoué",
                              refs=refs, cost=cost)
        return StepResult(status=STEP_SUCCEEDED, detail="site bâti", refs=refs, cost=cost)

    def _verify_step() -> StepResult:
        # La vérification passe par la **capacité preview résolue** (substituable, I9), pas un serveur câblé.
        handle = preview.open(workspace, entrypoint=entrypoint)
        try:
            vfact = verify_url(handle.url_for(entrypoint), entrypoint=entrypoint,
                               subject=f"http:{entrypoint}", expected_sha256=ctx.get("entrypoint_sha"),
                               clock=clock)
            ctx["preview_ref"] = handle.preview_ref()
        finally:
            handle.close()
        recorded = verification_store.record(vfact)
        ctx["verification"] = recorded
        status = STEP_SUCCEEDED if recorded.get("verdict") == "passed" else STEP_FAILED
        return StepResult(status=status, detail=recorded.get("detail", ""),
                          refs={"verification_id": recorded.get("verification_id")})

    steps = [
        Step(name="build", kind="build", run=_build_step, billable=True,
             max_usd=getattr(site_build, "max_budget_usd", None)),
        Step(name="verify", kind="verify", run=_verify_step, prerequisites=["build"]),
    ]

    runner = BuildRunner(run_store, budget, pursuit_ref=pursuit_ref, clock=clock, config=config,
                         prev_run_ref=(interrupted[0]["run_ref"] if interrupted else None))
    run_out = runner.run(steps)

    provenance: Dict[str, Any] = {}
    build_fact = ctx.get("build_fact")
    verification = ctx.get("verification")
    if build_fact:
        provenance["build_id"] = build_fact.get("build_id")
        provenance["tool_ref"] = build_fact.get("tool_ref")
    if verification:
        provenance["verification_id"] = verification.get("verification_id")
    provenance["run_id"] = run_out.get("steps") and getattr(runner, "_run_id", None)

    report: Dict[str, Any] = {"status": "failed", "run": run_out, "provenance": provenance,
                              "interrupted": [i.get("event_id") for i in interrupted],
                              "verification": verification, "build": build_fact,
                              "preview_ref": ctx.get("preview_ref")}

    if run_out.get("status") == RUN_SUCCEEDED and verification and verification.get("verdict") == "passed":
        as_of = clock()
        entry = (build_fact or {}).get("artefact")
        delivered = delivered_store.record(build_delivered(
            pursuit_ref=pursuit_ref, artifact_ref=entry, preview_ref=ctx.get("preview_ref"),
            verification_ref=verification.get("verification_id"),
            build_ref=(build_fact or {}).get("build_id"), as_of=as_of))
        provenance["delivered_id"] = delivered.get("delivered_id")
        report.update({"status": "delivered", "delivered": delivered})
    elif run_out.get("budget_exhausted"):
        report["status"] = "budget_exhausted"
    return report


__all__ = ["run_delivery"]
