"""Budget réellement borné d'un build — ``BudgetLedger`` append-only (JALON 2, A4 + condition Rose).

Deux gardes, de natures **honnêtement différentes** :

* **GARDE 2 — nombre d'appels facturables** : *mathématiquement dure*. BrainAI contrôle exactement combien de
  fois il franchit la frontière ; ``calls_made >= max_calls`` interdit tout nouvel appel. Enforceable à 100 %.
* **GARDE 1 — plafond monétaire** : *bornée mais non strictement garantie a priori*. Avant chaque invocation on
  exige ``coût_réel_déjà_consommé + enveloppe_max_prochaine_invocation <= plafond`` (l'enveloppe = le
  ``--max-budget-usd`` natif du fournisseur). Mais ce plafond fournisseur est un **arrêt agrégé entre appels**,
  pas une garantie qu'un appel déjà lancé ne dépasse pas légèrement. La propriété **réellement dure** reste donc
  le **compteur d'appels** ; le plafond USD est **best-effort borné**, le résidu est consigné RS-2 (RS-039).

Les coûts sont **réels** quand disponibles, ``unavailable`` sinon — **jamais inventés**. ``budget_exhausted`` est
émis dès que **l'une** des gardes interdit de poursuivre, et **arrête réellement** le run. Store append-only. Stdlib pur.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from scc_brainai_bootstrap.core.clock import short_id


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetLedger:
    """Journal **append-only** des événements budgétaires d'un build, et **gardes** d'arrêt. ``ceiling_usd`` =
    plafond monétaire du build ; ``max_calls`` = plafond du nombre d'appels facturables (garde dure). Chaque coût
    réellement dépensé est consigné (``kind=real``) ou marqué ``unavailable`` — jamais fabriqué."""

    def __init__(self, path: Path, *, ceiling_usd: float, max_calls: int,
                 clock: Callable[[], str] = _system_clock):
        if ceiling_usd <= 0:
            raise ValueError("ceiling_usd doit être strictement positif")
        if max_calls <= 0:
            raise ValueError("max_calls doit être strictement positif")
        self._path = Path(path)
        self._ceiling = float(ceiling_usd)
        self._max_calls = int(max_calls)
        self._clock = clock

    @property
    def path(self) -> Path:
        return self._path

    @property
    def ceiling_usd(self) -> float:
        return self._ceiling

    @property
    def max_calls(self) -> int:
        return self._max_calls

    # -- relecture ------------------------------------------------------- #
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

    def _append(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(fact, ensure_ascii=False) + "\n")
        return fact

    # -- agrégats HONNÊTES ---------------------------------------------- #
    def spent_real(self) -> float:
        """Somme des coûts **réels** consignés (les ``unavailable`` n'y entrent pas — jamais d'invention)."""
        total = 0.0
        for e in self.read_all():
            if e.get("fact_type") == "budget_charge" and e.get("cost_kind") == "real":
                v = e.get("cost_value")
                if isinstance(v, (int, float)):
                    total += float(v)
        return total

    def calls_made(self) -> int:
        return sum(1 for e in self.read_all() if e.get("fact_type") == "budget_charge")

    def calls_remaining(self) -> int:
        return max(0, self._max_calls - self.calls_made())

    def has_unavailable_cost(self) -> bool:
        return any(e.get("fact_type") == "budget_charge" and e.get("cost_kind") != "real"
                   for e in self.read_all())

    # -- gardes ---------------------------------------------------------- #
    def can_start_call(self, next_call_max_usd: Optional[float]) -> Tuple[bool, Optional[str]]:
        """Décide **AVANT** l'appel. Renvoie ``(autorisé, raison_de_refus)``.

        - GARDE 2 (dure) : refuse si plus aucun appel disponible.
        - GARDE 1 (best-effort bornée) : si une **enveloppe max** de la prochaine invocation est fournie, exige
          ``spent_real + enveloppe <= ceiling`` ; sinon (aucune enveloppe garantie) refuse dès que
          ``spent_real >= ceiling`` (on ne prétend pas à un plafond dur — cf. RS-039)."""
        if self.calls_remaining() <= 0:
            return False, "plafond du nombre d'appels atteint"
        spent = self.spent_real()
        if next_call_max_usd is not None:
            if spent + float(next_call_max_usd) > self._ceiling + 1e-9:
                return False, "plafond monétaire atteint (enveloppe de la prochaine invocation)"
        else:
            if spent >= self._ceiling - 1e-9:
                return False, "plafond monétaire atteint (aucune enveloppe garantie)"
        return True, None

    # -- écritures append-only ------------------------------------------ #
    def record_charge(self, cost: Any, *, invocation_ref: Optional[str] = None,
                      label: str = "") -> Dict[str, Any]:
        """Consigne un coût **réel** (``{"value":…, "kind":"real"}``) ou ``unavailable`` — jamais inventé.
        Compte comme **un appel facturable** (garde 2)."""
        kind = "unavailable"
        value: Optional[float] = None
        if isinstance(cost, dict) and cost.get("kind") == "real" and isinstance(cost.get("value"), (int, float)):
            kind, value = "real", float(cost["value"])
        as_of = self._clock()
        fact = {"fact_type": "budget_charge", "cost_kind": kind, "cost_value": value,
                "invocation_ref": invocation_ref, "label": label, "as_of": as_of,
                "ceiling_usd": self._ceiling, "max_calls": self._max_calls}
        fact["budget_id"] = short_id("budg", {"cost_kind": kind, "cost_value": value,
                                              "invocation_ref": invocation_ref, "as_of": as_of})
        return self._append(fact)

    def record_exhausted(self, reason: str) -> Dict[str, Any]:
        """Émet un fait ``budget_exhausted`` (arrêt réel du run). Reflète l'état **réellement** garanti."""
        as_of = self._clock()
        fact = {"fact_type": "budget_exhausted", "reason": reason,
                "spent_real_usd": self.spent_real(), "calls_made": self.calls_made(),
                "ceiling_usd": self._ceiling, "max_calls": self._max_calls,
                "hard_guarantee": "call_count", "usd_guarantee": "best_effort_bounded",
                "as_of": as_of}
        fact["budget_id"] = short_id("budgx", {"reason": reason, "as_of": as_of})
        return self._append(fact)


__all__ = ["BudgetLedger"]
