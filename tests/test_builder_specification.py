"""SPECIFICATION-PROPOSE-001 — spécification réelle gouvernée à partir d'un Brief.

Prouve que BrainAI peut faire **produire** une Spécification structurée par un LLM (Claude Code via
:class:`ClaudeCodeSpecificationAdapter`, implémentant :class:`SpecificationCapability`) à partir d'un
**fait Brief source complet**, et la **refléter comme fait `specification` proposé** append-only —
**sans** modifier aucun état officiel ni le Brief source (R5), avec **coût honnête** (réel ou
``unavailable`` — R2) et **aucun retry** (R6). La Spécification reste une **proposition** : elle ne
devient jamais officielle et ne déclenche **aucun Build**.

Tous les tests sont à **0 €** (enveloppe factice / adaptateur factice / budget refusé avant frontière).
Aucun appel réel n'est effectué.

Critères : S1 fait complet · S2 traçabilité déterministe de la source (référence + contenu liés, source
intacte) · S3 append-only + identité au contenu · S4 gouvernance (reste ``proposed``, rien déclenché) ·
S5 budget refusé **avant** toute frontière externe · S6 échecs gouvernables (schéma strict, timeout,
illisible, exit≠0, erreur client) avec RV-1 · S7 horodatage injectable (jamais figé sur un appel réel) ·
S8 confinement exact · S9 (frontière) — test dédié inchangé.
"""

from __future__ import annotations

import inspect
import json
import os
import re
from pathlib import Path

import pytest

from scc_brainai_bootstrap.builder import specification as S
from scc_brainai_bootstrap.builder.specification import (
    SPEC_SCHEMA,
    BriefSourceError,
    ClaudeCodeSpecificationAdapter,
    SpecificationCapability,
    build_prompt,
    build_specification,
    produce_specification,
    validate_brief_source,
)
from scc_brainai_bootstrap.builder.specifications import SpecificationStore
from scc_brainai_bootstrap.core.clock import digest

AS_OF = "2026-08-06T12:00:00+00:00"

# --- Brief source réel du refuge (jamais réécrit) : fait Brief COMPLET (proposal_id + status + brief). ---
SOURCE_BRIEF = {
    "objective": "Gérer un refuge animalier : animaux, adoptants, rendez-vous.",
    "context": "Petite structure associative.",
    "actors": ["Personnel du refuge", "Adoptant", "Vétérinaire"],
    "scope": ["Animaux", "Adoptants", "Rendez-vous"],
    "assumptions": ["Usage web interne"],
    "open_questions": ["Multi-refuge ?"],
    "constraints": ["Budget limité"],
}
SOURCE_FACT = {"proposal_id": "prop_5f95586415f8", "status": "proposed",
               "capability": "understanding", "brief": SOURCE_BRIEF}

_SPEC_KEYS = ("product_objective", "users_and_roles", "functional_scope", "features",
              "entities_and_data", "key_journeys", "constraints", "acceptance_criteria",
              "assumptions", "open_questions", "out_of_scope")

_VALID_SPEC_OBJ = {
    "product_objective": "Application de gestion centralisée d'un refuge animalier.",
    "users_and_roles": ["Personnel (soigneur, admin)", "Adoptant"],
    "functional_scope": ["Registre animaux", "Base adoptants", "Rendez-vous"],
    "features": ["Fiche animal", "Recherche adoptant", "Planning RDV"],
    "entities_and_data": ["Animal", "Adoptant", "RendezVous"],
    "key_journeys": ["Enregistrer un animal", "Planifier une visite d'adoption"],
    "constraints": ["Budget limité", "Usage web interne"],
    "acceptance_criteria": ["Un animal peut être créé et retrouvé", "Un RDV peut être planifié"],
    "assumptions": ["Un seul refuge en V1"],
    "open_questions": ["Notifications par email ?"],
    "out_of_scope": ["Paiement en ligne", "Application mobile native"],
}
_VALID_SPEC = json.dumps(_VALID_SPEC_OBJ, ensure_ascii=False)


