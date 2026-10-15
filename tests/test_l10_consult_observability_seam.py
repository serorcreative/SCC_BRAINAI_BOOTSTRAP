"""Tests du seam ``consult`` (Observability first) — contrat REVIEW-ROSE (SHA 6456c571…).

Déterministe, 0 LLM, 0 USD, 0 réseau, 0 subprocess. Fakes uniquement (aucun 09 réel n'est requis pour la logique
du seam / de la conversion ; la voie rapporteuse est exercée via un faux ``scc_control_plane`` à espions).

Couvre : conversion §4 (succès / unavailable / unexpected / persistence_failure / prerequisite_failure /
invalid_envelope a & b / refused_before_call) ; D-1 (standalone, refus de toute pursuit_ref) ; C-C (decision_source) ;
D-2 (phases, un seul record, ref réelle même sur échec, prérequis horodatage) ; D-3 (contexte persisté, id-hash
inchangé) ; R-B (paire (pursuit_ref, invocation_id) non unique intra-contexte) ; rétrocompat de la voie historique.

STATUT : PRÉPARÉ, **NON EXÉCUTÉ**. Aucun finding (dont F-02) n'est fermé par la seule présence de ce fichier.
"""
from __future__ import annotations

import sys
import types

import pytest

from dataclasses import replace

from scc_brainai_bootstrap.builder.brainai import (
    BrainAI, Capabilities, RunContext, consult_intent, validate_intent, Intent, IntentError,
    CapabilityInjectionError,
)
from scc_brainai_bootstrap.builder.observability_read import (
    OBS_HEALTH, produce_observability_read, produce_observability_report,
    LocalControlPlaneReadAdapter, ObservabilityReadError,
)
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from brainai_app.composition import demo_capabilities

CLK = "2026-07-06T00:00:00+00:00"
PROVIDER = "local_control_plane"


# --------------------------------------------------------------------- #
# Fakes moteur (seam) — capacité observability injectée, sans 09
# --------------------------------------------------------------------- #
class _FakeObs:
    """Capacité observability-read factice — satisfait le Protocol structurel ; renvoie un rapport figé."""

    served_capability = OBS_HEALTH
    name = PROVIDER

    def __init__(self, report):
        self._report = report
        self.calls = []

    def contract(self):
        return None

    def read(self, *, project_id, clock, pursuit_ref, decision_source):
        self.calls.append({"project_id": project_id, "pursuit_ref": pursuit_ref,
                           "decision_source": decision_source})
        return dict(self._report)


class _DummyWorkspace:
    def ensure(self):
        return "."


class _DummyStores:
    proposals = object()
    specifications = object()
    builds = object()


def _report(*, exec_status="succeeded", kind="ok", result=None, exec_error="",
            persist_status="recorded", tool_ref="tinv_x", persist_error="",
            prereq_status="ok", prereq_error="", as_of=CLK, capability=OBS_HEALTH, provider=PROVIDER):
    if result is None and exec_status == "succeeded":
        result = {"global_state": {"counts": {"jobs": 0}}, "component_health": {"overall": "OK"}}
    return {
        "capability": capability, "provider": provider,
        "execution": {"status": exec_status, "ok": exec_status == "succeeded", "kind": kind,
                      "result": result, "error": exec_error},
        "persistence": {"status": persist_status, "tool_ref": tool_ref, "error": persist_error},
        "prerequisite": {"status": prereq_status, "error": prereq_error},
        "as_of": as_of,
    }


def _run_consult(report, *, capability=OBS_HEALTH):
    fake = _FakeObs(report)
    caps = replace(demo_capabilities(), observability=fake)
    brain = BrainAI(caps, clock=lambda: CLK)
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    outcome = brain.pursue(consult_intent(capability), context=ctx)
    return outcome, fake


# --------------------------------------------------------------------- #
# Conversion §4 — enveloppe Outcome.invocation par cas ; state TOUJOURS "active"
# --------------------------------------------------------------------- #
def test_consult_success():
    out, fake = _run_consult(_report())
    inv = out.invocation
    assert out.state == "active" and out.wait_reason is None
    assert inv["ok"] is True and inv["status"] == "succeeded"
    assert inv["provider"] == PROVIDER and inv["capability"] == OBS_HEALTH
    assert inv["tool_ref"] == "tinv_x" and inv["provenance"] == "recorded_and_referenced"
    assert inv["result"]["global_state"] == {"counts": {"jobs": 0}}
    assert inv["decision_source"] == "explicit_request" and inv["pursuit_ref"].startswith("pursuit_")
    assert out.cost_total == {"value": None, "kind": "unavailable"}
    assert out.reply == f"Consultation « {OBS_HEALTH} » effectuée."
    assert len(fake.calls) == 1 and fake.calls[0]["pursuit_ref"] == inv["pursuit_ref"]


def test_consult_unavailable_recorded_has_real_ref():
    out, _ = _run_consult(_report(exec_status="failed", kind="unavailable", result=None,
                                  exec_error="09 absent", tool_ref="tinv_fail"))
    inv = out.invocation
    assert out.state == "active"
    assert inv["ok"] is False and inv["status"] == "unavailable"
    assert inv["tool_ref"] == "tinv_fail" and inv["provenance"] == "recorded_and_referenced"
    assert inv["result"] is None and inv["error"]


def test_consult_unexpected_recorded():
    out, _ = _run_consult(_report(exec_status="failed", kind="unexpected_error", result=None,
                                  exec_error="boom", tool_ref="tinv_x"))
    inv = out.invocation
    assert inv["status"] == "unexpected_error" and inv["ok"] is False
    assert inv["tool_ref"] == "tinv_x" and inv["provenance"] == "recorded_and_referenced"


def test_consult_persistence_failure():
    out, _ = _run_consult(_report(persist_status="failed_indeterminate", tool_ref=None,
                                  persist_error="disk full"))
    inv = out.invocation
    assert inv["status"] == "persistence_failure" and inv["ok"] is False
    assert inv["tool_ref"] is None and inv["provenance"] == "write_failed_indeterminate"


def test_consult_prerequisite_failure():
    out, _ = _run_consult(_report(prereq_status="failed", prereq_error="clock", as_of=None,
                                  persist_status="not_attempted", tool_ref=None))
    inv = out.invocation
    assert inv["status"] == "prerequisite_failure" and inv["as_of"] is None
    assert inv["tool_ref"] is None and inv["provenance"] == "not_attempted"


def test_consult_invalid_envelope_a_recorded():
    # (a) exécution succeeded mais result sans les deux clés attendues ; fait enregistré → ref réelle
    out, _ = _run_consult(_report(result={"global_state": {"x": 1}}, tool_ref="tinv_x"))
    inv = out.invocation
    assert inv["status"] == "invalid_envelope" and inv["ok"] is False
    assert inv["tool_ref"] == "tinv_x" and inv["provenance"] == "recorded_and_referenced"


def test_consult_invalid_envelope_b_provider_mismatch():
    # (b) enveloppe malformée (provider ≠ cap.name) → not_guaranteed, aucun tool_ref affirmé
    out, _ = _run_consult(_report(provider="wrong"))
    inv = out.invocation
    assert inv["status"] == "invalid_envelope" and inv["provenance"] == "not_guaranteed"
    assert inv["tool_ref"] is None


def test_consult_refused_before_call_uncabled_slug():
    out, fake = _run_consult(_report(), capability=OBS_HEALTH)  # placeholder to build fake
    # slug non câblé : la capacité sert observability.health, on demande autre chose
    fake2 = _FakeObs(_report())
    caps = replace(demo_capabilities(), observability=fake2)
    brain = BrainAI(caps, clock=lambda: CLK)
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    outcome = brain.pursue(consult_intent("git.status"), context=ctx)
    inv = outcome.invocation
    assert outcome.state == "active"
    assert inv["status"] == "refused_before_call" and inv["provenance"] == "not_called"
    assert inv["tool_ref"] is None and inv["result"] is None
    assert len(fake2.calls) == 0                     # AUCUN appel de lecture (refus avant appel)


def test_consult_capability_not_injected_raises():
    caps = demo_capabilities()                        # aucune observability injectée
    brain = BrainAI(caps, clock=lambda: CLK)
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    with pytest.raises(CapabilityInjectionError):
        brain.pursue(consult_intent(OBS_HEALTH), context=ctx)


# --------------------------------------------------------------------- #
# D-1 + C-C : validation d'intention (protège aussi l'appel DIRECT au moteur)
# --------------------------------------------------------------------- #
def test_consult_intent_rejects_bad_decision_source():
    with pytest.raises(IntentError):
        consult_intent(OBS_HEALTH, decision_source="autonomous")


