"""Modèle de coût **BrainAI-owned, déterministe** pour L8 (Solution Architecture + Cost Gate).

CONNECTER, PAS RECONSTRUIRE. Ce module ne fait **aucun** appel réseau, n'utilise **aucun** LLM, n'invente
**aucun** prix, **ne fabrique aucune devise**. Il fournit :

1. une **sémantique de coût par SOURCE** (fail-closed sur source inconnue) :
   - ``provider_call`` : coût d'un appel fournisseur réel — ``real`` (USD depuis l'enveloppe/contrat) ou
     ``unavailable`` (le fournisseur n'a pas renvoyé d'USD) ;
   - ``internal_deterministic`` : computation interne BrainAI (arbitrage L7, sélection d'architecture, calcul de
     coût) — **jamais** un coût fournisseur : coût provider ``n_a``, **exclu** du calcul de complétude provider.
   BrainAI n'est PAS un fournisseur : on ne lui attribue jamais ``real=0``. Un ``partial`` légitime causé par un
   **vrai** fournisseur ``unavailable`` reste honnête.

2. un modèle d'**estimation de coût de solution** (TCO) : construction (one-time) + exploitation récurrente, où
   **chaque montant** porte SA propre qualification ``known | estimate | assumption | unknown | n_a`` (un montant
   inconnu n'est JAMAIS zéro ; ``n_a`` n'est PAS un inconnu), sa devise (ou ``None`` = non déterminée, jamais
   fabriquée), sa période, sa base de calcul, ses hypothèses propres et sa confiance ; scénarios
   ``low | expected | high`` sur le récurrent. v1 **n'invente aucun prix** (kind ``unknown`` par défaut si le taux
   n'est pas connu ; ``n_a`` uniquement quand la dimension est réellement non applicable).

Fonctions pures, déterministes, testables à 0 $.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scc_brainai_bootstrap.core.clock import short_id

# --------------------------------------------------------------------- #
# Sémantique de coût par SOURCE (correctif L7 : le calcul déterministe BrainAI n'est pas un coût fournisseur)
# --------------------------------------------------------------------- #
PROVIDER_CALL = "provider_call"
INTERNAL_DETERMINISTIC = "internal_deterministic"
COST_SOURCES: Tuple[str, ...] = (PROVIDER_CALL, INTERNAL_DETERMINISTIC)

# Niveaux de connaissance d'un montant (JAMAIS confondus). ``unknown`` ≠ 0 ; ``n_a`` ≠ ``unknown``.
KNOWN = "known"
ESTIMATE = "estimate"
ASSUMPTION = "assumption"
UNKNOWN = "unknown"
N_A = "n_a"
COST_KINDS: Tuple[str, ...] = (KNOWN, ESTIMATE, ASSUMPTION, UNKNOWN, N_A)

# Scénarios économiques (récurrent).
SCENARIOS: Tuple[str, ...] = ("low", "expected", "high")

# Complétude d'une estimation (distincte de la complétude provider de l'arc).
COMPLETE = "complete"
HAS_UNKNOWNS = "has_unknowns"


def is_provider_incomplete(cost: Any, *, source: str) -> bool:
    """Un coût rend-il la complétude **provider** incomplète ? **Fail-closed** : ``source`` DOIT appartenir à
    :data:`COST_SOURCES` (une source inconnue lève, jamais traitée comme interne par défaut).

    - ``internal_deterministic`` (computation BrainAI) : **exclu** — ne dégrade jamais la complétude provider ;
    - ``provider_call`` : incomplet SAUF si USD réel présent (``kind == "real"`` + valeur numérique)."""
    if source not in COST_SOURCES:
        raise ValueError(f"cost_source inconnue : {source!r} (attendu ∈ {COST_SOURCES})")
    if source == INTERNAL_DETERMINISTIC:
        return False
    # source == PROVIDER_CALL
    if isinstance(cost, dict) and cost.get("kind") == "real" and isinstance(cost.get("value"), (int, float)):
        return False
    return True                                         # provider_call sans USD réel → incomplet (unavailable)


def provider_real_value(cost: Any, *, source: str) -> Optional[float]:
    """Montant USD **réel** à additionner au dépensé, ou ``None``. **Fail-closed** : ``source`` DOIT appartenir à
    :data:`COST_SOURCES`. Seul un ``provider_call`` de kind ``real`` avec valeur numérique contribue ;
    ``internal_deterministic`` ne contribue **aucun** montant provider."""
    if source not in COST_SOURCES:
        raise ValueError(f"cost_source inconnue : {source!r} (attendu ∈ {COST_SOURCES})")
    if source == INTERNAL_DETERMINISTIC:
        return None
    if isinstance(cost, dict) and cost.get("kind") == "real" and isinstance(cost.get("value"), (int, float)):
        return float(cost["value"])
    return None


# --------------------------------------------------------------------- #
# Montants qualifiés — chaque montant porte SA propre qualification (et ses propres hypothèses)
# --------------------------------------------------------------------- #
def amount(*, kind: str, value: Optional[float] = None, currency: Optional[str] = None,
           period: Optional[str] = None, basis: Optional[str] = None,
           confidence: Optional[str] = None,
           assumptions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Construit un **montant de coût qualifié**. ``kind`` ∈ :data:`COST_KINDS`. Invariants fail-closed :
    - ``unknown`` : ``value`` DOIT être ``None`` (un inconnu n'est jamais un nombre, surtout pas 0) ;
    - ``n_a`` : ``value`` DOIT être ``None`` (non applicable ≠ inconnu ≠ zéro) ;
    - ``known`` / ``estimate`` / ``assumption`` : ``value`` DOIT être un nombre ≥ 0.
    ``currency`` : ``None`` = **non déterminée** (jamais fabriquée en USD) ; une devise réelle (ex. ``"USD"``) n'est
    posée que si connue. ``period`` (ex. ``"month"``) porté pour un coût récurrent. ``assumptions`` : hypothèses
    **propres à ce montant**."""
    if kind not in COST_KINDS:
        raise ValueError(f"kind de coût invalide : {kind!r} (attendu ∈ {COST_KINDS})")
    if kind in (UNKNOWN, N_A):
        if value is not None:
            raise ValueError(f"un montant '{kind}' ne porte JAMAIS de valeur (reçu {value!r})")
    else:
        if not isinstance(value, (int, float)):
            raise ValueError(f"un montant '{kind}' exige une valeur numérique (reçu {value!r})")
        if value < 0:
            raise ValueError(f"un montant '{kind}' ne peut être négatif (reçu {value!r})")
    out: Dict[str, Any] = {
        "kind": kind,
        "value": (float(value) if value is not None else None),
        "currency": currency,                           # None = non déterminée (jamais fabriquée)
    }
    if period is not None:
        out["period"] = period
    if basis is not None:
        out["basis"] = basis
    if confidence is not None:
        out["confidence"] = confidence
    if assumptions:
        out["assumptions"] = list(assumptions)
    return out


