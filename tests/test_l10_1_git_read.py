"""L10.1 — Git READ-ONLY typé (git.status / git.diff / git.branches.list) — déterministe, $0, sans LLM, sans
réseau. Chaque test s'exécute sur un dépôt Git **throwaway** créé dans ``tmp_path``. Prouve : résolution de
capacités, lecture réelle confinée, SEC-3 (diff redacté), confinement (cwd/toplevel/git-dir/common-dir/object-dir),
refus des filtres de contenu et des alternates, fail-closed, provenance secret-safe, et **absence** de toute
surface de mutation / remote / command.run."""

from __future__ import annotations

import subprocess

import pytest

from brainai_app import providers
from scc_brainai_bootstrap.builder import git_read as gr
from scc_brainai_bootstrap.builder.git_read import GitReadError, LocalGitReadAdapter, produce_git_read
from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore

CLOCK = lambda: "2026-09-09T00:00:00+00:00"  # noqa: E731


# --------------------------------------------------------------------- #
# Échafaudage : dépôt Git throwaway (git réel, hors capacité — la capacité, elle, passe par run_confined).
# --------------------------------------------------------------------- #
def _run_git(args, cwd):
    r = subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=Test",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True)
    assert r.returncode == 0, (args, r.stderr)
    return r


def _mkrepo(tmp_path, name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    _run_git(["init", "-q", "-b", "main"], repo)
    (repo / "README.md").write_text("hello world\n", encoding="utf-8")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "init"], repo)
    return repo


def _store(tmp_path):
    return ToolInvocationStore(tmp_path / "tinv.jsonl")


def _read(cap, repo, tmp_path, **kw):
    return produce_git_read(capability=cap, adapter=LocalGitReadAdapter(), cwd=repo,
                            tool_store=_store(tmp_path), project_id="p", clock=CLOCK,
                            allowed_root=repo, **kw)


# --------------------------------------------------------------------- #
# A. RÉSOLUTION DE CAPACITÉS
# --------------------------------------------------------------------- #
def test_git_read_providers_and_capabilities_canonical():
    assert providers.GIT_READ_PROVIDERS == ("local_git",)
    assert providers.GIT_READ_CAPABILITIES == ("git.status", "git.diff", "git.branches.list")


def test_resolve_three_capabilities_local_git_with_contract():
    for cap in providers.GIT_READ_CAPABILITIES:
        impl = providers.resolve_git_read(cap)
        assert impl.name == "local_git"
        c = impl.contract().to_dict()
        assert c["cost_report"] == {"mode": "unavailable", "fabricated": False}
        assert c["native_budget"] == {"usd_cap": "none", "call_cap": "none"}
        assert c["confinement"]["network"] == {"required": False, "isolation": "not_proven"}


def test_unknown_capability_and_provider_fail_closed():
    for bad in ("git.push", "git.commit", "git.fetch", "git.add", "git.branch.create", "command.run"):
        with pytest.raises(LookupError):
            providers.resolve_git_read(bad)
    with pytest.raises(LookupError):
        providers.resolve_git_read("git.status", provider="inconnu")


# --------------------------------------------------------------------- #
# B. STATUS
# --------------------------------------------------------------------- #
def test_status_clean_repo(tmp_path):
    repo = _mkrepo(tmp_path)
    out = _read(gr.GIT_STATUS, repo, tmp_path)
    assert out["ok"] and out["status"] == "succeeded"
    assert out["result"]["clean"] is True and out["result"]["entries"] == []


def test_status_dirty_repo_deterministic(tmp_path):
    repo = _mkrepo(tmp_path)
    (repo / "NEW.txt").write_text("x\n", encoding="utf-8")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    a = _read(gr.GIT_STATUS, repo, tmp_path)
    b = _read(gr.GIT_STATUS, repo, tmp_path)
    assert a["result"]["clean"] is False
    paths = {e["path"] for e in a["result"]["entries"]}
    assert "NEW.txt" in paths and "README.md" in paths
    assert a["result"] == b["result"]                      # déterministe


