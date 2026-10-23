"""Seam provider-neutral ``test.run`` et faits append-only ``TestResult``.

Le producteur central valide l'artefact et son empreinte avant l'appel, exécute exactement une
capacité injectée, vérifie de nouveau l'empreinte après l'appel, puis consigne une
``ToolInvocation`` et un ``TestResult``. Les sorties sont caviardées sur le texte complet puis
bornées avant toute persistance.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Protocol

from scc_brainai_bootstrap.builder.diagnostics import DIAG_MAX, redact
from scc_brainai_bootstrap.builder.site import MAX_ARTIFACT_BYTES
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError
from scc_brainai_bootstrap.core.clock import short_id

TEST_RUN_CAPABILITY = "test.run"


class TestRunCapability(Protocol):
    capability: str
    name: str

    def run(self, *, cwd: Path, artifact_ref: Dict[str, Any]) -> Dict[str, Any]: ...


class TestResultStore:
    """Journal JSONL append-only des résultats de test."""

    __test__ = False

    def __init__(self, path: Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        facts: List[Dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                facts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return facts

    def record(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        stored = {key: value for key, value in fact.items() if key != "test_result_id"}
        result_id = short_id("testres", {
            "artifact_ref": stored.get("artifact_ref"),
            "artifact_sha256": stored.get("artifact_sha256"),
            "status": stored.get("status"),
            "tool_ref": stored.get("tool_ref"),
            "as_of": stored.get("as_of"),
        })
        stored = {"test_result_id": result_id, **stored}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return (redact(str(value or "")) or "")[:DIAG_MAX]


def _sha256(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise WorkspaceError("artefact illisible") from exc
    if size <= 0 or size > MAX_ARTIFACT_BYTES:
        raise WorkspaceError(f"taille d'artefact invalide : {size}")
    hasher = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                total += len(chunk)
                if total > MAX_ARTIFACT_BYTES:
                    raise WorkspaceError("taille d'artefact invalide pendant la lecture")
                hasher.update(chunk)
    except OSError as exc:
        raise WorkspaceError("artefact illisible") from exc
    if total <= 0:
        raise WorkspaceError("artefact vide")
    return hasher.hexdigest()


def _validated_artifact(workspace: Workspace, artifact_ref: Any) -> tuple[Path, str, str]:
    if not isinstance(artifact_ref, dict):
        raise WorkspaceError("artifact_ref objet requis")
    relative_path = artifact_ref.get("relative_path")
    expected_sha256 = artifact_ref.get("sha256")
    if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
        raise WorkspaceError("artifact_ref incomplet")
    if len(expected_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha256.lower()):
        raise WorkspaceError("empreinte d'artefact invalide")
    target = workspace.resolve_within(relative_path)
    if not target.is_file():
        raise WorkspaceError("artefact à tester absent ou non régulier")
    return target, relative_path, expected_sha256.lower()


def _artifact_evidence(artifact_ref: Any) -> tuple[str, Any]:
    """Extrait une référence bornée pour un fait d'échec sans faire confiance à l'entrée."""
    if not isinstance(artifact_ref, dict):
        return "", None
    relative_path = artifact_ref.get("relative_path")
    expected_sha256 = artifact_ref.get("sha256")
    safe_path = _clean(relative_path) if isinstance(relative_path, str) else ""
    safe_sha256 = None
    if (isinstance(expected_sha256, str) and len(expected_sha256) == 64
            and all(ch in "0123456789abcdef" for ch in expected_sha256.lower())):
        safe_sha256 = expected_sha256.lower()
    return safe_path, safe_sha256


def _failed_result(*, adapter: TestRunCapability, artifact_ref: Any, store: TestResultStore,
                   as_of: str, diagnostic: Any, attempted: bool,
                   artifact_path: str = "", artifact_sha256: Any = None) -> Dict[str, Any]:
    """Persiste un échec terminal sûr de la frontière ``test.run``."""
    if not artifact_path and artifact_sha256 is None:
        artifact_path, artifact_sha256 = _artifact_evidence(artifact_ref)
    return store.record({
        "fact_type": "test_result", "capability": TEST_RUN_CAPABILITY,
        "adapter": _clean(getattr(adapter, "name", "unknown")),
        "artifact_ref": artifact_path, "artifact_sha256": artifact_sha256,
        "status": "failed", "attempted": attempted, "tool_ref": None,
        "exit_code": None, "timed_out": False,
        "diagnostic": {"stdout": "", "stderr": _clean(diagnostic)},
        "cost": {"value": None, "kind": "unavailable"}, "as_of": as_of,
    })


def produce_test_run(*, adapter: TestRunCapability, artifact_ref: Dict[str, Any],
                     store: TestResultStore, tool_store: Any, workspace: Workspace,
                     project_id: str, clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """Exécute une fois la capacité injectée et persiste les faits sûrs correspondants."""
    if getattr(adapter, "capability", None) != TEST_RUN_CAPABILITY or not callable(getattr(adapter, "run", None)):
        raise TypeError("capacité test.run valide requise")
    as_of = clock()
    try:
        target, relative_path, expected_sha256 = _validated_artifact(workspace, artifact_ref)
        before_sha256 = _sha256(target)
    except WorkspaceError as exc:
        return _failed_result(adapter=adapter, artifact_ref=artifact_ref, store=store, as_of=as_of,
                              diagnostic=exc, attempted=False)
    if before_sha256 != expected_sha256:
        return _failed_result(
            adapter=adapter, artifact_ref=artifact_ref, store=store, as_of=as_of,
            diagnostic="empreinte pré-test divergente", attempted=False,
            artifact_path=relative_path, artifact_sha256=expected_sha256)

    try:
        raw = adapter.run(cwd=workspace.path, artifact_ref=dict(artifact_ref))
    except Exception as exc:
        diagnostic = f"exception test.run ({type(exc).__name__}) : {exc}"
        try:
            if _sha256(target) != expected_sha256:
                diagnostic += " ; artefact modifié ou absent pendant le test"
        except WorkspaceError:
            diagnostic += " ; artefact modifié ou absent pendant le test"
        return _failed_result(
            adapter=adapter, artifact_ref=artifact_ref, store=store, as_of=as_of,
            diagnostic=diagnostic, attempted=True,
            artifact_path=relative_path, artifact_sha256=expected_sha256)
    raw_is_dict = isinstance(raw, dict)
    called = raw_is_dict and raw.get("called") is True
    exit_code = raw.get("exit_code") if raw_is_dict else None
    timed_out_value = raw.get("timed_out") if raw_is_dict else None
    timed_out = timed_out_value if isinstance(timed_out_value, bool) else False
    exit_valid = exit_code is None or (isinstance(exit_code, int) and not isinstance(exit_code, bool))
    timeout_valid = isinstance(timed_out_value, bool)
    argv_value = raw.get("argv") if raw_is_dict else None
    argv_valid = isinstance(argv_value, list) and bool(argv_value) and all(isinstance(v, str) for v in argv_value)
    raw_valid = raw_is_dict and called and exit_valid and timeout_valid and argv_valid
    stdout = _clean(raw.get("stdout") if raw_is_dict else "")
    stderr = _clean(raw.get("stderr") if raw_is_dict else "résultat test.run non objet")
    tool_ref = None
    if raw_valid:
        tool_status = "timeout" if timed_out else ("succeeded" if exit_code == 0 else "failed")
        # ``argv`` fait partie de l'identité ToolInvocation : le fournisseur local construit un argv fermé,
        # validé et sans credential. Il est donc conservé exactement ; seules stdout/stderr sont caviardées.
        argv = list(argv_value)
        tool_fact = tool_store.record(
            project_id=project_id, tool=getattr(adapter, "name", "test.run"), argv=argv,
            cwd=str(workspace.path), status=tool_status, exit_code=exit_code,
            stdout=stdout, stderr=stderr, timed_out=timed_out, as_of=as_of)
        tool_ref = tool_fact["invocation_id"]

    try:
        after_sha256 = _sha256(target)
    except (OSError, WorkspaceError):
        after_sha256 = None
    hash_stable = after_sha256 == expected_sha256
    passed = raw_valid and not timed_out and exit_code == 0 and hash_stable
    if not hash_stable:
        stderr = _clean((stderr + "\n" if stderr else "") + "artefact modifié ou absent pendant le test")
    elif not called:
        stderr = _clean((stderr + "\n" if stderr else "") + "capacité test.run non exécutée")
    elif not raw_valid:
        stderr = _clean((stderr + "\n" if stderr else "") + "résultat test.run invalide")

    return store.record({
        "fact_type": "test_result", "capability": TEST_RUN_CAPABILITY,
        "adapter": getattr(adapter, "name", "unknown"), "artifact_ref": relative_path,
        "artifact_sha256": expected_sha256, "status": "passed" if passed else "failed",
        "attempted": called,
        "tool_ref": tool_ref, "exit_code": exit_code, "timed_out": timed_out,
        "diagnostic": {"stdout": stdout, "stderr": stderr},
        "cost": {"value": None, "kind": "unavailable"}, "as_of": as_of,
    })


__all__ = ["TEST_RUN_CAPABILITY", "TestRunCapability", "TestResultStore", "produce_test_run"]