def line_item(*, category: str, construction: Dict[str, Any], recurring: Dict[str, Any],
              notes: Optional[str] = None) -> Dict[str, Any]:
    """Une **ligne de coût** = une catégorie avec DEUX montants qualifiés indépendamment : ``construction``
    (one-time) et ``recurring`` (récurrent, période portée par le montant). Ex. construction ``known`` +
    récurrent ``estimate`` est parfaitement représentable (qualifications distinctes)."""
    return {"category": category, "construction": construction, "recurring": recurring,
            "notes": notes}


def has_unknown(estimate: Dict[str, Any]) -> bool:
    """L'estimation comporte-t-elle au moins un montant matériel ``unknown`` (construction OU récurrent d'une
    ligne) ? ``n_a`` ne compte PAS comme inconnu. Parcourt réellement chaque ligne et chaque slot."""
    for li in estimate.get("line_items", []):
        for slot in ("construction", "recurring"):
            slot_amount = li.get(slot) or {}
            if slot_amount.get("kind") == UNKNOWN:
                return True
    return False


def completeness(estimate: Dict[str, Any]) -> str:
    """Complétude de l'estimation : :data:`HAS_UNKNOWNS` s'il existe un inconnu matériel, sinon :data:`COMPLETE`.
    (Distincte de la complétude *provider* de l'arc, gérée par :func:`is_provider_incomplete`.)"""
    return HAS_UNKNOWNS if has_unknown(estimate) else COMPLETE


