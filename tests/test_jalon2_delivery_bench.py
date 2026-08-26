"""Banc **Étage 1** de JALON 2 — livraison réelle, **déterministe, 0 $** (fakes ; aucun appel payant).

Couvre les propriétés structurelles de la livraison : build réel confiné (A1), runner/BuildStep (T2/A2),
vérification liée au hash (T3), budget réellement borné (T4), mémoire + ``delivered`` (T5), preview substituable
(T6/I9), anti-câblage fournisseur / anti-domaine (A5/I8). Aucun réseau sortant, aucune dépense — toutes les
capacités facturables sont **factices**. L'Étage 2 (parcours réel payant) vit hors de ce banc.
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import pytest

from brainai_app.delivery.budget import BudgetLedger
from brainai_app.delivery.delivered import DeliveredStore
from brainai_app.delivery.memory import open_memory_store, write_delivery_memory
from brainai_app.delivery.preview_capability import LocalPreviewAdapter
from brainai_app.delivery.runner import (
    BuildRunner, BuildRunStore, STEP_FAILED, STEP_SUCCEEDED, Step, StepResult, detect_interrupted_runs)
from brainai_app.delivery.service import run_delivery
from brainai_app.delivery.verify import VerificationStore, is_verified, verify_http
from scc_brainai_bootstrap.builder.builds import BuildStore
from scc_brainai_bootstrap.builder.site import SITE_ENTRYPOINT, collect_artifacts, produce_site_build
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError

CLOCK = lambda: "2026-08-21T00:00:00+00:00"  # noqa: E731 (horloge figée pour le déterminisme)

_SPEC = {"specification_id": "spec_bench", "status": "proposed", "specification": {
    "product_objective": "Page de présentation d'un club de lecture",
    "users_and_roles": ["Visiteur", "Membre"], "functional_scope": ["Présentation"],
    "features": ["Prochaine lecture", "Rejoindre"], "entities_and_data": ["Club", "Livre"],
    "key_journeys": ["Découvrir"], "constraints": ["Statique"], "acceptance_criteria": ["Se charge"],
    "assumptions": ["Public"], "open_questions": [], "out_of_scope": ["Paiement"]}}

_HTML = "<!doctype html><html><head><meta charset=utf-8><title>Club</title></head><body><h1>Club</h1></body></html>"


def _env(cost=0.0):
    return {"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
            "result": "ok", "total_cost_usd": cost, "usage": {"input_tokens": 5, "output_tokens": 7}}


class FakeSite:
    """Adaptateur de build **factice** conforme au Protocol — écrit un vrai fichier, **aucun appel réel**."""
    capability = "build"; name = "fake_provider"; model = "fake"; max_budget_usd = 0.5

    def __init__(self, *, behavior="ok", cost=0.15):
        self.behavior = behavior
        self.cost = cost
        self.calls = 0

    def build(self, spec, *, cwd, budget_remaining_usd):
        self.calls += 1
        if budget_remaining_usd < self.max_budget_usd:
            return {"called": False, "refused": "budget insuffisant", "envelope": None, "exit_code": None,
                    "timed_out": False, "prompt": "p", "argv": ["fake"], "stdout": None, "stderr": None}
        if self.behavior == "ok":
            (Path(cwd) / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
            return {"called": True, "envelope": _env(self.cost), "exit_code": 0, "timed_out": False,
                    "prompt": "p", "argv": ["fake", "-p"], "stdout": "", "stderr": ""}
        if self.behavior == "empty_entry":
            (Path(cwd) / SITE_ENTRYPOINT).write_text("", encoding="utf-8")
            return {"called": True, "envelope": _env(self.cost), "exit_code": 0, "timed_out": False,
                    "prompt": "p", "argv": ["fake"], "stdout": "", "stderr": ""}
        if self.behavior == "no_entry":                       # écrit un autre fichier, pas index.html
            (Path(cwd) / "readme.txt").write_text("x", encoding="utf-8")
            return {"called": True, "envelope": _env(self.cost), "exit_code": 0, "timed_out": False,
                    "prompt": "p", "argv": ["fake"], "stdout": "", "stderr": ""}
        if self.behavior == "escape_symlink":                 # tente une évasion par symlink sortant
            (Path(cwd) / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
            outside = Path(cwd).resolve().parent.parent / "outside_secret"
            outside.mkdir(exist_ok=True)
            (outside / "secret.txt").write_text("SECRET", encoding="utf-8")
            (Path(cwd) / "leak").symlink_to(outside / "secret.txt")
            return {"called": True, "envelope": _env(self.cost), "exit_code": 0, "timed_out": False,
                    "prompt": "p", "argv": ["fake"], "stdout": "", "stderr": ""}
        if self.behavior == "error":
            return {"called": True, "envelope": {"is_error": True, "subtype": "success", "result": None},
                    "exit_code": 1, "timed_out": False, "prompt": "p", "argv": ["fake"], "stdout": "err", "stderr": "e"}
        if self.behavior == "timeout":
            (Path(cwd) / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
            return {"called": True, "envelope": None, "exit_code": None, "timed_out": True,
                    "prompt": "p", "argv": ["fake"], "stdout": "", "stderr": ""}
        raise AssertionError(self.behavior)


class FakePreview:
    """Capacité preview **substituée** (I9) : même contrat que ``LocalPreviewAdapter``, autre fournisseur."""
    capability = "preview.local"; name = "fake_preview"

    def __init__(self):
        self.opened = 0

    def open(self, workspace, *, entrypoint="index.html"):
        self.opened += 1
        from brainai_app.delivery.serving import WorkspacePreview
        return WorkspacePreview(workspace, entrypoint=entrypoint).start()


def _ws(tmp_path):
    ws = Workspace(tmp_path / "exec", "site"); ws.ensure(); return ws


def _stores(tmp_path):
    return dict(build_store=BuildStore(tmp_path / "b.jsonl"),
                tool_store=ToolInvocationStore(tmp_path / "t.jsonl"),
                run_store=BuildRunStore(tmp_path / "r.jsonl"),
                verification_store=VerificationStore(tmp_path / "v.jsonl"),
                delivered_store=DeliveredStore(tmp_path / "d.jsonl"))


def _produce(tmp_path, adapter, budget=1.0):
    ws = _ws(tmp_path)
    return produce_site_build(spec_source=_SPEC, adapter=adapter,
                              store=BuildStore(tmp_path / "b.jsonl"),
                              tool_store=ToolInvocationStore(tmp_path / "t.jsonl"),
                              workspace=ws, project_id="site", budget_remaining_usd=budget,
                              cwd=ws.path, clock=CLOCK), ws


# --------------------------------------------------------------------- #
# A — build réel confiné (T1 / A1)
# --------------------------------------------------------------------- #
def test_site_build_success_records_artifact_toolinvocation_and_sha256(tmp_path):
    out, ws = _produce(tmp_path, FakeSite())
    fact = out["fact"]
    assert fact["status"] == "proposed"
    assert fact["artefact"]["relative_path"] == SITE_ENTRYPOINT
    # sha256 = empreinte des octets RÉELLEMENT écrits
    written = (ws.path / SITE_ENTRYPOINT).read_bytes()
    assert fact["artefact"]["sha256"] == hashlib.sha256(written).hexdigest()
    # ToolInvocation enregistrée (succès), référencée par le build
    tinv = ToolInvocationStore(tmp_path / "t.jsonl").read_all()
    assert len(tinv) == 1 and tinv[0]["status"] == "succeeded"
    assert fact["tool_ref"] == tinv[0]["invocation_id"]


def test_site_build_failure_client_error_is_failed_fact(tmp_path):
    out, _ = _produce(tmp_path, FakeSite(behavior="error"))
    assert out["fact"]["status"] == "failed" and out["fact"]["error"] != "success"
    assert out["fact"]["artefacts"] == []


def test_site_build_timeout_is_failed_fact(tmp_path):
    out, _ = _produce(tmp_path, FakeSite(behavior="timeout"))
    assert out["fact"]["status"] == "failed" and out["fact"]["error"] == "safety_watchdog_exceeded"
    tinv = ToolInvocationStore(tmp_path / "t.jsonl").read_all()
    assert tinv[0]["status"] == "timeout" and tinv[0]["timed_out"] is True   # statut BRUT ToolInvocation inchangé


def test_missing_entrypoint_is_failure(tmp_path):
    out, _ = _produce(tmp_path, FakeSite(behavior="no_entry"))
    assert out["fact"]["status"] == "failed" and "point d'entrée" in out["fact"]["error"]


def test_empty_entrypoint_is_failure(tmp_path):
    out, _ = _produce(tmp_path, FakeSite(behavior="empty_entry"))
    assert out["fact"]["status"] == "failed"


def test_escape_symlink_detected_build_failed_never_silent(tmp_path):
    """A1 : une évasion (symlink sortant) est **détectée** et matérialisée par un fait ``failed`` — jamais tue."""
    out, ws = _produce(tmp_path, FakeSite(behavior="escape_symlink"))
    assert out["fact"]["status"] == "failed"
    assert "évasion hors workspace" in out["fact"]["error"]
    assert out["fact"]["artefacts"] == []


def test_resolve_within_blocks_dotdot_and_absolute(tmp_path):
    """A1 : toute référence d'artefact passe par ``resolve_within`` — ``..``/absolu refusés avant tout effet."""
    ws = _ws(tmp_path)
    for bad in ("../escape.html", "/etc/passwd", "a/../../b.html"):
        with pytest.raises(WorkspaceError):
            ws.resolve_within(bad)


