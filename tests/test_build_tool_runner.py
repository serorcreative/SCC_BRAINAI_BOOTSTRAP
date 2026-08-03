"""Preuve A (BRAINAI-JALON-ZERO-001) — frontière d'exécution subprocess **réelle et confinée**.

Prouve que BrainAI peut **provoquer un effet réel** (écrire un fichier via un vrai sous-processus)
tout en gardant la **maîtrise complète** : confinement au Workspace, capture intégrale, timeout réel,
et **fait ToolInvocation** append-only pour chaque exécution (succès comme échec). Aucun état officiel
n'est modifié ; aucune écriture hors Workspace n'est possible.

Critères : A1 fichier produit · A2 fait appendé · A3 écriture hors workspace impossible · A4 timeout
réellement testé · A5 aucun autre store modifié · A6 stdout/stderr/exit_code capturés.
"""

from __future__ import annotations

import os
import sys

import pytest

from scc_brainai_bootstrap.builder import invoke_tool
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError

AS_OF = "2026-08-03T00:00:00+00:00"
PY = sys.executable  # interpréteur réel = l'« outil » de la preuve (argv absolu, aucun PATH requis)


def _pid_alive(pid: int) -> bool:
    """True si ``pid`` existe **encore** dans la table (y compris zombie non récolté).

    ``kill(pid, 0)`` réussit tant que l'entrée process existe — un zombie répond donc ``True`` ;
    ``ESRCH`` (:class:`ProcessLookupError`) prouve la **récolte** effective (plus aucune entrée)."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:      # existe mais hors de notre portée — reste « vivant »
        return True


def _store(tmp_path):
    return ToolInvocationStore(tmp_path / "build" / "tool_invocations.jsonl")


def _workspace(tmp_path, pid="refuge-001"):
    ws = Workspace(tmp_path / "build", pid)
    ws.ensure()
    return ws


# --------------------------------------------------------------------- #
# A1 + A2 + A6 — effet réel confiné + fait append-only + capture
# --------------------------------------------------------------------- #
def test_real_subprocess_writes_file_and_records_fact(tmp_path):
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    target = ws.resolve_within("out/hello.txt")          # A3 : chemin validé AVANT l'appel
    script = "import sys,pathlib; p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(sys.argv[2], encoding='utf-8'); print('written', p.name)"
    argv = [PY, "-c", script, str(target), "Refuge animalier — v1"]

    fact = invoke_tool(store=store, workspace=ws, argv=argv, timeout=30, as_of=AS_OF)

    # A1 : le fichier existe réellement, avec le contenu attendu.
    assert target.exists() and target.read_text(encoding="utf-8") == "Refuge animalier — v1"
    # A2 : un fait ToolInvocation a été appendé et est relisible.
    assert fact["status"] == "succeeded" and fact["project_id"] == "refuge-001"
    assert store.read_all() == [fact]
    # A6 : stdout / stderr / exit_code capturés dans le fait (exactement ce que l'outil a produit).
    assert fact["exit_code"] == 0
    assert "written hello.txt" in fact["stdout"]
    assert fact["stderr"] == ""
    assert fact["timed_out"] is False


def test_failed_subprocess_is_recorded_not_raised(tmp_path):
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    argv = [PY, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"]
    fact = invoke_tool(store=store, workspace=ws, argv=argv, timeout=30, as_of=AS_OF)
    # l'échec de l'outil est un FAIT, jamais une exception.
    assert fact["status"] == "failed" and fact["exit_code"] == 3 and "boom" in fact["stderr"]


# --------------------------------------------------------------------- #
# A3 — impossible d'écrire hors workspace (refus AVANT tout effet)
# --------------------------------------------------------------------- #
def test_path_traversal_rejected_before_any_effect(tmp_path):
    ws = _workspace(tmp_path)
    for evil in ("../../../data/hack.txt", "../escape.txt", "a/../../b.txt"):
        with pytest.raises(WorkspaceError):
            ws.resolve_within(evil)


def test_absolute_and_null_paths_rejected(tmp_path):
    ws = _workspace(tmp_path)
    for evil in ("/etc/passwd", "/tmp/x", "ok\x00.txt", ""):
        with pytest.raises(WorkspaceError):
            ws.resolve_within(evil)


def test_cannot_target_real_data_or_repo(tmp_path):
    # Un chemin absolu vers le vrai data/ ou un dépôt est rejeté (chemin absolu → refus).
    ws = _workspace(tmp_path)
    for evil in ("/Users/x/17_BRAINAI_BOOTSTRAP/data/dossiers.jsonl",
                 "../../../../17_BRAINAI_BOOTSTRAP/data/x"):
        with pytest.raises(WorkspaceError):
            ws.resolve_within(evil)


def test_invalid_project_id_rejected(tmp_path):
    for bad in ("../evil", "a/b", "..", "A_MAJ", "trop" + "x" * 70, ""):
        with pytest.raises(WorkspaceError):
            Workspace(tmp_path / "build", bad)


# --------------------------------------------------------------------- #
# T1a — échappée par lien symbolique refusée AVANT tout effet externe
# --------------------------------------------------------------------- #
def test_symlink_escape_rejected_before_any_effect(tmp_path):
    """Un symlink DANS le workspace pointant DEHORS est refusé par ``resolve_within`` (qui résout
    les liens) — donc BrainAI ne passe jamais un tel chemin à un outil : aucun effet partiel."""
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    outside = tmp_path / "outside_secret"            # cible HORS workspace
    outside.mkdir()

    # (a) symlink-répertoire : <ws>/escape -> outside ; écrire « escape/hack.txt » échapperait.
    (ws.path / "escape").symlink_to(outside, target_is_directory=True)
    # (b) symlink-fichier : <ws>/evil.txt -> outside/secret.txt (cible inexistante mais résolue).
    (ws.path / "evil.txt").symlink_to(outside / "secret.txt")

    for escaping in ("escape/hack.txt", "evil.txt"):
        with pytest.raises(WorkspaceError):
            ws.resolve_within(escaping)              # refus AVANT toute construction d'argv

    # Aucun fichier n'a été créé hors du workspace, et aucune invocation n'a été ouverte
    # (le garde-fou précède la frontière subprocess) → aucun fait partiel, aucun effet partiel.
    assert list(outside.iterdir()) == []
    assert store.read_all() == []


# --------------------------------------------------------------------- #
# A4 — timeout réellement testé
# --------------------------------------------------------------------- #
def test_timeout_is_real_and_recorded_as_failure(tmp_path):
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    argv = [PY, "-c", "import time; time.sleep(5)"]
    fact = invoke_tool(store=store, workspace=ws, argv=argv, timeout=1, as_of=AS_OF)
    # Le processus a dépassé la limite : tué, reflété comme fait en échec (timeout).
    assert fact["status"] == "timeout" and fact["timed_out"] is True and fact["exit_code"] is None


# --------------------------------------------------------------------- #
# T1c — après timeout : processus tué, récolté, aucun zombie résiduel
# --------------------------------------------------------------------- #
def test_timeout_leaves_no_zombie_process(tmp_path):
    """Le sous-processus dépassant le timeout est tué ET **récolté** (attendu) par le runner :
    à son retour, le pid enfant n'existe plus (ni vivant, ni zombie)."""
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    # L'enfant publie son PID (flush) AVANT de dormir → capturé dans le stdout partiel du timeout.
    argv = [PY, "-c",
            "import os,sys,time; sys.stdout.write(str(os.getpid())+'\\n'); sys.stdout.flush(); time.sleep(30)"]

    fact = invoke_tool(store=store, workspace=ws, argv=argv, timeout=1, as_of=AS_OF)

    assert fact["status"] == "timeout" and fact["timed_out"] is True
    child_pid = int(fact["stdout"].strip().splitlines()[0])   # PID réel du sous-processus tué
    # À ce point, run_confined est revenu : subprocess.run a tué PUIS récolté l'enfant.
    assert not _pid_alive(child_pid), f"pid {child_pid} encore présent (zombie/vivant) après timeout"


# --------------------------------------------------------------------- #
# A5 — aucun autre store modifié (seul tool_invocations.jsonl est écrit)
# --------------------------------------------------------------------- #
def test_only_tool_invocations_store_written(tmp_path):
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    target = ws.resolve_within("f.txt")
    invoke_tool(store=store, workspace=ws,
                argv=[PY, "-c", "import sys,pathlib; pathlib.Path(sys.argv[1]).write_text('x')", str(target)],
                timeout=30, as_of=AS_OF)
    # Sous la racine build/, seuls le workspace du Projet et le journal existent — rien d'autre.
    written = sorted(p.name for p in (tmp_path / "build").rglob("*") if p.is_file())
    assert written == ["f.txt", "tool_invocations.jsonl"]
    # Le store contient exactement une invocation.
    assert len(store.read_all()) == 1


def test_facts_are_append_only(tmp_path):
    ws = _workspace(tmp_path)
    store = _store(tmp_path)
    for i in range(3):
        invoke_tool(store=store, workspace=ws,
                    argv=[PY, "-c", f"print({i})"], timeout=30, as_of=AS_OF)
    lines = store.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3                    # append-only : 3 faits, aucun écrasement
    assert len(store.read_all()) == 3