def _envelope(result: str, *, ok: bool = True, cost=0.0217846, usage=None):
    """Enveloppe Claude Code réaliste — AUCUN appel réel."""
    return {
        "type": "result", "subtype": "success" if ok else "error_max_turns",
        "is_error": not ok, "api_error_status": None, "num_turns": 1,
        "result": result, "total_cost_usd": cost,
        "usage": usage if usage is not None else {"input_tokens": 120, "output_tokens": 210},
        "modelUsage": {"claude-haiku-4-5": {"costUSD": cost}},
    }


def _spec(envelope, *, timed_out=False, exit_code=0, as_of=AS_OF, source=SOURCE_FACT,
          argv=None, stdout=None, stderr=None):
    return build_specification(brief_source=source, prompt=build_prompt(source["brief"]),
                               capability="specification", adapter="claude_code", model="haiku",
                               envelope=envelope, exit_code=exit_code, timed_out=timed_out, as_of=as_of,
                               argv=argv, stdout=stdout, stderr=stderr)


class _FakeAdapter:
    """Adaptateur factice conforme au Protocol — renvoie une enveloppe canned, **sans appel réel**.

    Applique la **même garde budget** que l'adaptateur réel (refus AVANT toute frontière) et compte les
    invocations de ``propose`` (pour prouver l'absence de retry)."""

    capability = "specification"
    name = "claude_code"

    def __init__(self, envelope, *, budget_floor=0.50, model="haiku", exit_code=0, timed_out=False):
        self._env = envelope
        self.budget_floor = budget_floor
        self.model = model
        self._exit = exit_code
        self._timed_out = timed_out
        self.calls: list = []

    def propose(self, brief, *, cwd, budget_remaining_usd):
        self.calls.append(dict(brief))
        prompt = build_prompt(brief)
        if budget_remaining_usd < self.budget_floor:
            return {"called": False, "refused": "budget insuffisant", "envelope": None,
                    "exit_code": None, "timed_out": False, "prompt": prompt,
                    "argv": ["claude"], "stdout": None, "stderr": None}
        return {"called": True, "envelope": self._env, "exit_code": self._exit,
                "timed_out": self._timed_out, "prompt": prompt,
                "argv": ["claude", "-p", "<prompt>"], "stdout": "<stdout>", "stderr": ""}


# ===================================================================== #
# R8 — séparation capacité / outil concret
# ===================================================================== #
def test_adapter_implements_capability_protocol():
    adapter = ClaudeCodeSpecificationAdapter()
    assert isinstance(adapter, SpecificationCapability)
    assert adapter.capability == "specification" and adapter.name == "claude_code"


# ===================================================================== #
# S1 — fait COMPLET (à partir d'une source Brief complète et cohérente)
# ===================================================================== #
def test_specification_fact_is_complete_on_success(tmp_path):
    store = SpecificationStore(tmp_path / "specs.jsonl")
    fact = store.record(_spec(_envelope(_VALID_SPEC)))
    assert fact["specification_id"].startswith("spec_")                 # id adressé-contenu (par le store)
    assert fact["fact_type"] == "specification"
    assert fact["status"] == "proposed" and fact["error"] is None and fact["diagnostic"] is None
    assert fact["model"] == "haiku"
    assert fact["capability"] == "specification" and fact["adapter"] == "claude_code"
    assert fact["brief_ref"] == SOURCE_FACT["proposal_id"]              # référence à la source
    assert fact["brief_sha256"] == digest(SOURCE_BRIEF)                 # empreinte du contenu source
    assert fact["prompt_sha256"] and "BRIEF" in fact["prompt"]
    assert fact["params"] == {"output_format": "json", "json_schema": "SPEC_SCHEMA"}
    assert all(k in fact["specification"] for k in _SPEC_KEYS)          # 11 champs
    assert fact["usage"]["output_tokens"] == 210
    assert fact["cost"] == {"value": 0.0217846, "kind": "real"}
    assert fact["as_of"] == AS_OF