def build_cost_estimate(*, pursuit_ref: str, architecture_ref: str, option_ref: str, as_of: str,
                        line_items: List[Dict[str, Any]], scenarios: Dict[str, Any],
                        assumptions: Optional[List[str]] = None,
                        material_assumptions: Optional[List[Dict[str, Any]]] = None,
                        unknowns: Optional[List[str]] = None,
                        currency: Optional[str] = None, status: str = "proposed") -> Dict[str, Any]:
    """Construit un fait **cost_estimate** immuable pour **UNE option d'architecture** (``option_ref``), source
    ``internal_deterministic`` (BrainAI calcule, aucun coût fournisseur). ``scenarios`` : mapping
    ``low|expected|high`` → ``{recurring_total: <amount>, assumptions: [...]}``. ``currency`` de synthèse : ``None``
    = non déterminée (jamais fabriquée). ``cost_completeness`` calculée (jamais fabriquée). ``status`` ∈
    {``proposed``, ``failed``}. Les inconnues explicites sont conservées (jamais muées en 0).

    Deux familles d'hypothèses **distinctes** : ``assumptions`` = descriptif libre (wording, HORS fingerprint du
    gate) ; ``material_assumptions`` = **hypothèses structurées matérielles** (volumétrie, requêtes/transactions,
    stockage, trafic, appels API/LLM, fréquence, période, quota/tier, montée en charge, …) sous forme
    ``{"key", "value", "unit"?}`` — elles influencent l'économie/l'architecture et **entrent dans le fingerprint**
    (leur changement ⇒ RE-COST → NEW GO). v1 : peut être vide (volumétrie non encore fournie) mais le contrat la
    porte."""
    for sc in scenarios:
        if sc not in SCENARIOS:
            raise ValueError(f"scénario invalide : {sc!r} (attendu ∈ {SCENARIOS})")
    estimate = {
        "fact_type": "cost_estimate",
        "cost_source": INTERNAL_DETERMINISTIC,
        "pursuit_ref": pursuit_ref,
        "architecture_ref": architecture_ref,
        "option_ref": option_ref,                       # estimation PAR option d'architecture
        "currency": currency,                           # None = non déterminée
        "line_items": line_items,
        "scenarios": scenarios,
        "assumptions": list(assumptions or []),                 # descriptif libre — HORS fingerprint
        "material_assumptions": list(material_assumptions or []),  # structuré matériel — DANS le fingerprint
        "unknowns": list(unknowns or []),
        "status": status,
        "as_of": as_of,
    }
    estimate["cost_completeness"] = completeness(estimate)
    return estimate