def test_collect_artifacts_confined_only(tmp_path):
    ws = _ws(tmp_path)
    (ws.path / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
    (ws.path / "style.css").write_text("body{}", encoding="utf-8")
    arts = collect_artifacts(ws)
    assert {a["relative_path"] for a in arts} == {SITE_ENTRYPOINT, "style.css"}


# --------------------------------------------------------------------- #
# B — vérification liée au hash (T3)
# --------------------------------------------------------------------- #
def test_verification_passed_http_200(tmp_path):
    ws = _ws(tmp_path)
    (ws.path / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
    sha = hashlib.sha256((ws.path / SITE_ENTRYPOINT).read_bytes()).hexdigest()
    v = verify_http(ws, entrypoint=SITE_ENTRYPOINT, expected_sha256=sha, clock=CLOCK)
    assert v["verdict"] == "passed" and v["proof"]["http_status"] == 200 and v["kind"] == "http"
    assert v["sha256"] == sha


def test_verification_failed_when_absent(tmp_path):
    ws = _ws(tmp_path)                                          # aucun index.html servi
    v = verify_http(ws, entrypoint=SITE_ENTRYPOINT, clock=CLOCK)
    assert v["verdict"] == "failed"


def test_verified_bound_to_hash_one_byte_change(tmp_path):
    ws = _ws(tmp_path)
    (ws.path / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
    sha = hashlib.sha256((ws.path / SITE_ENTRYPOINT).read_bytes()).hexdigest()
    v = verify_http(ws, entrypoint=SITE_ENTRYPOINT, expected_sha256=sha, clock=CLOCK)
    store = VerificationStore(tmp_path / "v.jsonl"); store.record(v)
    assert is_verified(sha, store.read_all()) is True
    # un octet change → l'ancienne vérification ne couvre plus le nouveau contenu
    (ws.path / SITE_ENTRYPOINT).write_text(_HTML + " ", encoding="utf-8")
    new_sha = hashlib.sha256((ws.path / SITE_ENTRYPOINT).read_bytes()).hexdigest()
    assert new_sha != sha
    assert is_verified(new_sha, store.read_all()) is False


def test_verification_no_implicit_propagation(tmp_path):
    """« vérifié » ne se propage pas : un sujet vérifié ne rend pas un autre sujet vérifié."""
    ws = _ws(tmp_path)
    (ws.path / SITE_ENTRYPOINT).write_text(_HTML, encoding="utf-8")
    sha = hashlib.sha256((ws.path / SITE_ENTRYPOINT).read_bytes()).hexdigest()
    v = verify_http(ws, entrypoint=SITE_ENTRYPOINT, subject="http:index.html", expected_sha256=sha, clock=CLOCK)
    store = VerificationStore(tmp_path / "v.jsonl"); store.record(v)
    assert is_verified(sha, store.read_all(), subject="http:index.html") is True
    assert is_verified(sha, store.read_all(), subject="http:autre.html") is False


# --------------------------------------------------------------------- #
# C — budget réellement borné (T4)
# --------------------------------------------------------------------- #
def test_call_count_hard_cap(tmp_path):
    b = BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=100.0, max_calls=2)
    b.record_charge({"value": 0.1, "kind": "real"})
    b.record_charge({"value": 0.1, "kind": "real"})
    ok, reason = b.can_start_call(0.5)
    assert ok is False and "nombre d'appels" in reason


def test_usd_ceiling_precheck_blocks_before_call(tmp_path):
    b = BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=0.30, max_calls=10)
    # 0 dépensé mais l'enveloppe de la prochaine invocation (0,5) dépasserait le plafond
    ok, reason = b.can_start_call(0.5)
    assert ok is False and "plafond monétaire" in reason


def test_costs_real_or_unavailable_never_invented(tmp_path):
    b = BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=3.0, max_calls=5)
    b.record_charge({"value": 0.2, "kind": "real"})
    b.record_charge({"value": None, "kind": "unavailable"})
    assert b.spent_real() == pytest.approx(0.2)                 # l'unavailable n'est jamais compté
    assert b.has_unavailable_cost() is True
    assert b.calls_made() == 2


