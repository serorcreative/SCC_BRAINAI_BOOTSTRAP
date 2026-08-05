"""Capacité de **compréhension** — produire un Brief structuré à partir d'un besoin (JALON-ZERO, B).

BrainAI dépend d'une **capacité**, jamais d'un outil (R8) : le noyau demande « comprends ce besoin,
propose un Brief » ; l'outil concret (ici **Claude Code** non-interactif) est un **adaptateur**
interchangeable (demain Codex, Gemini, Cursor…). Un modèle **propose**, il ne décide jamais (R5) :
la sortie est un **fait proposition** (``status: proposed``), soumis à validation humaine.

Confinement de l'appel : ``argv`` only (jamais shell), ``cwd`` neutre, **env minimal** (``HOME``
requis pour l'auth de session, ``PATH``/``LANG`` ; rien d'autre), **timeout**, **plafond coût**
(``--max-budget-usd``). Le coût réel est lu dans l'enveloppe (``total_cost_usd``) — sinon
``unavailable``, **jamais fabriqué** (R2). Aucun retry (R6). Stdlib pur.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.tool_runner import run_confined

# Schéma **structuré** attendu du Brief (sortie forcée par ``--json-schema``). Champs minimaux d'une
# compréhension de besoin : objectif reformulé, contexte, acteurs, périmètre, hypothèses, questions
# ouvertes, contraintes — un modèle **décrit** le besoin, il ne décide ni ne spécifie (R5).
BRIEF_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "objective": {"type": "string"},                              # objectif reformulé
        "context": {"type": "string"},                                # contexte
        "actors": {"type": "array", "items": {"type": "string"}},     # acteurs / utilisateurs pressentis
        "scope": {"type": "array", "items": {"type": "string"}},      # périmètre initial
        "assumptions": {"type": "array", "items": {"type": "string"}},  # hypothèses
        "open_questions": {"type": "array", "items": {"type": "string"}},  # questions ouvertes
        "constraints": {"type": "array", "items": {"type": "string"}},  # contraintes identifiées
    },
    "required": ["objective", "context", "actors", "scope", "assumptions",
                 "open_questions", "constraints"],
}

_BRIEF_REQUIRED = tuple(BRIEF_SCHEMA["required"])


def build_prompt(need: str) -> str:
    """Prompt déterministe : demande un Brief structuré (aucun secret, aucune donnée fabriquée)."""
    return (
        "Tu produis un BRIEF de compréhension à partir d'un besoin utilisateur en langage naturel. "
        "Réponds UNIQUEMENT via le schéma imposé : objectif reformulé, contexte, acteurs ou "
        "utilisateurs pressentis, périmètre initial, hypothèses, questions ouvertes, contraintes "
        "identifiées. Ne réalise aucune action, ne rédige aucune spécification, ne propose aucune "
        "décision : décris et cadre le besoin.\n\n"
        f"BESOIN : {need}"
    )


def parse_envelope(stdout: str) -> Optional[Dict[str, Any]]:
    """Parse l'enveloppe JSON de Claude Code (``--output-format json``), ou ``None`` si invalide."""
    try:
        obj = json.loads(stdout)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_cost(envelope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Coût **réel** si présent dans l'enveloppe, sinon ``unavailable`` — jamais inventé."""
    if envelope is not None and isinstance(envelope.get("total_cost_usd"), (int, float)):
        return {"value": float(envelope["total_cost_usd"]), "kind": "real"}
    return {"value": None, "kind": "unavailable"}


# --------------------------------------------------------------------- #
# Diagnostic brut BORNÉ + ASSAINI d'un échec (RV-1). Un fait ``failed`` doit rester gouvernable
# sans rejouer l'appel, SANS jamais fuiter de secret. L'environnement n'est JAMAIS inclus.
# --------------------------------------------------------------------- #
_DIAG_MAX = 1200          # bornage d'un flux (stdout/stderr/result)

# Redaction best-effort **documentée** — noms sensibles identifiables avec frontières de mots :
# ``monkey=value`` reste visible ; ``api_key/token/secret/password/credential`` (+ variantes) masqués.
_SK_RE = re.compile(r"sk-[A-Za-z0-9._\-]{8,}")                       # clés type sk-…
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")          # en-têtes Bearer
_SENSITIVE_NAME = re.compile(                                        # <nom sensible> = <valeur>
    r"(?i)(?<![\w-])"
    r"([\"']?[A-Za-z0-9_-]*?"
    r"(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|token|secret|password|passwd|credentials?)"
    r"[A-Za-z0-9_-]*[\"']?\s*[:=]\s*[\"']?)"
    r"([^\s\"',}]+)")
_HEX_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")                        # longues chaînes hex
_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")               # longues chaînes base64
_ABS_PATH_RE = re.compile(r"^/[^\s]*$")                              # token = chemin absolu

_PROMPT_FLAGS = {"-p", "--print"}
_SCHEMA_FLAGS = {"--json-schema"}
_AUTH_FLAG_RE = re.compile(r"(?i)(auth|token|secret|password|passwd|credential|api[_-]?key|apikey|bearer)")


def _redact(s: str) -> str:
    """Redaction best-effort : ``sk-…``, ``Bearer``, affectations à **nom sensible identifiable**
    (api_key/token/secret/password/credential + variantes, avec frontières — ``monkey`` reste
    visible), longues chaînes hex/base64 ; le chemin ``HOME`` → ``~``. Ne masque **que** ces motifs.
    L'environnement n'est jamais inclus."""
    home = os.environ.get("HOME")
    if home:
        s = s.replace(home, "~")
    s = _SK_RE.sub("[REDACTED-KEY]", s)
    s = _BEARER_RE.sub("Bearer [REDACTED]", s)
    s = _SENSITIVE_NAME.sub(lambda m: m.group(1) + "[REDACTED]", s)
    s = _HEX_RE.sub("[REDACTED-HEX]", s)
    s = _B64_RE.sub("[REDACTED-B64]", s)
    return s


def _clean(text: Any, limit: int = _DIAG_MAX) -> Optional[str]:
    """Assainit **puis** borne (redaction sur le texte COMPLET → aucune fuite au bord de troncature)."""
    if text is None:
        return None
    s = text if isinstance(text, str) else str(text)
    if not s:
        return None
    s = _redact(s)
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
        parts.append(_neutralize_path(_redact(raw)))
        if raw in _PROMPT_FLAGS and i + 1 < n:            # forme -p <valeur>
            parts.append("<REDACTED-PROMPT>"); i += 2; continue
        if raw in _SCHEMA_FLAGS and i + 1 < n:
            parts.append("<REDACTED-SCHEMA>"); i += 2; continue
        if raw.startswith("-") and _AUTH_FLAG_RE.search(raw) and i + 1 < n:
            parts.append("<REDACTED>"); i += 2; continue
        i += 1
    return _clean(" ".join(parts))


def _diagnostic(*, argv: Any, stdout: Any, stderr: Any, exit_code: Any, timed_out: bool,
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


def build_proposal(*, need: str, prompt: str, capability: str, adapter: str, model: str,
                   envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool,
                   as_of: str, argv: Any = None, stdout: Any = None,
                   stderr: Any = None) -> Dict[str, Any]:
    """Construit un **fait proposition** honnête (pur, testable).

    ``proposed`` uniquement si : pas de timeout, ``exit_code == 0`` (ou ``None``), enveloppe lisible,
    non ``is_error``, ``subtype == "success"``, ET Brief conforme. Sinon ``failed`` — sans crash, avec
    ``error`` (jamais ``"success"``) et un ``diagnostic`` brut borné assaini. Coût toujours enregistré
    (réel ou ``unavailable``). ``diagnostic = None`` sur un fait ``proposed``."""
    cost = _extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    base: Dict[str, Any] = {
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "need": need,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "BRIEF_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    diag = _diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                       timed_out=timed_out, envelope=envelope)
    nonzero_exit = exit_code is not None and exit_code != 0
    # Échec d'appel : timeout / exit non nul / enveloppe illisible / erreur cerveau / subtype ≠ success.
    if (timed_out or envelope is None or nonzero_exit
            or envelope.get("is_error") or envelope.get("subtype") != "success"):
        if timed_out:
            reason = "timeout"
        elif envelope is None:
            reason = "enveloppe illisible"
        elif nonzero_exit:
            reason = f"exit non nul ({exit_code})"
        elif envelope.get("is_error") and envelope.get("subtype") == "success":
            reason = "erreur client sans détail (voir diagnostic)"
        else:
            reason = str(envelope.get("api_error_status") or envelope.get("subtype") or "erreur d'appel")
        if reason == "success":     # garde-fou : ``error`` ne peut jamais afficher "success"
            reason = "erreur client sans détail (voir diagnostic)"
        return {**base, "status": "failed", "brief": None, "error": reason, "diagnostic": diag}
    # Réponse présente : valider le format Brief.
    result = envelope.get("result")
    brief: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                brief = parsed
        except json.JSONDecodeError:
            brief = None
    elif isinstance(result, dict):
        brief = result
    if not isinstance(brief, dict) or not all(k in brief for k in _BRIEF_REQUIRED):
        return {**base, "status": "failed", "brief": None, "error": "format Brief invalide",
                "diagnostic": diag}
    return {**base, "status": "proposed", "brief": brief, "error": None, "diagnostic": None}


@runtime_checkable
class NeedUnderstandingCapability(Protocol):
    """**Capacité** « comprendre un besoin » (R8) — BrainAI en dépend, jamais d'un outil concret.

    Contrat minimal : produire, pour un ``need`` en langage naturel, la matière brute d'un fait
    proposition (enveloppe/exit/timeout/prompt), **après** contrôle du budget. L'implémentation
    concrète (ici Claude Code) est interchangeable ; le reste du système ne connaît que ce Protocol,
    jamais la commande ``claude``."""

    capability: str
    name: str

    def propose(self, need: str, *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeUnderstandingAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`NeedUnderstandingCapability` (R8)."""

    capability = "understanding"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = 120.0, claude_bin: str = "claude"):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré, modèle explicite,
        plafond coût, outils fichier/bash **désactivés** (Brief = texte seul)."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(BRIEF_SCHEMA, ensure_ascii=False),
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        # Env minimal : HOME est requis pour l'auth de session locale ; rien d'autre de sensible.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"), "LANG": "C.UTF-8"}
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        return env

    def propose(self, need: str, *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le reste
        ne couvre pas le plafond. Renvoie ``{called, envelope, exit_code, timed_out, prompt, argv,
        stdout, stderr}`` — ne construit pas le fait (séparation : voir :func:`build_proposal`)."""
        prompt = build_prompt(need)
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


__all__ = ["BRIEF_SCHEMA", "build_prompt", "parse_envelope", "build_proposal",
           "NeedUnderstandingCapability", "ClaudeCodeUnderstandingAdapter"]