def test_status_no_mutation_no_remote(tmp_path):
    repo = _mkrepo(tmp_path)
    before = _run_git(["status", "--porcelain"], repo).stdout
    out = _read(gr.GIT_STATUS, repo, tmp_path)
    after = _run_git(["status", "--porcelain"], repo).stdout
    assert before == after                                 # aucune mutation
    assert not any("remote" in tok for tok in out["argv"])
    assert "--ignore-submodules=all" in out["argv"]


# --------------------------------------------------------------------- #
# C. DIFF (SEC-3 : redacté / borné ; aucun programme externe)
# --------------------------------------------------------------------- #
def test_diff_tracked_change_redacted_output(tmp_path):
    repo = _mkrepo(tmp_path)
    (repo / "README.md").write_text("hello world\nplus\n", encoding="utf-8")
    out = _read(gr.GIT_DIFF, repo, tmp_path)
    assert out["ok"] and out["result"]["changed"] is True
    assert "text_redacted" in out["result"] and "text" not in out["result"]     # jamais de brut
    assert "raw_sha256" not in out["result"]                                    # aucun fingerprint du brut
    assert "+plus" in out["result"]["text_redacted"]
    assert "--no-ext-diff" in out["argv"] and "--no-textconv" in out["argv"] and "--no-color" in out["argv"]


def test_diff_staged_argument_strict(tmp_path):
    repo = _mkrepo(tmp_path)
    with pytest.raises(GitReadError):
        gr.diff_argv(staged="yes")                          # type non booléen refusé
    with pytest.raises(GitReadError):
        _read(gr.GIT_DIFF, repo, tmp_path, staged="yes")


def test_diff_no_mutation(tmp_path):
    repo = _mkrepo(tmp_path)
    (repo / "README.md").write_text("z\n", encoding="utf-8")
    before = _run_git(["rev-parse", "HEAD"], repo).stdout
    _read(gr.GIT_DIFF, repo, tmp_path)
    after = _run_git(["rev-parse", "HEAD"], repo).stdout
    assert before == after


# --------------------------------------------------------------------- #
# D. BRANCHES LIST
# --------------------------------------------------------------------- #
def test_branches_list_current_and_multiple(tmp_path):
    repo = _mkrepo(tmp_path)
    _run_git(["branch", "feature"], repo)
    _run_git(["branch", "other"], repo)
    out = _read(gr.GIT_BRANCHES, repo, tmp_path)
    names = {b["name"]: b for b in out["result"]}
    assert {"main", "feature", "other"} <= set(names)
    assert names["main"]["current"] is True
    assert names["feature"]["current"] is False
    assert all(len(b["sha"]) >= 7 for b in out["result"])
    assert "refs/heads/" in out["argv"] and not any("remotes" in tok for tok in out["argv"])


# --------------------------------------------------------------------- #
# E. CONFINEMENT
# --------------------------------------------------------------------- #
def test_confinement_cwd_outside_allowed_root(tmp_path):
    repo = _mkrepo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(GitReadError):
        produce_git_read(capability=gr.GIT_STATUS, adapter=LocalGitReadAdapter(), cwd=repo,
                         tool_store=_store(tmp_path), project_id="p", clock=CLOCK, allowed_root=other)


def test_confinement_non_git_dir(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitReadError):
        produce_git_read(capability=gr.GIT_STATUS, adapter=LocalGitReadAdapter(), cwd=plain,
                         tool_store=_store(tmp_path), project_id="p", clock=CLOCK, allowed_root=plain)


def test_confinement_relative_path_refused(tmp_path):
    with pytest.raises(GitReadError):
        produce_git_read(capability=gr.GIT_STATUS, adapter=LocalGitReadAdapter(), cwd="relative/path",
                         tool_store=_store(tmp_path), project_id="p", clock=CLOCK, allowed_root=str(tmp_path))


