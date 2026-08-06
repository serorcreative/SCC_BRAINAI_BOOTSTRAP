"""BUILD-PROPOSE-001 — Tâche 1 (contrat seul) : validation, schéma, prompt, capacité, adaptateur.

Prouve à **0 €** le contrat de la capacité de build : validation stricte de la Spéc source, schéma strict
du manifeste, prompt déterministe dérivé exclusivement de la Spéc, Protocol + adaptateur Claude Code confiné
avec garde budget **avant** toute frontière externe. **Aucune** matérialisation, **aucun** store, **aucun**
``produce_build``, **aucun** appel réel dans cette tâche.
"""

from __future__ import annotations

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
    build_prompt,
    validate_spec_source,
)

# --- Spécification source complète (fait `specification` proposé, 11 champs). ---
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


# ===================================================================== #
# R8 — capacité ≠ outil
# ===================================================================== #
def test_adapter_implements_capability_protocol():
    adapter = ClaudeCodeBuildAdapter()
    assert isinstance(adapter, BuildCapability)
    assert adapter.capability == "build" and adapter.name == "claude_code"


# ===================================================================== #
# validate_spec_source — source complète + refus AVANT appel
# ===================================================================== #
def test_validate_spec_source_accepts_complete_source():
    sid, spec = validate_spec_source(SPEC_SOURCE)
    assert sid == "spec_d5c02d00891b" and spec is SPEC_SOURCE["specification"]


@pytest.mark.parametrize("bad, why", [
    ("pas un dict", "objet"),
    ({"status": "proposed", "specification": _SPEC}, "specification_id"),          # sans id
    ({"specification_id": "", "status": "proposed", "specification": _SPEC}, "specification_id"),
    ({"specification_id": "spec_x", "status": "failed", "specification": _SPEC}, "proposed"),
    ({"specification_id": "spec_x", "status": "proposed"}, "11 champs"),            # sans specification
    ({"specification_id": "spec_x", "status": "proposed", "specification": "x"}, "11 champs"),
    ({"specification_id": "spec_x", "status": "proposed",
      "specification": {k: v for k, v in _SPEC.items() if k != "out_of_scope"}}, "11 champs"),  # 10/11
])
def test_validate_spec_source_rejects_invalid(bad, why):
    with pytest.raises(SpecSourceError) as exc:
        validate_spec_source(bad)
    assert why in str(exc.value)


# ===================================================================== #
# MANIFEST_SCHEMA — exactement cinq clés
# ===================================================================== #
def test_manifest_schema_has_exactly_five_keys():
    assert set(MANIFEST_SCHEMA["properties"]) == {"name", "summary", "users", "features", "entities"}
    assert MANIFEST_SCHEMA["required"] == ["name", "summary", "users", "features", "entities"]
    assert MANIFEST_SCHEMA["additionalProperties"] is False
    assert ARTIFACT_FILENAME == "manifest.json" and NAME_MAX == 80


# ===================================================================== #
# _valid_manifest — validation locale stricte
# ===================================================================== #
def test_valid_manifest_accepts_well_formed():
    assert B._valid_manifest(_VALID_MANIFEST) is True
    assert B._valid_manifest({**_VALID_MANIFEST, "users": [], "features": [], "entities": []}) is True  # listes vides OK


def test_valid_manifest_rejects_extra_property_including_paths():
    assert B._valid_manifest({**_VALID_MANIFEST, "unexpected": "x"}) is False
    assert B._valid_manifest({**_VALID_MANIFEST, "path": "manifest.json"}) is False   # aucun chemin/fichier
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


# ===================================================================== #
# build_prompt — déterministe, dérivé exclusivement de la Spéc
# ===================================================================== #
def test_build_prompt_is_derived_only_from_spec_and_forbids_invention_and_paths():
    prompt = build_prompt(_SPEC)
    assert _SPEC["product_objective"] in prompt                       # part de la Spéc fournie
    assert "SPÉCIFICATION" in prompt
    assert "n'invente AUCUNE" in prompt                               # aucune invention
    assert "AUCUN chemin ni nom de fichier" in prompt                 # aucun chemin/fichier
    assert "AUCUNE propriété supplémentaire" in prompt
    for k in ("name", "summary", "users", "features", "entities"):    # exactement les cinq clés citées
        assert k in prompt
    assert str(NAME_MAX) in prompt                                    # borne du titre


def test_build_prompt_is_deterministic():
    assert build_prompt(_SPEC) == build_prompt(_SPEC)


# ===================================================================== #
# Adaptateur — argv confiné et structuré (le modèle n'écrit jamais de fichier)
# ===================================================================== #
def test_argv_is_confined_and_structured():
    argv = ClaudeCodeBuildAdapter(model="haiku", max_budget_usd=0.30).build_argv("prompt")
    assert argv[0] == "claude" and "-p" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--max-budget-usd") + 1] == "0.3"
    assert "--json-schema" in argv and "--disallowedTools" in argv
    for tool in ("Bash", "Edit", "Write", "Read"):                   # écriture fichier DÉSACTIVÉE
        assert tool in argv


# ===================================================================== #
# Garde budget AVANT toute frontière externe
# ===================================================================== #
def test_budget_gate_refuses_before_any_external_frontier(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "run_confined", lambda *a, **k: pytest.fail("run_confined appelé malgré budget insuffisant"))
    adapter = ClaudeCodeBuildAdapter(max_budget_usd=0.50)
    cwd = tmp_path / "neutral"; cwd.mkdir()
    out = adapter.propose(_SPEC, cwd=cwd, budget_remaining_usd=0.10)  # reste < plafond
    assert out["called"] is False and out["refused"] == "budget insuffisant"


# ===================================================================== #
# Environnement confiné — composition exacte
# ===================================================================== #
def test_env_composition_is_exactly_identity_and_no_more():
    env = ClaudeCodeBuildAdapter()._env()
    allowed = {"PATH", "LANG"}
    for k in ("HOME", "USER", "LOGNAME"):
        if os.environ.get(k):
            allowed.add(k)
    assert set(env) == allowed
    assert not any(re.search(r"(?i)token|secret|password|api[_-]?key|credential|bearer", k) for k in env)
