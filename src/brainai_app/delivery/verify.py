"""Vérifications réelles — le statut « vérifié » n'existe que par un fait ``Verification`` (JALON 2, A3).

Portée **exacte** de « vérifié » (condition Rose) : jamais implicitement tout le projet. Chaque
``Verification`` identifie **ce qui** a été vérifié et **comment** :

* ``verification_id`` ; ``subject`` (objet réellement vérifié) ; ``kind`` (``http``/``build``/``test``…) ;
* ``proof`` (sortie brute conservée : statut HTTP, en-têtes clefs) + ``tool_ref`` (ToolInvocation le cas échéant) ;
* ``verdict`` (``passed``/``failed``) ; **``sha256`` DU CONTENU vérifié** ; ``as_of``.

« vérifié » est lié au **hash**, pas au chemin : si un seul octet de l'artefact change après coup, le nouveau
contenu **n'est pas** couvert par une ``Verification`` antérieure (son ``sha256`` diffère). Le statut « vérifié »
est une **attribution SYSTÈME** sur ``verdict=passed`` — jamais émis par un modèle (RS-037). Aucune propagation :
un build vérifié ≠ un endpoint vérifié ≠ des tests vérifiés. Store append-only, coûts jamais fabriqués. Stdlib pur.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scc_brainai_bootstrap.builder.workspace import Workspace
from scc_brainai_bootstrap.core.clock import short_id
from brainai_app.delivery.serving import WorkspacePreview

VERIFICATION_KINDS = ("http", "build", "test")


def build_verification(*, subject: str, kind: str, verdict: str, sha256: Optional[str],
                       as_of: str, proof: Optional[Dict[str, Any]] = None,
                       tool_ref: Optional[str] = None, detail: str = "") -> Dict[str, Any]:
    """Construit un fait ``Verification`` immuable (pur). ``verdict`` ∈ {passed, failed}. ``sha256`` = empreinte
    **du contenu réellement vérifié** (``None`` si l'objet n'a pas de contenu adressable). Le :class:`VerificationStore`
    adresse l'``id``. Le statut système « vérifié » ne se déduit **que** d'un ``verdict == "passed"``."""
    if verdict not in ("passed", "failed"):
        raise ValueError(f"verdict invalide : {verdict!r}")
    return {
        "fact_type": "verification",
        "subject": subject,
        "kind": kind,
        "verdict": verdict,
        "sha256": sha256,
        "proof": proof if proof is not None else {},
        "tool_ref": tool_ref,
        "detail": detail,
        "as_of": as_of,
    }


class VerificationStore:
    """Journal **append-only** des vérifications (fichier injecté, hors ``data/``)."""

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _load_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def read_all(self) -> List[Dict[str, Any]]:
        return self._load_all()

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute un fait ``Verification`` immuable ; **le store adresse l'``id``** (id appelant ignoré) depuis
        le contenu vérifiant (``subject``/``kind``/``verdict``/``sha256``/``as_of``)."""
        stored = {k: v for k, v in fact.items() if k != "verification_id"}
        vid = short_id("verif", {"subject": stored.get("subject"), "kind": stored.get("kind"),
                                 "verdict": stored.get("verdict"), "sha256": stored.get("sha256"),
                                 "as_of": stored.get("as_of")})
        stored = {"verification_id": vid, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


def is_verified(content_sha256: str, verifications: List[Dict[str, Any]], *,
                subject: Optional[str] = None, kind: str = "http") -> bool:
    """Vrai **seulement si** un fait ``Verification`` ``passed`` couvre **exactement** ce ``sha256`` (et, si
    fourni, ce ``subject`` et ``kind``). Lie « vérifié » au **hash** : un octet change → plus aucune couverture."""
    for v in verifications:
        if (v.get("verdict") == "passed" and v.get("sha256") == content_sha256
                and v.get("kind") == kind
                and (subject is None or v.get("subject") == subject)):
            return True
    return False


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_url(url: str, *, entrypoint: str = "index.html", subject: Optional[str] = None,
               expected_sha256: Optional[str] = None, timeout: float = 10.0,
               clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """Vérifie une **preview déjà servie** (URL jeton-née, fournie par la capacité preview résolue) par un **GET
    réel**. ``verdict = passed`` **ssi** ``200`` **et** (si ``expected_sha256``) l'empreinte du corps servi
    correspond — « vérifié » lié au hash. Ainsi la vérification passe par la **capacité preview substituable**
    (I9), pas par un serveur câblé en dur. Sortie brute conservée en ``proof``. Ne fait qu'un fait (non enregistré)."""
    subject = subject or f"http:{entrypoint}"
    as_of = clock()
    try:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (loopback, jeton)
                status = resp.getcode()
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            status, body, ctype = exc.code, exc.read() if hasattr(exc, "read") else b"", ""
    except Exception as exc:  # noqa: BLE001 — un échec réseau est un fait failed, jamais une exception qui remonte
        return build_verification(subject=subject, kind="http", verdict="failed", sha256=None, as_of=as_of,
                                  proof={"error": str(exc)}, detail="GET indisponible")
    body_sha = hashlib.sha256(body).hexdigest()
    proof = {"http_status": status, "content_type": ctype, "byte_size": len(body), "entrypoint": entrypoint}
    ok_status = status == 200
    ok_hash = expected_sha256 is None or body_sha == expected_sha256
    verdict = "passed" if (ok_status and ok_hash) else "failed"
    detail = "" if verdict == "passed" else (
        f"statut HTTP {status} (attendu 200)" if not ok_status else "contenu servi ≠ artefact enregistré (hash divergent)")
    return build_verification(subject=subject, kind="http", verdict=verdict, sha256=body_sha,
                              as_of=as_of, proof=proof, detail=detail)


def verify_http(workspace: Workspace, *, entrypoint: str = "index.html",
                subject: Optional[str] = None, expected_sha256: Optional[str] = None,
                timeout: float = 10.0, clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """Sert le Workspace en **loopback confiné** puis effectue un **GET réel** sur ``entrypoint`` (convenance
    autonome — bancs T3 isolés). ``verdict = passed`` **ssi** ``200`` **et** (si ``expected_sha256``) hash du corps
    servi correspondant. Sortie brute conservée en ``proof``. Ne construit qu'un fait (non enregistré)."""
    subject = subject or f"http:{entrypoint}"
    as_of = clock()
    try:
        with WorkspacePreview(workspace, entrypoint=entrypoint) as preview:
            url = preview.url_for(entrypoint)
            try:
                with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (loopback, jeton)
                    status = resp.getcode()
                    body = resp.read()
                    ctype = resp.headers.get("Content-Type", "")
            except urllib.error.HTTPError as exc:
                status, body, ctype = exc.code, exc.read() if hasattr(exc, "read") else b"", ""
    except Exception as exc:  # noqa: BLE001 — un échec réseau est un fait failed, jamais une exception qui remonte
        return build_verification(subject=subject, kind="http", verdict="failed", sha256=None, as_of=as_of,
                                  proof={"error": str(exc)}, detail="preview/GET indisponible")

    body_sha = hashlib.sha256(body).hexdigest()
    proof = {"http_status": status, "content_type": ctype, "byte_size": len(body),
             "entrypoint": entrypoint}
    ok_status = status == 200
    ok_hash = expected_sha256 is None or body_sha == expected_sha256
    verdict = "passed" if (ok_status and ok_hash) else "failed"
    detail = ""
    if not ok_status:
        detail = f"statut HTTP {status} (attendu 200)"
    elif not ok_hash:
        detail = "contenu servi ≠ artefact enregistré (hash divergent)"
    return build_verification(subject=subject, kind="http", verdict=verdict, sha256=body_sha,
                              as_of=as_of, proof=proof, detail=detail)


__all__ = ["VERIFICATION_KINDS", "build_verification", "VerificationStore", "is_verified",
           "verify_url", "verify_http"]
