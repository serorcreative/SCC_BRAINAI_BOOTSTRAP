"""Faits **build_authorization** — USER GO explicite du Cost/Build Gate (L8).

CONNECTER, PAS RECONSTRUIRE. Même patron *trace-shaped* append-only que :class:`ConfirmationStore` (id
content-addressed, ``as_of`` figé, ``pursuit_ref``, acteur **déclaré / non vérifié** RS-029) — mais fait
**distinct** : une **autorisation de construction** liée à une proposition précise (spec + architecture
sélectionnée + estimation + hypothèses matérielles + services/providers payants). **Inerte** (record ≠
exécution) : l'arc lit le store pour décider Rung 3. Lecture **fail-closed**. Aucune mémoire parallèle.

Le **gate_fingerprint** ne porte que sur les données **MATÉRIELLES** : contenu de spec, empreinte matérielle de
l'option sélectionnée, montants de coût qualifiés + scénarios + complétude, **hypothèses matérielles structurées**
(volumétrie/quotas/période/montée en charge…), **providers payants** et **services externes payants** pertinents,
et présence d'inconnues. Il **exclut** tout élément purement descriptif : commentaire, wording, ordre, texte libre
(résumé/scalabilité/maintenabilité), base de calcul textuelle. Ainsi : ``NO GO = NO BUILD`` ; toute modification
**matérielle** (y compris une hypothèse économique ou un service/provider payant) ⇒ fingerprint différent ⇒
``RE-COST → NEW USER GO`` ; un simple changement de wording/ordre n'invalide **pas** un GO.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.confirmations import declared_actor
from scc_brainai_bootstrap.core.clock import digest, short_id

DECISIONS = ("approved", "declined")


def _canonical_str_set(values: Optional[List[Any]], *, field: str) -> List[str]:
    """Ensemble **matériel** canonique **fail-closed** : chaque valeur DOIT être une chaîne **non vide** (trim
    appliqué) ; une entrée non-chaîne ou vide lève ``ValueError`` (jamais convertie silencieusement en chaîne).
    Déduplication + tri déterministe (indépendant de l'ordre)."""
    out: set = set()
    for v in (values or []):
        if not isinstance(v, str):
            raise ValueError(f"{field} : valeur non-chaîne {v!r} (fail-closed — jamais convertie)")
        s = v.strip()
        if not s:
            raise ValueError(f"{field} : valeur vide (fail-closed)")
        out.add(s)
    return sorted(out)


def _amount_material(a: Any) -> Dict[str, Any]:
    """Part **matérielle** d'un montant qualifié (kind + value + currency + period). Exclut base/assumptions/
    confiance textuels (wording)."""
    a = a or {}
    return {"kind": a.get("kind"), "value": a.get("value"),
            "currency": a.get("currency"), "period": a.get("period")}


def _estimate_material(estimate: Optional[Dict[str, Any]]) -> Any:
    """Part **matérielle** d'une estimation : lignes (catégorie + montants construction/récurrent matériels, triées
    par catégorie), scénarios (récurrent matériel, triés), ``cost_completeness`` et ``status``. Exclut assumptions/
    basis textuels et l'ordre d'insertion. ``None`` si estimation absente."""
    if not isinstance(estimate, dict):
        return None
    items = sorted(
        ({"category": li.get("category"),
          "construction": _amount_material(li.get("construction")),
          "recurring": _amount_material(li.get("recurring"))}
         for li in estimate.get("line_items", [])),
        key=lambda x: str(x["category"]))
    scen = estimate.get("scenarios") or {}
    scenarios = {sc: _amount_material((scen.get(sc) or {}).get("recurring_total")) for sc in sorted(scen)}
    return {"line_items": items, "scenarios": scenarios,
            "material_assumptions": canonical_material_assumptions(estimate.get("material_assumptions")),
            "cost_completeness": estimate.get("cost_completeness"), "status": estimate.get("status")}


def canonical_material_assumptions(material_assumptions: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Forme **canonique et fail-closed** des hypothèses MATÉRIELLES structurées. Chaque élément DOIT être un dict
    portant ``key`` (chaîne non vide, **trim**) et ``value`` **réelle** (jamais ``None`` — un inconnu se représente
    comme inconnu ailleurs, pas comme une hypothèse ``None``) ; ``unit`` optionnelle (**trim** si chaîne). Chaque
    hypothèse est réduite à ``{"key", "value", "unit"}``, dédupliquée, et rendue dans un ordre canonique indépendant
    de l'ordre d'entrée. **Fail-closed** :
    - élément non-dict ⇒ ``ValueError`` (jamais ignoré silencieusement) ;
    - ``key`` absente/non-chaîne/vide (après trim) ⇒ ``ValueError`` ;
    - ``value`` absente ou ``None`` ⇒ ``ValueError`` ;
    - **même ``key`` (après trim) avec ``value``/``unit`` différentes ⇒ ``ValueError`` (contradictoires ; ex.
      ``active_users=1000`` et ``active_users=50000`` ne peuvent coexister). ``"active_users"`` et
      ``" active_users "`` désignent la MÊME clé (contradiction détectée)."""
    by_key: Dict[str, Dict[str, Any]] = {}
    for a in (material_assumptions or []):
        if not isinstance(a, dict):
            raise ValueError(f"hypothèse matérielle non-dict : {a!r} (fail-closed)")
        key = a.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"hypothèse matérielle sans 'key' non vide : {a!r} (fail-closed)")
        key = key.strip()
        if "value" not in a or a.get("value") is None:
            raise ValueError(f"hypothèse matérielle '{key}' sans 'value' réelle (None interdit — un inconnu "
                             f"se représente comme inconnu, pas comme hypothèse) (fail-closed)")
        unit = a.get("unit")
        if isinstance(unit, str):
            unit = unit.strip()
        norm = {"key": key, "value": a.get("value"), "unit": unit}
        prev = by_key.get(key)
        if prev is not None and prev != norm:
            raise ValueError(f"hypothèses matérielles contradictoires pour '{key}' : "
                             f"{prev} vs {norm} (fail-closed)")
        by_key[key] = norm                              # dédup : clés strictement identiques collapsent
    return [by_key[k] for k in sorted(by_key)]          # ordre canonique par clé


def _option_material(opt: Any) -> Dict[str, Any]:
    """Matière **structurelle** d'une option d'architecture : ``id`` + listes ``components``/``external_services``/
    ``dependencies``/``risks`` (dédupliquées, triées). Exclut ``summary``/``scalability``/``maintainability``
    (texte libre) et tout wording."""
    o = opt or {}
    return {
        "id": o.get("id"),
        "components": sorted({str(x) for x in o.get("components", [])}),
        "external_services": sorted({str(x) for x in o.get("external_services", [])}),
        "dependencies": sorted({str(x) for x in o.get("dependencies", [])}),
        "risks": sorted({str(x) for x in o.get("risks", [])}),
    }


def _canonical_comparison_options(comparison_options: Any) -> Dict[str, Dict[str, Any]]:
    """Valide **fail-closed** la liste des options comparées et renvoie ``{option_id → matière option}``. Exigences :
    liste **non vide** ; chaque option dict avec ``id`` chaîne non vide et les 4 champs listes de chaînes ; ``id``
    **uniques**. Sinon ``ValueError``."""
    if not isinstance(comparison_options, (list, tuple)) or not comparison_options:
        raise ValueError("gate_fingerprint : 'comparison_options' (liste non vide) requis (fail-closed)")
    out: Dict[str, Dict[str, Any]] = {}
    for opt in comparison_options:
        if not isinstance(opt, dict):
            raise ValueError(f"comparison_options : option non-dict {opt!r} (fail-closed)")
        oid = opt.get("id")
        if not isinstance(oid, str) or not oid.strip():
            raise ValueError(f"comparison_options : option sans 'id' non vide {opt!r} (fail-closed)")
        for arr in ("components", "external_services", "dependencies", "risks"):
            v = opt.get(arr, [])
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise ValueError(f"comparison_options : champ '{arr}' de '{oid}' non liste de chaînes (fail-closed)")
        if oid in out:
            raise ValueError(f"comparison_options : id dupliqué '{oid}' (fail-closed)")
        out[oid] = _option_material(opt)
    return out


def _canonical_comparison_estimates(comparison_estimates: Any) -> Dict[str, Dict[str, Any]]:
    """Valide **fail-closed** le mapping ``option_id → fait cost_estimate`` de **toutes** les options comparées.
    Exigences : mapping **non vide** ; chaque ``option_id`` chaîne non vide ; chaque fait un dict
    ``fact_type == "cost_estimate"`` + ``status == "proposed"`` + ``option_ref == option_id`` (aucune vérité
    contradictoire). Sinon ``ValueError``."""
    if not isinstance(comparison_estimates, dict) or not comparison_estimates:
        raise ValueError("gate_fingerprint : 'comparison_estimates' (mapping non vide option_id→cost_estimate) "
                         "requis (fail-closed — jamais {} silencieux)")
    out: Dict[str, Dict[str, Any]] = {}
    for oid, est in comparison_estimates.items():
        if not isinstance(oid, str) or not oid.strip():
            raise ValueError(f"comparison_estimates : option_id non-chaîne/vide {oid!r} (fail-closed)")
        if not isinstance(est, dict) or est.get("fact_type") != "cost_estimate" or est.get("status") != "proposed":
            raise ValueError(f"comparison_estimates : fait invalide pour '{oid}' (cost_estimate proposed requis)")
        if est.get("option_ref") != oid:
            raise ValueError(f"comparison_estimates : option_ref ({est.get('option_ref')!r}) ≠ clé ({oid!r}) — "
                             f"vérité contradictoire (fail-closed)")
        out[oid] = est
    return out


def gate_fingerprint(*, spec_sha256: str, selected_option_id: str, comparison_options: Any,
                     comparison_estimates: Dict[str, Any], cost_unknowns: List[str],
                     paid_providers: Optional[List[str]] = None,
                     paid_external_services: Optional[List[str]] = None) -> str:
    """Empreinte **canonique déterministe** de la proposition MATÉRIELLE soumise au GO — **sources de vérité
    uniques** = ``comparison_options`` (matière structurelle de **toutes** les options) + ``comparison_estimates``
    (estimation de **toutes** les options, hypothèses matérielles incluses). Aucune seconde vérité architecturale
    séparée : ``selected_option_id`` désigne l'entrée dans ``comparison_options_material``. Ainsi un changement
    matériel d'une **alternative même non sélectionnée** (architecture OU coût) change l'empreinte ⇒ ancien GO
    invalide ⇒ NEW USER GO. Invariante par permutation ; wording/rationale/ordre/commentaire **hors** empreinte.

    Fail-closed : ``comparison_options`` et ``comparison_estimates`` non vides et valides ; **ensemble des ids
    EXACTEMENT égal** entre options et estimations (aucune option sans estimation ni l'inverse) ;
    ``selected_option_id`` non vide et présent dans cet ensemble."""
    co = _canonical_comparison_options(comparison_options)
    ce = _canonical_comparison_estimates(comparison_estimates)
    if set(co) != set(ce):
        raise ValueError(f"gate_fingerprint : ids options {sorted(co)} ≠ ids estimations {sorted(ce)} "
                         f"(chaque option DOIT avoir son estimation et réciproquement) (fail-closed)")
    if not isinstance(selected_option_id, str) or not selected_option_id.strip():
        raise ValueError("gate_fingerprint : 'selected_option_id' (chaîne non vide) requis (fail-closed)")
    if selected_option_id not in co:
        raise ValueError(f"gate_fingerprint : option sélectionnée '{selected_option_id}' absente des options "
                         f"comparées (fail-closed)")
    material = {
        "spec_sha256": spec_sha256,
        "selected_option_id": selected_option_id,
        # Matière STRUCTURELLE de toutes les options comparées (ordre canonique par id).
        "comparison_options_material": [[oid, co[oid]] for oid in sorted(co)],
        # Estimation MATÉRIELLE (coûts + hypothèses) de toutes les options comparées (ordre canonique par id).
        "comparison_estimates_material": [[oid, _estimate_material(ce[oid])] for oid in sorted(ce)],
        "paid_providers": _canonical_str_set(paid_providers, field="paid_providers"),
        "paid_external_services": _canonical_str_set(paid_external_services, field="paid_external_services"),
        "cost_unknowns": _canonical_str_set(cost_unknowns, field="cost_unknowns"),
    }
    return "fp_" + digest(material)


def build_authorization_fact(*, pursuit_ref: str, spec_ref: str, architecture_ref: str,
                             selected_option_id: str, estimate_refs: List[str], gate_fingerprint: str,
                             decision: str, as_of: str, actor: Any = None,
                             material_assumptions: Optional[List[Dict[str, Any]]] = None,
                             paid_providers: Optional[List[str]] = None,
                             paid_external_services: Optional[List[str]] = None,
                             dependencies: Optional[List[str]] = None,
                             cost_unknowns: Optional[List[str]] = None,
                             commentary: Optional[str] = None) -> Dict[str, Any]:
    """Construit un fait ``build_authorization`` immuable et **inerte**. ``decision`` ∈ :data:`DECISIONS`. Prouve
    explicitement « j'autorise CETTE architecture, avec CES coûts, CES inconnues, CES hypothèses matérielles et CES
    services/providers payants » : lie la proposition (pursuit + spec + architecture + option sélectionnée +
    estimations + hypothèses matérielles canoniques + providers/services payants + dépendances + inconnues de coût)
    à son ``gate_fingerprint`` matériel, sous un acteur **déclaré / non vérifié**. ``commentary`` **descriptif**
    (hors fingerprint). Ne déclenche rien."""
    if decision not in DECISIONS:
        raise ValueError(f"décision invalide : {decision!r} (attendu ∈ {DECISIONS})")
    return {
        "fact_type": "build_authorization",
        "pursuit_ref": pursuit_ref,
        "spec_ref": spec_ref,
        "architecture_ref": architecture_ref,
        "selected_option_id": selected_option_id,
        "estimate_refs": _canonical_str_set(estimate_refs, field="estimate_refs"),
        "material_assumptions": canonical_material_assumptions(material_assumptions),
        "paid_providers": _canonical_str_set(paid_providers, field="paid_providers"),
        "paid_external_services": _canonical_str_set(paid_external_services, field="paid_external_services"),
        "dependencies": _canonical_str_set(dependencies, field="dependencies"),
        "cost_unknowns": _canonical_str_set(cost_unknowns, field="cost_unknowns"),
        "gate_fingerprint": gate_fingerprint,
        "decision": decision,
        "actor": declared_actor(actor),
        "commentary": commentary,                       # descriptif — hors fingerprint
        "as_of": as_of,
    }


class BuildAuthorizationStore:
    """Journal **append-only** des autorisations de build (fichier injecté, hors ``data/``). Id
    **content-addressed**, ``as_of`` figé ; lecture **fail-closed** (ligne illisible lève). Inerte. Aucune mémoire
    parallèle."""

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
                raise ValueError(f"BuildAuthorizationStore: ligne {i} JSON invalide ({exc}) — fail-closed") from exc
        return out

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait autorisation immuable ; **le store adresse lui-même l'identifiant** (id appelant ignoré)
        à partir du **fait complet** (hors ``authorization_id``) — content-addressed."""
        stored = {k: v for k, v in fact.items() if k != "authorization_id"}
        authorization_id = short_id("auth", stored)
        stored = {"authorization_id": authorization_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


def resolve_cost_gate(*, architecture_store: Any, cost_estimate_store: Any, pursuit_ref: str,
                      current_spec: Any) -> Dict[str, Any]:
    """Reconstruit **déterministiquement** le Cost Gate d'une Pursuit à partir des faits **PERSISTÉS** (frontière
    réelle CHOIX 2, ``_deliver``) — **sans ré-exécuter l'arc ni aucun provider**.

    **Ancre sur l'artefact réellement exécuté** : ``current_spec`` est le **fait Spécification courant** que
    ``_deliver`` s'apprête à construire (via ``_spec_fact_for(outcome)``). Validé par la primitive canonique
    :func:`validate_spec_source` (fournit ``specification_id`` courant + specification), puis
    ``spec_sha256 = digest(specification)`` calculé **ici** — aucun hash historique arbitraire (empêche un ancien
    Outcome de réactiver un ancien GO). Fail-closed : architecture ``proposed`` scellée par
    ``(pursuit_ref, spec_sha256)``, estimations ``proposed`` par option, comparaison/sélection BrainAI, puis
    **fingerprint COMPLET** (toutes options + toutes estimations, via ``comparison_options``/``comparison_estimates``,
    ``paid_*=[]`` en v1). Retourne ``{"status", "gate", "reason"}`` : ``resolved`` + ``gate`` si cohérent ; sinon
    ``absent`` / ``ambiguous`` / ``missing_estimate`` / ``incoherent`` (``gate=None`` ⇒ REFUS). v1 : unicité
    ``proposed`` par clé garantie par l'idempotence (aucune supersession)."""
    from scc_brainai_bootstrap.builder.solution_architecture import compare_architectures  # lazy — évite tout cycle
    from scc_brainai_bootstrap.builder.build import validate_spec_source, SpecSourceError

    if not isinstance(pursuit_ref, str) or not pursuit_ref.strip():
        return {"status": "incoherent", "gate": None, "reason": "pursuit_ref requis (chaîne non vide) — fail-closed"}
    if architecture_store is None or cost_estimate_store is None:
        return {"status": "absent", "gate": None,
                "reason": "journaux L8 absents (architecture/estimate) — fail-closed (aucun read_all)"}
    try:
        current_specification_id, specification = validate_spec_source(current_spec)  # primitive canonique
    except SpecSourceError as exc:
        return {"status": "incoherent", "gate": None, "reason": f"spécification courante invalide ({exc}) — fail-closed"}
    spec_sha256 = digest(specification)                   # ancre matérielle = l'artefact réellement exécuté

    archs = [f for f in architecture_store.read_all()
             if f.get("fact_type") == "solution_architecture" and f.get("status") == "proposed"
             and f.get("pursuit_ref") == pursuit_ref and f.get("spec_sha256") == spec_sha256]
    if not archs:
        return {"status": "absent", "gate": None,
                "reason": "aucune architecture proposée persistée pour cette Pursuit/état matériel courant"}
    if len({a["architecture_id"] for a in archs}) > 1:
        return {"status": "ambiguous", "gate": None, "reason": "architectures proposées incompatibles (fail-closed)"}
    arch = archs[0]
    option_ids = {o["id"] for o in arch.get("options", [])}
    estimates: Dict[str, Any] = {}
    for opt in arch.get("options", []):
        matches = [f for f in cost_estimate_store.read_all()
                   if f.get("fact_type") == "cost_estimate" and f.get("status") == "proposed"
                   and f.get("pursuit_ref") == pursuit_ref
                   and f.get("architecture_ref") == arch["architecture_id"] and f.get("option_ref") == opt["id"]]
        if not matches:
            return {"status": "missing_estimate", "gate": None,
                    "reason": f"estimation persistée manquante pour l'option {opt['id']}"}
        if len({m["estimate_id"] for m in matches}) > 1:   # v1 : ne survient pas (idempotence) ; réserve supersession
            return {"status": "ambiguous", "gate": None,
                    "reason": f"estimations incompatibles pour l'option {opt['id']} (fail-closed)"}
        e = matches[0]
        if e.get("option_ref") not in option_ids:
            return {"status": "incoherent", "gate": None,
                    "reason": "estimation dont l'option n'existe plus dans l'architecture (fail-closed)"}
        estimates[opt["id"]] = e

    comparison = compare_architectures(arch["options"], estimates)
    fp = gate_fingerprint(spec_sha256=spec_sha256, selected_option_id=comparison["selected_id"],
                          comparison_options=arch["options"], comparison_estimates=estimates,
                          cost_unknowns=comparison["cost_unknowns"], paid_providers=[], paid_external_services=[])
    gate = {
        "spec_ref": current_specification_id,             # curseur COURANT (la spec que _deliver exécute)
        "architecture_spec_ref": arch.get("spec_ref"),    # provenance historique de l'architecture (audit seul)
        "architecture_ref": arch["architecture_id"],
        "selected_option_id": comparison["selected_id"],
        "selection_rationale": comparison["selection_rationale"],
        "comparison": comparison["comparison"],
        "cost_unknowns": comparison["cost_unknowns"],
        "estimate_refs": sorted(e["estimate_id"] for e in estimates.values()),
        "material_assumptions": (estimates.get(comparison["selected_id"]) or {}).get("material_assumptions", []),
        # Matière de l'option SÉLECTIONNÉE conservée pour le fait d'autorisation (dépendances réelles).
        "dependencies": sorted({str(x) for x in comparison["selected"].get("dependencies", [])}),
        "paid_external_services": [],
        "paid_providers": [],
        "gate_fingerprint": fp,
    }
    return {"status": "resolved", "gate": gate, "reason": None}


def authorization_status(store: Any, *, pursuit_ref: str, gate_fingerprint: str) -> str:
    """Statut d'autorisation pour ``(pursuit_ref, gate_fingerprint)`` en lisant le journal (fail-closed) :
    ``"approved"`` / ``"declined"`` / ``"none"``. La **décision la plus récente** (par ``as_of``, tie-break
    ``authorization_id``) portant EXACTEMENT ce fingerprint et cette pursuit fait autorité — un GO obsolète (autre
    fingerprint) ne compte jamais ; un ``declined`` postérieur annule un ``approved`` antérieur. ``store`` ``None``
    ⇒ ``"none"`` (fail-closed : NO GO = NO BUILD)."""
    if store is None:
        return "none"
    matching = [f for f in store.read_all()
                if f.get("fact_type") == "build_authorization"
                and f.get("pursuit_ref") == pursuit_ref
                and f.get("gate_fingerprint") == gate_fingerprint
                and f.get("decision") in DECISIONS]
    if not matching:
        return "none"
    latest = max(matching, key=lambda f: (str(f.get("as_of") or ""), str(f.get("authorization_id") or "")))
    return latest["decision"]


__all__ = ["DECISIONS", "canonical_material_assumptions", "gate_fingerprint",
           "build_authorization_fact", "BuildAuthorizationStore", "authorization_status",
           "resolve_cost_gate"]
