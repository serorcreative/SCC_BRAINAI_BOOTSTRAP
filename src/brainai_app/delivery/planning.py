"""Ordonnancement des étapes de build — **enveloppe** le vrai ``14_BRAINAI_PLANNING`` (Kahn).

Doctrine « connecter, pas reconstruire » : l'algorithme d'ordre topologique **n'est pas recopié**. Ce module
est un **adaptateur de types** ``BuildStep ↔ PlanTask`` autour de la fonction réelle
``scc_brainai_planning.dependencies.topological_order`` (Kahn déterministe, détection de cycles). Le module
planning sibling est rendu importable par **injection de chemin** (``config.planning_src``), exactement comme
:class:`MemoryComponent` procède pour ``11_MEMORY`` — aucune copie, aucune modification du sibling.

Séquence d'usage **prouvée** du sibling : construire les ``PlanTask`` (``title`` = nom d'étape, ``prerequisites``
= titres des étapes amont) → ``finalize()`` (frappe l'``id`` stable) → ``resolve_prerequisites`` (titres → ids)
→ ``topological_order`` (ids). L'ordre renvoyé est reprojeté vers les noms d'étapes d'origine.

Si le sibling est indisponible (absent/illisible), on **ne fabrique pas** un ordre silencieux : on lève
:class:`PlanningUnavailable` (l'appelant en fait un fait honnête). Aucune duplication de l'algorithme.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List, Optional, Tuple

from scc_brainai_bootstrap.core.config import BrainAIConfig


class PlanningUnavailable(RuntimeError):
    """Le moteur ``14_PLANNING`` n'a pas pu être raccordé (chemin absent/illisible). Jamais silencieux."""


def _load_planning(config: Optional[BrainAIConfig]) -> Any:
    """Rend ``scc_brainai_planning`` importable via ``config.planning_src`` (injection de chemin, non invasive)
    puis retourne le module ``dependencies`` (Kahn) et le modèle ``PlanTask``. Lève :class:`PlanningUnavailable`."""
    cfg = config or BrainAIConfig()
    src = str(cfg.planning_src)
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        dependencies = importlib.import_module("scc_brainai_planning.dependencies")
        model = importlib.import_module("scc_brainai_planning.core.model")
    except Exception as exc:  # noqa: BLE001 — l'indisponibilité devient un fait, jamais un ordre inventé
        raise PlanningUnavailable(f"14_PLANNING non raccordable ({src}) : {exc}") from exc
    return dependencies, model


def order_steps(step_names: List[str], prerequisites: Dict[str, List[str]], *,
                config: Optional[BrainAIConfig] = None) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Ordonne des **étapes de build** par le **vrai** Kahn de ``14_PLANNING``.

    ``step_names`` : noms d'étapes (uniques). ``prerequisites`` : ``{étape: [étapes amont…]}`` (par noms).
    Renvoie ``(ordre_par_noms, blockers)`` — ``blockers`` non vide en cas de cycle/prérequis manquant, tel que
    produit par le sibling (jamais réinterprété). **Enveloppe** ; ne recompute rien."""
    dependencies, model = _load_planning(config)
    PlanTask = model.PlanTask

    tasks = [PlanTask(title=name, prerequisites=list(prerequisites.get(name, []))) for name in step_names]
    for t in tasks:
        t.finalize()                                  # frappe l'id stable AVANT résolution des prérequis
    missing = dependencies.resolve_prerequisites(tasks)   # titres amont → ids (sibling)
    order_ids, cycle_blockers = dependencies.topological_order(tasks)   # Kahn réel (sibling)

    id_to_name = {t.id: t.title for t in tasks}
    order_names = [id_to_name.get(i, i) for i in order_ids]
    blockers = list(missing) + list(cycle_blockers)
    return order_names, blockers


__all__ = ["PlanningUnavailable", "order_steps"]