def test_budget_exhausted_stops_run_real(tmp_path):
    """Arrêt RÉEL : plafond USD atteint avant l'appel ⇒ ``budget_exhausted`` + run ``failed``, aucune étape lancée."""
    st = _stores(tmp_path)
    budget = BudgetLedger(tmp_path / "bud.jsonl", ceiling_usd=0.30, max_calls=5)
    fake = FakeSite(cost=0.5)
    rep = run_delivery(spec_source=_SPEC, workspace=_ws(tmp_path), project_id="site", pursuit_ref="p1",
                       site_build=fake, preview=LocalPreviewAdapter(), budget=budget, clock=CLOCK, **st)
    assert rep["status"] == "budget_exhausted"
    assert fake.calls == 0                                      # jamais appelé (pré-garde)
    assert any(e["fact_type"] == "budget_exhausted" for e in budget.read_all())


# --------------------------------------------------------------------- #
# D — runner / BuildStep / A2 (T2)
# --------------------------------------------------------------------- #
def _mk(name, status, prereq=None, cost=None, billable=False):
    return Step(name=name, kind="x", run=lambda: StepResult(status=status, refs={"n": name}, cost=cost),
                billable=billable, max_usd=0.5 if billable else None, prerequisites=prereq or [])


def test_steps_ordered_by_real_kahn(tmp_path):
    store = BuildRunStore(tmp_path / "r.jsonl")
    r = BuildRunner(store, BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=3, max_calls=3),
                    pursuit_ref="p", clock=CLOCK)
    out = r.run([_mk("verify", STEP_SUCCEEDED, prereq=["build"]), _mk("build", STEP_SUCCEEDED)])
    assert [s["step"] for s in out["steps"]] == ["build", "verify"]


