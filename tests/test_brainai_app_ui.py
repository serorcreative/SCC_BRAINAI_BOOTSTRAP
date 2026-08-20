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

from brainai_app import composition, contract, server
from brainai_app.composition import converse, realize, run_pursuit, to_viewmodel


def _ready_fake_caps() -> "composition.Capabilities":
    """Capacités de **test** : arc démo 0 € + une conversation qui atteint réellement ``ready`` au 2e tour.

    A3 impose que la démo produit ne simule jamais une compréhension ; les fakes déterministes vivent donc
    **dans les tests**. On l'injecte en monkeypatchant ``composition._capabilities`` (aucune modification de
    l'API : le seam reste privé au module). La fake est **sans état** — sa ``readiness`` dépend de l'historique
    relu côté moteur, jamais d'un compteur d'instance."""
    from scc_brainai_bootstrap.builder.brainai import Capabilities
    from brainai_app.composition import _demo_envelope, demo_capabilities

    class _ReadyOnSecondTurn:
        capability = "conversation"; name = "test-fake"; model = "test-fake"

        def propose(self, message, *, history, cwd, budget_remaining_usd):
            if not history:
                obj = {"reply": "Compris. Quel est le périmètre exact ?", "readiness": "continue"}
            else:
                first = next((h.get("content") for h in history if h.get("role") == "user"), message)
                obj = {"reply": "Je reformule votre besoin ; je peux lancer sur confirmation.",
                       "readiness": "ready",
                       "matured_need": {"besoin_fondamental": first, "solutions_privilegiees": [],
                                        "inconnues_nommees": [], "hypotheses_actives": []}}
            return {"called": True, "envelope": _demo_envelope(obj), "exit_code": 0, "timed_out": False,
                    "prompt": "(fake)", "argv": ["fake"], "stdout": "", "stderr": ""}

    base = demo_capabilities()
    return Capabilities(understanding=base.understanding, specification=base.specification,
                        build=base.build, conversation=_ReadyOnSecondTurn())


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
    reply = vm["conversation"]["reply"]
    assert vm["conversation"]["need"].startswith("Je veux")
    assert "validation" in reply and "officiel" not in reply   # formulation orientée utilisateur


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
    assert "Bienvenue dans BrainAI" in html and "Que souhaitez-vous obtenir" in html
    assert "Décrivez simplement ce que vous souhaitez obtenir" in html   # placeholder ouvert
    assert "<h2>Progression</h2>" in html                                 # intitulé compréhensible
    assert "deliverable" in html and "@keyframes pop" in html             # livrables mis en évidence + animation
    assert "/v1/pursue" in html and "X-BrainAI-Token" in html
    # composant de dévoilement REMPLAÇABLE (source d'événements swappable) + progressif, sans rechargement
    assert "async function* replaySource" in html and "async function drive" in html and "function makeView" in html
    assert "progress_label" in html and "deliverables" in html and "location.reload" not in html
    # panneau système
    assert "BrainAI Version" in html and "Version du contrat" in html and "Mode d'exécution" in html
    # dialogue multi-tour : envoie converse, garde le pursuit_id, propose la réalisation, appelle realize
    assert 'kind: "converse"' in html and 'kind: "realize"' in html
    assert "currentPursuitId" in html and "pursuit_ref" in html
    assert "Lancer la réalisation" in html                                # action de confirmation visible


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


# ===================================================================== #
# Slice CONVERSATION — dialogue multi-tour visible, même Pursuit, réalisation sur confirmation (démo 0 €)
# ===================================================================== #
def test_converse_demo_turn1_is_active_and_proposes_nothing_yet():
    vm = converse("Je veux quelque chose pour mon refuge")
    p = vm["pursuit"]
    assert p["state"] == "active" and p["wait_reason"] is None            # dialogue vivant, aucun gate
    assert p["pursuit_id"].startswith("pursuit_") and p["cost"]["kind"] == "real"
    assert p["proposal"] == {"readiness": "continue"}                     # appréciation, pas encore mûr
    assert "aucune cognition" in vm["conversation"]["reply"].lower()      # démo HONNÊTE : rien de compris
    assert vm["steps"] == [] and vm["deliverables"] == []                 # l'arc n'est jamais lancé


