"""Capacité **Solution Architecture** (L8) — options d'architecture + comparaison/sélection BrainAI post-estimation.

CONNECTER, PAS RECONSTRUIRE. Miroir du motif ``specification`` (validation source → ``adapter.propose`` sous garde
budget → **un** fait honnête → store append-only). Responsabilités **séparées** :

- **Génération d'OPTIONS** : *provider-assistée* — un fournisseur (consultant) propose **une ou plusieurs** options
  via le même Protocol/plumbing (charte provider-neutral + schéma structuré). Appel fournisseur ⇒
  ``cost_source = provider_call``. Le fait conserve **toutes** les options valides ; **aucune sélection** ici.
- **COMPARAISON / SÉLECTION** : *appartient à BrainAI* — :func:`compare_architectures` compare les options **après**
  estimation de coût par option, de façon **déterministe et provider-neutral**. Le coût garde ses DEUX dimensions
  SÉPARÉES (construction one-time vs récurrent mensuel) : jamais de « total global » sans horizon. Décision coût
  seulement par **dominance de Pareto** (≤ construction ET ≤ récurrent, strictement meilleure sur ≥1) et seulement
  si réellement comparable (proposé, sans inconnue, même devise, même période). Sinon ``tradeoff`` / non décisif :
  repli sur critères structurels conservateurs, compromis exposé. Inconnu ≠ 0 ; estimation manquante ≠ avantage ;
  ``n_a`` ≠ inconnu. Aucun fournisseur ne décide à la place de BrainAI. Pas de moteur d'optimisation, pas de L9.

Topologie : Specification → Architecture OPTIONS → Cost Estimate par option → Comparaison/Sélection BrainAI →
Cost Gate → USER GO → Build (même Pursuit, aucun second pipeline).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract, claude_text_contract
from scc_brainai_bootstrap.builder.build import validate_spec_source
from scc_brainai_bootstrap.builder.claude_code_runtime import diagnostic, extract_cost, parse_envelope
from scc_brainai_bootstrap.builder.cognitive_identity import CONDENSED_IDENTITY, compose_prompt
from scc_brainai_bootstrap.builder.cost_estimate import COMPLETE, ESTIMATE, KNOWN, N_A, PROVIDER_CALL
from scc_brainai_bootstrap.builder.provider_env import (
    AUTH_KEYCHAIN_HOME, auth_channel, confined_env, inbound_channels)
from scc_brainai_bootstrap.builder.tool_runner import DEFAULT_WATCHDOG_S, SAFETY_WATCHDOG_EXCEEDED, run_confined
from scc_brainai_bootstrap.core.clock import digest, short_id

ARCHITECTURE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "components": {"type": "array", "items": {"type": "string"}},
                    "external_services": {"type": "array", "items": {"type": "string"}},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "scalability": {"type": "string"},
                    "maintainability": {"type": "string"},
                },
                "required": ["id", "summary", "components", "external_services", "dependencies",
                             "risks", "scalability", "maintainability"],
            },
        },
    },
    "required": ["options"],
}
_OPTION_REQUIRED = tuple(ARCHITECTURE_SCHEMA["properties"]["options"]["items"]["required"])


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_architecture_prompt(spec: Dict[str, Any]) -> str:
    """Prompt déterministe : demande **une ou plusieurs** options d'architecture structurées à partir de la Spéc.
    Préfixé par l'essence de l'identité (``CONDENSED_IDENTITY``) via :func:`compose_prompt` — le fournisseur
    **propose** (consultant, R5), il ne choisit pas, n'estime pas les coûts, ne décide pas."""
    mission = (
        "Tu proposes une ou plusieurs OPTIONS d'architecture de solution à partir d'une spécification produit. "
        "Réponds UNIQUEMENT via le schéma imposé : pour chaque option, un id, un résumé, les composants "
        "techniques, les services externes nécessaires, les dépendances matérielles, les risques, la scalabilité "
        "et la maintenabilité. Tu ne choisis pas, tu n'estimes pas les coûts, tu ne décides pas : tu proposes des "
        "options claires et comparables. Toute hypothèse est nommée explicitement dans le résumé de l'option.\n\n"
        f"SPÉCIFICATION : {json.dumps(spec, ensure_ascii=False)}"
    )
    return compose_prompt(CONDENSED_IDENTITY, mission)