def test_first_failure_stops_no_retry(tmp_path):
    store = BuildRunStore(tmp_path / "r.jsonl")
    r = BuildRunner(store, BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=3, max_calls=3),
                    pursuit_ref="p", clock=CLOCK)
    calls = {"verify": 0}

    def verify_run():
        calls["verify"] += 1
        return StepResult(status=STEP_SUCCEEDED)

    out = r.run([_mk("build", STEP_FAILED),
                 Step(name="verify", kind="x", run=verify_run, prerequisites=["build"])])
    assert out["status"] == "failed"
    assert calls["verify"] == 0                                # étape aval jamais lancée, aucun retry


def test_cancellation_honest_order(tmp_path):
    store = BuildRunStore(tmp_path / "r.jsonl")
    gate = threading.Event()

    def slow():
        gate.wait(2)
        return StepResult(status=STEP_SUCCEEDED)

    r = BuildRunner(store, BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=3, max_calls=3), pursuit_ref="p")
    r.start([Step(name="build", kind="x", run=slow),
             Step(name="verify", kind="x", run=lambda: StepResult(STEP_SUCCEEDED), prerequisites=["build"])])
    time.sleep(0.2)
    r.request_cancel()                                         # (1) acte humain → fait d'annulation
    gate.set()                                                 # (2) l'étape en vol termine réellement
    r.wait(3)
    seq = [f["fact_type"] for f in store.read_all()]
    i_cancel = seq.index("cancellation_requested")
    i_step_done = next(i for i, f in enumerate(store.read_all())
                       if f["fact_type"] == "build_step" and f.get("status") == STEP_SUCCEEDED)
    i_run_cancel = next(i for i, f in enumerate(store.read_all())
                        if f["fact_type"] == "build_run" and f.get("status") == "cancelled")
    assert i_cancel < i_step_done < i_run_cancel               # ordre honnête (A2)


