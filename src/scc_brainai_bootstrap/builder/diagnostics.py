"""Primitives de diagnostic **NEUTRES** (sans fournisseur) — bornage + redaction des secrets (RV-1).

Foyer unique de ``DIAG_MAX`` et :func:`redact` (déplacés depuis ``claude_code_runtime`` pour préserver la
**neutralité de fournisseur du moteur** — I9 : ``builder/brainai`` et ``brainai_app/composition`` ne doivent
nommer aucun module de fournisseur concret). ``claude_code_runtime`` les **réexporte** pour compatibilité des
adaptateurs existants ; **source unique** de la redaction (dupliquer ferait courir un risque de divergence →
fuite). Dépend **uniquement de la bibliothèque standard**.
"""

from __future__ import annotations

import os
import re

# --------------------------------------------------------------------- #
# Diagnostic brut BORNÉ + ASSAINI d'un échec (RV-1). Un fait ``failed`` doit rester gouvernable sans
# rejouer l'appel, SANS jamais fuiter de secret. L'environnement n'est JAMAIS inclus.
# --------------------------------------------------------------------- #
DIAG_MAX = 1200          # bornage d'un flux (stdout/stderr/result)

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


def redact(s: str) -> str:
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


__all__ = ["DIAG_MAX", "redact"]