def _valid_option(opt: Any) -> bool:
    """Option valide : dict portant l'ensemble EXACT des clés requises, ``id`` non vide, et les quatre champs
    listes (``components``/``external_services``/``dependencies``/``risks``) sont des listes de chaînes."""
    if not isinstance(opt, dict) or not all(k in opt for k in _OPTION_REQUIRED):
        return False
    if not isinstance(opt.get("id"), str) or not opt["id"].strip():
        return False
    for arr in ("components", "external_services", "dependencies", "risks"):
        v = opt.get(arr)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return False
    return True


def _valid_architecture(obj: Any) -> bool:
    """Architecture valide : dict avec ``options`` = liste **non vide** d'options toutes valides et à ``id``
    **distincts** (unicité requise pour estimation/comparaison par option déterministe)."""
    if not isinstance(obj, dict):
        return False
    options = obj.get("options")
    if not isinstance(options, list) or not options:
        return False
    if not all(_valid_option(o) for o in options):
        return False
    ids = [o["id"] for o in options]
    return len(set(ids)) == len(ids)


def canonicalize_options(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordre **stable** des options par ``id`` (déterminisme, indépendant de l'ordre fournisseur) ; contenu
    inchangé. Ne sélectionne rien."""
    return sorted(options, key=lambda o: str(o.get("id", "")))


# --------------------------------------------------------------------- #
# COMPARAISON / SÉLECTION — BrainAI, déterministe, provider-neutral, POST-estimation
# Deux dimensions de coût SÉPARÉES (jamais additionnées sans horizon). Dominance de Pareto uniquement.
# --------------------------------------------------------------------- #
def _known_amount(a: Any) -> bool:
    return isinstance(a, dict) and a.get("kind") in (KNOWN, ESTIMATE) and isinstance(a.get("value"), (int, float))


def _cost_view(estimate: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Vue de coût **par option**, SANS additionner construction et récurrent. Renvoie ``construction_total`` et
    ``expected_recurring_total`` séparément (ou ``None`` si non sommables), ``recurring_period``, ``currency``,
    ``cost_completeness``, ``comparable`` (bool) et ``reasons`` (explicites). Un inconnu ne devient JAMAIS 0 : il
    rend la dimension non sommable (``None``) et remonte une raison. ``n_a`` est distinct (ignoré du total, pas un
    inconnu). Estimation manquante ⇒ non comparable (jamais un avantage implicite)."""
    view: Dict[str, Any] = {
        "construction_total": None, "expected_recurring_total": None,
        "recurring_period": None, "currency": None,
        "cost_completeness": (estimate or {}).get("cost_completeness", "no_estimate"),
        "comparable": False, "reasons": [],
    }
    if not isinstance(estimate, dict) or estimate.get("status") != "proposed":
        view["reasons"].append("estimation manquante ou non proposed (jamais un avantage implicite)")
        return view
    reasons: List[str] = []
    currencies: set = set()

    # --- Construction (one-time) : somme des montants connus ; un inconnu rend le total non sommable ---
    construction = 0.0
    construction_ok = True
    saw_construction = False
    for li in estimate.get("line_items", []):
        c = li.get("construction") or {}
        kind = c.get("kind")
        if kind == N_A:
            continue                                     # non applicable : ni inconnu, ni 0 dans le total
        if _known_amount(c):
            saw_construction = True
            construction += float(c["value"])
            if c.get("currency"):
                currencies.add(c["currency"])
            else:
                construction_ok = False
                reasons.append("montant de construction sans devise déterminée")
        else:
            construction_ok = False
            reasons.append("coût de construction inconnu (jamais 0)")
    if not saw_construction:
        construction_ok = False                          # aucun montant de construction sommable
        reasons.append("aucun coût de construction chiffré")

    # --- Récurrent attendu (mensuel) : montant du scénario 'expected' ---
    exp = ((estimate.get("scenarios") or {}).get("expected") or {}).get("recurring_total") or {}
    rec_ok = _known_amount(exp)
    rec_val = float(exp["value"]) if rec_ok else None
    rec_period = exp.get("period") if rec_ok else None
    if not rec_ok:
        reasons.append("coût récurrent attendu inconnu (jamais 0)")
    elif exp.get("currency"):
        currencies.add(exp["currency"])
    else:
        reasons.append("montant récurrent sans devise déterminée")

    currency: Optional[str] = None
    if len(currencies) == 1:
        currency = next(iter(currencies))
    elif len(currencies) > 1:
        reasons.append("devises hétérogènes au sein de l'option → non comparable")

    view["construction_total"] = construction if construction_ok else None
    view["expected_recurring_total"] = rec_val
    view["recurring_period"] = rec_period
    view["currency"] = currency
    view["reasons"] = reasons
    view["comparable"] = bool(construction_ok and rec_ok and currency is not None
                              and rec_period is not None and view["cost_completeness"] == COMPLETE)
    return view


def _structural_pick(cards: List[Dict[str, Any]]) -> str:
    """Repli **conservateur déterministe** : min ``(services externes, risques, dépendances, id)``. Aucun texte
    libre (scalabilité/maintenabilité) transformé en score numérique en v1."""
    return min(cards, key=lambda c: (c["external_services"], c["risks"], c["dependencies"], c["id"]))["id"]


def compare_architectures(options: List[Dict[str, Any]],
                          estimates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compare **déterministiquement** les options (post-estimation) → sélection BrainAI + comparaison auditable.
    ``estimates`` : mapping ``option_id → fait cost_estimate`` (ou absent).

    Coût : DEUX dimensions séparées (construction one-time vs récurrent mensuel), **jamais** additionnées sans
    horizon. Une option n'est **économiquement dominante** que si — pour un ensemble réellement comparable
    (proposé, sans inconnue, même devise, même période) — elle est ``<=`` sur construction **ET** ``<=`` sur
    récurrent, **strictement** meilleure sur au moins une dimension, face à **toutes** les autres. Décision :
    - **fail-closed** : au moins une option valide requise ;
    - **1 option** → candidate BrainAI (auditable) ;
    - **≥2** : si une **unique** option domine toutes les autres → retenue par le coût ; sinon coût en
      ``tradeoff`` / **non décisif** (jamais de classement économique fabriqué) → repli structurel conservateur,
      compromis exposé. Coûts non comparables (inconnue / estimation manquante / devise ≠ / période ≠) → coût non
      décisif de même. ``comparison`` expose, par option, les deux dimensions séparées + devise + période +
      complétude + scalabilité + maintenabilité + raisons."""
    if not isinstance(options, list) or not options or not all(_valid_option(o) for o in options):
        raise ValueError("compare_architectures : au moins une option valide requise (fail-closed)")
    canon = canonicalize_options(options)
    views: Dict[str, Dict[str, Any]] = {o["id"]: _cost_view(estimates.get(o["id"])) for o in canon}
    cards: List[Dict[str, Any]] = []
    for o in canon:
        v = views[o["id"]]
        cards.append({
            "id": o["id"],
            "external_services": len(o.get("external_services", [])),
            "dependencies": len(o.get("dependencies", [])),
            "risks": len(o.get("risks", [])),
            "components": len(o.get("components", [])),
            "scalability": o.get("scalability"),         # texte libre — conservé pour audit, jamais scoré en v1
            "maintainability": o.get("maintainability"),
            "construction_total": v["construction_total"],
            "expected_recurring_total": v["expected_recurring_total"],
            "recurring_period": v["recurring_period"],
            "currency": v["currency"],
            "cost_completeness": v["cost_completeness"],
            "cost_comparable": v["comparable"],
            "cost_reasons": v["reasons"],
        })
    cost_unknowns = [c["id"] for c in cards if not c["cost_comparable"]]

    by_id = {o["id"]: o for o in canon}
    if len(canon) == 1:
        selected_id = canon[0]["id"]
        decisive = ["single_option"]
        rationale = "option unique valide → candidate sélectionnée par BrainAI (décision auditable)."
        cost_decisive = False
    else:
        currencies = {views[i]["currency"] for i in views}
        periods = {views[i]["recurring_period"] for i in views}
        uniform = (all(views[i]["comparable"] for i in views)
                   and len(currencies) == 1 and None not in currencies
                   and len(periods) == 1 and None not in periods)
        dominant = _sole_dominant([o["id"] for o in canon], views) if uniform else None
        if dominant is not None:
            selected_id = dominant
            decisive = ["cost_pareto_domination(construction,recurring)"]
            rationale = ("dominance économique claire : ≤ construction ET ≤ récurrent, strictement meilleure sur "
                         "au moins une dimension, face à toutes les autres (même devise, même période).")
            cost_decisive = True
        else:
            selected_id = _structural_pick(cards)
            decisive = ["external_services", "risks", "dependencies"]
            if uniform:
                rationale = ("coûts comparables mais AUCUNE dominance de Pareto (tradeoff construction/récurrent "
                             "sans horizon défini) → coût NON décisif, aucun classement économique fabriqué ; "
                             "repli sur critères structurels conservateurs. TCO sur horizon explicite : non défini "
                             "en v1.")
            else:
                rationale = ("coûts NON comparables (inconnue / estimation manquante / devise ou période "
                             "différentes → jamais 0 ni avantage implicite) → coût NON décisif ; repli sur "
                             "critères structurels conservateurs.")
            cost_decisive = False
    return {
        "selected": by_id[selected_id],
        "selected_id": selected_id,
        "selection_rationale": rationale,
        "decisive_criteria": decisive,
        "cost_decisive": cost_decisive,
        "comparison": cards,
        "cost_unknowns": cost_unknowns,
    }


def _sole_dominant(ids: List[str], views: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Retourne l'unique option dominant **toutes** les autres au sens de Pareto (≤ construction ET ≤ récurrent,
    strictement meilleure sur ≥1), ou ``None`` (égalité/tradeoff). Suppose l'ensemble déjà comparable/uniforme."""
    def dom(a: str, b: str) -> bool:
        va, vb = views[a], views[b]
        ca, ra = va["construction_total"], va["expected_recurring_total"]
        cb, rb = vb["construction_total"], vb["expected_recurring_total"]
        return ca <= cb and ra <= rb and (ca < cb or ra < rb)
    for x in ids:
        if all(dom(x, y) for y in ids if y != x):
            return x
    return None


# --------------------------------------------------------------------- #
# Fait solution_architecture (options seules) + orchestration
# --------------------------------------------------------------------- #
def build_architecture_fact(*, spec_source: Dict[str, Any], prompt: str, capability: str, adapter: str,
                            model: str, envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool,
                            as_of: str, pursuit_ref: str, argv: Any = None, stdout: Any = None,
                            stderr: Any = None) -> Dict[str, Any]:
    """Construit un fait **solution_architecture** honnête (pur, testable) portant **toutes** les options valides
    (ordre canonique par ``id``) — **aucune sélection** ici (la sélection BrainAI a lieu après estimation via
    :func:`compare_architectures`). ``cost_source = provider_call``. ``proposed`` uniquement si : pas de timeout,
    ``exit_code == 0`` (ou ``None``), enveloppe lisible, non ``is_error``, ``subtype == "success"``, ET options
    valides à ids distincts. Sinon ``failed`` (honnête, ``error``, ``diagnostic`` borné ; jamais de faux
    ``proposed``). Conserve ``spec_ref`` (= ``specification_id``), ``spec_sha256``, ``prompt_sha256``, ``cost``,
    ``usage``, ``as_of``, capability/adapter/model. Le store adresse l'id au contenu."""
    if not isinstance(pursuit_ref, str) or not pursuit_ref.strip():
        raise ValueError("build_architecture_fact : 'pursuit_ref' (chaîne non vide) requis — aucun fait orphelin/inter-Pursuit")
    specification_id, spec = validate_spec_source(spec_source)   # défensif : source cohérente et intacte
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    spec_sha256 = digest(spec)
    base: Dict[str, Any] = {
        "fact_type": "solution_architecture",
        "pursuit_ref": pursuit_ref,                              # scelle le fait à SA Pursuit (aucun inter-Pursuit)
        "cost_source": PROVIDER_CALL,
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "spec_ref": specification_id,                            # = specification_id (convention *_ref)
        "spec_sha256": spec_sha256,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "ARCHITECTURE_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    diag = diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                      timed_out=timed_out, envelope=envelope)
    nonzero_exit = exit_code is not None and exit_code != 0
    if (timed_out or envelope is None or nonzero_exit
            or envelope.get("is_error") or envelope.get("subtype") != "success"):
        if timed_out:
            reason = SAFETY_WATCHDOG_EXCEEDED
        elif envelope is None:
            reason = "enveloppe illisible"
        elif nonzero_exit:
            reason = f"exit non nul ({exit_code})"
        elif envelope.get("is_error") and envelope.get("subtype") == "success":
            reason = "erreur client sans détail (voir diagnostic)"
        else:
            reason = str(envelope.get("api_error_status") or envelope.get("subtype") or "erreur d'appel")
        if reason == "success":
            reason = "erreur client sans détail (voir diagnostic)"
        return {**base, "status": "failed", "options": None, "error": reason, "diagnostic": diag}
    # Réponse présente : parser puis valider localement le format Architecture (schéma strict + ids distincts).
    result = envelope.get("result")
    arch: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                arch = parsed
        except json.JSONDecodeError:
            arch = None
    elif isinstance(result, dict):
        arch = result
    if not _valid_architecture(arch):
        return {**base, "status": "failed", "options": None,
                "error": "format Architecture invalide", "diagnostic": diag}
    options = canonicalize_options(arch["options"])              # toutes les options valides, ordre canonique
    return {**base, "status": "proposed", "options": options, "error": None, "diagnostic": None}


@runtime_checkable
class SolutionArchitectureCapability(Protocol):
    """**Capacité** « proposer une architecture de solution » (R8) — BrainAI en dépend, jamais d'un outil concret.
    Contrat minimal : pour une ``spec`` structurée, produire la matière brute d'un fait (enveloppe/exit/timeout/
    prompt), **après** contrôle du budget. Implémentation interchangeable (consultant fournisseur)."""

    capability: str
    name: str
    model: str

    def propose(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeArchitectureAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`SolutionArchitectureCapability` (consultant
    d'architecture pour la capacité canonique ``architect.solution``). Miroir strict du motif
    ``ClaudeCodeSpecificationAdapter`` : texte seul, outils fichier/bash **désactivés**, budget vérifié AVANT,
    **une seule** invocation, **aucun retry**, argv-only (jamais shell), env confiné, watchdog. Claude **propose
    des OPTIONS** uniquement — **aucune sélection** dans l'adaptateur ; la comparaison/sélection reste BrainAI
    (:func:`compare_architectures`). CONNECTER, PAS RECONSTRUIRE : simple implémentation Claude Code, pas une
    nouvelle abstraction provider (L9 = généralisation ExecutionProvider)."""

    capability = "architect.solution"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = DEFAULT_WATCHDOG_S, claude_bin: str = "claude",
                 auth_mode: str = AUTH_KEYCHAIN_HOME, isolated_home: Optional[str] = None,
                 oauth_token: Optional[str] = None):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin
        self.auth_mode = auth_mode                  # bascule d'auth (B1 défaut) — étanchéité J3/T1
        self.isolated_home = isolated_home
        self.oauth_token = oauth_token

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré (``ARCHITECTURE_SCHEMA``), modèle
        explicite, plafond coût, outils fichier/bash **désactivés** (proposition d'options = texte seul)."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(ARCHITECTURE_SCHEMA, ensure_ascii=False),
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        return confined_env(self.auth_mode, isolated_home=self.isolated_home, oauth_token=self.oauth_token)

    def contract(self) -> AdapterContract:
        """Contrat d'adaptateur complet (T2) — texte seul (aucun outil fichier), coût réel (I6)."""
        return claude_text_contract(
            capability=self.capability, auth_channel=auth_channel(self.auth_mode),
            inbound_channels=inbound_channels(self.auth_mode),
            tools_disallowed=["Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch"])

    def propose(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable** — **une seule** invocation, **aucun retry**. Vérifie le budget AVANT (R2/B4) ;
        refuse sans appel (``run_confined`` non atteint) si le reste ne couvre pas le plafond. Renvoie
        ``{called, envelope, exit_code, timed_out, prompt, argv, stdout, stderr}`` — ne construit pas le fait."""
        prompt = build_architecture_prompt(spec)
        argv = self.build_argv(prompt)
        if budget_remaining_usd < self.max_budget_usd:
            return {"called": False, "envelope": None, "exit_code": None, "timed_out": False,
                    "prompt": prompt, "argv": argv, "stdout": None, "stderr": None,
                    "refused": "budget insuffisant"}
        result = run_confined(argv, cwd=cwd, timeout=self.timeout, env=self._env())
        envelope = None if result["timed_out"] else parse_envelope(result["stdout"])
        return {"called": True, "envelope": envelope, "exit_code": result["exit_code"],
                "timed_out": result["timed_out"], "prompt": prompt, "argv": argv,
                "stdout": result["stdout"], "stderr": result["stderr"]}


def produce_solution_architecture(*, spec_source: Dict[str, Any], adapter: SolutionArchitectureCapability,
                                  store: Any, budget_remaining_usd: float, cwd: Path, pursuit_ref: str,
                                  clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """**Chemin normal unique** Spécification → Architecture (options). ``pursuit_ref`` (obligatoire) scelle le
    fait à SA Pursuit — **validé AVANT tout appel provider**. Ordre : (0) valide ``pursuit_ref`` (chaîne non vide,
    sinon ``ValueError``, aucun appel) ; (1) valide le fait Spéc source (refus **avant** frontière externe) ;
    (2) **un seul** ``adapter.propose`` (garde budget incluse) ; (3) refus budget ⇒ **aucun fait** ; (4) sinon
    horodatage réel, construction du fait (options seules, aucune sélection) avec le **même** ``pursuit_ref``,
    **un seul** ``store.record`` — **aucun retry** (R6). Renvoie ``{"attempted", "recorded", "refused", "fact"}``."""
    if not isinstance(pursuit_ref, str) or not pursuit_ref.strip():   # (0) fail-closed AVANT tout appel provider
        raise ValueError("produce_solution_architecture : 'pursuit_ref' (chaîne non vide) requis")
    _, spec = validate_spec_source(spec_source)                 # (1) refus AVANT tout appel externe
    raw = adapter.propose(spec, cwd=cwd, budget_remaining_usd=budget_remaining_usd)  # (2) garde budget incluse
    if not raw.get("called"):                                    # (3) refus budget : aucune frontière, aucun fait
        return {"attempted": False, "recorded": False, "refused": raw.get("refused"), "fact": None}
    as_of = clock()                                             # (4) horodatage réel (jamais figé)
    fact = build_architecture_fact(
        spec_source=spec_source, prompt=raw["prompt"], capability=adapter.capability,
        adapter=adapter.name, model=getattr(adapter, "model", None), envelope=raw["envelope"],
        exit_code=raw["exit_code"], timed_out=raw["timed_out"], as_of=as_of, pursuit_ref=pursuit_ref,
        argv=raw.get("argv"), stdout=raw.get("stdout"), stderr=raw.get("stderr"))
    recorded = store.record(fact)                               # un seul fait, jamais de retry
    return {"attempted": True, "recorded": True, "refused": None, "fact": recorded}


class SolutionArchitectureStore:
    """Journal **append-only** des faits architecture (fichier injecté, hors ``data/``). Id **content-addressed**,
    ``as_of`` figé ; lecture **fail-closed** (ligne illisible lève). Aucune mémoire parallèle."""

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
                raise ValueError(f"SolutionArchitectureStore: ligne {i} JSON invalide ({exc}) — fail-closed") from exc
        return out

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait architecture immuable ; **le store adresse lui-même l'identifiant** (id appelant ignoré)
        à partir du **fait complet** (hors ``architecture_id``) — content-addressed."""
        stored = {k: v for k, v in fact.items() if k != "architecture_id"}
        architecture_id = short_id("arch", stored)
        stored = {"architecture_id": architecture_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


__all__ = ["ARCHITECTURE_SCHEMA", "build_architecture_prompt", "canonicalize_options",
           "compare_architectures", "build_architecture_fact", "SolutionArchitectureCapability",
           "ClaudeCodeArchitectureAdapter", "produce_solution_architecture", "SolutionArchitectureStore"]