def estimate_costs(option: Dict[str, Any], *, pursuit_ref: str, architecture_ref: str,
                   as_of: str) -> Dict[str, Any]:
    """Estimateur **déterministe v1** pour **UNE option d'architecture** (pas une option déjà sélectionnée) —
    **sans inventer aucun prix ni aucune devise**. Chaque composant/service externe devient une ligne dont les
    montants sont ``unknown`` (devise ``None`` = non déterminée, base explicite) tant qu'aucun taux n'est connu —
    un inconnu n'est jamais 0. ``n_a`` n'est utilisé que là où la dimension est réellement non applicable (v1 n'en
    pose aucun par défaut : un service externe PEUT nécessiter setup/onboarding/intégration → construction
    ``unknown``). Hypothèses de volumétrie et inconnues remontées explicitement ; scénarios ``low|expected|high``
    agrègent le récurrent (``unknown`` tant qu'aucun taux n'est connu). Extensible : une table de tarifs connus
    pourra requalifier des montants en ``known``/``estimate`` sans changer le contrat. Appelée **par option** →
    BrainAI compare ensuite les alternatives (:func:`solution_architecture.compare_architectures`)."""
    option_id = str(option.get("id") or "")
    components: List[str] = [c for c in option.get("components", []) if isinstance(c, str)]
    external: List[str] = [s for s in option.get("external_services", []) if isinstance(s, str)]
    dependencies: List[str] = [d for d in option.get("dependencies", []) if isinstance(d, str)]

    line_items: List[Dict[str, Any]] = []
    unknowns: List[str] = []
    # Composants internes : construction inconnue tant que non chiffrée ; récurrent d'exploitation inconnu.
    for comp in components:
        line_items.append(line_item(
            category=f"component:{comp}",
            construction=amount(kind=UNKNOWN, basis="composant non encore chiffré (v1 sans table de coûts)"),
            recurring=amount(kind=UNKNOWN, period="month",
                             basis="coût d'exploitation non encore chiffré (v1)")))
        unknowns.append(f"coût du composant '{comp}'")
    # Services externes : construction INCONNUE (setup/onboarding/intégration possibles — jamais n_a par défaut) ;
    # récurrent inconnu (dépend du service et de la volumétrie).
    for svc in external:
        line_items.append(line_item(
            category=f"external_service:{svc}",
            construction=amount(kind=UNKNOWN,
                                basis="coût one-time éventuel (setup/onboarding/intégration) non connu (v1)"),
            recurring=amount(kind=UNKNOWN, period="month",
                             basis="tarif du service externe non connu (v1) — dépend du volume")))
        unknowns.append(f"coût du service externe '{svc}' (one-time éventuel + récurrent)")

    # Scénarios : récurrent agrégé inconnu tant qu'aucun taux n'est connu (jamais 0, devise non déterminée).
    scenarios = {
        sc: {"recurring_total": amount(kind=UNKNOWN, period="month",
                                       basis=f"agrégat récurrent scénario {sc} — taux inconnus (v1)"),
             "assumptions": [f"scénario {sc} : hypothèses de volumétrie non encore fournies"]}
        for sc in SCENARIOS
    }
    assumptions = [
        "v1 : aucun prix inventé, aucune devise fabriquée ; montants inconnus explicites (jamais 0).",
        f"option d'architecture évaluée : {option_id or '?'}.",
    ]
    if dependencies:
        assumptions.append("dépendances matérielles : " + ", ".join(dependencies))

    status = "proposed" if option_id else "failed"
    return build_cost_estimate(
        pursuit_ref=pursuit_ref, architecture_ref=architecture_ref, option_ref=option_id, as_of=as_of,
        line_items=line_items, scenarios=scenarios, assumptions=assumptions, unknowns=unknowns,
        status=status)


class CostEstimateStore:
    """Journal **append-only** des estimations de coût (fichier injecté, hors ``data/``). Même patron
    *trace-shaped* que les stores existants : id **content-addressed**, ``as_of`` figé, ``pursuit_ref`` ;
    lecture **fail-closed** (toute ligne non vide illisible lève). Aucune mémoire parallèle."""

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _load_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for i, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"CostEstimateStore: ligne {i} JSON invalide ({exc}) — lecture fail-closed") from exc
        return out

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait estimation immuable ; **le store adresse lui-même l'identifiant** (id appelant ignoré)
        à partir du **fait complet** (hors ``estimate_id``) — content-addressed."""
        stored = {k: v for k, v in fact.items() if k != "estimate_id"}
        estimate_id = short_id("est", stored)
        stored = {"estimate_id": estimate_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = [
    "PROVIDER_CALL", "INTERNAL_DETERMINISTIC", "COST_SOURCES",
    "KNOWN", "ESTIMATE", "ASSUMPTION", "UNKNOWN", "N_A", "COST_KINDS",
    "SCENARIOS", "COMPLETE", "HAS_UNKNOWNS",
    "is_provider_incomplete", "provider_real_value",
    "amount", "line_item", "has_unknown", "completeness",
    "build_cost_estimate", "estimate_costs", "CostEstimateStore",
]