def test_cost_unavailable_when_absent_never_fabricated():
    env = _envelope(_VALID_SPEC); del env["total_cost_usd"]
    assert _spec(env)["cost"] == {"value": None, "kind": "unavailable"}


# ===================================================================== #
# S2 (point 1) — source Brief complète : refus AVANT appel des sources invalides
# ===================================================================== #
@pytest.mark.parametrize("bad, why", [
    ("pas un dict", "objet"),
    ({"status": "proposed", "brief": SOURCE_BRIEF}, "proposal_id"),                  # sans id
    ({"proposal_id": "prop_x", "status": "failed", "brief": SOURCE_BRIEF}, "proposed"),  # failed
    ({"proposal_id": "prop_x", "status": "proposed"}, "brief"),                      # sans brief
    ({"proposal_id": "prop_x", "status": "proposed", "brief": "pas un dict"}, "brief"),
    ({"proposal_id": "", "status": "proposed", "brief": SOURCE_BRIEF}, "proposal_id"),   # id vide
])
def test_validate_brief_source_rejects_invalid(bad, why):
    with pytest.raises(BriefSourceError) as exc:
        validate_brief_source(bad)
    assert why in str(exc.value)


def test_produce_refuses_invalid_source_before_any_external_call(tmp_path, monkeypatch):
    # Garde-fou : toute frontière externe fait échouer le test.
    monkeypatch.setattr(S, "run_confined", lambda *a, **k: pytest.fail("frontière externe atteinte !"))
    store = SpecificationStore(tmp_path / "specs.jsonl")
    adapter = ClaudeCodeSpecificationAdapter(max_budget_usd=0.50)
    bad_source = {"proposal_id": "prop_x", "status": "failed", "brief": SOURCE_BRIEF}
    with pytest.raises(BriefSourceError):
        produce_specification(brief_source=bad_source, adapter=adapter, store=store,
                              budget_remaining_usd=5.0, cwd=tmp_path)
    assert store.read_all() == []                                       # aucun fait produit


# ===================================================================== #
# S2 (point 1) — impossible d'associer une référence à un autre contenu
# ===================================================================== #
def test_reference_and_content_are_bound_to_a_single_source():
    # L'API n'expose AUCUN moyen de fournir brief_ref/brief séparément.
    params = set(inspect.signature(build_specification).parameters)
    assert "brief_source" in params
    assert "brief_ref" not in params and "brief" not in params
    # ref et empreinte proviennent du MÊME objet source : on ne peut pas les décorréler.
    fact = _spec(_envelope(_VALID_SPEC))
    assert fact["brief_ref"] == SOURCE_FACT["proposal_id"]
    assert fact["brief_sha256"] == digest(SOURCE_FACT["brief"])
    other = {"proposal_id": "prop_autre", "status": "proposed",
             "brief": dict(SOURCE_BRIEF, objective="Tout autre besoin.")}
    f2 = _spec(_envelope(_VALID_SPEC), source=other)
    assert f2["brief_ref"] == "prop_autre" and f2["brief_sha256"] == digest(other["brief"])
    assert f2["brief_sha256"] != fact["brief_sha256"]                   # contenu ≠ → empreinte ≠


def test_source_brief_is_not_modified():
    before = json.dumps(SOURCE_FACT, sort_keys=True, ensure_ascii=False)
    _spec(_envelope(_VALID_SPEC))
    assert json.dumps(SOURCE_FACT, sort_keys=True, ensure_ascii=False) == before


# ===================================================================== #
# S3 (point 2) — identité adressée au CONTENU, calculée par le store
# ===================================================================== #
def test_same_brief_prompt_asof_but_different_spec_content_gives_different_ids(tmp_path):
    store = SpecificationStore(tmp_path / "specs.jsonl")
    spec_a = dict(_VALID_SPEC_OBJ)
    spec_b = dict(_VALID_SPEC_OBJ, product_objective="Objectif produit DIFFÉRENT.")
    f1 = store.record(_spec(_envelope(json.dumps(spec_a, ensure_ascii=False))))
    f2 = store.record(_spec(_envelope(json.dumps(spec_b, ensure_ascii=False))))   # mêmes Brief/prompt/as_of
    assert f1["prompt_sha256"] == f2["prompt_sha256"] and f1["as_of"] == f2["as_of"]
    assert f1["specification"] != f2["specification"]
    assert f1["specification_id"] != f2["specification_id"]             # contenu ≠ → id ≠


