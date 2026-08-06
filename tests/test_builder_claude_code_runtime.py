"""CLAUDE-CODE-RUNTIME-001 — primitives runtime Claude Code (API publique stable).

Prouve directement, à **0 €**, l'API publique de :mod:`claude_code_runtime` : `parse_envelope`,
`extract_cost`, `diagnostic`, `redact`, `DIAG_MAX`. Mêmes cas que ceux aujourd'hui prouvés via
`understanding` (redaction RV-1, coût honnête, diagnostic borné/assaini), exercés ici sur l'API publique.
"""

from __future__ import annotations

import os

from scc_brainai_bootstrap.builder import claude_code_runtime as R


# --------------------------------------------------------------------- #
# API publique — surface exacte
# --------------------------------------------------------------------- #
def test_public_api_surface_is_exact():
    assert set(R.__all__) == {"parse_envelope", "extract_cost", "diagnostic", "redact", "DIAG_MAX"}
    for name in R.__all__:
        assert hasattr(R, name)
    assert isinstance(R.DIAG_MAX, int) and R.DIAG_MAX == 1200
    # Les helpers/regex restent privés (hors __all__).
    for priv in ("_summarize_argv", "_clean", "_neutralize_path", "_SK_RE", "_SENSITIVE_NAME"):
        assert priv not in R.__all__


# --------------------------------------------------------------------- #
# parse_envelope
# --------------------------------------------------------------------- #
def test_parse_envelope_valid_and_invalid():
    assert R.parse_envelope('{"a": 1}') == {"a": 1}
    assert R.parse_envelope("garbage {") is None
    assert R.parse_envelope('["not", "a", "dict"]') is None
    assert R.parse_envelope(None) is None


# --------------------------------------------------------------------- #
# extract_cost — réel / unavailable, jamais fabriqué
# --------------------------------------------------------------------- #
def test_extract_cost_real_and_unavailable():
    assert R.extract_cost({"total_cost_usd": 0.0217846}) == {"value": 0.0217846, "kind": "real"}
    assert R.extract_cost({"total_cost_usd": 0}) == {"value": 0.0, "kind": "real"}
    assert R.extract_cost({}) == {"value": None, "kind": "unavailable"}
    assert R.extract_cost(None) == {"value": None, "kind": "unavailable"}
    assert R.extract_cost({"total_cost_usd": "0.02"}) == {"value": None, "kind": "unavailable"}  # str → refusé


# --------------------------------------------------------------------- #
# redact — masque les secrets, garde le reste
# --------------------------------------------------------------------- #
def test_redact_keeps_monkey_but_masks_sensitive_names():
    assert R.redact("monkey=value") == "monkey=value"            # nom non sensible → visible
    for good in ("api_key=value", "token=value", "secret=value", "password=value", "credential=value"):
        r = R.redact(good)
        assert "value" not in r and "[REDACTED]" in r, good       # valeur masquée
        assert good.split("=")[0] in r                            # nom visible


def test_redact_masks_key_bearer_hex_b64_and_home():
    assert "[REDACTED-KEY]" in R.redact("x sk-ant-api03-FAKEfakeVALUE1234567890ABCDEFxyz y")
    assert "Bearer [REDACTED]" in R.redact("Authorization: Bearer FAKEBEARERtoken1234567890abcXYZ")
    assert "[REDACTED-HEX]" in R.redact("h " + "deadbeef" * 8 + " z")
    # base64 avec caractères NON hexadécimaux (sinon capté par _HEX_RE, appliqué avant _B64_RE).
    assert "[REDACTED-B64]" in R.redact("b " + "Zm9vYmFy" * 6 + " z")
    home = os.environ.get("HOME")
    if home:
        assert "~/x/config.json" in R.redact(f"{home}/x/config.json") and home not in R.redact(f"{home}/x")


# --------------------------------------------------------------------- #
# diagnostic — 9 champs, borné, assaini, structurel
# --------------------------------------------------------------------- #
def _diag(**kw):
    base = dict(argv=None, stdout=None, stderr=None, exit_code=0, timed_out=False, envelope=None)
    base.update(kw)
    return R.diagnostic(**base)


