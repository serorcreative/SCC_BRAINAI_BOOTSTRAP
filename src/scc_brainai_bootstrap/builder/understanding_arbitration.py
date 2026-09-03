"""Arbitrage **BrainAI** de contributions multi-provider à ``understand.need`` (L7).

CONNECTER, PAS RECONSTRUIRE. Ce module n'appelle **aucun** provider, ne fait **aucun** réseau, n'utilise
**aucun** LLM décideur et **ne connaît aucun nom concret de fournisseur**. Il opère uniquement sur des **Briefs**
(dicts conformes à ``BRIEF_SCHEMA``) produits séparément par les contributions ; la provenance vit dans
``ProposalStore``/``ArbitrationStore`` (trace), jamais en entrée de la décision. Fonctions **pures**,
**déterministes**, **testables à 0 $**.

Invariant central — **invariance par permutation** : deux exécutions avec le **même contenu** de Briefs dans un
**ordre différent** produisent la **même** classification et le **même** brief convergé (représentation
canonique indépendante de l'ordre des contributions ; aucune priorité implicite de position).

Classification v1 (déterministe, étroite) : ``consensus`` · ``complementarity`` · ``divergence`` ·
``contradiction`` (négation explicite, jeu fermé) · ``insufficient``. Aucune divergence n'est transformée en
consensus ; aucune contradiction sémantique profonde n'est inventée. Toute contradiction établie (array **ou**
scalaire) est **fail-closed** et n'est **jamais** arbitrée par une policy : seule une divergence scalaire peut
passer par :class:`ArbitrationPolicy`.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from scc_brainai_bootstrap.builder.understanding import BRIEF_SCHEMA

# Partition des champs du Brief par type JSON (aucun nom de provider ici) — ordre = ordre du schéma.
_PROPS: Dict[str, Any] = BRIEF_SCHEMA["properties"]
SCALAR_FIELDS: Tuple[str, ...] = tuple(k for k, v in _PROPS.items() if v.get("type") == "string")
ARRAY_FIELDS: Tuple[str, ...] = tuple(k for k, v in _PROPS.items() if v.get("type") == "array")
BRIEF_FIELDS: Tuple[str, ...] = tuple(_PROPS.keys())

# Jeu **fermé** de marqueurs de négation pour la contradiction v1 (étroite, transparente, non sémantique).
_NEG_PREFIXES: Tuple[str, ...] = (
    "pas de ", "pas d'", "aucun ", "aucune ", "sans ", "non ", "ne pas ", "no ", "not ", "without ",
)


# --------------------------------------------------------------------- #
# Canonicalisation — Unicode NFC, trim, collapse spaces, clé casefold, invariance d'ordre
# --------------------------------------------------------------------- #
def normalize(value: Any) -> str:
    """Forme d'**affichage** canonique déterministe : NFC, trim, espaces compactés. Non-chaîne → ``""``."""
    if not isinstance(value, str):
        return ""
    n = unicodedata.normalize("NFC", value).strip()
    return " ".join(n.split())


def _key(value: Any) -> str:
    """Clé de **comparaison/déduplication** : forme normalisée repliée par casse (casefold)."""
    return normalize(value).casefold()


def _strip_neg(key: str) -> Optional[str]:
    """Retire un préfixe de négation connu (jeu fermé) ; ``None`` si aucun. Base = reste normalisé casefold."""
    for p in _NEG_PREFIXES:
        if key.startswith(p) and len(key) > len(p):
            return " ".join(key[len(p):].split())
    return None


def _reps_from(values: List[str]) -> Dict[str, str]:
    """Map ``clé → représentant d'affichage`` déterministe : le représentant est la **plus petite** forme
    normalisée (ordre de points de code) parmi toutes celles partageant la clé — indépendant de l'ordre d'entrée."""
    groups: Dict[str, List[str]] = {}
    for v in values:
        n = normalize(v)
        if n == "":
            continue
        groups.setdefault(n.casefold(), []).append(n)
    return {k: min(forms) for k, forms in groups.items()}


