"""Plan d'exécution réelle de BrainAI (BRAINAI-JALON-ZERO-001).

**Frontière logique** (Arbitrage 2) entre la Cognition (le cerveau, gouvernance déterministe) et
l'Exécution (provoquer un effet réel dans le monde, sous maîtrise complète). Ce paquet ne modifie
**aucune** des 31 opérations du Contrat, n'est **pas** exposé par le transport (R4), et n'introduit
**aucune** couche Producteur ni Builder complet (R6) : il pose **uniquement** la frontière prouvée —

* :func:`invoke_tool` — exécute un outil réel confiné et **enregistre un fait ToolInvocation**
  (succès/échec/timeout), sans jamais modifier d'état officiel (R5).

BrainAI dépend d'une **capacité**, jamais d'un outil (R8) : ``invoke_tool`` accepte un ``argv``
quelconque ; l'outil concret (Claude Code, npm, git…) est un détail d'appelant, pas du noyau.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.tool_runner import run_confined
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError


def invoke_tool(*, store: ToolInvocationStore, workspace: Workspace, argv: List[str],
                timeout: float, as_of: str) -> Dict[str, Any]:
    """Exécute ``argv`` **dans** le Workspace du Projet et enregistre un **fait ToolInvocation**.

    L'issue est déterminée par le résultat réel : ``timeout`` si l'outil a dépassé la limite,
    ``succeeded`` si ``exit_code == 0``, ``failed`` sinon. Aucun état officiel n'est modifié ; le
    fait est append-only et reflète **exactement** ce que l'outil a produit."""
    result = run_confined(argv, cwd=workspace.path, timeout=timeout)
    if result["timed_out"]:
        status = "timeout"
    elif result["exit_code"] == 0:
        status = "succeeded"
    else:
        status = "failed"
    tool = Path(argv[0]).name if argv else ""
    return store.record(
        project_id=workspace.project_id, tool=tool, argv=list(argv),
        cwd=str(workspace.path), status=status, exit_code=result["exit_code"],
        stdout=result["stdout"], stderr=result["stderr"],
        timed_out=result["timed_out"], as_of=as_of,
    )


__all__ = ["invoke_tool", "Workspace", "WorkspaceError", "ToolInvocationStore", "run_confined"]
