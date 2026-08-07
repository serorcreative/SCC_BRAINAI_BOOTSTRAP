"""BRAINAI-UI-001 T1 — vertical slice : navigateur → loopback → composition root → BrainAI.pursue → ViewModel.

Tests **0 €** (mode démo, capacités factices) : contrat/enveloppe, projection ViewModel (pilotée par
``Outcome.steps``, agnostique au nombre de facultés), et transport loopback (page servie, jeton exigé, liste
blanche des opérations, une opération ``pursue``). Aucun appel réel, `data/` non touché (session en tmp).
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from brainai_app import contract, server
from brainai_app.composition import run_pursuit, to_viewmodel


def _req(url, *, method="GET", token=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-BrainAI-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@pytest.fixture
def live_server():
    httpd = server.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", server.SESSION_TOKEN
    finally:
        httpd.shutdown(); httpd.server_close()


# ===================================================================== #
# Contrat (axe versionné)
# ===================================================================== #
def test_contract_describe_and_envelope():
    d = contract.describe()
    assert d["contract_version"] == "brainai-app/v1"
    assert set(d["operations"]) == {"contract", "pursue"}
    assert contract.OPERATIONS["pursue"]["kind"] == "action"
    e = contract.envelope("pursue", {"x": 1}, "t")
    assert e["operation"] == "pursue" and e["kind"] == "action" and e["generated_as_of"] == "t"
    assert e["data"] == {"x": 1} and e["contract_version"] == "brainai-app/v1"


# ===================================================================== #
# ViewModel — projection de l'Outcome, pilotée par steps
# ===================================================================== #
def test_run_pursuit_demo_viewmodel():
    vm = run_pursuit("Je veux une application de gestion d'un refuge animalier.", mode="demo")
    p = vm["pursuit"]
    assert p["state"] == "awaiting" and p["wait_reason"] == "governance"     # non autoritatif
    assert p["pursuit_id"].startswith("pursuit_") and p["cost"]["kind"] == "real"
    assert isinstance(p["elapsed_ms"], int) and p["mode"] == "demo" and p["budget_usd"] == 2.0
    assert p["brainai_version"] == "arc-propose-001" and p["contract_version"] == "brainai-app/v1"
    assert [s["label"] for s in vm["steps"]] == ["Brief", "Specification", "Manifest"]
    assert [s["progress_label"] for s in vm["steps"]] == ["Compréhension", "Spécification", "Construction"]
    assert all(s["status"] == "proposed" for s in vm["steps"])
    assert [d["label"] for d in vm["deliverables"]] == ["Brief", "Specification", "Manifest"]
    assert vm["conversation"]["need"].startswith("Je veux") and "validation" in vm["conversation"]["reply"]


def test_deliverables_are_faculty_agnostic():
    # Un Outcome avec une faculté INCONNUE => libellé = nom brut (aucune liste de facultés codée en dur).
    from scc_brainai_bootstrap.builder.brainai import Outcome
    out = Outcome(state="awaiting", wait_reason="governance", project_id="p", pursuit_id="pursuit_x",
                  as_of="t", steps=({"faculty": "observation", "status": "proposed", "fact_id": "obs_1"},),
                  cost_total={"value": 0.0, "kind": "real"})
    vm = to_viewmodel(out, need="x", mode="demo", budget_usd=2.0, elapsed_ms=1)
    assert vm["steps"][0]["label"] == "observation"                # repli libellé livrable
    assert vm["steps"][0]["progress_label"] == "observation"       # repli libellé de progression
    assert vm["deliverables"][0]["label"] == "observation" and vm["deliverables"][0]["fact_id"] == "obs_1"


# ===================================================================== #
# Transport loopback (ADR-UI-001/002/003)
# ===================================================================== #
def test_server_binds_loopback_only():
    httpd = server.make_server("127.0.0.1", 0)
    try:
        assert httpd.server_address[0] == "127.0.0.1"     # jamais 0.0.0.0
    finally:
        httpd.server_close()


def test_get_root_serves_welcome_page(live_server):
    base, _ = live_server
    with urllib.request.urlopen(base + "/", timeout=10) as resp:
        html = resp.read().decode("utf-8")
        assert resp.status == 200
    assert "Bienvenue dans BrainAI" in html and "Que souhaitez-vous créer" in html
    assert "/v1/pursue" in html and "X-BrainAI-Token" in html
    # composant de dévoilement REMPLAÇABLE (source d'événements swappable) + progressif, sans rechargement
    assert "async function* replaySource" in html and "async function drive" in html and "function makeView" in html
    assert "progress_label" in html and "deliverables" in html and "location.reload" not in html
    # panneau système
    assert "BrainAI Version" in html and "Version du contrat" in html and "Mode d'exécution" in html


def test_contract_endpoint_requires_token(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/contract")                 # sans jeton
    assert code == 401
    code, env = _req(base + "/v1/contract", token=token)  # avec jeton
    assert code == 200 and env["operation"] == "contract" and env["data"]["contract_version"] == "brainai-app/v1"


def test_pursue_requires_token(live_server):
    base, _ = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", body={"need": "x"})
    assert code == 401


def test_pursue_demo_via_http_end_to_end(live_server):
    base, token = live_server
    code, env = _req(base + "/v1/pursue", method="POST", token=token,
                     body={"need": "Une application de gestion d'un refuge animalier.", "mode": "demo"})
    assert code == 200 and env["operation"] == "pursue" and env["kind"] == "action"
    vm = env["data"]
    assert vm["pursuit"]["state"] == "awaiting" and vm["pursuit"]["pursuit_id"].startswith("pursuit_")
    assert [d["label"] for d in vm["deliverables"]] == ["Brief", "Specification", "Manifest"]


def test_unknown_operation_is_rejected(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/frobnicate", method="POST", token=token, body={})
    assert code == 404                                    # liste blanche du contrat


def test_pursue_empty_need_is_rejected(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token, body={"need": "   "})
    assert code == 400