def test_validate_intent_rejects_any_pursuit_ref():
    bad = Intent(kind="consult", pursuit_ref="pursuit_abc",
                 payload={"capability": OBS_HEALTH, "decision_source": "explicit_request"})
    with pytest.raises(IntentError):
        validate_intent(bad)


def test_validate_intent_rejects_unexpected_payload_key():
    bad = Intent(kind="consult", payload={"capability": OBS_HEALTH, "x": 1})
    with pytest.raises(IntentError):
        validate_intent(bad)


def test_validate_intent_rejects_bad_decision_source_direct():
    bad = Intent(kind="consult", payload={"capability": OBS_HEALTH, "decision_source": "nope"})
    with pytest.raises(IntentError):
        validate_intent(bad)


# --------------------------------------------------------------------- #
# D-2 : voie rapporteuse produce_observability_report (fake 09 à espions)
# --------------------------------------------------------------------- #
class _FakeToolStore:
    def __init__(self, boom=False):
        self.records = []
        self._boom = boom

    def record(self, **kw):
        if self._boom:
            raise OSError("store indisponible")
        self.records.append(kw)
        return {"invocation_id": "tinv_fake"}


def _fake_module(calls, *, gs=None, ch=None):
    mod = types.ModuleType("scc_control_plane")

    def load_config(path=None):
        calls.append("load_config")
        return types.SimpleNamespace(as_of=CLK)

    class FakeControlPlane:
        def __init__(self, config):
            calls.append("__init__")

        def global_state(self):
            calls.append("global_state")
            return dict(gs if gs is not None else {"counts": {"jobs": 0}})

        def component_health(self):
            calls.append("component_health")
            return dict(ch if ch is not None else {"overall": "OK"})

    mod.ControlPlane = FakeControlPlane
    mod.load_config = load_config
    return mod


def _report_call(tmp_path, tool_store, *, pursuit_ref="pursuit_zzz", decision_source="explicit_request",
                 clock=lambda: CLK, monkey=None, mod=None):
    if mod is not None and monkey is not None:
        monkey.setitem(sys.modules, "scc_control_plane", mod)
    return produce_observability_report(
        capability=OBS_HEALTH, adapter=LocalControlPlaneReadAdapter(),
        control_plane_src=tmp_path, scc_root=tmp_path, tool_store=tool_store,
        project_id="proj", clock=clock, pursuit_ref=pursuit_ref, decision_source=decision_source)


def test_report_success_counts_and_context(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls)
    ts = _FakeToolStore()
    rep = _report_call(tmp_path, ts, monkey=monkeypatch, mod=mod)
    assert calls == ["load_config", "__init__", "global_state", "component_health"]  # 2 primitives 1× chacune
    assert rep["execution"]["status"] == "succeeded" and rep["execution"]["ok"] is True
    assert rep["persistence"]["status"] == "recorded" and rep["persistence"]["tool_ref"] == "tinv_fake"
    assert rep["prerequisite"]["status"] == "ok" and rep["as_of"] == CLK
    assert len(ts.records) == 1                                    # UN SEUL record
    assert ts.records[0]["pursuit_ref"] == "pursuit_zzz"          # D-3 contexte transmis
    assert ts.records[0]["decision_source"] == "explicit_request"


def test_report_execution_failure_records_real_ref(monkeypatch, tmp_path):
    ts = _FakeToolStore()
    # control_plane_src=None ⇒ ObservabilityReadError en phase exécution, MAIS fait enregistré (ref réelle)
    rep = produce_observability_report(
        capability=OBS_HEALTH, adapter=LocalControlPlaneReadAdapter(),
        control_plane_src=None, scc_root=None, tool_store=ts,
        project_id="proj", clock=lambda: CLK, pursuit_ref="pursuit_e", decision_source="explicit_request")
    assert rep["execution"]["status"] == "failed" and rep["execution"]["kind"] == "unavailable"
    assert rep["persistence"]["status"] == "recorded" and rep["persistence"]["tool_ref"] == "tinv_fake"
    assert len(ts.records) == 1


def test_report_prerequisite_failure_skips_record(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls)
    ts = _FakeToolStore()

    def boom_clock():
        raise RuntimeError("clock down")

    rep = _report_call(tmp_path, ts, clock=boom_clock, monkey=monkeypatch, mod=mod)
    assert rep["prerequisite"]["status"] == "failed" and rep["as_of"] is None
    assert rep["persistence"]["status"] == "not_attempted" and rep["persistence"]["tool_ref"] is None
    assert len(ts.records) == 0                                    # aucun record tenté


def test_report_persistence_failure_indeterminate(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls)
    ts = _FakeToolStore(boom=True)
    rep = _report_call(tmp_path, ts, monkey=monkeypatch, mod=mod)
    assert rep["persistence"]["status"] == "failed_indeterminate" and rep["persistence"]["tool_ref"] is None
    assert rep["persistence"]["error"]


# --------------------------------------------------------------------- #
# Rétrocompat de la voie historique (produce_observability_read INCHANGÉE)
# --------------------------------------------------------------------- #
def test_historical_success_dict(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls)
    monkeypatch.setitem(sys.modules, "scc_control_plane", mod)
    out = produce_observability_read(
        capability=OBS_HEALTH, adapter=LocalControlPlaneReadAdapter(),
        control_plane_src=tmp_path, scc_root=tmp_path, tool_store=_FakeToolStore(),
        project_id="proj", clock=lambda: CLK)
    assert out["ok"] is True and out["status"] == "succeeded" and out["tool_ref"] == "tinv_fake"
    assert set(out["result"].keys()) == {"global_state", "component_health"}


def test_historical_failure_raises_and_records():
    ts = _FakeToolStore()
    with pytest.raises(ObservabilityReadError):
        produce_observability_read(
            capability=OBS_HEALTH, adapter=LocalControlPlaneReadAdapter(),
            control_plane_src=None, scc_root=None, tool_store=ts,
            project_id="proj", clock=lambda: CLK)
    assert len(ts.records) == 1 and ts.records[0]["status"] == "failed"


# --------------------------------------------------------------------- #
# D-3 : id-hash inchangé ; contexte additif ; R-B : paire non unique intra-contexte
# --------------------------------------------------------------------- #
def test_id_hash_unchanged_by_context(tmp_path):
    s = ToolInvocationStore(tmp_path / "tinv.jsonl")
    a = s.record(project_id="p", tool="t", argv=["a"], cwd="", status="succeeded", exit_code=0,
                 stdout="", stderr="", timed_out=False, as_of=CLK)
    b = s.record(project_id="p", tool="t", argv=["a"], cwd="", status="succeeded", exit_code=0,
                 stdout="", stderr="", timed_out=False, as_of=CLK,
                 pursuit_ref="pursuit_x", decision_source="explicit_request")
    assert a["invocation_id"] == b["invocation_id"]               # id-hash inchangé (champs descriptifs)
    assert "pursuit_ref" not in a and a.get("decision_source") is None
    assert b["pursuit_ref"] == "pursuit_x" and b["decision_source"] == "explicit_request"


def test_correlation_pair_not_unique_intra_context(tmp_path):
    # R-B : deux faits de MÊME pursuit_ref/as_of/argv/project_id → MÊME paire (pursuit_ref, invocation_id)
    s = ToolInvocationStore(tmp_path / "tinv.jsonl")
    kw = dict(project_id="p", tool="t", argv=["a"], cwd="", status="succeeded", exit_code=0,
              stdout="", stderr="", timed_out=False, as_of=CLK, pursuit_ref="pursuit_x",
              decision_source="explicit_request")
    f1 = s.record(**kw)
    f2 = s.record(**kw)
    facts = [f for f in s.read_all()
             if f.get("pursuit_ref") == "pursuit_x" and f["invocation_id"] == f1["invocation_id"]]
    assert len(facts) == 2                                        # relecture 'plusieurs' = ambiguë, non unique
    assert f1["invocation_id"] == f2["invocation_id"]


# ===================================================================== #
# COMPLÉMENTS rev2 (R-01..R-07) — PRÉPARÉS, NON EXÉCUTÉS.
# ===================================================================== #
import io
import os
from pathlib import Path                                   # R-05 : Path était utilisé sans import (corrigé)

from scc_brainai_bootstrap.builder.brainai import _convert_observability_report, _valid_iso
from scc_brainai_bootstrap.builder.claude_code_runtime import DIAG_MAX