def _contradiction_pairs(keys: List[str], rep: Dict[str, str]) -> List[List[str]]:
    """Paires ``(a, b)`` où l'une est la négation explicite de l'autre (v1 étroite). Sortie déterministe,
    triée, sans doublon ; valeurs = représentants d'affichage."""
    present = set(keys)
    seen: set = set()
    out: List[List[str]] = []
    for k in sorted(present):
        base = _strip_neg(k)
        if base and base != k and base in present:
            a, b = sorted((k, base))
            if (a, b) in seen:
                continue
            seen.add((a, b))
            out.append([rep[a], rep[b]])
    return out


# --------------------------------------------------------------------- #
# Politique d'arbitrage — provider-neutral, injectable, traçable
# --------------------------------------------------------------------- #
@runtime_checkable
class ArbitrationPolicy(Protocol):
    """Politique d'arbitrage **provider-neutral** pour une **divergence scalaire** UNIQUEMENT. Reçoit le nom du
    champ et un tuple **canonique** (trié, dédupliqué, order-invariant) de candidats ; retourne
    ``{"value", "justification"}`` (valeur justifiée) **ou** ``None`` (= UNRESOLVED). N'est **jamais** consultée
    pour une contradiction (array ou scalaire), toujours fail-closed. Ne reçoit **jamais** de nom de fournisseur
    ni de position de cohorte. Toute pondération éventuelle doit être explicite/injectée/traçable."""

    def resolve(self, *, field: str, candidates: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
        ...


class PreserveOrFailClosed:
    """Politique **par défaut** : ne fabrique **jamais** de valeur. Toute divergence scalaire reste **non
    résolue** (``None``) → l'arbitrage échoue fail-closed. Aucun nom de fournisseur, aucune préférence."""

    def resolve(self, *, field: str, candidates: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
        return None


# --------------------------------------------------------------------- #
# Classification — déterministe, order-invariant
# --------------------------------------------------------------------- #
def classify_briefs(briefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Classe, champ par champ, un ensemble de Briefs (traité comme **multiset non ordonné**). Retourne un dict
    JSON-sérialisable, **invariant par permutation** des Briefs à contenu identique.

    Arrays : ``consensus`` = intersection canonique ; ``complementarity`` = union \\ intersection ;
    ``contradiction`` = négation explicite détectée. Scalaires : ``consensus`` si une seule valeur normalisée ;
    sinon ``divergence`` (ou ``contradiction`` si négation), candidats canoniques exposés à la policy.
    ``insufficient`` global si moins de 2 Briefs."""
    n = len(briefs)
    fields: Dict[str, Any] = {}

    for field in ARRAY_FIELDS:
        per_brief: List[set] = []
        all_values: List[str] = []
        for b in briefs:
            vals = b.get(field) or []
            vals = [v for v in vals if isinstance(v, str)]
            all_values.extend(vals)
            per_brief.append({_key(v) for v in vals if normalize(v) != ""})
        rep = _reps_from(all_values)
        union: set = set().union(*per_brief) if per_brief else set()
        inter: set = set(per_brief[0]) if per_brief else set()
        for ks in per_brief[1:]:
            inter &= ks
        contradictions = _contradiction_pairs(sorted(union), rep)
        consensus = [rep[k] for k in sorted(inter)]
        complementary = [rep[k] for k in sorted(union - inter)]
        if contradictions:
            category = "contradiction"
        elif union and union == inter:
            category = "consensus"
        elif complementary:
            category = "complementarity"
        else:
            category = "consensus"  # union vide (tous champs vides) → consensus trivial sur l'absence
        fields[field] = {
            "kind": "array", "category": category,
            "consensus": consensus, "complementary": complementary,
            "union": [rep[k] for k in sorted(union)], "contradictions": contradictions,
        }

    for field in SCALAR_FIELDS:
        norms = [normalize(b.get(field)) for b in briefs]
        rep = _reps_from(norms)
        distinct = sorted(set(nk for nk in (v.casefold() for v in norms) if nk != ""))
        candidates = [rep[k] for k in distinct]
        contradictions = _contradiction_pairs(distinct, rep)
        if len(distinct) <= 1:
            category = "consensus"
        elif contradictions:
            category = "contradiction"
        else:
            category = "divergence"
        fields[field] = {
            "kind": "scalar", "category": category,
            "value": candidates[0] if len(distinct) == 1 else None,
            "candidates": candidates, "contradictions": contradictions,
        }

    return {"contributions": n, "insufficient": n < 2, "fields": fields}


# --------------------------------------------------------------------- #
# Convergence — brief convergé BrainAI, ou UNRESOLVED fail-closed
# --------------------------------------------------------------------- #
def converge(briefs: List[Dict[str, Any]], classification: Optional[Dict[str, Any]] = None, *,
             policy: Optional[ArbitrationPolicy] = None) -> Dict[str, Any]:
    """Produit un **brief convergé provider-neutral** à partir des contributions, ou un état ``unresolved``
    **fail-closed** (aucune valeur fabriquée). Déterministe et invariant par permutation.

    Fail-closed si : moins de 2 Briefs ; toute **contradiction** (array ou scalaire) — **sans** consulter la
    policy ; toute **divergence scalaire** que la ``policy`` ne résout pas (défaut :class:`PreserveOrFailClosed`
    → toujours non résolue). Sinon : arrays → union canonique (consensus ∪ complémentarité) ; scalaires → valeur
    de consensus ou valeur résolue par la policy. ``rationale`` trace la décision par champ."""
    pol: ArbitrationPolicy = policy if policy is not None else PreserveOrFailClosed()
    cls = classification if classification is not None else classify_briefs(briefs)

    if len(briefs) < 2:
        return {"status": "unresolved", "reason": "insufficient_contributions",
                "unresolved_fields": [], "rationale": cls}

    converged: Dict[str, Any] = {}
    rationale: Dict[str, Any] = {}
    unresolved: List[str] = []

    for field in BRIEF_FIELDS:
        fc = cls["fields"][field]
        cat = fc["category"]
        if fc["kind"] == "array":
            if cat == "contradiction":
                unresolved.append(field)
                rationale[field] = {"category": cat, "resolved_by": None,
                                    "contradictions": fc["contradictions"]}
                continue
            converged[field] = fc["union"]
            rationale[field] = {"category": cat, "resolved_by": "union",
                                "consensus_count": len(fc["consensus"]), "total": len(fc["union"])}
        else:  # scalar
            if cat == "consensus":
                converged[field] = fc["value"] if fc["value"] is not None else ""
                rationale[field] = {"category": cat, "resolved_by": "consensus"}
            elif cat == "contradiction":
                # Contradiction déterministe établie : TOUJOURS fail-closed, la policy n'est PAS consultée.
                unresolved.append(field)
                rationale[field] = {"category": cat, "resolved_by": None,
                                    "candidates": fc["candidates"], "contradictions": fc["contradictions"]}
            else:  # divergence scalaire → seule voie de résolution : ArbitrationPolicy injectée
                res = pol.resolve(field=field, candidates=tuple(fc["candidates"]))
                if res is None or "value" not in res:
                    unresolved.append(field)
                    rationale[field] = {"category": cat, "resolved_by": None,
                                        "candidates": fc["candidates"]}
                    continue
                converged[field] = res["value"]
                rationale[field] = {"category": cat, "resolved_by": "policy",
                                    "justification": res.get("justification"),
                                    "candidates": fc["candidates"]}

    if unresolved:
        return {"status": "unresolved", "reason": "unresolved_fields",
                "unresolved_fields": sorted(unresolved), "rationale": rationale}
    # Brief convergé ordonné selon le schéma (provider-neutral, order-invariant).
    brief = {field: converged[field] for field in BRIEF_FIELDS}
    return {"status": "converged", "brief": brief, "unresolved_fields": [], "rationale": rationale}


__all__ = [
    "normalize", "classify_briefs", "converge",
    "ArbitrationPolicy", "PreserveOrFailClosed",
    "SCALAR_FIELDS", "ARRAY_FIELDS", "BRIEF_FIELDS",
]
