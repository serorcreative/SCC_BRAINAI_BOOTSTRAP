"""Faits **Turn** — un tour de conversation au sein d'une Pursuit (BRAINAI-CONVERSATION-001 · Tâche 2).

Le dialogue **EST** une Pursuit ; un tour n'a **pas** d'identité cognitive propre : il porte le ``pursuit_ref``
de la Pursuit et **un** fait immuable par échange (message humain + ``reply`` de BrainAI + appréciation
``readiness`` + ``matured_need`` éventuel + usage/coût, ``real``/``unavailable`` — jamais fabriqués). Store JSONL
**append-only**, relu du disque, **reconstructible par ``pursuit_ref``**. Déterministe (``as_of`` figé, id
adressé-contenu). **Même patron** que :class:`ProposalStore`/:class:`SpecificationStore`/:class:`BuildStore` : le
fait est *trace-shaped* (``fact_type="turn"``, ``pursuit_ref``, ``as_of``) — un futur journal de traces unifié le
subsume sans rupture. Stdlib pur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.core.clock import short_id


class TurnStore:
    """Journal append-only des tours de conversation, dans un fichier hors ``data/`` (injecté)."""

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

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait tour immuable (déjà construit par :func:`build_turn`).

        **Le store adresse lui-même l'identifiant** à partir du **fait complet sans identifiant** : tout
        ``turn_id`` fourni par l'appelant est **ignoré** (retiré puis recalculé). L'identifiant dépend du
        **statut**, du **contenu** (``reply``/``readiness``/``matured_need`` en succès, ``diagnostic`` en
        échec), du **message** humain, de la **capacité**, de l'**adaptateur**, du **modèle**, de l'empreinte
        du **prompt**, du **``pursuit_ref``** (appartenance à la Pursuit) et de l'**horodatage** — deux tours
        distincts, ou deux Pursuits produisant le même échange, donnent **deux identifiants distincts**."""
        stored = {k: v for k, v in fact.items() if k != "turn_id"}  # id appelant ignoré
        turn_id = short_id("turn", {
            "status": stored.get("status"),
            "reply": stored.get("reply"),
            "readiness": stored.get("readiness"),
            "matured_need": stored.get("matured_need"),
            "diagnostic": stored.get("diagnostic"),
            "message": stored.get("message"),
            "capability": stored.get("capability"),
            "adapter": stored.get("adapter"),
            "model": stored.get("model"),
            "prompt_sha256": stored.get("prompt_sha256"),
            "pursuit_ref": stored.get("pursuit_ref"),
            "as_of": stored.get("as_of"),
        })
        stored = {"turn_id": turn_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["TurnStore"]