def test_same_content_same_id_is_deterministic():
    a = SpecificationStore(Path("/dev/null"))   # jamais écrit : on n'appelle pas record ici
    id1 = _id_of(_spec(_envelope(_VALID_SPEC)))
    id2 = _id_of(_spec(_envelope(_VALID_SPEC)))
    assert id1 == id2 and id1.startswith("spec_")


def test_failed_and_proposed_differ_by_id():
    proposed = _id_of(_spec(_envelope(_VALID_SPEC)))
    failed = _id_of(_spec(_envelope("pas du JSON")))   # même source/as_of, statut différent
    assert proposed != failed                                          # le statut participe à l'id


def test_caller_supplied_specification_id_is_ignored(tmp_path):
    store = SpecificationStore(tmp_path / "specs.jsonl")
    fact = _spec(_envelope(_VALID_SPEC))
    forged = dict(fact, specification_id="spec_FORGERY")
    stored = store.record(forged)
    assert stored["specification_id"] != "spec_FORGERY"                # id appelant ignoré, recalculé
    assert stored["specification_id"].startswith("spec_")


def test_two_specifications_append_only(tmp_path):
    store = SpecificationStore(tmp_path / "specs.jsonl")
    f1 = store.record(_spec(_envelope(json.dumps(dict(_VALID_SPEC_OBJ), ensure_ascii=False))))
    f2 = store.record(_spec(_envelope(json.dumps(dict(_VALID_SPEC_OBJ, features=["Autre"]), ensure_ascii=False))))
    lines = store.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and len(store.read_all()) == 2
    assert f1["specification_id"] != f2["specification_id"]
    assert json.loads(lines[0])["specification_id"] == f1["specification_id"]   # 1ʳᵉ ligne intacte


def _id_of(fact):
    """Calcule l'id via le store, sans écrire sur disque (répertoire tmp implicite non touché)."""
    import tempfile
    store = SpecificationStore(Path(tempfile.mkdtemp()) / "s.jsonl")
    return store.record(fact)["specification_id"]


# ===================================================================== #
# S4 — gouvernance : reste proposed ; aucune mutation/validation/Build
# ===================================================================== #
def test_specification_stays_proposed_and_triggers_nothing(tmp_path):
    store = SpecificationStore(tmp_path / "specs.jsonl")
    fact = store.record(_spec(_envelope(_VALID_SPEC)))
    assert fact["status"] == "proposed"
    for forbidden in ("validated", "official", "approved", "build", "build_triggered", "artifact"):
        assert forbidden not in fact
    produced = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert produced == {"specs.jsonl"}                                 # aucun fichier applicatif


# ===================================================================== #
# S6 (point 3) — validation LOCALE STRICTE du schéma
# ===================================================================== #
def test_wrong_type_is_failure():
    bad = dict(_VALID_SPEC_OBJ, product_objective=["devrait être une chaîne"])   # mauvais type
    fact = _spec(_envelope(json.dumps(bad, ensure_ascii=False)))
    assert fact["status"] == "failed" and "format Spécification invalide" in fact["error"]


def test_extra_property_is_failure():
    bad = dict(_VALID_SPEC_OBJ, unexpected="propriété en trop")        # propriété supplémentaire
    fact = _spec(_envelope(json.dumps(bad, ensure_ascii=False)))
    assert fact["status"] == "failed" and "format Spécification invalide" in fact["error"]


def test_non_textual_list_element_is_failure():
    bad = dict(_VALID_SPEC_OBJ, features=["ok", 123])                  # élément non textuel dans une liste
    fact = _spec(_envelope(json.dumps(bad, ensure_ascii=False)))
    assert fact["status"] == "failed" and "format Spécification invalide" in fact["error"]