def test_reject_content_filter_gitattributes(tmp_path):
    repo = _mkrepo(tmp_path)
    (repo / ".gitattributes").write_text("* filter=secret\n", encoding="utf-8")
    with pytest.raises(GitReadError):
        _read(gr.GIT_STATUS, repo, tmp_path)
    with pytest.raises(GitReadError):
        _read(gr.GIT_DIFF, repo, tmp_path)


def test_reject_content_filter_subdir_gitattributes(tmp_path):
    repo = _mkrepo(tmp_path)
    sub = repo / "sub"
    sub.mkdir()
    (sub / ".gitattributes").write_text("*.bin filter=x\n", encoding="utf-8")
    with pytest.raises(GitReadError):
        _read(gr.GIT_STATUS, repo, tmp_path)


def test_reject_content_filter_config(tmp_path):
    repo = _mkrepo(tmp_path)
    _run_git(["config", "filter.foo.clean", "cat"], repo)
    with pytest.raises(GitReadError):
        _read(gr.GIT_STATUS, repo, tmp_path)


def test_reject_alternates(tmp_path):
    repo = _mkrepo(tmp_path)
    info = repo / ".git" / "objects" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "alternates").write_text("/tmp/other/objects\n", encoding="utf-8")
    with pytest.raises(GitReadError):
        _read(gr.GIT_STATUS, repo, tmp_path)


def test_branches_list_exempt_from_filter_check(tmp_path):
    # git.branches.list ne lit aucun contenu worktree : un .gitattributes filter= ne doit PAS le bloquer.
    repo = _mkrepo(tmp_path)
    (repo / ".gitattributes").write_text("* filter=secret\n", encoding="utf-8")
    out = _read(gr.GIT_BRANCHES, repo, tmp_path)
    assert out["ok"] is True