def _conv(report):
    return _convert_observability_report(report, capability=OBS_HEALTH, provider=PROVIDER, served=OBS_HEALTH,
                                         decision_source="explicit_request", pursuit_id="pursuit_zzz")


# --- R-01 : validation stricte de forme AVANT priorité R-A ---
def test_convert_rejects_ok_status_mismatch():
    r = _report(); r["execution"]["ok"] = False           # status=succeeded mais ok=false
    inv = _conv(r)
    assert inv["status"] == "invalid_envelope" and inv["provenance"] == "not_guaranteed" and inv["ok"] is False


def test_convert_rejects_ok_absent():
    r = _report(); del r["execution"]["ok"]
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_unknown_exec_status():
    r = _report(); r["execution"]["status"] = "weird"; r["execution"]["ok"] = False
    assert _conv(r)["provenance"] == "not_guaranteed"


def test_convert_rejects_unknown_kind():
    r = _report(exec_status="failed", kind="???", tool_ref="t"); r["execution"]["ok"] = False
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_prereq_failed_with_recorded():
    r = _report(prereq_status="failed", as_of=None)       # persistance reste recorded → combinaison interdite
    assert _conv(r)["status"] == "invalid_envelope" and _conv(r)["provenance"] == "not_guaranteed"


def test_convert_rejects_recorded_without_tool_ref():
    r = _report(tool_ref=None)                            # recorded sans tool_ref réel
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_non_str_error():
    r = _report(); r["execution"]["error"] = 123
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_tool_ref_without_recorded():
    r = _report(persist_status="failed_indeterminate", tool_ref="tinv_x")   # tool_ref non nul sans recorded
    assert _conv(r)["status"] == "invalid_envelope"


# --- R-02 : horodatage ISO ---
def test_valid_iso_helper():
    assert _valid_iso(CLK) is True
    assert _valid_iso("not-an-iso-date") is False
    assert _valid_iso("") is False and _valid_iso(None) is False and _valid_iso(123) is False


def test_report_non_iso_clock_fails_prereq(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls)
    ts = _FakeToolStore()
    rep = _report_call(tmp_path, ts, clock=lambda: "not-iso", monkey=monkeypatch, mod=mod)
    assert rep["prerequisite"]["status"] == "failed" and rep["as_of"] is None
    assert rep["persistence"]["status"] == "not_attempted" and len(ts.records) == 0     # record EMPÊCHÉ


def test_consult_raises_on_non_iso_turn_clock():
    fake = _FakeObs(_report())
    caps = replace(demo_capabilities(), observability=fake)
    brain = BrainAI(caps, clock=lambda: "not-iso")        # horloge de tour invalide ⇒ panne technique
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    with pytest.raises(RuntimeError):
        brain.pursue(consult_intent(OBS_HEALTH), context=ctx)
    assert len(fake.calls) == 0                            # aucune lecture tentée


def test_consult_refus_as_of_null():
    fake = _FakeObs(_report())
    caps = replace(demo_capabilities(), observability=fake)
    brain = BrainAI(caps, clock=lambda: CLK)
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    out = brain.pursue(consult_intent("git.status"), context=ctx)
    assert out.invocation["as_of"] is None                # R-A : refus avant appel ⇒ as_of null
    assert out.as_of == CLK                               # instant de tour conservé, distinct


def test_consult_success_outcome_as_of_is_turn():
    out, _ = _run_consult(_report())
    assert out.as_of == CLK and out.invocation["as_of"] == CLK   # tour vs invocation ; ici même horloge figée


# --- R-03 : diagnostics bornés / typés ---
def test_convert_bounds_combined_error():
    long = "x" * (DIAG_MAX * 2)
    r = _report(persist_status="failed_indeterminate", tool_ref=None, persist_error=long)
    r["execution"]["status"] = "failed"; r["execution"]["ok"] = False; r["execution"]["kind"] = "unavailable"
    r["execution"]["error"] = "y" * (DIAG_MAX * 2)
    inv = _conv(r)
    assert inv["status"] == "persistence_failure"
    assert len(inv["error"]) <= DIAG_MAX                  # la SOMME des deux causes est bornée


def test_consult_refus_error_bounded():
    fake = _FakeObs(_report())
    caps = replace(demo_capabilities(), observability=fake)
    brain = BrainAI(caps, clock=lambda: CLK)
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    out = brain.pursue(consult_intent("z" * (DIAG_MAX * 2)), context=ctx)
    assert out.invocation["status"] == "refused_before_call"
    assert len(out.invocation["error"]) <= DIAG_MAX


# --- R-04 : store à signature strictement historique (sans **kwargs) ---
class _StrictStore:
    """Store injecté conforme à l'ANCIENNE signature (aucun pursuit_ref/decision_source, aucun **kwargs)."""

    def __init__(self):
        self.records = []

    def record(self, *, project_id, tool, argv, cwd, status, exit_code, stdout, stderr, timed_out, as_of):
        self.records.append({"as_of": as_of})
        return {"invocation_id": "tinv_strict"}


def test_historical_read_strict_store_no_context(monkeypatch, tmp_path):
    calls = []
    mod = _fake_module(calls)
    monkeypatch.setitem(sys.modules, "scc_control_plane", mod)
    ts = _StrictStore()
    out = produce_observability_read(                     # voie HISTORIQUE, SANS contexte ⇒ pas de kwargs supplémentaires
        capability=OBS_HEALTH, adapter=LocalControlPlaneReadAdapter(),
        control_plane_src=tmp_path, scc_root=tmp_path, tool_store=ts,
        project_id="proj", clock=lambda: CLK)
    assert out["ok"] is True and len(ts.records) == 1     # aucun TypeError, un seul enregistrement


# --- R-05 : intégration HTTP + composition + chaîne complète + relecture indépendante ---
from brainai_app import server as _srv


class _Handler(_srv._Handler):                            # exerce le vrai do_POST sans socket ni réseau
    def __init__(self, body: bytes, token):
        self.responses = []
        self.path = "/v1/pursue"
        self.headers = {"Content-Length": str(len(body)), "X-BrainAI-Token": token}
        self.rfile = io.BytesIO(body)

    def _send_json(self, code, obj):
        self.responses.append((code, obj))


def _post(payload, *, token=None):
    import json as _json
    body = _json.dumps(payload).encode("utf-8")
    h = _Handler(body, token if token is not None else _srv.SESSION_TOKEN)
    h.do_POST()
    return h.responses[-1]


def _hermetic_env(monkeypatch, tmp_path):
    """09 factice + control_plane_src=tmp (dir réel) + racine d'état de test isolée."""
    calls = []
    monkeypatch.setitem(sys.modules, "scc_control_plane", _fake_module(calls))
    from scc_brainai_bootstrap.core.config import BrainAIConfig
    monkeypatch.setattr(BrainAIConfig, "control_plane_src", property(lambda self: tmp_path), raising=True)
    monkeypatch.setenv("BRAINAI_STATE_ROOT", str(tmp_path / "state"))
    return calls


def _isolate_session_cache(monkeypatch):
    """R07-REV6-C : isole le cache de session GLOBAL ``_SESSIONS`` (dict neuf par test), pour que les assertions sur
    ce cache ne dépendent JAMAIS de l'ordre d'exécution d'autres tests utilisant la même horloge figée (même pid)."""
    import brainai_app.composition as _comp
    monkeypatch.setattr(_comp, "_SESSIONS", {}, raising=True)


def test_http_consult_success_and_provenance_reread(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    code, env = _post({"kind": "consult", "mode": "real", "capability": OBS_HEALTH})
    assert code == 200
    data = env["data"]
    assert data["invocation"]["ok"] is True and data["invocation"]["status"] == "succeeded"
    assert data["finalization"]["settled"] is True and data["finalization"]["provenance_durable"] is True
    pid = data["invocation"]["pursuit_ref"]
    # relecture INDÉPENDANTE du cache mémoire : nouveau store sur le répertoire déterministe stabilisé
    tinv = Path(os.environ["BRAINAI_STATE_ROOT"]) / "pursuits" / pid / "tinv.jsonl"
    facts = ToolInvocationStore(tinv).read_all()
    match = [f for f in facts if f.get("pursuit_ref") == pid]
    assert len(match) == 1 and match[0]["decision_source"] == "explicit_request" and match[0]["status"] == "succeeded"
    # R-05 : corrélation par la PAIRE complète — invocation_id relu == tool_ref retourné
    assert match[0]["invocation_id"] == data["invocation"]["tool_ref"]


def test_http_consult_bad_decision_source_400(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH, "decision_source": "autonomous"})
    assert code == 400