def test_demo_conversation_is_honest_and_never_matures():
    # T4/A3 — le mode démo ne simule JAMAIS une compréhension : ``continue`` toujours, aucune maturité, jamais
    # « c'est clair pour moi », quelle que soit la longueur de l'échange. Aucune porte de gouvernance ouverte.
    vm1 = converse("Je veux un système révolutionnaire")
    pid = vm1["pursuit"]["pursuit_id"]
    assert vm1["pursuit"]["proposal"] == {"readiness": "continue"}
    for msg in ("Des précisions", "Encore des précisions", "Et encore"):
        vm = converse(msg, pursuit_ref=pid)
        p = vm["pursuit"]
        assert p["pursuit_id"] == pid
        assert p["state"] == "active" and p["wait_reason"] is None        # jamais de gate ouvert par la démo
        assert p["proposal"] == {"readiness": "continue"}                 # jamais mûr
        assert "clair pour moi" not in vm["conversation"]["reply"].lower()  # aucune usurpation de compréhension


def test_converse_turn2_reuses_pursuit_and_reaches_confirmation(monkeypatch):
    # ready/realize exercés par une FAKE dédiée (la démo produit reste honnête — A3).
    monkeypatch.setattr(composition, "_capabilities", lambda mode: _ready_fake_caps())
    vm1 = converse("Je veux un outil pour mon refuge")
    pid = vm1["pursuit"]["pursuit_id"]
    vm2 = converse("Gérer les animaux et les adoptants", pursuit_ref=pid)
    p = vm2["pursuit"]
    assert p["pursuit_id"] == pid                                         # MÊME Pursuit (identité conservée)
    assert p["state"] == "awaiting" and p["wait_reason"] == "confirmation"
    assert p["proposal"]["readiness"] == "ready" and p["proposal"]["matured_need"]
    assert vm2["deliverables"] == []                                      # toujours pas d'arc avant confirmation


def test_realize_runs_arc_on_the_same_pursuit_with_ready_fake(monkeypatch):
    # ready puis realize exercés par la FAKE dédiée ; le dernier tour EST le tour ready (garde A4-1 satisfaite).
    monkeypatch.setattr(composition, "_capabilities", lambda mode: _ready_fake_caps())
    vm1 = converse("Je veux un outil pour mon refuge")
    pid = vm1["pursuit"]["pursuit_id"]
    converse("Gérer animaux et adoptants", pursuit_ref=pid)               # atteint readiness=ready (fake)
    vm3 = realize(pid)                                                    # CONFIRMATION humaine
    p = vm3["pursuit"]
    assert p["pursuit_id"] == pid                                         # aucun nouveau pursuit_id
    assert p["state"] == "awaiting" and p["wait_reason"] == "governance"
    assert [d["label"] for d in vm3["deliverables"]] == ["Brief", "Specification", "Manifest"]


def test_http_converse_then_realize_honest_demo_keeps_one_pursuit_and_refuses(live_server):
    # Transport HTTP de bout en bout sous démo HONNÊTE : deux tours conservent la Pursuit ; la démo ne mûrit
    # jamais, donc realize REFUSE honnêtement (aucun besoin mûri) — sans lancer l'arc, même Pursuit conservée.
    base, token = live_server
    _, e1 = _req(base + "/v1/pursue", method="POST", token=token,
                 body={"kind": "converse", "message": "Je veux un outil pour mon refuge"})
    pid = e1["data"]["pursuit"]["pursuit_id"]
    assert e1["data"]["pursuit"]["state"] == "active"
    _, e2 = _req(base + "/v1/pursue", method="POST", token=token,
                 body={"kind": "converse", "message": "Gérer animaux", "pursuit_ref": pid})
    assert e2["data"]["pursuit"]["pursuit_id"] == pid                     # session conservée côté serveur
    assert e2["data"]["pursuit"]["state"] == "active"                     # démo honnête : jamais mûr
    _, e3 = _req(base + "/v1/pursue", method="POST", token=token,
                 body={"kind": "realize", "pursuit_ref": pid})
    assert e3["data"]["pursuit"]["pursuit_id"] == pid                     # MÊME Pursuit
    assert e3["data"]["pursuit"]["refused"] == "Aucun besoin mûri disponible."  # refus honnête, verbatim
    assert e3["data"]["deliverables"] == []                              # aucun arc lancé


def test_converse_without_message_is_rejected(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token, body={"kind": "converse", "message": "  "})
    assert code == 400


def test_realize_without_pursuit_ref_is_rejected(live_server):
    base, token = live_server
    code, _ = _req(base + "/v1/pursue", method="POST", token=token, body={"kind": "realize"})
    assert code == 400
