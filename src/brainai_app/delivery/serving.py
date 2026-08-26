"""Serveur **loopback confiné** d'un Workspace — preview locale réelle (JALON 2, Q4=A).

Sert les fichiers **réellement bâtis** d'un Workspace de Pursuit, en respectant les garde-fous UI hérités
(ADR-UI-001/004) : liaison **loopback** ``127.0.0.1`` uniquement ; **port éphémère** ; **jeton** par serveur ;
**default-deny** (toute requête sans jeton valide → 401). Chaque chemin demandé repasse par
:meth:`Workspace.resolve_within` : impossible de sortir du Workspace (``..``/absolu/symlink). Lecture seule ;
rien n'est exécuté (les fichiers sont **servis**, jamais lancés).

Utilisé par la **vérification** (:mod:`.verify`, GET → 200 sur le contenu réel) et par la **capacité preview**
(T6). Aucun déploiement public : la surface reste locale (le déploiement public est une capacité distincte,
différée RS-2/J3+). Stdlib pur.
"""

from __future__ import annotations

import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlsplit

from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError

# Types MIME minimaux (pas de dépendance ; défaut = octet-stream).
_MIME = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".txt": "text/plain; charset=utf-8", ".ico": "image/x-icon",
}


def _content_type(rel: str) -> str:
    dot = rel.rfind(".")
    return _MIME.get(rel[dot:].lower(), "application/octet-stream") if dot != -1 else "application/octet-stream"


class WorkspacePreview:
    """Preview loopback d'un Workspace : serveur éphémère, jeton, default-deny, confiné par ``resolve_within``.

    Usage : ``with WorkspacePreview(workspace, entrypoint="index.html") as pv: pv.url_for(...)`` — le serveur
    tourne en tâche de fond ; ``close()`` (ou la sortie du ``with``) l'arrête. ``base_url``/``token`` exposent la
    surface locale ; ``preview_ref`` en est le reflet non secret (jeton **jamais** consigné dans un fait)."""

    def __init__(self, workspace: Workspace, *, entrypoint: str = "index.html",
                 host: str = "127.0.0.1"):
        self._workspace = workspace
        self._root = Path(workspace.path).resolve()
        self._entrypoint = entrypoint
        self._token = secrets.token_urlsafe(24)
        self._host = host
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._port = 0

    # -- cycle de vie ---------------------------------------------------- #
    def start(self) -> "WorkspacePreview":
        root, token = self._root, self._token
        workspace = self._workspace

        class _Handler(BaseHTTPRequestHandler):
            server_version = "BrainAI-Preview/loopback"

            def log_message(self, *_a):  # silence
                return

            def _deny(self, code: int, msg: str) -> None:
                body = msg.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                parts = urlsplit(self.path)
                # default-deny : jeton requis (en-tête OU query ?t=)
                supplied = self.headers.get("X-BrainAI-Token")
                if supplied is None:
                    for kv in parts.query.split("&"):
                        if kv.startswith("t="):
                            supplied = unquote(kv[2:])
                            break
                if not supplied or not secrets.compare_digest(supplied, token):
                    self._deny(401, "jeton requis")
                    return
                rel = unquote(parts.path).lstrip("/") or entrypoint
                try:
                    target = workspace.resolve_within(rel)          # confinement : jamais hors Workspace
                except WorkspaceError:
                    self._deny(403, "hors périmètre")
                    return
                if not target.is_file():
                    self._deny(404, "introuvable")
                    return
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", _content_type(rel))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._httpd = ThreadingHTTPServer((self._host, 0), _Handler)
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def __enter__(self) -> "WorkspacePreview":
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- surface --------------------------------------------------------- #
    @property
    def token(self) -> str:
        return self._token

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def url_for(self, rel: Optional[str] = None) -> str:
        rel = (rel or self._entrypoint).lstrip("/")
        return f"{self.base_url}/{rel}?t={self._token}"

    def preview_ref(self) -> dict:
        """Reflet **non secret** de la preview (jamais le jeton) — pour un fait/ViewModel."""
        return {"kind": "local_loopback", "host": self._host, "port": self._port,
                "entrypoint": self._entrypoint, "base_url": self.base_url}

    def address(self) -> Tuple[str, int]:
        return self._host, self._port


__all__ = ["WorkspacePreview"]
