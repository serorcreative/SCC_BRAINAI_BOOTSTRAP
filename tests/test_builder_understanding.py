"""Preuve B (BRAINAI-JALON-ZERO-001) — compréhension réelle par une intelligence louée.

Prouve que BrainAI peut faire **produire** un Brief structuré par un LLM (Claude Code via
:class:`ClaudeCodeUnderstandingAdapter`, implémentant la capacité :class:`NeedUnderstandingCapability`),
et le **refléter comme fait proposition** (``status: proposed``) append-only — **sans** modifier aucun
état officiel (R5), avec **coût honnête** (réel ou ``unavailable``, jamais fabriqué — R2) et **aucun
retry**.

Les tests unitaires (enveloppe **factice**) valident toute la logique de fait à **0 €**. Un unique
test **facturable** (``test_real_claude_brief``) est **désactivé** sauf ``BRAINAI_JALON_LLM=1`` — il
n'est jamais joué par un run de tests normal, et effectue **au plus deux** appels réels.

Critères : B1 fait complet (identifiant, modèle, empreinte, params, réponse structurée, usage, coût,
horodatage, statut) · B2 deux appels → deux faits append-only distincts · B3 aucun état officiel
modifié · B4 budget contrôlé AVANT l'appel · B5 réponse invalide = fait ``failed`` sans crash.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scc_brainai_bootstrap.builder import understanding as U
from scc_brainai_bootstrap.builder.proposals import ProposalStore
from scc_brainai_bootstrap.builder.understanding import (
    BRIEF_SCHEMA,
    ClaudeCodeUnderstandingAdapter,
    NeedUnderstandingCapability,
    build_prompt,
    build_proposal,
    parse_envelope,
)

AS_OF = "2026-08-04T00:00:00+00:00"
# Besoin réel exact du jalon (Tâche 4).
NEED = "Je voudrais une application de gestion pour un refuge animalier : animaux, adoptants, rendez-vous."

# Champs minimaux d'un Brief de compréhension (objectif, contexte, acteurs, périmètre, hypothèses,
# questions ouvertes, contraintes).
_BRIEF_KEYS = ("objective", "context", "actors", "scope", "assumptions", "open_questions", "constraints")

_VALID_BRIEF = (
    '{"objective":"Gérer un refuge animalier",'
    '"context":"Petite structure associative",'
    '"actors":["Bénévole","Adoptant","Vétérinaire"],'
    '"scope":["Animaux","Adoptants","Rendez-vous"],'
    '"assumptions":["Usage web interne"],'
    '"open_questions":["Multi-refuge ?"],'
    '"constraints":["Budget limité"]}'
)


# Enveloppe Claude Code réaliste (structure vérifiée par la sonde) — AUCUN appel réel.
def _envelope(result: str, *, ok: bool = True, cost=0.0150691, usage=None):
    return {
        "type": "result", "subtype": "success" if ok else "error_max_turns",
        "is_error": not ok, "api_error_status": None, "num_turns": 1,
        "result": result, "total_cost_usd": cost,
        "usage": usage if usage is not None else {"input_tokens": 10, "output_tokens": 78},
        "modelUsage": {"claude-haiku-4-5": {"costUSD": cost}},
    }


def _proposal(envelope, *, timed_out=False, exit_code=0, as_of=AS_OF):
    return build_proposal(need=NEED, prompt=build_prompt(NEED), capability="understanding",
                          adapter="claude_code", model="haiku", envelope=envelope,
                          exit_code=exit_code, timed_out=timed_out, as_of=as_of)


# --------------------------------------------------------------------- #
# Séparation interface de capacité / outil concret (R8)
# --------------------------------------------------------------------- #
def test_adapter_implements_capability_protocol():
    adapter = ClaudeCodeUnderstandingAdapter()
    assert isinstance(adapter, NeedUnderstandingCapability)   # Protocol runtime_checkable
    assert adapter.capability == "understanding" and adapter.name == "claude_code"


# --------------------------------------------------------------------- #
# B1 — fait COMPLET (identifiant, modèle, empreinte, params, réponse, usage, coût, horodatage, statut)
# --------------------------------------------------------------------- #
def test_proposal_fact_is_complete_on_success(tmp_path):
    store = ProposalStore(tmp_path / "proposals.jsonl")
    fact = store.record(_proposal(_envelope(_VALID_BRIEF)))
    assert fact["proposal_id"].startswith("prop_")                       # identifiant
    assert fact["status"] == "proposed"                                  # statut
    assert fact["model"] == "haiku"                                      # modèle
    assert fact["capability"] == "understanding" and fact["adapter"] == "claude_code"
    assert fact["prompt_sha256"] and NEED in fact["prompt"]              # empreinte du prompt
    assert fact["params"]["output_format"] == "json"                     # paramètres
    assert fact["params"]["json_schema"] == "BRIEF_SCHEMA"
    assert all(k in fact["brief"] for k in _BRIEF_KEYS)                  # réponse structurée
    assert fact["brief"]["actors"] == ["Bénévole", "Adoptant", "Vétérinaire"]
    assert fact["usage"]["output_tokens"] == 78                          # usage réel
    assert fact["cost"] == {"value": 0.0150691, "kind": "real"}          # coût + kind (jamais fabriqué)
    assert fact["as_of"] == AS_OF and fact["error"] is None              # horodatage


def test_cost_unavailable_when_absent_never_fabricated():
    env = _envelope(_VALID_BRIEF)
    del env["total_cost_usd"]                                     # enveloppe sans coût
    fact = _proposal(env)
    assert fact["cost"] == {"value": None, "kind": "unavailable"}  # jamais inventé


# --------------------------------------------------------------------- #
# B5 — format invalide / erreur = échec enregistré, sans crash, sans mutation
# --------------------------------------------------------------------- #
def test_invalid_json_result_is_recorded_as_failure():
    fact = _proposal(_envelope("ceci n'est pas du JSON"))
    assert fact["status"] == "failed" and fact["brief"] is None
    assert "format Brief invalide" in fact["error"]


def test_missing_required_key_is_failure():
    # « constraints » manquant → schéma non respecté.
    partial = '{"objective":"x","context":"y","actors":[],"scope":[],"assumptions":[],"open_questions":[]}'
    fact = _proposal(_envelope(partial))
    assert fact["status"] == "failed" and "format Brief invalide" in fact["error"]


def test_brain_error_envelope_is_failure():
    fact = _proposal(_envelope(_VALID_BRIEF, ok=False))
    assert fact["status"] == "failed" and fact["brief"] is None


def test_timeout_is_failure_without_crash():
    fact = _proposal(None, timed_out=True)
    assert fact["status"] == "failed" and fact["error"] == "timeout" and fact["cost"]["kind"] == "unavailable"


def test_unreadable_envelope_is_failure():
    assert parse_envelope("garbage {") is None
    fact = _proposal(None)
    assert fact["status"] == "failed" and "illisible" in fact["error"]


# --------------------------------------------------------------------- #
# B2 — deux appels → deux faits distincts, append-only, sans mutation
# --------------------------------------------------------------------- #
def test_two_proposals_two_facts_append_only(tmp_path):
    store = ProposalStore(tmp_path / "proposals.jsonl")
    f1 = store.record(_proposal(_envelope(_VALID_BRIEF)))
    f2 = store.record(_proposal(_envelope(_VALID_BRIEF, cost=0.02), as_of="2026-08-04T09:05:00+00:00"))
    lines = store.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and len(store.read_all()) == 2         # append-only, aucun écrasement
    assert f1["proposal_id"] != f2["proposal_id"]                 # deux faits DISTINCTS
    assert f1["cost"]["value"] == 0.0150691 and f2["cost"]["value"] == 0.02


# --------------------------------------------------------------------- #
# B4 — budget contrôlé AVANT l'appel (refus sans appel si insuffisant)
# --------------------------------------------------------------------- #
def test_budget_gate_refuses_before_calling(tmp_path):
    adapter = ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50)
    cwd = tmp_path / "neutral"; cwd.mkdir()
    out = adapter.propose(NEED, cwd=cwd, budget_remaining_usd=0.10)   # reste < plafond
    assert out["called"] is False and out["refused"] == "budget insuffisant"


def test_argv_is_confined_and_structured():
    argv = ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.30).build_argv("prompt")
    assert argv[0] == "claude" and "-p" in argv                   # jamais de shell (argv only)
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--max-budget-usd") + 1] == "0.3"
    assert "--json-schema" in argv and "--disallowedTools" in argv
    assert BRIEF_SCHEMA["required"][0] == "objective" and "constraints" in BRIEF_SCHEMA["required"]


# --------------------------------------------------------------------- #
# RV-1 — diagnostic brut BORNÉ + ASSAINI dans tout fait failed (secret jamais persisté)
# --------------------------------------------------------------------- #
_SECRET_KEY = "sk-ant-api03-FAKEfakeVALUE1234567890ABCDEFxyz"
_SECRET_BEARER = "FAKEBEARERtoken1234567890abcXYZ"
_SECRET_PWD = "SuperSecretHunter2000Value"
_SECRET_HEX = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
_SECRET_VALUES = [_SECRET_KEY, _SECRET_BEARER, _SECRET_PWD, _SECRET_HEX]


def _failed_fact(*, stdout="", stderr="", envelope=None, exit_code=0, timed_out=False, argv=None):
    return build_proposal(need=NEED, prompt=build_prompt(NEED), capability="understanding",
                          adapter="claude_code", model="haiku", envelope=envelope,
                          exit_code=exit_code, timed_out=timed_out, as_of=AS_OF,
                          argv=argv, stdout=stdout, stderr=stderr)


def test_proposed_fact_has_no_diagnostic():
    fact = _proposal(_envelope(_VALID_BRIEF))
    assert fact["status"] == "proposed" and fact["diagnostic"] is None


def test_redaction_keeps_monkey_but_masks_sensitive_names():
    assert U._redact("monkey=value") == "monkey=value"          # nom non sensible → visible
    for good in ("api_key=value", "token=value", "secret=value",
                 "password=value", "credential=value"):
        r = U._redact(good)
        assert "value" not in r and "[REDACTED]" in r, good     # nom sensible → valeur masquée
        assert good.split("=")[0] in r                          # le nom reste visible


def test_diagnostic_stdout_is_bounded_and_marked():
    # Remplissage non-hex/non-base64 (espaces) : on teste le BORNAGE, pas la redaction.
    long = "diagnostic-line " * 100          # ~1600 chars, aucun motif sensible
    assert len(long) > U._DIAG_MAX
    d = _failed_fact(stdout=long, timed_out=True)["diagnostic"]["stdout"]
    assert d is not None and len(d) <= U._DIAG_MAX + 40 and "tronqués" in d


def test_home_path_replaced_by_tilde():
    home = os.environ.get("HOME")
    assert home, "HOME requis pour ce test"
    d = _failed_fact(stderr=f"cannot open {home}/x/config.json", timed_out=True)["diagnostic"]
    assert "~/x/config.json" in d["stderr"] and home not in d["stderr"]


def test_fake_secrets_redacted_in_every_stream_and_never_persisted(tmp_path):
    stdout = f"log line key : {_SECRET_KEY} suite"
    stderr = f"Authorization: Bearer {_SECRET_BEARER}"
    env = _envelope(f'{{"password":"{_SECRET_PWD}","hash":"{_SECRET_HEX}"}}', ok=False)  # is_error → failed
    argv = ["claude", "-p", "brief", "--token", _SECRET_KEY]
    fact = _failed_fact(stdout=stdout, stderr=stderr, envelope=env, argv=argv)
    store = ProposalStore(tmp_path / "p.jsonl")
    store.record(fact)
    blob = store.path.read_text(encoding="utf-8")               # fait PERSISTÉ (sérialisé)
    for secret in _SECRET_VALUES:                               # AUCUN champ ne contient le secret
        assert secret not in blob, f"secret fuité : {secret!r}"
    d = fact["diagnostic"]
    assert "[REDACTED-KEY]" in d["stdout"] and "[REDACTED]" in d["stderr"]
    assert "[REDACTED]" in d["result"] and "[REDACTED-HEX]" in d["result"]


def test_nonzero_exit_is_failure_even_with_valid_envelope():
    fact = _failed_fact(envelope=_envelope(_VALID_BRIEF), exit_code=1, stderr="boom")
    assert fact["status"] == "failed" and fact["brief"] is None
    assert "exit non nul (1)" in fact["error"] and fact["diagnostic"]["exit_code"] == 1


def test_client_error_without_detail_never_says_success():
    env = _envelope("peu importe")           # subtype "success" par défaut
    env["is_error"] = True                   # is_error=true AVEC subtype="success"
    fact = _failed_fact(envelope=env, exit_code=0)
    assert fact["status"] == "failed"
    assert fact["error"] == "erreur client sans détail (voir diagnostic)"
    assert fact["error"] != "success"
    assert fact["diagnostic"]["is_error"] is True and fact["diagnostic"]["subtype"] == "success"


def test_argv_summary_is_structural_prompt_schema_and_paths():
    argv = ["/usr/local/bin/claude", "-p", _SECRET_PWD,
            "--json-schema", '{"x":"' + _SECRET_HEX + '"}',
            "--auth-token", _SECRET_KEY, "--model", "haiku",
            "/Users/secretuser/private/key.pem"]
    summ = _failed_fact(timed_out=True, argv=argv)["diagnostic"]["argv_summary"]
    assert summ is not None
    # Valeurs structurellement remplacées :
    assert "<REDACTED-PROMPT>" in summ and _SECRET_PWD not in summ
    assert "<REDACTED-SCHEMA>" in summ and _SECRET_HEX not in summ
    assert "<REDACTED>" in summ and _SECRET_KEY not in summ
    # Aucun chemin absolu sensible ; forme utile préservée (flags + modèle) :
    assert "/Users/secretuser" not in summ and "/usr/local/bin/claude" not in summ
    assert "--model" in summ and "haiku" in summ and "-p" in summ


# --------------------------------------------------------------------- #
# APPEL RÉEL (facturable) — désactivé sauf BRAINAI_JALON_LLM=1 ; AU PLUS 2 appels.
# Scénario Tâche 4 : appel #1 démontre B1/B3/B4 ; appel #2 (si #1 vert) démontre B2.
# --------------------------------------------------------------------- #
@pytest.mark.skipif(not os.environ.get("BRAINAI_JALON_LLM"),
                    reason="appel LLM facturable — activer explicitement via BRAINAI_JALON_LLM=1")
def test_real_claude_brief(tmp_path):
    adapter = ClaudeCodeUnderstandingAdapter(model="haiku", max_budget_usd=0.50, timeout=180)
    cwd = tmp_path / "neutral"; cwd.mkdir()
    # Sortie persistable pour la preuve (BRAINAI_JALON_OUT), sinon éphémère (tmp).
    out_path = os.environ.get("BRAINAI_JALON_OUT")
    store = ProposalStore(Path(out_path) if out_path else tmp_path / "proposals.jsonl")
    remaining = 5.0

    def _record(out, as_of):
        return store.record(build_proposal(
            need=NEED, prompt=out["prompt"], capability="understanding", adapter="claude_code",
            model="haiku", envelope=out["envelope"], exit_code=out["exit_code"],
            timed_out=out["timed_out"], as_of=as_of,
            argv=out.get("argv"), stdout=out.get("stdout"), stderr=out.get("stderr")))

    # --- Appel réel #1 : B4 (budget avant) + B1 (fait complet) + B3 (un seul fait) ---
    out1 = adapter.propose(NEED, cwd=cwd, budget_remaining_usd=remaining)   # B4 : contrôle avant appel
    assert out1["called"] is True
    fact1 = _record(out1, "2026-08-04T10:00:00+00:00")
    assert fact1["status"] == "proposed", f"échec réel #1 : {fact1.get('error')}"   # STOP si non vert
    assert fact1["proposal_id"].startswith("prop_")
    assert fact1["cost"]["kind"] == "real" and fact1["cost"]["value"] is not None   # coût réel
    assert all(k in fact1["brief"] for k in _BRIEF_KEYS)                            # B1 réponse structurée
    assert len(store.read_all()) == 1                                              # B3 : un seul fait
    remaining -= fact1["cost"]["value"]

    # --- Appel réel #2 (SEULEMENT si #1 vert) : B2 (deux faits distincts append-only) ---
    out2 = adapter.propose(NEED, cwd=cwd, budget_remaining_usd=remaining)
    assert out2["called"] is True
    fact2 = _record(out2, "2026-08-04T10:05:00+00:00")
    assert fact2["status"] == "proposed", f"échec réel #2 : {fact2.get('error')}"
    facts = store.read_all()
    assert len(facts) == 2 and fact1["proposal_id"] != fact2["proposal_id"]        # B2
