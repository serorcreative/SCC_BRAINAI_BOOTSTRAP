"""Faits **ToolInvocation** — trace append-only de chaque appel d'outil externe (JALON-ZERO).

Chaque exécution d'un outil réel (subprocess) produit **un fait immuable**, **succès comme échec
comme timeout** — jamais une valeur fabriquée. C'est la matérialisation de la maîtrise BrainAI : un
outil **produit un résultat**, il ne modifie **aucun état officiel** (R5) ; le fait est **proposé**
(observable, gouvernable), jamais autoritatif. Store JSONL **append-only** (patron des faits
BrainAI), relu du disque. Déterministe (``as_of`` figé, id adressé-contenu). Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id


class ToolInvocationStore:
    """Journal append-only des invocations d'outils, dans un fichier hors ``data/`` (injecté)."""

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _load_all(self) -> List[Dict[str, Any]]:
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

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, *, project_id: str, tool: str, argv: List[str], cwd: str,
               status: str, exit_code: Any, stdout: str, stderr: str,
               timed_out: bool, as_of: str,
               pursuit_ref: Optional[str] = None, decision_source: Optional[str] = None) -> Dict[str, Any]:
        """Ajoute un fait ToolInvocation immuable. ``status`` ∈ {succeeded, failed, timeout}.
        Capture **exactement** ``exit_code``/``stdout``/``stderr`` produits par l'outil (jamais
        fabriqués). Renvoie le fait enregistré.

        **D-3 (extension ADDITIVE, rétro-compatible)** : ``pursuit_ref`` et ``decision_source`` sont
        **optionnels** (défaut ``None``). Les anciens appels **sans** ces mots-clés restent valides et
        produisent un fait **sans** ces champs (absence = absence, jamais complétée fictivement). Ces
        champs sont **descriptifs**, **non constitutifs de l'identité** : ``invocation_id`` reste
        ``short_id("tinv", {project_id, argv, as_of})`` **inchangé** (anciens ids non recalculés, aucune
        migration). Ils ne détournent ni ``argv``/``cwd``/``project_id``."""
        fact = {
            "invocation_id": short_id("tinv", {"project_id": project_id, "argv": argv,
                                               "as_of": as_of}),
            "project_id": project_id,
            "tool": tool,
            "argv": list(argv),
            "cwd": cwd,
            "status": status,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "as_of": as_of,
        }
        if pursuit_ref is not None:                 # D-3 : champ additif, présent seulement si fourni
            fact["pursuit_ref"] = pursuit_ref
        if decision_source is not None:             # D-3 : champ additif, présent seulement si fourni
            fact["decision_source"] = decision_source
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(fact, ensure_ascii=False) + "\n")
        return fact


__all__ = ["ToolInvocationStore"]
