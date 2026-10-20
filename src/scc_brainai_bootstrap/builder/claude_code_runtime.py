"""Primitives **runtime Claude Code** — infrastructure commune des adaptateurs Claude Code (JALON-ZERO).

Ce module **n'est pas** un contrat générique de « toute intelligence louée » : il **connaît explicitement**
le protocole et le CLI **Claude Code non-interactif** — la forme de l'enveloppe ``--output-format json``
(``total_cost_usd``, ``is_error``, ``subtype``, ``api_error_status``, ``result``) et les drapeaux d'``argv``
(``-p``/``--print``, ``--json-schema``, drapeaux d'auth). Il **stabilise** ce que les adaptateurs Claude Code
(compréhension, spécification, build) partagent réellement, **sans** prétendre définir l'API de tous les
fournisseurs.

API publique **stable** : :func:`parse_envelope`, :func:`extract_cost`, :func:`diagnostic`, :func:`redact`,
:data:`DIAG_MAX`. Les expressions régulières et les helpers de nettoyage/résumé restent **privés** (surface
publique minimale). **Source unique** de la redaction des secrets (RV-1) : dupliquer cette logique
ferait courir un risque de divergence → fuite. Dépend **uniquement de la bibliothèque standard**.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.diagnostics import DIAG_MAX, redact  # réexport (RV-1) ; foyer neutre : builder/diagnostics


def parse_envelope(stdout: str) -> Optional[Dict[str, Any]]:
    """Parse l'enveloppe JSON de Claude Code (``--output-format json``), ou ``None`` si invalide."""
    try:
        obj = json.loads(stdout)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def extract_cost(envelope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Coût **réel** si présent dans l'enveloppe (``total_cost_usd``), sinon ``unavailable`` — jamais inventé."""
    if envelope is not None and isinstance(envelope.get("total_cost_usd"), (int, float)):
        return {"value": float(envelope["total_cost_usd"]), "kind": "real"}
    return {"value": None, "kind": "unavailable"}


# --------------------------------------------------------------------- #
# Diagnostic brut BORNÉ + ASSAINI d'un échec (RV-1). Un fait ``failed`` doit rester gouvernable sans
# rejouer l'appel, SANS jamais fuiter de secret. L'environnement n'est JAMAIS inclus.
# ``DIAG_MAX`` et ``redact`` vivent désormais dans ``builder/diagnostics`` (module NEUTRE, I9) et sont
# réexportés ci-dessus (import en tête) pour les adaptateurs ; **source unique** de la redaction conservée.
# --------------------------------------------------------------------- #
_ABS_PATH_RE = re.compile(r"^/[^\s]*$")                              # token = chemin absolu

_PROMPT_FLAGS = {"-p", "--print"}
_SCHEMA_FLAGS = {"--json-schema"}
_AUTH_FLAG_RE = re.compile(r"(?i)(auth|token|secret|password|passwd|credential|api[_-]?key|apikey|bearer)")


def _clean(text: Any, limit: int = DIAG_MAX) -> Optional[str]:
    """Assainit **puis** borne (redaction sur le texte COMPLET → aucune fuite au bord de troncature)."""
    if text is None:
        return None
    s = text if isinstance(text, str) else str(text)
    if not s:
        return None
    s = redact(s)
    return s if len(s) <= limit else s[:limit] + f"…[+{len(s) - limit} chars tronqués]"


def _neutralize_path(tok: str) -> str:
    """Un token qui est un **chemin absolu** est neutralisé en ``<abs-path:basename>``."""
    if _ABS_PATH_RE.match(tok):
        base = tok.rstrip("/").rsplit("/", 1)[-1] or "root"
        return f"<abs-path:{base}>"
    return tok


def _summarize_argv(argv: Any) -> Optional[str]:
    """Résumé **structurel** d'``argv`` : valeur de ``-p/--print`` → ``<REDACTED-PROMPT>``, de
    ``--json-schema`` → ``<REDACTED-SCHEMA>``, des flags auth/token/secret/password/credential →
    ``<REDACTED>``, chemins absolus neutralisés. Seuls les flags et la forme utile restent visibles."""
    if not argv:
        return None
    parts: List[str] = []
    i, n = 0, len(argv)
    while i < n:
        raw = str(argv[i])
        if raw.startswith("-") and "=" in raw:            # forme --flag=value
            flag = raw.split("=", 1)[0]
            if flag in _PROMPT_FLAGS:
                parts.append(f"{flag}=<REDACTED-PROMPT>"); i += 1; continue
            if flag in _SCHEMA_FLAGS:
                parts.append(f"{flag}=<REDACTED-SCHEMA>"); i += 1; continue
            if _AUTH_FLAG_RE.search(flag):
                parts.append(f"{flag}=<REDACTED>"); i += 1; continue
        parts.append(_neutralize_path(redact(raw)))
        if raw in _PROMPT_FLAGS and i + 1 < n:            # forme -p <valeur>
            parts.append("<REDACTED-PROMPT>"); i += 2; continue
        if raw in _SCHEMA_FLAGS and i + 1 < n:
            parts.append("<REDACTED-SCHEMA>"); i += 2; continue
        if raw.startswith("-") and _AUTH_FLAG_RE.search(raw) and i + 1 < n:
            parts.append("<REDACTED>"); i += 2; continue
        i += 1
    return _clean(" ".join(parts))


def diagnostic(*, argv: Any, stdout: Any, stderr: Any, exit_code: Any, timed_out: bool,
               envelope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Diagnostic **brut, borné, assaini** d'un échec (9 champs). Aucun secret, aucun environnement."""
    return {
        "argv_summary": _summarize_argv(argv),
        "stdout": _clean(stdout),
        "stderr": _clean(stderr),
        "result": _clean(envelope.get("result")) if envelope is not None else None,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "is_error": envelope.get("is_error") if envelope is not None else None,
        "subtype": envelope.get("subtype") if envelope is not None else None,
        "api_error_status": envelope.get("api_error_status") if envelope is not None else None,
    }


__all__ = ["parse_envelope", "extract_cost", "diagnostic", "redact", "DIAG_MAX"]