# --------------------------------------------------------------------- #
# F. FAIL-CLOSED
# --------------------------------------------------------------------- #
def test_git_absent_fail_closed(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)

    def _boom(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(gr, "run_confined", _boom)
    with pytest.raises(GitReadError):
        _read(gr.GIT_STATUS, repo, tmp_path)


def test_timeout_fail_closed(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    real = gr.run_confined

    def _fake(argv, *, cwd, timeout, env=None):
        # confinement + filtres passent en RÉEL ; seule l'opération (status/diff/for-each-ref) « time out ».
        if any(m in argv for m in ("status", "diff", "for-each-ref")) and "rev-parse" not in argv:
            return {"exit_code": None, "stdout": "", "stderr": "", "timed_out": True}
        return real(argv, cwd=cwd, timeout=timeout, env=env)
    monkeypatch.setattr(gr, "run_confined", _fake)
    out = _read(gr.GIT_STATUS, repo, tmp_path)
    assert out["ok"] is False and out["status"] == "timeout" and out["result"] is None


def test_invalid_capability_produce_fail_closed(tmp_path):
    repo = _mkrepo(tmp_path)
    with pytest.raises(GitReadError):
        produce_git_read(capability="git.push", adapter=LocalGitReadAdapter(), cwd=repo,
                         tool_store=_store(tmp_path), project_id="p", clock=CLOCK, allowed_root=repo)


def test_adapter_contract_conformant():
    from scc_brainai_bootstrap.builder.adapter_contract import require_contract
    require_contract(LocalGitReadAdapter())                 # ne lève pas : contrat T2 complet


# --------------------------------------------------------------------- #
# G. PROVENANCE (secret-safe, N4/SEC-3)
# --------------------------------------------------------------------- #
def test_provenance_fact_recorded(tmp_path):
    repo = _mkrepo(tmp_path)
    store = ToolInvocationStore(tmp_path / "tinv.jsonl")
    out = produce_git_read(capability=gr.GIT_STATUS, adapter=LocalGitReadAdapter(), cwd=repo,
                           tool_store=store, project_id="p", clock=CLOCK, allowed_root=repo)
    facts = store.read_all()
    assert len(facts) == 1
    f = facts[0]
    assert f["tool"] == "local_git:git.status" and f["status"] == "succeeded"
    assert f["invocation_id"] == out["tool_ref"]


def test_provenance_no_secret_in_diff(tmp_path):
    repo = _mkrepo(tmp_path)
    token = "sk-ABCDEFGHIJ1234567890"
    (repo / "README.md").write_text("hello world\n" + token + "\n", encoding="utf-8")
    store = ToolInvocationStore(tmp_path / "tinv.jsonl")
    out = produce_git_read(capability=gr.GIT_DIFF, adapter=LocalGitReadAdapter(), cwd=repo,
                           tool_store=store, project_id="p", clock=CLOCK, allowed_root=repo)
    assert token not in out["result"]["text_redacted"]      # SEC-3 : jamais exposé à BrainAI
    fact = store.read_all()[0]
    assert token not in fact["stdout"]                      # N4 : jamais dans la provenance


# --------------------------------------------------------------------- #
# H. ABSENCE DE MUTATION / REMOTE / COMMAND.RUN (tests négatifs)
# --------------------------------------------------------------------- #
def test_exactly_three_capabilities_no_fourth():
    assert len(gr.GIT_READ_CAPABILITIES) == 3
    assert set(gr.GIT_READ_CAPABILITIES) == {"git.status", "git.diff", "git.branches.list"}


def test_argv_builders_have_no_mutating_or_remote_tokens():
    forbidden = {"push", "fetch", "pull", "commit", "add", "reset", "clean", "stash", "merge",
                 "rebase", "cherry-pick", "checkout", "switch", "remote", "clone", "--all"}
    for argv in (gr.status_argv(), gr.diff_argv(), gr.diff_argv(True), gr.branches_list_argv()):
        assert not (set(argv) & forbidden), argv
        assert not any("remotes" in tok for tok in argv)


def test_no_generic_command_run_capability():
    assert not hasattr(providers, "resolve_command_run")
    assert "command.run" not in providers.GIT_READ_CAPABILITIES
    assert "command.run" not in getattr(providers, "GIT_READ_PROVIDERS", ())


def test_hardened_env_present():
    env = gr._GIT_ENV
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null" and env["GIT_CONFIG_SYSTEM"] == "/dev/null"
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_OPTIONAL_LOCKS"] == "0"
    assert "GIT_ALTERNATE_OBJECT_DIRECTORIES" not in env


def test_no_bridge_to_cognitive_stack():
    # Vérifie les IMPORTS réels (AST) — aucun pont vers CognitiveStack/13/15/16 (N5). Robuste aux docstrings.
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(gr))
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
    forbidden = ("reasoning", "decision", "execution", "cognition", "planning")
    for m in mods:
        assert not any(f in m for f in forbidden), m
    # imports strictement limités à builder/core/stdlib
    assert all(m.startswith("scc_brainai_bootstrap.builder") or m.startswith("scc_brainai_bootstrap.core")
               or "." not in m or m in ("__future__",) for m in mods), mods


# --------------------------------------------------------------------- #
# POST-AUDIT — F-6.1 (bypass), F-6.2 (allowed_root obligatoire), F-6.9 (SEC-3 status/branches)
# --------------------------------------------------------------------- #
def test_resolver_returns_handle_without_naked_run(tmp_path):
    # F-6.1 : le resolver public ne livre AUCUNE voie d'exécution nue.
    h = providers.resolve_git_read(gr.GIT_STATUS)
    assert h.name == "local_git" and h.contract()              # contrat T2 disponible
    assert not hasattr(h, "run")
    assert not hasattr(h, "_run")
    assert not hasattr(h, "build_argv")
    assert hasattr(h, "read")
    with pytest.raises(AttributeError):                        # scénario ClaudeS rendu impossible
        h.run(gr.GIT_STATUS, cwd=str(tmp_path))
    # F-6.1 renforcé : même en récupérant l'adaptateur interne, AUCUNE primitive d'exécution n'existe.
    adapter = h._adapter
    for attr in ("run", "_run", "build_argv", "_build_argv"):
        assert not hasattr(adapter, attr), attr
    callables = {n for n in dir(adapter) if not n.startswith("__") and callable(getattr(adapter, n))}
    assert callables == {"contract"}, callables


def test_internal_adapter_has_no_public_run():
    # F-6.1 : l'adaptateur est INERTE — aucune méthode d'exécution (publique ou "_privée").
    a = LocalGitReadAdapter()
    for attr in ("run", "_run", "build_argv", "_build_argv"):
        assert not hasattr(a, attr), attr
    callables = {n for n in dir(a) if not n.startswith("__") and callable(getattr(a, n))}
    assert callables == {"contract"}, callables


def test_handle_read_success_via_public_api(tmp_path):
    repo = _mkrepo(tmp_path)
    store = ToolInvocationStore(tmp_path / "tinv.jsonl")
    h = providers.resolve_git_read(gr.GIT_STATUS)
    out = h.read(cwd=repo, allowed_root=repo, tool_store=store, project_id="p", clock=CLOCK)
    assert out["ok"] and out["result"]["clean"] is True
    assert len(store.read_all()) == 1                          # provenance systématique


def test_handle_read_requires_allowed_root(tmp_path):
    # F-6.2 : aucune exécution publique sans allowed_root explicite.
    repo = _mkrepo(tmp_path)
    store = ToolInvocationStore(tmp_path / "tinv.jsonl")
    h = providers.resolve_git_read(gr.GIT_STATUS)
    with pytest.raises(TypeError):
        h.read(cwd=repo, tool_store=store, project_id="p", clock=CLOCK)   # allowed_root manquant


def test_produce_requires_allowed_root(tmp_path):
    # F-6.2 : produce_git_read exige allowed_root (mot-clé sans défaut) ; None ⇒ GitReadError.
    repo = _mkrepo(tmp_path)
    store = ToolInvocationStore(tmp_path / "tinv.jsonl")
    with pytest.raises(TypeError):
        produce_git_read(capability=gr.GIT_STATUS, adapter=LocalGitReadAdapter(), cwd=repo,
                         tool_store=store, project_id="p", clock=CLOCK)   # allowed_root absent
    with pytest.raises(GitReadError):
        produce_git_read(capability=gr.GIT_STATUS, adapter=LocalGitReadAdapter(), cwd=repo,
                         tool_store=store, project_id="p", clock=CLOCK, allowed_root=None)


def test_provenance_mandatory_on_public_path(tmp_path):
    repo = _mkrepo(tmp_path)
    store = ToolInvocationStore(tmp_path / "tinv.jsonl")
    (repo / "README.md").write_text("hello world\nchange\n", encoding="utf-8")
    h = providers.resolve_git_read(gr.GIT_DIFF)
    out = h.read(cwd=repo, allowed_root=repo, tool_store=store, project_id="p", clock=CLOCK)
    assert out["ok"] and store.read_all()[0]["tool"] == "local_git:git.diff"


def test_sec3_status_secret_path_redacted(tmp_path):
    # F-6.9 : un nom de fichier secret-like n'apparaît pas brut dans result.
    repo = _mkrepo(tmp_path)
    token = "sk-STATUSSECRET1234567"
    (repo / token).write_text("x\n", encoding="utf-8")
    out = _read(gr.GIT_STATUS, repo, tmp_path)
    assert all(token not in e["path"] for e in out["result"]["entries"])
    assert token not in str(out["result"])


def test_sec3_branches_secret_name_redacted(tmp_path):
    # F-6.9 : un nom de branche secret-like n'apparaît pas brut ; le sha reste intact.
    repo = _mkrepo(tmp_path)
    token = "sk-branchsecret1234567"
    _run_git(["branch", token], repo)
    out = _read(gr.GIT_BRANCHES, repo, tmp_path)
    assert all(token not in b["name"] for b in out["result"])
    assert token not in str(out["result"])
    assert all(len(b["sha"]) >= 7 for b in out["result"])      # contrat sha préservé