def test_run_interrupted_detected_and_idempotent(tmp_path):
    store = BuildRunStore(tmp_path / "r.jsonl")
    store.append({"fact_type": "build_run", "run_id": "run_z", "pursuit_ref": "p", "status": "running",
                  "as_of": "t0"})
    store.append({"fact_type": "build_step", "run_ref": "run_z", "step": "build", "status": "running",
                  "as_of": "t0"})
    emitted = detect_interrupted_runs(store, clock=CLOCK)
    assert len(emitted) == 1 and emitted[0]["fact_type"] == "run_interrupted"
    assert emitted[0]["interrupted_steps"] == ["build"]
    assert detect_interrupted_runs(store, clock=CLOCK) == []   # idempotent : jamais reconstaté


def test_resume_is_new_run_referencing_previous(tmp_path):
    store = BuildRunStore(tmp_path / "r.jsonl")
    store.append({"fact_type": "build_run", "run_id": "run_prev", "pursuit_ref": "p", "status": "running",
                  "as_of": "t0"})
    detect_interrupted_runs(store, clock=CLOCK)
    r = BuildRunner(store, BudgetLedger(tmp_path / "b.jsonl", ceiling_usd=3, max_calls=3),
                    pursuit_ref="p", clock=CLOCK, prev_run_ref="run_prev")
    r.run([_mk("build", STEP_SUCCEEDED)])
    runs = [f for f in store.read_all() if f["fact_type"] == "build_run" and f.get("prev_run_ref") == "run_prev"]
    assert runs and runs[0]["run_id"] != "run_prev"            # reprise = NOUVEAU run référençant le précédent


# --------------------------------------------------------------------- #
# E — livraison complète, delivered, mémoire (T5)
# --------------------------------------------------------------------- #
def test_full_delivery_delivered_fact_and_provenance(tmp_path):
    st = _stores(tmp_path)
    rep = run_delivery(spec_source=_SPEC, workspace=_ws(tmp_path), project_id="site", pursuit_ref="p_ok",
                       site_build=FakeSite(), preview=LocalPreviewAdapter(),
                       budget=BudgetLedger(tmp_path / "bud.jsonl", ceiling_usd=3.0, max_calls=2),
                       clock=CLOCK, **st)
    assert rep["status"] == "delivered"
    d = DeliveredStore(tmp_path / "d.jsonl").read_all()
    assert len(d) == 1
    fact = d[0]
    for k in ("pursuit_ref", "artifact_ref", "preview_ref", "verification_ref", "as_of"):
        assert k in fact
    assert fact["artifact_ref"]["relative_path"] == SITE_ENTRYPOINT
    prov = rep["provenance"]
    assert prov["build_id"] and prov["verification_id"] and prov["delivered_id"] and prov["tool_ref"]