def test_missing_required_key_is_failure():
    bad = dict(_VALID_SPEC_OBJ); del bad["out_of_scope"]
    fact = _spec(_envelope(json.dumps(bad, ensure_ascii=False)))
    assert fact["status"] == "failed" and "format Spécification invalide" in fact["error"]


# ===================================================================== #
# S6 — autres échecs gouvernables, sans crash ni retry, avec RV-1
# ===================================================================== #
def test_invalid_json_result_is_failure():
    fact = _spec(_envelope("ceci n'est pas du JSON"))
    assert fact["status"] == "failed" and fact["specification"] is None and fact["diagnostic"] is not None


def test_timeout_is_failure_without_crash():
    fact = _spec(None, timed_out=True)
    assert fact["status"] == "failed" and fact["error"] == "timeout"
    assert fact["cost"]["kind"] == "unavailable" and fact["diagnostic"]["timed_out"] is True


def test_unreadable_envelope_is_failure():
    fact = _spec(None)
    assert fact["status"] == "failed" and "illisible" in fact["error"]


def test_brain_error_envelope_is_failure():
    fact = _spec(_envelope(_VALID_SPEC, ok=False))
    assert fact["status"] == "failed" and fact["specification"] is None


def test_nonzero_exit_is_failure_even_with_valid_envelope():
    fact = _spec(_envelope(_VALID_SPEC), exit_code=1, stderr="boom")
    assert fact["status"] == "failed" and "exit non nul (1)" in fact["error"]
    assert fact["diagnostic"]["exit_code"] == 1


def test_client_error_without_detail_never_says_success():
    env = _envelope("peu importe"); env["is_error"] = True             # is_error=true, subtype=success
    fact = _spec(env)
    assert fact["status"] == "failed"
    assert fact["error"] == "erreur client sans détail (voir diagnostic)" and fact["error"] != "success"


def test_secret_redacted_in_failed_diagnostic_and_never_persisted(tmp_path):
    secret = "sk-ant-api03-FAKEfakeVALUE1234567890ABCDEFxyz"
    env = _envelope(f'{{"leak":"{secret}"}}', ok=False)
    fact = _spec(env, stdout=f"log {secret}", argv=["claude", "-p", "x"])
    store = SpecificationStore(tmp_path / "s.jsonl")
    store.record(fact)
    assert secret not in store.path.read_text(encoding="utf-8")        # jamais persisté (RV-1)
    assert "[REDACTED-KEY]" in fact["diagnostic"]["stdout"]


# ===================================================================== #
# S5 (point 5) — budget refusé AVANT toute frontière externe
# ===================================================================== #
def test_budget_refusal_happens_before_external_frontier(tmp_path, monkeypatch):
    # run_confined piégé : s'il est appelé, le test ÉCHOUE.
    monkeypatch.setattr(S, "run_confined", lambda *a, **k: pytest.fail("run_confined appelé malgré budget insuffisant"))
    store = SpecificationStore(tmp_path / "specs.jsonl")
    adapter = ClaudeCodeSpecificationAdapter(max_budget_usd=0.50)      # adaptateur RÉEL
    cwd = tmp_path / "neutral"; cwd.mkdir()
    out = produce_specification(brief_source=SOURCE_FACT, adapter=adapter, store=store,
                                budget_remaining_usd=0.10, cwd=cwd)     # reste < plafond
    assert out["attempted"] is False and out["recorded"] is False and out["refused"] == "budget insuffisant"
    assert store.read_all() == []                                      # aucun fait, aucune frontière franchie


def test_argv_is_confined_and_structured():
    argv = ClaudeCodeSpecificationAdapter(model="haiku", max_budget_usd=0.30).build_argv("prompt")
    assert argv[0] == "claude" and "-p" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--max-budget-usd") + 1] == "0.3"
    for tool in ("Bash", "Edit", "Write", "Read"):
        assert tool in argv                                           # aucun outil de Build autorisé


