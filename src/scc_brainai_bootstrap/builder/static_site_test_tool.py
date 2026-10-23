"""Vérificateur statique minimal exécuté par le provider local ``test.run``.

Ce programme est volontairement minuscule et stdlib-only. Il reçoit uniquement une référence
d'artefact relative et son empreinte attendue, travaille dans le ``cwd`` confiné fourni par
BrainAI, ne modifie rien et n'émet jamais le contenu de l'artefact.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path, PurePosixPath
from typing import List, Optional

MAX_ARTIFACT_BYTES = 2_000_000


def _fail(code: int, detail: str) -> int:
    print(f"FAIL static-site-check: {detail}", file=sys.stderr)
    return code


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        return _fail(2, "arguments invalides")
    relative_path, expected_sha256 = args
    posix_path = PurePosixPath(relative_path)
    if (not relative_path or len(relative_path) > 256 or "\x00" in relative_path
            or "\\" in relative_path or posix_path.is_absolute()
            or any(part in ("", ".", "..") for part in posix_path.parts)):
        return _fail(3, "référence d'artefact non confinée")
    if (len(expected_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in expected_sha256.lower())):
        return _fail(4, "empreinte attendue invalide")

    root = Path.cwd().resolve()
    target = (root / Path(*posix_path.parts)).resolve()
    if target == root or root not in target.parents:
        return _fail(5, "artefact hors workspace")
    if not target.is_file():
        return _fail(6, "artefact absent ou non régulier")

    try:
        size = target.stat().st_size
        if size <= 0 or size > MAX_ARTIFACT_BYTES:
            return _fail(7, "taille d'artefact invalide")
        with target.open("rb") as handle:
            data = handle.read(MAX_ARTIFACT_BYTES + 1)
        if len(data) > MAX_ARTIFACT_BYTES:
            return _fail(7, "taille d'artefact invalide")
    except OSError:
        return _fail(8, "artefact illisible")
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected_sha256.lower():
        return _fail(9, "empreinte divergente")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(10, "artefact non UTF-8")

    lowered = text.lower()
    required = ("<html", "<head", "</head>", "<body", "</body>", "</html>")
    if not all(marker in lowered for marker in required):
        return _fail(11, "structure HTML minimale invalide")
    print(f"PASS static-site-check: {relative_path} sha256={observed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