def test_memory_written_to_fake_dir_write_only(tmp_path):
    store = open_memory_store(tmp_path / "fake_memory")        # répertoire mémoire FACTICE
    entry = write_delivery_memory(store, pursuit_ref="p", project="site", result="club",
                                  decisions=["confirmée"], artifact_ref={"relative_path": "index.html"},
                                  preview_ref={"kind": "local_loopback"},
                                  provenance_ids={"build_id": "b1"}, as_of="t0")
    assert entry.id.startswith("mem_")
    jsonl = (tmp_path / "fake_memory" / "brain_memory.jsonl")
    assert jsonl.exists() and "pursuit_delivered" in jsonl.read_text(encoding="utf-8")


# --------------------------------------------------------------------- #
# F — substituabilité (I9), anti-câblage (A5), anti-domaine (I8)
# --------------------------------------------------------------------- #
def test_preview_capability_substitutable_fake_provider(tmp_path):
    """I9 : remplacer la capacité preview par une fake ne change RIEN à la logique métier (livraison verte)."""
    st = _stores(tmp_path)
    fake_prev = FakePreview()
    rep = run_delivery(spec_source=_SPEC, workspace=_ws(tmp_path), project_id="site", pursuit_ref="p_sub",
                       site_build=FakeSite(), preview=fake_prev,
                       budget=BudgetLedger(tmp_path / "bud.jsonl", ceiling_usd=3.0, max_calls=2),
                       clock=CLOCK, **st)
    assert rep["status"] == "delivered" and fake_prev.opened == 1


def test_site_capability_substitutable_via_binder_swap():
    """I9 : substituabilité par **changement de binder** (registre) — aucune modif de la logique métier."""
    from brainai_app import providers
    sentinel = object()
    descriptors = providers.delivery_descriptors()
    binders = dict(providers.delivery_binders())
    binders[(providers.CLAUDE_CODE, providers.BUILD_SITE)] = lambda: sentinel
    impl = providers.resolve_capability(providers.BUILD_SITE, descriptors, binders)
    assert impl is sentinel                                     # le descriptor/binder substitue l'implémentation


def test_deploy_public_is_deferred_descriptor_unavailable():
    """Q4 : le déploiement public est **différé** (RS-2/J3+) — descriptor présent mais indisponible/non lié."""
    from brainai_app import providers
    d = providers.deferred_deploy_public_descriptor()
    assert d.capabilities == [providers.DEPLOY_PUBLIC] and d.availability == "unavailable"


def test_no_provider_slug_in_delivery_business_code():
    """A5/anti-câblage : la logique de livraison (service) ne nomme AUCUN fournisseur — capacités injectées."""
    src = Path(__file__).resolve().parents[1] / "src" / "brainai_app" / "delivery" / "service.py"
    text = src.read_text(encoding="utf-8")
    for slug in ("claude_code", "ClaudeCode", "claude_bin", "anthropic"):
        assert slug not in text, f"slug fournisseur câblé dans service.py : {slug}"


def test_no_domain_rule_in_builder_or_delivery():
    """I8/anti-domaine : aucune règle spécifique au domaine du Parcours 1 (« club de lecture ») ni immobilier
    dans BrainAI/builder/delivery. On cible des **mots entiers** domaine (pas des sous-chaînes de mots français
    courants comme « livraison »/« relecture »)."""
    import re
    roots = [Path(__file__).resolve().parents[1] / "src" / "scc_brainai_bootstrap" / "builder",
             Path(__file__).resolve().parents[1] / "src" / "brainai_app" / "delivery"]
    forbidden = (r"\bclub\b", r"club de lecture", r"\bimmobili", r"book\s*club", r"\bISBN\b")
    offenders = []
    for root in roots:
        for py in root.glob("*.py"):
            low = py.read_text(encoding="utf-8").lower()
            for pat in forbidden:
                if re.search(pat, low):
                    offenders.append(f"{py.name}:{pat}")
    assert not offenders, f"règle de domaine détectée : {offenders}"
