"""Transport **loopback** minimal (ADR-UI-001/002/003/004) — stdlib pure, une opération : ``pursue``.

- **127.0.0.1 uniquement**, **port éphémère**, **jeton de session** (ADR-UI-001 ; jamais ``0.0.0.0``).
- **HTTP/JSON**, dispatcher générique piloté par le contrat : ``POST /v1/{operation}`` + ``GET /v1/contract``
  (ADR-UI-002) ; liste blanche contre ``contract.OPERATIONS`` ; enveloppe renvoyée **verbatim**.
- **stdlib ``http.server``**, zéro dépendance (ADR-UI-003).
- Actions **locales** autorisées en loopback ; le distant (lecture seule) est différé (ADR-UI-004).

Le transport **n'ajoute aucune logique** : il liste-blanche, authentifie, appelle le composition root et sert
le résultat. ``GET /`` sert la page statique ; le navigateur transmet le jeton (reçu dans l'URL) en en-tête
``X-BrainAI-Token`` pour ``/v1/*``.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

from brainai_app import contract
from brainai_app.composition import run_pursuit

_STATIC = Path(__file__).resolve().parent / "static"
SESSION_TOKEN = secrets.token_urlsafe(24)          # jeton de session (ADR-UI-001), régénéré à chaque import


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Handler(BaseHTTPRequestHandler):
    server_version = "BrainAI-UI/loopback"

    # -- utilitaires --
    def _send_json(self, code: int, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name: str, ctype: str) -> None:
        try:
            body = (_STATIC / name).read_bytes()
        except OSError:
            self._send_json(404, {"error": "ressource introuvable"}); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return self.headers.get("X-BrainAI-Token") == SESSION_TOKEN

    def _path(self) -> str:
        return self.path.split("?", 1)[0]

    def log_message(self, *args: Any) -> None:   # silencieux
        return

    # -- routes --
    def do_GET(self) -> None:
        path = self._path()
        if path in ("/", "/index.html"):
            self._send_static("index.html", "text/html; charset=utf-8"); return
        if path == "/v1/contract":
            if not self._authorized():
                self._send_json(401, {"error": "jeton requis"}); return
            self._send_json(200, contract.envelope("contract", contract.describe(), _now())); return
        self._send_json(404, {"error": "route inconnue"})

    def do_POST(self) -> None:
        path = self._path()
        operation = path[len("/v1/"):] if path.startswith("/v1/") else ""
        # liste blanche : seule une opération 'action' connue est servie (contract est en lecture, via GET)
        if operation not in contract.OPERATIONS or contract.OPERATIONS[operation]["kind"] != "action":
            self._send_json(404, {"error": f"opération inconnue : {operation!r}"}); return
        if not self._authorized():
            self._send_json(401, {"error": "jeton requis"}); return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "corps JSON invalide"}); return
        if operation == "pursue":
            need = str(payload.get("need") or "").strip()
            mode = payload.get("mode") or "demo"
            if not need:
                self._send_json(400, {"error": "champ 'need' requis (non vide)"}); return
            if mode not in ("demo", "real"):
                self._send_json(400, {"error": "mode invalide (demo|real)"}); return
            data = run_pursuit(need, mode=mode)
            self._send_json(200, contract.envelope("pursue", data, _now())); return
        self._send_json(404, {"error": "opération non servie"})


def make_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Serveur loopback. ``host`` **doit** rester ``127.0.0.1`` ; ``port=0`` → port éphémère."""
    return ThreadingHTTPServer((host, port), _Handler)


def serve() -> None:
    srv = make_server()
    host, port = srv.server_address[:2]
    url = f"http://127.0.0.1:{port}/?t={SESSION_TOKEN}"
    print("BrainAI UI (loopback, mode démo par défaut).")
    print("Ouvrez cette URL dans votre navigateur :")
    print("  " + url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    serve()