def test_http_consult_pursuit_ref_refused_400(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH, "pursuit_ref": "pursuit_x"})
    assert code == 400


def test_http_consult_unexpected_key_400(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH, "surprise": 1})
    assert code == 400


def test_http_consult_no_token_401(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH}, token="wrong")
    assert code == 401


def test_http_consult_technical_error_500(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    sentinel = "SENTINELLE_PRIVEE_RT_zzq"                  # DISTINCTE de tout message public du serveur
    monkeypatch.setattr(_srv, "consult", lambda *a, **k: (_ for _ in ()).throw(RuntimeError(sentinel)))
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH})
    assert code == 500
    assert env["error"] == "erreur interne"               # message public constant (R-03)
    assert sentinel not in str(env)                        # l'exception privée n'est jamais divulguée


def test_composition_consult_projection(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    from brainai_app.composition import consult as _consult_fn
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["invocation"]["ok"] is True and vm["finalization"]["settled"] is True
    assert "conversation" in vm and "pursuit" in vm      # projection to_viewmodel complète


# --- R-07 : collision de destination — transit conservé, aucun journal perdu, cache non réaffecté ---
import datetime as _dtmod


class _FrozenDT:
    """Fige l'horloge du moteur : ``_system_clock`` fait ``datetime.now(tz).isoformat()``. En remplaçant le nom
    ``datetime`` du module moteur par cette classe, ``now()`` renvoie toujours CLK et ``fromisoformat`` (utilisé par
    ``_valid_iso``) délègue au vrai ``datetime`` — l'injection est donc **effectivement consommée**."""

    @classmethod
    def now(cls, tz=None):
        return _dtmod.datetime.fromisoformat(CLK)

    @staticmethod
    def fromisoformat(s):
        return _dtmod.datetime.fromisoformat(s)


def test_collision_keeps_transit_and_new_journal(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    _isolate_session_cache(monkeypatch)                       # cache isolé : assertion indépendante de l'ordre d'exécution
    import scc_brainai_bootstrap.builder.brainai as _b
    from brainai_app.composition import consult as _consult_fn
    import brainai_app.composition as _comp
    # injection EFFECTIVE au point consommé : `_system_clock` (défaut du constructeur) lit `datetime` du module moteur
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)
    vm1 = _consult_fn(OBS_HEALTH, mode="real")
    vm2 = _consult_fn(OBS_HEALTH, mode="real")
    pid = vm1["invocation"]["pursuit_ref"]
    # PRÉALABLE explicite : les deux identités sont bien identiques (sinon le test de collision n'a pas de sens)
    assert pid == vm2["invocation"]["pursuit_ref"]
    assert vm1["finalization"]["settled"] is True and vm1["finalization"]["provenance_durable"] is True
    assert vm2["finalization"]["settled"] is False and vm2["finalization"]["provenance_durable"] is False
    settled = Path(os.environ["BRAINAI_STATE_ROOT"]) / "pursuits" / pid / "tinv.jsonl"
    assert settled.exists()                                # 1er journal déterministe NON supprimé
    transit = Path(vm2["finalization"]["transit_kept"]) / "tinv.jsonl"
    assert transit.exists()                               # 2e journal CONSERVÉ dans le transit (aucune perte)
    # cache d'identité NON réaffecté : il pointe toujours le chemin déterministe de la 1ère consultation
    assert _comp._SESSIONS.get(pid) == (Path(os.environ["BRAINAI_STATE_ROOT"]) / "pursuits" / pid)


# --- Corrélation inter-contextes : deux Pursuits distinctes, même invocation_id ---
def test_correlation_two_contexts_same_id_not_mixed(tmp_path):
    kw = dict(project_id="p", tool="t", argv=["a"], cwd="", status="succeeded", exit_code=0,
              stdout="", stderr="", timed_out=False, as_of=CLK, decision_source="explicit_request")
    sA = ToolInvocationStore(tmp_path / "A" / "tinv.jsonl")
    sB = ToolInvocationStore(tmp_path / "B" / "tinv.jsonl")
    fa = sA.record(pursuit_ref="pursuit_A", **kw)
    fb = sB.record(pursuit_ref="pursuit_B", **kw)
    assert fa["invocation_id"] == fb["invocation_id"]     # même id (mêmes project/argv/as_of) — PAS une corruption
    # corrélation par (pursuit_ref, invocation_id) dans le contexte : 1 dans A, 0 pour B dans A
    inA = [f for f in sA.read_all() if f.get("pursuit_ref") == "pursuit_A" and f["invocation_id"] == fa["invocation_id"]]
    crossA = [f for f in sA.read_all() if f.get("pursuit_ref") == "pursuit_B"]
    assert len(inA) == 1 and len(crossA) == 0            # aucun mélange inter-contextes


# ===================================================================== #
# COMPLÉMENTS rev3 (R-01 non hachable/clés absentes ; R-03 deux causes/reply ; R-05 compteurs/instant de tour).
# PRÉPARÉS, NON EXÉCUTÉS.
# ===================================================================== #

# --- R-01 : valeurs non hachables et clés absentes → refus gouverné (jamais TypeError/KeyError) ---
def test_convert_rejects_unhashable_status():
    r = _report(); r["execution"]["status"] = []          # non hachable : ne doit PAS lever à l'appartenance au set
    inv = _conv(r)
    assert inv["status"] == "invalid_envelope" and inv["provenance"] == "not_guaranteed"


def test_convert_rejects_unhashable_kind():
    r = _report(exec_status="failed", tool_ref="t"); r["execution"]["ok"] = False; r["execution"]["kind"] = {"x": 1}
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_missing_result_key():
    r = _report(exec_status="failed", kind="unavailable", tool_ref="t"); r["execution"]["ok"] = False
    del r["execution"]["result"]                          # clé requise absente → refus (pas de KeyError à l'indexation)
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_missing_as_of_key():
    r = _report(); del r["as_of"]
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_missing_tool_ref_key():
    r = _report(); del r["persistence"]["tool_ref"]
    assert _conv(r)["status"] == "invalid_envelope"


def test_convert_rejects_missing_prereq_error_key():
    r = _report(); del r["prerequisite"]["error"]
    assert _conv(r)["status"] == "invalid_envelope"


# --- R-03 : deux causes toutes deux identifiées ; reply bornée sans slug brut ---
def test_convert_two_causes_both_identified_persist():
    r = _report(persist_status="failed_indeterminate", tool_ref=None, persist_error="PERSISTERR")
    r["execution"]["status"] = "failed"; r["execution"]["ok"] = False; r["execution"]["kind"] = "unavailable"
    r["execution"]["error"] = "EXECERR"
    inv = _conv(r)
    assert inv["status"] == "persistence_failure"
    assert "persistance" in inv["error"] and "exécution" in inv["error"]   # les deux phases identifiées
    assert len(inv["error"]) <= DIAG_MAX


def test_convert_two_causes_both_identified_prereq():
    r = _report(prereq_status="failed", as_of=None, persist_status="not_attempted", tool_ref=None,
                prereq_error="CLOCKERR")
    r["execution"]["status"] = "failed"; r["execution"]["ok"] = False; r["execution"]["kind"] = "unexpected_error"
    r["execution"]["error"] = "EXECERR2"
    inv = _conv(r)
    assert inv["status"] == "prerequisite_failure"
    assert "prérequis" in inv["error"] and "exécution" in inv["error"]
    assert len(inv["error"]) <= DIAG_MAX


def test_consult_refus_reply_bounded_no_raw_slug():
    long_slug = "z" * (DIAG_MAX * 2)
    fake = _FakeObs(_report())
    caps = replace(demo_capabilities(), observability=fake)
    brain = BrainAI(caps, clock=lambda: CLK)
    ctx = RunContext(budget_usd=2.0, project_id="session", workspace=_DummyWorkspace(), stores=_DummyStores())
    out = brain.pursue(consult_intent(long_slug), context=ctx)
    assert out.invocation["status"] == "refused_before_call"
    assert len(out.reply) <= DIAG_MAX + 60                # reply = libellé fixe + slug borné (≤ DIAG_MAX)
    assert long_slug not in out.reply                     # jamais le slug brut entier réémis


# --- R-02/R-05 : instant de tour conservé distinct sur échec de prérequis (S4) ---
def test_consult_prereq_failure_keeps_turn_instant():
    r = _report(prereq_status="failed", as_of=None, persist_status="not_attempted", tool_ref=None)
    out, _ = _run_consult(r)
    assert out.invocation["status"] == "prerequisite_failure" and out.invocation["as_of"] is None
    assert out.as_of == CLK                              # instant de tour VALIDE conservé, distinct de l'invocation


# --- R-05 : erreur réelle de primitive suivie d'un record en échec ; compteur incrémenté AVANT la levée ---
class _CountingBoomStore:
    def __init__(self):
        self.attempts = 0

    def record(self, **kw):
        self.attempts += 1                               # incrémenté AVANT la levée (compteur de tentatives réel)
        raise OSError("store down")


def _fake_module_boom_primitive(calls):
    mod = types.ModuleType("scc_control_plane")

    def load_config(path=None):
        calls.append("load_config")
        return types.SimpleNamespace(as_of=CLK)

    class FCP:
        def __init__(self, config):
            calls.append("__init__")

        def global_state(self):
            calls.append("global_state")
            return {"x": 1}

        def component_health(self):
            calls.append("component_health")
            raise RuntimeError("primitive down")         # échec RÉEL d'une primitive

    mod.ControlPlane = FCP
    mod.load_config = load_config
    return mod


def test_report_primitive_fail_then_persist_fail_counts(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setitem(sys.modules, "scc_control_plane", _fake_module_boom_primitive(calls))
    store = _CountingBoomStore()
    rep = produce_observability_report(
        capability=OBS_HEALTH, adapter=LocalControlPlaneReadAdapter(),
        control_plane_src=tmp_path, scc_root=tmp_path, tool_store=store,
        project_id="p", clock=lambda: CLK, pursuit_ref="pursuit_e", decision_source="explicit_request")
    assert "component_health" in calls                   # primitive réellement tentée
    assert rep["execution"]["status"] == "failed" and rep["execution"]["kind"] == "unexpected_error"
    assert rep["persistence"]["status"] == "failed_indeterminate"
    assert store.attempts == 1                            # UNE tentative d'écriture comptée avant la levée


# ===================================================================== #
# COMPLÉMENTS rev4 (R-07 non-remplacement vide/tardif/panne ; R-05 horloge séquencée, deux causes longues,
# modes+non-activation, branches HTTP). PRÉPARÉS, NON EXÉCUTÉS.
# ===================================================================== #
import os as _os_mod

from scc_brainai_bootstrap.builder.brainai import new_pursuit_id, consult_intent as _ci


def _consult_pid():
    """Identité déterministe d'une consultation à l'horloge figée CLK (même formule que le moteur)."""
    return new_pursuit_id(_ci(OBS_HEALTH), "session", CLK)


# --- R-07 : destination VIDE pré-existante NON remplacée (os.rename l'aurait remplacée) ---
def test_finalization_refuses_empty_destination(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import scc_brainai_bootstrap.builder.brainai as _b
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)   # horloge figée ⇒ pid déterministe
    pid = _consult_pid()
    empty_target = Path(os.environ["BRAINAI_STATE_ROOT"]) / "pursuits" / pid
    empty_target.mkdir(parents=True)                               # destination VIDE pré-existante
    assert empty_target.exists() and not any(empty_target.iterdir())
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["finalization"]["settled"] is False and vm["finalization"]["reason"] == "destination_existante"
    assert vm["finalization"]["provenance_durable"] is False
    # destination vide NON remplacée (toujours vide) ; transit conservé avec son journal
    assert not any(empty_target.iterdir())
    assert (Path(vm["finalization"]["transit_kept"]) / "tinv.jsonl").exists()


# --- R-07 : collision tardive simulée (mkdir lève FileExistsError « à la frontière ») ---
def test_finalization_late_collision(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import scc_brainai_bootstrap.builder.brainai as _b
    import brainai_app.composition as _comp
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)
    real_mkdir = _os_mod.mkdir

    def boom_mkdir(path, *a, **k):
        if str(path).endswith(_consult_pid()):
            raise FileExistsError("apparue à la frontière")
        return real_mkdir(path, *a, **k)

    monkeypatch.setattr(_comp.os, "mkdir", boom_mkdir, raising=True)
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["finalization"]["settled"] is False and vm["finalization"]["reason"] == "destination_existante"
    assert (Path(vm["finalization"]["transit_kept"]) / "tinv.jsonl").exists()   # transit conservé


# --- R-07 : PREMIÈRE panne (le lien exclusif échoue avant tout transfert) → finalisation_partielle ---
def test_finalization_move_failure_partial(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    _isolate_session_cache(monkeypatch)
    import scc_brainai_bootstrap.builder.brainai as _b
    import brainai_app.composition as _comp
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)
    link_calls = {"n": 0}

    def boom_link(*a, **k):
        link_calls["n"] += 1                             # R07-C : compteur prouvant l'injection ATTEINTE
        raise OSError("lien impossible")                 # panne technique (pas une collision : pas FileExistsError)

    # R07-C : la garde de disponibilité (_FOLLOW_OPS capturé à l'import) n'est PAS faussée par ce monkeypatch ;
    # l'injection atteint donc le vrai point de publication (plus de faux "mecanisme_indisponible").
    monkeypatch.setattr(_comp.os, "link", boom_link, raising=True)   # revendication mkdir ok, publication échoue au 1er lien
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["finalization"]["settled"] is False and vm["finalization"]["reason"] == "finalisation_partielle"
    assert vm["finalization"]["provenance_durable"] is False
    assert link_calls["n"] == 1                          # injection atteinte EXACTEMENT une fois
    assert vm["finalization"]["published"] == []         # aucune entrée publiée : journal ENCORE dans le transit
    assert (Path(vm["finalization"]["transit_kept"]) / "tinv.jsonl").exists()   # preuves conservées, aucune perte
    # cette panne survient AVANT tout transfert : ce n'est PAS une preuve de toutes les pannes partielles
    assert (Path(vm["finalization"]["target"]) / "tinv.jsonl").exists() is False


# --- R-07/R-05 : provenance non durable sur report échoué/persistance indéterminée (niveau moteur) ---
def test_engine_provenance_values_for_failures():
    # persistance indéterminée → write_failed_indeterminate (pas de durabilité)
    out_p, _ = _run_consult(_report(persist_status="failed_indeterminate", tool_ref=None))
    assert out_p.invocation["provenance"] == "write_failed_indeterminate" and out_p.invocation["ok"] is False
    # prérequis échoué → not_attempted
    out_r, _ = _run_consult(_report(prereq_status="failed", as_of=None, persist_status="not_attempted", tool_ref=None))
    assert out_r.invocation["provenance"] == "not_attempted"


# --- R-05 : horloge séquencée réelle — tour valide puis S4 échouée (chaîne moteur→handle→rapport) ---
class _SeqDT:
    """`now()` : 1er appel valide (CLK), 2e appel lève (S4). `fromisoformat` délégué au vrai datetime."""
    calls = 0

    @classmethod
    def now(cls, tz=None):
        cls.calls += 1
        if cls.calls == 1:
            return _dtmod.datetime.fromisoformat(CLK)
        raise RuntimeError("S4 down")

    @staticmethod
    def fromisoformat(s):
        return _dtmod.datetime.fromisoformat(s)


def test_sequenced_clock_turn_valid_then_s4_fails(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import scc_brainai_bootstrap.builder.brainai as _b
    from brainai_app.composition import consult as _consult_fn
    _SeqDT.calls = 0
    monkeypatch.setattr(_b, "datetime", _SeqDT, raising=True)     # tour(1) valide, S4(2) lève
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["invocation"]["status"] == "prerequisite_failure"  # S4 échouée sur la chaîne réelle
    assert _SeqDT.calls == 2                                      # tour + S4 ; AUCUN 3e appel de secours
    pid = vm["invocation"]["pursuit_ref"]
    # aucun record après panne S4 (aucun fait persisté sous la destination ni le transit)
    det = Path(os.environ["BRAINAI_STATE_ROOT"]) / "pursuits" / pid / "tinv.jsonl"
    assert not det.exists()


# --- R-03/R-05 : deux causes LONGUES, deux marqueurs distincts conservés, borne respectée ---
def test_convert_two_long_causes_both_preserved():
    r = _report(persist_status="failed_indeterminate", tool_ref=None, persist_error="A" * (DIAG_MAX * 2))
    r["execution"]["status"] = "failed"; r["execution"]["ok"] = False; r["execution"]["kind"] = "unavailable"
    r["execution"]["error"] = "B" * (DIAG_MAX * 2)
    inv = _conv(r)
    assert inv["status"] == "persistence_failure" and len(inv["error"]) <= DIAG_MAX
    assert "persistance" in inv["error"] and "exécution" in inv["error"]   # deux libellés
    assert "persistance: [REDACTED-HEX]" in inv["error"] and "exécution: [REDACTED-HEX]" in inv["error"]


# --- R-05 : intégration — mode demo, non-activation des facultés cognitives/construction ---
def test_composition_consult_demo_mode_real_data_no_cognition(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import brainai_app.providers as _prov
    from brainai_app.composition import consult as _consult_fn
    # non-activation : si consult résolvait les capacités réelles (cognitives/builder), ceci lèverait
    monkeypatch.setattr(_prov, "real_capabilities",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("real_capabilities appelé")),
                        raising=True)
    vm = _consult_fn(OBS_HEALTH, mode="demo")                     # mode demo : données réelles (lecture locale)
    assert vm["invocation"]["ok"] is True and vm["invocation"]["status"] == "succeeded"
    assert vm["pursuit"]["mode"] == "demo"                        # R05-B : champ de mode RÉEL (projection to_viewmodel), plus d'échappatoire


# --- R-05 : branches HTTP explicites (IntentError→400 ; capacité non injectée→500 ; LookupError→500) ---
def test_http_consult_intent_error_400(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    monkeypatch.setattr(_srv, "consult",
                        lambda *a, **k: (_ for _ in ()).throw(IntentError("forme invalide")), raising=True)
    code, _env = _post({"kind": "consult", "capability": OBS_HEALTH})
    assert code == 400


def test_http_consult_capability_not_injected_500(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    # R05-A : sentinelle PRIVÉE distincte du message public (server.py L184 renvoie une constante contenant
    # « non injectée » ; l'ancienne assertion interdisait cette sous-chaîne et était donc contradictoire).
    sentinel = "SENTINELLE_PRIVEE_CAPINJ_zzq"
    monkeypatch.setattr(_srv, "consult",
                        lambda *a, **k: (_ for _ in ()).throw(CapabilityInjectionError(sentinel)), raising=True)
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH})
    assert code == 500
    assert env["error"] == "erreur interne (capacité non injectée)"   # message public constant (serveur R-03 intact)
    assert sentinel not in str(env)                              # l'exception privée n'est jamais divulguée


def test_http_consult_lookup_error_500(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    sentinel = "SENTINELLE_PRIVEE_LOOKUP_zzq"                    # même discipline : privé ≠ public
    monkeypatch.setattr(_srv, "consult",
                        lambda *a, **k: (_ for _ in ()).throw(LookupError(sentinel)), raising=True)
    code, env = _post({"kind": "consult", "capability": OBS_HEALTH})
    assert code == 500
    assert env["error"] == "erreur interne (résolution de capacité)"   # message public constant
    assert sentinel not in str(env)


# ===================================================================== #
# COMPLÉMENTS rev5 (R-07 publication exclusive par liens ; R-05 mode réel, non-activation, chaîne record,
# emplacements du journal, alias, collision au transfert, panne tardive ; deux causes longues exec+prérequis).
# PRÉPARÉS, NON EXÉCUTÉS. Les tests directs exercent le VRAI helper `_finalize_consult_transit` sur fixtures
# synthétiques confinées (aucun 09 réel, aucune valeur matérielle).
# ===================================================================== #

def _mk_transit(base, name=".staging-r5"):
    """Fabrique un transit synthétique confiné : un journal + un sous-répertoire avec un fichier."""
    root = base / name
    root.mkdir()
    (root / "tinv.jsonl").write_text('{"invocation_id":"tinv_x"}\n', encoding="utf-8")
    sub = root / "exec"
    sub.mkdir()
    (sub / "w.txt").write_text("x", encoding="utf-8")
    return root


# --- R-07 : publication EXCLUSIVE réussie (liens/mkdir relatifs aux descripteurs), transit vidé ---
def test_publish_exclusive_settles_and_moves(tmp_path):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_ok"
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is True and fin["reason"] is None
    assert (target / "tinv.jsonl").exists() and (target / "exec" / "w.txt").exists()
    assert not root.exists()                                     # transit vidé puis rmdir (jamais rmtree)
    assert set(fin["published"]) == {"tinv.jsonl", "exec/w.txt"}


# --- R-07 : destination existante VIDE → refus (jamais de remplacement) ---
def test_publish_refuses_existing_empty_destination(tmp_path):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_empty"
    target.mkdir()                                              # destination VIDE pré-existante
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "destination_existante"
    assert (root / "tinv.jsonl").exists()                      # transit conservé, non fusionné
    assert not any(target.iterdir())                           # destination vide NON remplie


# --- R-07 : destination NON vide → refus, sentinelle destination conservée intacte ---
def test_publish_refuses_nonempty_destination_sentinel_preserved(tmp_path):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_nonempty"
    target.mkdir()
    (target / "SENTINEL").write_text("keep-me", encoding="utf-8")
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "destination_existante"
    assert (target / "SENTINEL").read_text(encoding="utf-8") == "keep-me"   # jamais fusionné/écrasé
    assert (root / "tinv.jsonl").exists()


# --- R07-B : target lien symbolique (alias du transit) → jamais une finalisation ---
def test_publish_refuses_symlink_target_alias(tmp_path):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_alias"
    _os_mod.symlink(str(root), str(target))                    # target = lien symbolique vers le transit
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "cible_lien_symbolique"
    assert (root / "tinv.jsonl").exists()                      # transit intact ; resolve()==resolve() n'est PAS un settle


# --- R-07 : entrée de type non admis (lien symbolique) dans le transit → refus explicite ---
def test_publish_refuses_symlink_entry_type_inattendu(tmp_path):
    import brainai_app.composition as _comp
    root = tmp_path / ".staging-typ"
    root.mkdir()
    _os_mod.symlink(str(tmp_path / "ailleurs"), str(root / "alink"))   # jamais produit par consult ⇒ refus
    target = tmp_path / "pursuit_typ"
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "type_inattendu"
    assert (root / "alink").is_symlink()                       # lien NON suivi, NON recopié


# --- R-07 : collision AU TRANSFERT (le lien exclusif lève FileExistsError) → distincte, jamais de remplacement ---
def test_publish_collision_at_transfer(tmp_path, monkeypatch):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_coll"
    link_calls = {"n": 0}

    def boom_link(*a, **k):
        link_calls["n"] += 1                                   # R07-C : injection ATTEINTE (garde non faussée)
        raise FileExistsError("entrée apparue à la frontière")

    monkeypatch.setattr(_comp.os, "link", boom_link, raising=True)
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "collision_au_transfert"
    assert link_calls["n"] == 1                                # atteinte exactement une fois (pas de mecanisme_indisponible)
    assert (root / "tinv.jsonl").exists()                      # aucune donnée perdue


# --- R-07 : panne technique de revendication (mkdir OSError non-FileExists) → finalisation_impossible (distincte) ---
def test_publish_claim_technical_failure_distinct(tmp_path, monkeypatch):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_tech"

    def boom_mkdir(*a, **k):
        raise OSError("droits/FS")                            # jamais FileExistsError ⇒ distincte d'une collision

    monkeypatch.setattr(_comp.os, "mkdir", boom_mkdir, raising=True)
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "finalisation_impossible"
    assert (root / "tinv.jsonl").exists()


# --- R-07/R-05 : panne TARDIVE après un transfert réussi → journal SOUS target, honnêteté d'emplacement ---
def test_finalization_late_after_transfer_journal_in_target(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    _isolate_session_cache(monkeypatch)                       # assertion cache indépendante de l'ordre d'exécution
    import scc_brainai_bootstrap.builder.brainai as _b
    import brainai_app.composition as _comp
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)

    def boom_rmdir(*a, **k):
        raise OSError("transit non supprimable")             # panne APRÈS que le contenu a été publié

    monkeypatch.setattr(_comp.os, "rmdir", boom_rmdir, raising=True)
    vm = _consult_fn(OBS_HEALTH, mode="real")
    fin = vm["finalization"]
    assert fin["settled"] is False and fin["reason"] == "transit_non_supprimable"
    assert fin["provenance_durable"] is False
    assert "tinv.jsonl" in fin["published"]                    # journal réellement DÉPLACÉ
    assert (Path(fin["target"]) / "tinv.jsonl").exists()      # emplacement réel du journal : la DESTINATION
    assert not (Path(fin["transit_kept"]) / "tinv.jsonl").exists()   # honnêteté : plus sous transit_kept
    pid = vm["invocation"]["pursuit_ref"]
    assert _comp._SESSIONS.get(pid) is None                    # cache NON réaffecté (settle non affirmé)


# --- R-05 : chaîne horloge séquencée — AUCUNE tentative de record après panne S4 (espion réel) ---
def test_sequenced_clock_no_record_attempt_after_s4(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import scc_brainai_bootstrap.builder.brainai as _b
    from brainai_app.composition import consult as _consult_fn
    _SeqDT.calls = 0
    monkeypatch.setattr(_b, "datetime", _SeqDT, raising=True)   # tour(1) valide, S4(2) lève
    attempts = {"n": 0}
    real_record = ToolInvocationStore.record

    def counting_record(self, **kw):
        attempts["n"] += 1                                     # incrémenté AVANT toute levée éventuelle
        return real_record(self, **kw)

    monkeypatch.setattr(ToolInvocationStore, "record", counting_record, raising=True)
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["invocation"]["status"] == "prerequisite_failure"
    assert vm["invocation"]["as_of"] is None                   # invocation sans horodatage
    assert attempts["n"] == 0                                  # ZÉRO tentative d'écriture (pas seulement fichier absent)
    assert _SeqDT.calls == 2                                   # tour + S4 ; aucun 3e appel de secours
    assert vm["finalization"]["provenance_durable"] is False   # jamais de durabilité affirmée


# --- R-05 : refus avant appel (sans fait) → jamais provenance durable au niveau composition ---
def test_composition_refused_before_call_not_durable(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import scc_brainai_bootstrap.builder.brainai as _b
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)
    vm = _consult_fn("git.status", mode="real")               # slug non câblé ⇒ refused_before_call, aucun fait
    assert vm["invocation"]["status"] == "refused_before_call"
    assert vm["finalization"]["provenance_durable"] is False   # refus sans fait : jamais durable
    # la finalisation peut settle (transit publié, éventuellement vide) mais SANS durabilité affirmée
    assert vm["finalization"]["settled"] in (True, False)


# --- R-05 : persistance indéterminée (record lève) → jamais provenance durable au niveau composition ---
def test_composition_persistence_indeterminate_not_durable(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import scc_brainai_bootstrap.builder.brainai as _b
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)

    def boom_record(self, **kw):
        raise OSError("store indisponible")                   # persistance indéterminée

    monkeypatch.setattr(ToolInvocationStore, "record", boom_record, raising=True)
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["invocation"]["status"] == "persistence_failure"
    assert vm["invocation"]["provenance"] == "write_failed_indeterminate"
    assert vm["finalization"]["provenance_durable"] is False   # absence de fait ⇒ pas de durabilité


# --- R-05 : intégration mode RÉEL — champ de mode réel + non-activation des facultés cognitives ---
def test_composition_consult_real_mode_field_and_no_cognition(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import brainai_app.providers as _prov
    from brainai_app.composition import consult as _consult_fn
    # non-activation : consult ne doit JAMAIS résoudre les capacités réelles cognitives/builder (même en mode real)
    monkeypatch.setattr(_prov, "real_capabilities",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("real_capabilities appelé")),
                        raising=True)
    vm = _consult_fn(OBS_HEALTH, mode="real")
    assert vm["invocation"]["ok"] is True and vm["invocation"]["status"] == "succeeded"
    assert vm["pursuit"]["mode"] == "real"                     # champ de mode RÉEL reflété


# --- R-05 : non-activation au POINT consommé — propose() des facultés démo jamais appelé par consult ---
def test_consult_cognitive_propose_never_called(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    import brainai_app.composition as _comp
    from brainai_app.composition import consult as _consult_fn
    called = {"n": 0}
    orig = _comp.demo_capabilities

    def spied():
        caps = orig()
        for name in ("understanding", "specification", "build", "conversation"):
            cap = getattr(caps, name, None)
            if cap is not None and hasattr(cap, "propose"):
                def boom(*a, **k):
                    called["n"] += 1
                    raise AssertionError("faculté cognitive/construction appelée par consult")
                monkeypatch.setattr(cap, "propose", boom, raising=False)
        return caps

    monkeypatch.setattr(_comp, "demo_capabilities", spied, raising=True)
    for mode in ("demo", "real"):
        vm = _consult_fn(OBS_HEALTH, mode=mode)
        assert vm["invocation"]["status"] == "succeeded"
    assert called["n"] == 0                                    # aucune faculté cognitive/construction consommée


# --- R-03/R-05 : deux causes LONGUES exécution+PRÉREQUIS, deux marqueurs distincts, borne globale ---
def test_convert_two_long_causes_exec_prereq():
    r = _report(prereq_status="failed", as_of=None, persist_status="not_attempted", tool_ref=None,
                prereq_error="P" * (DIAG_MAX * 2))
    r["execution"]["status"] = "failed"; r["execution"]["ok"] = False; r["execution"]["kind"] = "unexpected_error"
    r["execution"]["error"] = "E" * (DIAG_MAX * 2)
    inv = _conv(r)
    assert inv["status"] == "prerequisite_failure" and len(inv["error"]) <= DIAG_MAX
    assert "prérequis" in inv["error"] and "exécution" in inv["error"]     # deux libellés distincts
    assert "prérequis horodatage: [REDACTED-B64]" in inv["error"] and "exécution: [REDACTED-HEX]" in inv["error"]


# ===================================================================== #
# COMPLÉMENTS rev6 (R07-A revendication via parent épinglé ; R07-B unlink échoue après hardlink → double nom honnête).
# PRÉPARÉS, NON EXÉCUTÉS. Tests directs du VRAI helper `_finalize_consult_transit` sur fixtures synthétiques.
# ===================================================================== #

# --- R07-A : parent de target redirigé par lien symbolique → revendication refusée (aucune redirection suivie) ---
def test_publish_refuses_redirected_parent(tmp_path):
    import brainai_app.composition as _comp
    realdir = tmp_path / "real"
    realdir.mkdir()
    redir = tmp_path / "redir"
    _os_mod.symlink(str(realdir), str(redir))                  # le PARENT commun (redir) est un lien symbolique
    # transit créé sous le parent redirigé (suit le lien à la création) ; root.parent == target.parent == redir
    root = redir / ".staging-rp"
    root.mkdir()
    (root / "tinv.jsonl").write_text("{}", encoding="utf-8")
    target = redir / "pursuit_rp"
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    # l'ouverture du parent par O_NOFOLLOW refuse le lien ⇒ échec explicite, jamais de destination créée hors arbre
    assert fin["settled"] is False and fin["reason"] == "finalisation_impossible"
    assert (root / "tinv.jsonl").exists()                      # transit conservé, aucune donnée déplacée


# --- R07-B : os.unlink échoue APRÈS un os.link réussi → fichier sous les DEUX noms, published honnête ---
def test_publish_unlink_fails_after_link_double_name(tmp_path, monkeypatch):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)                               # contient tinv.jsonl + exec/w.txt
    target = tmp_path / "pursuit_unlink"
    real_unlink = _comp.os.unlink

    def boom_unlink(*a, **k):
        raise OSError("retrait du nom source impossible")

    monkeypatch.setattr(_comp.os, "unlink", boom_unlink, raising=True)   # link OK, identité OK, unlink échoue
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "finalisation_partielle"
    # honnêteté : le fichier lié figure dans published ET dans both_names (encore sous les deux noms), PAS dans source_retired
    assert fin["published"], "published ne doit pas être vide par omission"
    first = fin["published"][0]
    assert first in fin["both_names"] and first not in fin["source_retired"]
    # emplacements réels : présent à destination ET encore dans le transit (mêmes octets)
    assert (Path(fin["target"]) / first).exists()
    assert (Path(fin["transit_kept"]) / first).exists()
    assert real_unlink is not None                            # (référence conservée pour lisibilité ; pas de retry)


# --- R07-B : succès normal — source_retired == published, both_names vide ---
def test_publish_success_source_retired_matches_published(tmp_path):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_full"
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is True
    assert sorted(fin["published"]) == sorted(fin["source_retired"]) == ["exec/w.txt", "tinv.jsonl"]
    assert fin["both_names"] == []
    assert not root.exists()


# ===================================================================== #
# COMPLÉMENTS rev7 (R07-A ancrage : ancêtre redirigé + substitution à la frontière ; R07-B unlink au niveau
# COMPOSITION sur le journal tinv.jsonl). PRÉPARÉS, NON EXÉCUTÉS.
# ===================================================================== #

# --- R07-A : un ANCÊTRE du parent est redirigé (lien) → aucune création sous l'arbre de redirection ---
def test_publish_refuses_redirected_ancestor(tmp_path):
    import brainai_app.composition as _comp
    # arbre légitime : base/real/pursuits/... ; ancêtre 'anc' est un lien vers base/real
    real = tmp_path / "real"
    (real / "pursuits").mkdir(parents=True)
    anc = tmp_path / "anc"
    _os_mod.symlink(str(real), str(anc))                       # ANCÊTRE (grand-parent du parent) redirigé
    # parent = anc/pursuits ; anchor = anc (lien) ; l'ouverture O_NOFOLLOW de l'ancrage refuse le lien
    root = anc / "pursuits" / ".staging-anc"
    root.mkdir()
    (root / "tinv.jsonl").write_text("{}", encoding="utf-8")
    target = anc / "pursuits" / "pursuit_anc"
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "finalisation_impossible"
    # aucune destination créée sous l'arbre réel via la redirection
    assert not (real / "pursuits" / "pursuit_anc").exists()
    assert (root / "tinv.jsonl").exists()                      # transit conservé


# --- R07-A : COLLISION à la frontière de revendication (mkdir relatif lève FileExistsError) → destination_existante ---
def test_publish_claim_frontier_collision(tmp_path, monkeypatch):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_bnd"
    real_mkdir = _os_mod.mkdir
    mk_calls = {"n": 0}

    def boom_mkdir(path, *a, **k):
        # ne perturbe que la REVENDICATION relative de la cible (dir_fd fourni, nom == target.name)
        if k.get("dir_fd") is not None and str(path) == target.name:
            mk_calls["n"] += 1
            raise FileExistsError("apparue à la frontière de revendication")
        return real_mkdir(path, *a, **k)

    monkeypatch.setattr(_comp.os, "mkdir", boom_mkdir, raising=True)
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)   # ancrage autorisé DÉCLARÉ (fixture)
    assert fin["settled"] is False and fin["reason"] == "destination_existante"   # collision : jamais publication
    assert mk_calls["n"] == 1                                   # injection atteinte à la frontière
    assert (root / "tinv.jsonl").exists()


# --- R07-A : VRAIE substitution de répertoire à la frontière — la cible revendiquée est remplacée par un lien
# vers un arbre de redirection ENTRE mkdir et open ; O_NOFOLLOW refuse ⇒ refus, AUCUNE publication sous la redirection.
def test_publish_claim_frontier_real_substitution(tmp_path, monkeypatch):
    import brainai_app.composition as _comp
    root = _mk_transit(tmp_path)
    target = tmp_path / "pursuit_sub"
    redir = tmp_path / "redir_target"
    redir.mkdir()
    real_mkdir = _os_mod.mkdir
    subbed = {"n": 0}

    def sub_mkdir(path, *a, **k):
        res = real_mkdir(path, *a, **k)                         # la revendication crée d'abord un vrai répertoire...
        dfd = k.get("dir_fd")
        if dfd is not None and str(path) == target.name and subbed["n"] == 0:
            subbed["n"] += 1
            _os_mod.rmdir(str(path), dir_fd=dfd)               # ...puis SUBSTITUTION réelle : on remplace la cible
            _os_mod.symlink(str(redir), str(path), dir_fd=dfd) # par un LIEN vers l'arbre de redirection
        return res

    monkeypatch.setattr(_comp.os, "mkdir", sub_mkdir, raising=True)
    fin = _comp._finalize_consult_transit(root, target, target.parent.parent)
    assert fin["settled"] is False and fin["reason"] == "finalisation_impossible"   # open O_NOFOLLOW refuse le lien substitué
    assert subbed["n"] == 1                                     # substitution EFFECTIVEMENT réalisée
    assert not any(redir.iterdir())                            # AUCUNE publication dans l'arbre de redirection
    assert (root / "tinv.jsonl").exists()                      # transit conservé (identité non établie ⇒ aucune donnée déplacée)


# --- R07-B : unlink du JOURNAL tinv.jsonl échoue après lien réussi (vrai consult) → double nom honnête ---
class _CountingUnlink:
    """Compte les tentatives d'unlink et lève systématiquement (aucun retry attendu)."""
    def __init__(self):
        self.n = 0

    def __call__(self, *a, **k):
        self.n += 1
        raise OSError("retrait du nom source impossible")


def test_composition_unlink_fails_journal_double_name(monkeypatch, tmp_path):
    _hermetic_env(monkeypatch, tmp_path)
    _isolate_session_cache(monkeypatch)
    import scc_brainai_bootstrap.builder.brainai as _b
    import brainai_app.composition as _comp
    from brainai_app.composition import consult as _consult_fn
    monkeypatch.setattr(_b, "datetime", _FrozenDT, raising=True)   # transit consult = tinv.jsonl UNIQUEMENT
    boom = _CountingUnlink()
    monkeypatch.setattr(_comp.os, "unlink", boom, raising=True)    # link+identité OK, unlink du journal échoue
    vm = _consult_fn(OBS_HEALTH, mode="real")
    fin = vm["finalization"]
    assert fin["settled"] is False and fin["reason"] == "finalisation_partielle"
    assert fin["provenance_durable"] is False
    assert "tinv.jsonl" in fin["published"]                     # publié à destination
    assert "tinv.jsonl" in fin["both_names"]                    # ENCORE sous le nom source (unlink échoué)
    assert "tinv.jsonl" not in fin["source_retired"]           # jamais faussement retiré
    assert boom.n == 1                                          # UNE seule tentative, aucun retry
    tgt = Path(fin["target"]) / "tinv.jsonl"
    src = Path(fin["transit_kept"]) / "tinv.jsonl"
    assert tgt.exists() and src.exists()                       # journal sous LES DEUX noms
    st_t = _os_mod.stat(str(tgt)); st_s = _os_mod.stat(str(src))
    assert (st_t.st_ino, st_t.st_dev) == (st_s.st_ino, st_s.st_dev)   # même inode : mêmes octets (lien physique)
    assert tgt.read_bytes() == src.read_bytes()               # identité/contenu concordants
    pid = vm["invocation"]["pursuit_ref"]
    assert _comp._SESSIONS.get(pid) is None                    # cache inchangé (settle non affirmé)


# ===================================================================== #
# COMPLÉMENT rev8 (R08-A) — preuve CIBLÉE de la garde ``ancrage_non_autorise`` : l'origine autorisée DÉCLARÉE est
# indépendante (non dérivée de la cible), et la garde intervient AVANT toute I/O (``os.open``) et AVANT la
# revendication (``os.mkdir``). PRÉPARÉ, NON EXÉCUTÉ.
# ===================================================================== #
def test_publish_refuses_unauthorized_anchor_before_io(tmp_path, monkeypatch):
    import brainai_app.composition as _comp
    # Arbre A : transit + cible partagent le MÊME parent (A/pursuits) ; target.parent.parent == A.
    a = tmp_path / "A"
    (a / "pursuits").mkdir(parents=True)
    root = a / "pursuits" / ".staging-ua"
    root.mkdir()
    (root / "tinv.jsonl").write_text('{"invocation_id":"tinv_x"}\n', encoding="utf-8")
    target = a / "pursuits" / "pursuit_ua"                     # NON créée
    # Ancrage autorisé B : INDÉPENDANT, non dérivé de la cible (A != B).
    b = tmp_path / "B"
    b.mkdir()
    assert target.parent.parent != b                           # préalable : l'ancrage déclaré n'est pas A

    # Compteurs : la garde doit retourner AVANT os.open et os.mkdir (relatifs au module composition).
    io_calls = {"open": 0, "mkdir": 0}
    real_open = _comp.os.open
    real_mkdir = _comp.os.mkdir
    def counting_open(*a_, **k_):
        io_calls["open"] += 1
        return real_open(*a_, **k_)
    def counting_mkdir(*a_, **k_):
        io_calls["mkdir"] += 1
        return real_mkdir(*a_, **k_)
    # installés APRÈS la construction de la fixture (celle-ci ne doit pas être comptée)
    monkeypatch.setattr(_comp.os, "open", counting_open, raising=True)
    monkeypatch.setattr(_comp.os, "mkdir", counting_mkdir, raising=True)

    fin = _comp._finalize_consult_transit(root, target, b)     # ancrage AUTORISÉ déclaré = B (≠ A)
    assert fin["settled"] is False and fin["reason"] == "ancrage_non_autorise"
    assert io_calls["open"] == 0 and io_calls["mkdir"] == 0    # garde AVANT toute I/O et toute revendication
    assert not target.exists()                                 # aucune cible créée
    assert (root / "tinv.jsonl").exists()                      # transit conservé intact
    # la branche renvoie uniquement transit_kept (pas de target/published) : état minimal, aucune publication
    assert "target" not in fin and "published" not in fin