# ===================================================================== #
# S4/S7 (point 4) — produce_specification : chemin normal unique
# ===================================================================== #
def test_produce_records_exactly_one_fact_per_external_attempt(tmp_path):
    adapter = _FakeAdapter(_envelope(_VALID_SPEC))
    store = SpecificationStore(tmp_path / "specs.jsonl")
    out = produce_specification(brief_source=SOURCE_FACT, adapter=adapter, store=store,
                                budget_remaining_usd=5.0, cwd=tmp_path,
                                clock=lambda: "2099-01-01T00:00:00+00:00")
    assert out["attempted"] and out["recorded"]
    assert out["fact"]["status"] == "proposed" and out["fact"]["fact_type"] == "specification"
    assert len(store.read_all()) == 1                                  # EXACTEMENT un fait
    assert len(adapter.calls) == 1                                     # AUCUN retry


def test_produce_uses_injectable_clock_for_real_timestamp(tmp_path):
    adapter = _FakeAdapter(_envelope(_VALID_SPEC))
    store = SpecificationStore(tmp_path / "specs.jsonl")
    stamp = "2031-05-04T03:02:01+00:00"
    out = produce_specification(brief_source=SOURCE_FACT, adapter=adapter, store=store,
                                budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: stamp)
    assert out["fact"]["as_of"] == stamp                              # horodatage vient de l'horloge injectée


def test_produce_default_clock_is_real_not_hardcoded():
    # L'horloge par défaut existe et n'est pas un littéral figé ; le module ne code aucun horodatage en dur.
    assert callable(S._system_clock)
    src = Path(S.__file__).read_text(encoding="utf-8")
    assert not re.search(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", src)


def test_produce_failed_call_still_records_exactly_one_fact(tmp_path):
    adapter = _FakeAdapter(_envelope("pas du JSON"))                   # réponse invalide → failed
    store = SpecificationStore(tmp_path / "specs.jsonl")
    out = produce_specification(brief_source=SOURCE_FACT, adapter=adapter, store=store,
                                budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: AS_OF)
    assert out["fact"]["status"] == "failed" and len(store.read_all()) == 1
    assert len(adapter.calls) == 1                                     # une tentative, aucun retry


# ===================================================================== #
# S8 — confinement : composition EXACTE de l'environnement transmis
# ===================================================================== #
def test_env_composition_is_exactly_identity_and_no_more():
    env = ClaudeCodeSpecificationAdapter()._env()
    allowed = {"PATH", "LANG"}
    for k in ("HOME", "USER", "LOGNAME"):
        if os.environ.get(k):
            allowed.add(k)
    assert set(env) == allowed
    for k in ("HOME", "USER", "LOGNAME"):
        if os.environ.get(k):
            assert env[k] == os.environ[k]
    assert not any(re.search(r"(?i)token|secret|password|api[_-]?key|credential|bearer", k) for k in env)


def test_build_prompt_prefixes_condensed_identity_arbitrates_and_weaves_blind_spots():
    # COGNITIVE-IDENTITY-001 T3 — la mission specification est préfixée par l'ESSENCE, tranche les choix
    # structurants (M4) et intègre les angles morts au raisonnement (M6), sans rubrique décorative. Schéma
    # et contrat inchangés (vérifiés par ailleurs).
    from scc_brainai_bootstrap.builder.cognitive_identity import CONDENSED_IDENTITY
    p = build_prompt(SOURCE_BRIEF)
    assert CONDENSED_IDENTITY[:40] in p and "ta nature" in p.lower()      # essence injectée
    assert p.index(CONDENSED_IDENTITY[:40]) < p.index("BRIEF (source")    # identité AVANT la tâche
    assert "SPÉCIFICATION" in p and "EXCLUSIVEMENT" in p                  # consignes historiques conservées
    assert "tranche explicitement plutôt que de rester neutre" in p       # M4 : arbitrage
    assert "angles morts identifiés sont intégrés" in p                   # M6 : pas de rubrique décorative
    assert "hypothèse faite faute d'information" in p                     # M5 : hypothèses nommées