def test_diagnostic_has_exactly_nine_fields():
    d = _diag()
    assert set(d) == {"argv_summary", "stdout", "stderr", "result", "exit_code",
                      "timed_out", "is_error", "subtype", "api_error_status"}


def test_diagnostic_stdout_is_bounded_and_marked():
    long = "diagnostic-line " * 100          # ~1600 chars, aucun motif sensible
    assert len(long) > R.DIAG_MAX
    d = _diag(stdout=long)["stdout"]
    assert d is not None and len(d) <= R.DIAG_MAX + 40 and "tronqués" in d


def test_diagnostic_reads_envelope_fields():
    env = {"result": "peu importe", "is_error": True, "subtype": "success", "api_error_status": 529}
    d = _diag(envelope=env, exit_code=1, timed_out=True)
    assert d["is_error"] is True and d["subtype"] == "success" and d["api_error_status"] == 529
    assert d["exit_code"] == 1 and d["timed_out"] is True
    assert d["result"] == "peu importe"


def test_diagnostic_argv_summary_is_structural_and_redacts():
    secret_pwd = "SuperSecretHunter2000Value"
    secret_hex = "deadbeef" * 8
    secret_key = "sk-ant-api03-FAKEfakeVALUE1234567890ABCDEFxyz"
    argv = ["/usr/local/bin/claude", "-p", secret_pwd,
            "--json-schema", '{"x":"' + secret_hex + '"}',
            "--auth-token", secret_key, "--model", "haiku",
            "/Users/secretuser/private/key.pem"]
    summ = _diag(argv=argv, timed_out=True)["argv_summary"]
    assert summ is not None
    assert "<REDACTED-PROMPT>" in summ and secret_pwd not in summ
    assert "<REDACTED-SCHEMA>" in summ and secret_hex not in summ
    assert "<REDACTED>" in summ and secret_key not in summ
    assert "/Users/secretuser" not in summ and "/usr/local/bin/claude" not in summ
    assert "--model" in summ and "haiku" in summ and "-p" in summ


def test_diagnostic_secret_in_streams_is_redacted():
    secret = "sk-ant-api03-FAKEfakeVALUE1234567890ABCDEFxyz"
    d = _diag(stdout=f"log {secret}", stderr=f"err {secret}",
              envelope={"result": f'{{"leak":"{secret}"}}'})
    assert secret not in (d["stdout"] or "") and "[REDACTED-KEY]" in d["stdout"]
    assert secret not in (d["stderr"] or "") and secret not in (d["result"] or "")


# --------------------------------------------------------------------- #
# Équivalence — les alias de compatibilité de understanding pointent vers l'API publique runtime
# --------------------------------------------------------------------- #
def test_understanding_aliases_are_the_runtime_public_api():
    from scc_brainai_bootstrap.builder import understanding as U
    assert U.parse_envelope is R.parse_envelope
    assert U._extract_cost is R.extract_cost
    assert U._diagnostic is R.diagnostic
    assert U._redact is R.redact
    assert U._DIAG_MAX == R.DIAG_MAX


# --------------------------------------------------------------------- #
# Contrôle statique — specification.py utilise l'API publique et ne référence plus understanding/_diagnostic/_cost
# --------------------------------------------------------------------- #
def test_specification_uses_runtime_public_api_only():
    import re as _re
    from pathlib import Path
    from scc_brainai_bootstrap.builder import specification
    src = Path(specification.__file__).read_text(encoding="utf-8")
    assert "from scc_brainai_bootstrap.builder.claude_code_runtime import" in src   # importe l'API publique
    assert "import understanding" not in src                                        # n'importe plus understanding
    assert _re.search(r"\bunderstanding\s+import\b", src) is None
    assert "U._diagnostic" not in src and "_diagnostic" not in src                  # aucune réf. au diagnostic privé
    assert _re.search(r"\bdef _cost\b", src) is None                                # aucun _cost local défini
    assert _re.search(r"(?<![A-Za-z_])_cost\s*\(", src) is None                     # aucun appel à un _cost local
