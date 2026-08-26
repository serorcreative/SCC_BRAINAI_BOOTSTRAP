"""ToolRunner — **frontière d'exécution** : lance un outil réel en sous-processus **confiné**.

Cœur du plan d'exécution réelle (JALON-ZERO, Preuve A). BrainAI ne dépend **jamais** d'un outil
concret (R8) : le ToolRunner exécute un ``argv`` **quelconque** sous garde-fous, et **tout** est
capturé (stdout/stderr/exit/timeout). Garde-fous **non négociables** (Arbitrage 1) :

* **``shell=False``** — jamais de shell ; **argv** seulement (aucune interpolation) ;
* **``cwd`` confiné** au Workspace du Projet ;
* **environnement minimal** — l'outil n'hérite pas de l'environnement du parent ;
* **watchdog de sécurité** — au-delà d'un plafond wall-clock de **dernier recours** (PAS une échéance de
  cognition), le processus est tué et l'appel est un **échec** étiqueté ``safety_watchdog_exceeded`` ;
* **capture** intégrale : ``stdout``, ``stderr``, ``exit_code``.

Le ToolRunner ne modifie **aucun** état officiel BrainAI (R5) ; il produit un **résultat** que
l'appelant transforme en **fait ToolInvocation** append-only. Stdlib pur.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# Environnement minimal : de quoi trouver un interpréteur, rien de sensible (pas d'héritage global).
_MINIMAL_ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin", "LANG": "C.UTF-8"}

# --------------------------------------------------------------------- #
# Watchdog de SÉCURITÉ de dernier recours — PAS une échéance de cognition.
# --------------------------------------------------------------------- #
# Tant que l'infrastructure ne sait pas distinguer une **réflexion longue mais saine** d'un **processus bloqué**
# (streaming + timeout d'inactivité + annulation utilisateur = palier suivant, RS-059), un **unique plafond
# wall-clock LARGE** empêche seulement un sous-processus **abandonné / zombie** de tourner éternellement.
# Ce n'est **jamais** une durée maximale de réflexion : sa valeur est gouvernée en amont
# (``brainai_app.delivery.watchdog_config`` : défaut / env / explicite, source tracée) et fixée très au-dessus
# de toute cognition saine réaliste. Son dépassement est étiqueté **``safety_watchdog_exceeded``** (anomalie),
# jamais « timeout de réflexion ». Un process **mort** (``exit_code != 0``) reste capté **immédiatement et
# séparément** — il n'a pas besoin du watchdog.
DEFAULT_WATCHDOG_S = 3600.0                    # 1 h : fusible anti-zombie, PAS une limite de cognition
SAFETY_WATCHDOG_EXCEEDED = "safety_watchdog_exceeded"   # motif d'échec explicite (distinct de exit≠0)


def run_confined(argv: List[str], *, cwd: Path, timeout: float,
                 env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Exécute ``argv`` en sous-processus confiné. **Ne lève jamais** sur un échec de l'outil :
    renvoie ``{exit_code, stdout, stderr, timed_out}`` — un timeout donne ``timed_out=True`` et
    ``exit_code=None``. ``shell`` est **toujours** ``False`` (argv only)."""
    if not argv or not isinstance(argv, (list, tuple)):
        raise ValueError("argv (liste non vide) requis")
    try:
        proc = subprocess.run(
            list(argv),
            cwd=str(cwd),
            env=dict(env) if env is not None else dict(_MINIMAL_ENV),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,          # l'échec de l'outil est un fait, pas une exception
            shell=False,          # NON négociable : jamais de shell
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"exit_code": None,
                "stdout": exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                "stderr": exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
                "timed_out": True}


__all__ = ["run_confined", "DEFAULT_WATCHDOG_S", "SAFETY_WATCHDOG_EXCEEDED"]
