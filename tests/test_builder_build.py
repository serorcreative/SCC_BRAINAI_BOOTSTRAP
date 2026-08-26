"""BUILD-PROPOSE-001 — capacité de build gouvernée : Spécification → manifeste confiné.

Prouve à **0 €** : contrat (T1) + matérialisation confinée + fait `build` + `produce_build` (T2).
Aucun appel réel : enveloppes/adaptateur factices, budget refusé avant frontière.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

import pytest

from scc_brainai_bootstrap.builder import build as B
from scc_brainai_bootstrap.builder.build import (
    ARTIFACT_FILENAME,
    MANIFEST_SCHEMA,
    NAME_MAX,
    BuildCapability,
    ClaudeCodeBuildAdapter,
    SpecSourceError,
    build_build,
    build_prompt,
    materialize_manifest,
    parse_manifest,
    produce_build,
    validate_spec_source,
)
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError

AS_OF = "2026-08-06T12:00:00+00:00"

_SPEC = {
    "product_objective": "Application de gestion centralisée d'un refuge animalier.",
    "users_and_roles": ["Personnel (soigneur, admin)", "Adoptant"],
    "functional_scope": ["Registre animaux", "Base adoptants", "Rendez-vous"],
    "features": ["Fiche animal", "Recherche adoptant", "Planning RDV"],
    "entities_and_data": ["Animal", "Adoptant", "RendezVous"],
    "key_journeys": ["Enregistrer un animal", "Planifier une visite"],
    "constraints": ["Budget limité"],
    "acceptance_criteria": ["Un animal peut être créé et retrouvé"],
    "assumptions": ["Un seul refuge en V1"],
    "open_questions": ["Notifications par email ?"],
    "out_of_scope": ["Paiement en ligne"],
}
SPEC_SOURCE = {"specification_id": "spec_d5c02d00891b", "status": "proposed",
               "fact_type": "specification", "specification": _SPEC}

_VALID_MANIFEST = {
    "name": "Gestion Refuge Animalier",
    "summary": "Application centralisée pour animaux, adoptants et rendez-vous d'un refuge.",
    "users": ["Personnel", "Adoptant"],
    "features": ["Fiche animal", "Recherche adoptant", "Planning RDV"],
    "entities": ["Animal", "Adoptant", "RendezVous"],
}


def _envelope(result, *, ok=True, cost=0.05, usage=None):
    return {
        "type": "result", "subtype": "success" if ok else "error_max_turns",
        "is_error": not ok, "api_error_status": None, "num_turns": 1,
        "result": result, "total_cost_usd": cost,
        "usage": usage if usage is not None else {"input_tokens": 100, "output_tokens": 60},
        "modelUsage": {"claude-haiku-4-5": {"costUSD": cost}},
    }


class _FakeAdapter:
    """Adaptateur factice conforme au Protocol — enveloppe canned, **sans appel réel**, compte les appels."""

    capability = "build"
    name = "claude_code"

    def __init__(self, envelope, *, budget_floor=0.50, model="haiku", exit_code=0, timed_out=False):
        self._env = envelope
        self.budget_floor = budget_floor
        self.model = model
        self._exit = exit_code
        self._timed_out = timed_out
        self.calls: list = []

    def propose(self, spec, *, cwd, budget_remaining_usd):
        self.calls.append(dict(spec))
        prompt = build_prompt(spec)
        if budget_remaining_usd < self.budget_floor:
            return {"called": False, "refused": "budget insuffisant", "envelope": None,
                    "exit_code": None, "timed_out": False, "prompt": prompt,
                    "argv": ["claude"], "stdout": None, "stderr": None}
        return {"called": True, "envelope": self._env, "exit_code": self._exit,
                "timed_out": self._timed_out, "prompt": prompt,
                "argv": ["claude", "-p", "<prompt>"], "stdout": "<stdout>", "stderr": ""}


def _ws(tmp_path, project_id="refuge-demo"):
    return Workspace(tmp_path / "exec-root", project_id)


# ===================================================================== #
# T1 — contrat (validation, schéma, prompt, adaptateur)
# ===================================================================== #
def test_adapter_implements_capability_protocol():
    adapter = ClaudeCodeBuildAdapter()
    assert isinstance(adapter, BuildCapability)
    assert adapter.capability == "build" and adapter.name == "claude_code"


def test_validate_spec_source_accepts_complete_source():
    sid, spec = validate_spec_source(SPEC_SOURCE)
    assert sid == "spec_d5c02d00891b" and spec is SPEC_SOURCE["specification"]


@pytest.mark.parametrize("bad, why", [
    ("pas un dict", "objet"),
    ({"status": "proposed", "specification": _SPEC}, "specification_id"),
    ({"specification_id": "", "status": "proposed", "specification": _SPEC}, "specification_id"),
    ({"specification_id": "spec_x", "status": "failed", "specification": _SPEC}, "proposed"),
    ({"specification_id": "spec_x", "status": "proposed"}, "11 champs"),
    ({"specification_id": "spec_x", "status": "proposed", "specification": "x"}, "11 champs"),
    ({"specification_id": "spec_x", "status": "proposed",
      "specification": {k: v for k, v in _SPEC.items() if k != "out_of_scope"}}, "11 champs"),
])
def test_validate_spec_source_rejects_invalid(bad, why):
    with pytest.raises(SpecSourceError) as exc:
        validate_spec_source(bad)
    assert why in str(exc.value)


def test_manifest_schema_has_exactly_five_keys():
    assert set(MANIFEST_SCHEMA["properties"]) == {"name", "summary", "users", "features", "entities"}
    assert MANIFEST_SCHEMA["required"] == ["name", "summary", "users", "features", "entities"]
    assert MANIFEST_SCHEMA["additionalProperties"] is False
    assert ARTIFACT_FILENAME == "manifest.json" and NAME_MAX == 80


def test_valid_manifest_accepts_well_formed():
    assert B._valid_manifest(_VALID_MANIFEST) is True
    assert B._valid_manifest({**_VALID_MANIFEST, "users": [], "features": [], "entities": []}) is True


def test_valid_manifest_rejects_extra_property_including_paths():
    assert B._valid_manifest({**_VALID_MANIFEST, "unexpected": "x"}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "path": "manifest.json"}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "filename": "m.json"}) is False


def test_valid_manifest_rejects_missing_key():
    m = dict(_VALID_MANIFEST); del m["entities"]
    assert B._valid_manifest(m) is False


def test_valid_manifest_rejects_empty_or_overlong_name():
    assert B._valid_manifest({**_VALID_MANIFEST, "name": ""}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "name": "   "}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "name": "x" * 80}) is True
    assert B._valid_manifest({**_VALID_MANIFEST, "name": "x" * 81}) is False


def test_valid_manifest_rejects_empty_summary_and_wrong_types():
    assert B._valid_manifest({**_VALID_MANIFEST, "summary": ""}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "name": ["not a str"]}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "users": "not a list"}) is False


def test_valid_manifest_rejects_non_textual_or_empty_list_element():
    assert B._valid_manifest({**_VALID_MANIFEST, "features": ["ok", 123]}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "features": ["ok", ""]}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "entities": ["ok", "  "]}) is False


def test_build_prompt_is_derived_only_from_spec_and_forbids_invention_and_paths():
    prompt = build_prompt(_SPEC)
    assert _SPEC["product_objective"] in prompt and "SPÉCIFICATION" in prompt
    assert "n'invente AUCUNE" in prompt
    assert "AUCUN chemin ni nom de fichier" in prompt and "AUCUNE propriété supplémentaire" in prompt
    for k in ("name", "summary", "users", "features", "entities"):
        assert k in prompt
    assert str(NAME_MAX) in prompt


def test_argv_is_confined_and_structured():
    argv = ClaudeCodeBuildAdapter(model="haiku", max_budget_usd=0.30).build_argv("prompt")
    assert argv[0] == "claude" and "-p" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--max-budget-usd") + 1] == "0.3"
    assert "--json-schema" in argv and "--disallowedTools" in argv
    for tool in ("Bash", "Edit", "Write", "Read"):
        assert tool in argv


def test_env_composition_is_exactly_identity_and_no_more():
    env = ClaudeCodeBuildAdapter()._env()
    allowed = {"PATH", "LANG"}
    for k in ("HOME", "USER", "LOGNAME"):
        if os.environ.get(k):
            allowed.add(k)
    assert set(env) == allowed
    assert not any(re.search(r"(?i)token|secret|password|api[_-]?key|credential|bearer", k) for k in env)


# ===================================================================== #
# T2 — parse_manifest / build_build (fait pur)
# ===================================================================== #
def test_parse_manifest_valid_and_invalid():
    assert parse_manifest(_envelope(json.dumps(_VALID_MANIFEST))) == _VALID_MANIFEST
    assert parse_manifest(_envelope("pas du JSON")) is None
    assert parse_manifest(_envelope(json.dumps({"name": "x"}))) is None          # incomplet
    assert parse_manifest(None) is None


_ART = {"relative_path": "manifest.json", "sha256": "a" * 64, "byte_size": 123}


def _bb(envelope, *, artefact=None, exit_code=0, timed_out=False, as_of=AS_OF, stdout=None, argv=None):
    return build_build(spec_source=SPEC_SOURCE, prompt=build_prompt(_SPEC), capability="build",
                       adapter="claude_code", model="haiku", envelope=envelope, exit_code=exit_code,
                       timed_out=timed_out, as_of=as_of, artefact=artefact, stdout=stdout, argv=argv)


def test_build_build_proposed_requires_materialized_artefact():
    ok = _bb(_envelope(json.dumps(_VALID_MANIFEST)), artefact=_ART)
    assert ok["status"] == "proposed" and ok["artefact"] == _ART and ok["diagnostic"] is None
    assert ok["fact_type"] == "build" and ok["spec_ref"] == "spec_d5c02d00891b"
    assert ok["spec_sha256"] and ok["prompt_sha256"] and ok["params"]["json_schema"] == "MANIFEST_SCHEMA"
    # valide mais artefact non fourni → garde-fou : failed, pas de faux "proposed"
    guard = _bb(_envelope(json.dumps(_VALID_MANIFEST)), artefact=None)
    assert guard["status"] == "failed" and guard["artefact"] is None


def test_build_build_failure_branches_have_no_artefact_and_have_diagnostic():
    for env, exit_code, timed_out, needle in [
        (None, 0, True, "safety_watchdog_exceeded"),
        (None, 0, False, "illisible"),
        (_envelope(json.dumps(_VALID_MANIFEST)), 1, False, "exit non nul (1)"),
        (_envelope(json.dumps(_VALID_MANIFEST), ok=False), 0, False, None),
        (_envelope(json.dumps({"name": "x"})), 0, False, "manifeste invalide"),
    ]:
        fact = _bb(env, artefact=_ART, exit_code=exit_code, timed_out=timed_out)
        assert fact["status"] == "failed" and fact["artefact"] is None
        assert fact["diagnostic"] is not None
        if needle:
            assert needle in fact["error"]


def test_cost_is_honest():
    assert _bb(_envelope(json.dumps(_VALID_MANIFEST)), artefact=_ART)["cost"] == {"value": 0.05, "kind": "real"}
    env = _envelope(json.dumps(_VALID_MANIFEST)); del env["total_cost_usd"]
    assert _bb(env, artefact=_ART)["cost"] == {"value": None, "kind": "unavailable"}


# ===================================================================== #
# T2 — matérialisation confinée
# ===================================================================== #
def test_materialize_writes_only_in_workspace_at_imposed_path(tmp_path):
    ws = _ws(tmp_path)
    art = materialize_manifest(_VALID_MANIFEST, ws)
    target = ws.path / "manifest.json"
    assert target.exists() and art["relative_path"] == "manifest.json"           # chemin imposé
    files = [p for p in ws.path.rglob("*") if p.is_file()]
    assert files == [target]                                                     # UNIQUEMENT dans le workspace
    data = target.read_bytes()
    assert art["sha256"] == hashlib.sha256(data).hexdigest()                     # hash == octets disque
    assert art["byte_size"] == len(data)                                         # taille exacte


def test_workspace_refuses_escape_absolute_parent_and_symlink(tmp_path):
    ws = _ws(tmp_path); ws.ensure()
    with pytest.raises(WorkspaceError):
        ws.resolve_within("/etc/passwd")                                         # absolu
    with pytest.raises(WorkspaceError):
        ws.resolve_within("../escape.json")                                      # ..
    outside = tmp_path / "outside"; outside.mkdir()
    (ws.path / "link").symlink_to(outside)
    with pytest.raises(WorkspaceError):
        ws.resolve_within("link/evil.json")                                      # symlink échappant


# ===================================================================== #
# T2 — produce_build : chemin normal unique
# ===================================================================== #
def test_produce_build_success_materializes_and_records_one_fact(tmp_path):
    adapter = _FakeAdapter(_envelope(json.dumps(_VALID_MANIFEST)))
    store = BuildStore(tmp_path / "builds.jsonl")
    ws = _ws(tmp_path)
    out = produce_build(spec_source=SPEC_SOURCE, adapter=adapter, store=store, workspace=ws,
                        budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: "2099-01-01T00:00:00+00:00")
    assert out["attempted"] and out["recorded"]
    fact = out["fact"]
    assert fact["status"] == "proposed" and fact["fact_type"] == "build"
    assert fact["spec_ref"] == "spec_d5c02d00891b" and fact["as_of"] == "2099-01-01T00:00:00+00:00"
    art = fact["artefact"]
    target = ws.path / "manifest.json"
    assert target.exists() and art["relative_path"] == "manifest.json"
    data = target.read_bytes()
    assert art["sha256"] == hashlib.sha256(data).hexdigest() and art["byte_size"] == len(data)
    assert len(store.read_all()) == 1                                            # EXACTEMENT un fait
    assert len(adapter.calls) == 1                                              # AUCUN retry


def test_produce_build_refuses_invalid_source_before_any_external_call(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "run_confined", lambda *a, **k: pytest.fail("frontière externe atteinte !"))
    store = BuildStore(tmp_path / "builds.jsonl")
    ws = _ws(tmp_path)
    adapter = ClaudeCodeBuildAdapter(max_budget_usd=0.50)
    bad = {"specification_id": "spec_x", "status": "failed", "specification": _SPEC}
    with pytest.raises(SpecSourceError):
        produce_build(spec_source=bad, adapter=adapter, store=store, workspace=ws,
                      budget_remaining_usd=5.0, cwd=tmp_path)
    assert store.read_all() == [] and not (ws.path / "manifest.json").exists()


def test_produce_build_budget_refusal_before_frontier(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "run_confined", lambda *a, **k: pytest.fail("run_confined appelé malgré budget insuffisant"))
    store = BuildStore(tmp_path / "builds.jsonl")
    ws = _ws(tmp_path)
    adapter = ClaudeCodeBuildAdapter(max_budget_usd=0.50)
    out = produce_build(spec_source=SPEC_SOURCE, adapter=adapter, store=store, workspace=ws,
                        budget_remaining_usd=0.10, cwd=tmp_path)
    assert out["attempted"] is False and out["refused"] == "budget insuffisant"
    assert store.read_all() == [] and not (ws.path / "manifest.json").exists()


def test_produce_build_failure_records_fact_without_artefact(tmp_path):
    adapter = _FakeAdapter(_envelope(json.dumps({"name": "x"})))                 # manifeste incomplet → failed
    store = BuildStore(tmp_path / "builds.jsonl")
    ws = _ws(tmp_path)
    out = produce_build(spec_source=SPEC_SOURCE, adapter=adapter, store=store, workspace=ws,
                        budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: AS_OF)
    fact = out["fact"]
    assert fact["status"] == "failed" and fact["artefact"] is None and "manifeste invalide" in fact["error"]
    assert not (ws.path / "manifest.json").exists()                             # AUCUN artefact sur échec
    assert len(store.read_all()) == 1 and len(adapter.calls) == 1              # un fait, aucun retry


def test_produce_build_client_error_records_failed_without_artefact(tmp_path):
    adapter = _FakeAdapter(_envelope(json.dumps(_VALID_MANIFEST), ok=False))    # is_error → failed
    store = BuildStore(tmp_path / "builds.jsonl")
    ws = _ws(tmp_path)
    out = produce_build(spec_source=SPEC_SOURCE, adapter=adapter, store=store, workspace=ws,
                        budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: AS_OF)
    assert out["fact"]["status"] == "failed" and out["fact"]["artefact"] is None
    assert not (ws.path / "manifest.json").exists()


def test_produce_build_injectable_clock(tmp_path):
    adapter = _FakeAdapter(_envelope(json.dumps(_VALID_MANIFEST)))
    store = BuildStore(tmp_path / "builds.jsonl"); ws = _ws(tmp_path)
    stamp = "2031-05-04T03:02:01+00:00"
    out = produce_build(spec_source=SPEC_SOURCE, adapter=adapter, store=store, workspace=ws,
                        budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: stamp)
    assert out["fact"]["as_of"] == stamp


def test_proposed_fact_is_non_authoritative(tmp_path):
    adapter = _FakeAdapter(_envelope(json.dumps(_VALID_MANIFEST)))
    store = BuildStore(tmp_path / "builds.jsonl"); ws = _ws(tmp_path)
    fact = produce_build(spec_source=SPEC_SOURCE, adapter=adapter, store=store, workspace=ws,
                         budget_remaining_usd=5.0, cwd=tmp_path, clock=lambda: AS_OF)["fact"]
    assert fact["status"] == "proposed"
    for forbidden in ("validated", "official", "approved", "build_triggered", "executed"):
        assert forbidden not in fact


# ===================================================================== #
# T2 — BuildStore : id adressé au contenu, calculé par le store
# ===================================================================== #
def test_build_id_by_content_and_caller_id_ignored(tmp_path):
    store = BuildStore(tmp_path / "builds.jsonl")
    f1 = _bb(_envelope(json.dumps(_VALID_MANIFEST)), artefact=dict(_ART, sha256="a" * 64))
    f2 = _bb(_envelope(json.dumps(_VALID_MANIFEST)), artefact=dict(_ART, sha256="b" * 64))   # contenu ≠
    r1, r2 = store.record(f1), store.record(f2)
    assert r1["build_id"].startswith("build_") and r1["build_id"] != r2["build_id"]          # contenu ≠ → id ≠
    forged = dict(f1, build_id="build_FORGERY")
    r3 = store.record(forged)
    assert r3["build_id"] != "build_FORGERY" and r3["build_id"].startswith("build_")          # id appelant ignoré
    lines = store.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and len(store.read_all()) == 3                                     # append-only


def test_failed_and_proposed_differ_by_id(tmp_path):
    store = BuildStore(tmp_path / "builds.jsonl")
    proposed = store.record(_bb(_envelope(json.dumps(_VALID_MANIFEST)), artefact=_ART))
    failed = store.record(_bb(_envelope("pas du JSON")))
    assert proposed["build_id"] != failed["build_id"]                                        # le statut participe


def test_diagnostic_rv1_redacts_secret_and_never_persisted(tmp_path):
    secret = "sk-ant-api03-FAKEfakeVALUE1234567890ABCDEFxyz"
    fact = _bb(_envelope(f'{{"leak":"{secret}"}}', ok=False), stdout=f"log {secret}", argv=["claude", "-p", "x"])
    store = BuildStore(tmp_path / "builds.jsonl"); store.record(fact)
    assert secret not in store.path.read_text(encoding="utf-8")
    assert "[REDACTED-KEY]" in fact["diagnostic"]["stdout"]
