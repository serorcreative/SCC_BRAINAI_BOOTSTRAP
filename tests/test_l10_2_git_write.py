"""L10.2 — Git **MUTATIONS LOCALES** typées (git.branch.create / git.commit) — déterministe, $0, sans LLM, sans
réseau, sur dépôts Git **throwaway** sous ``tmp_path`` (JAMAIS le dépôt BrainAI réel). TDD : ces tests
matérialisent le design Phase B/C ratifié. Imports de production **paresseux** (dans les corps) afin que la
COLLECTION réussisse même avant l'existence de ``git_write`` (le RED provient de la production manquante, pas
d'une erreur de collecte)."""

from __future__ import annotations

import subprocess

import pytest

CLOCK = lambda: "2026-09-13T00:00:00+00:00"          # noqa: E731
TS = "2026-09-13T12:00:00+00:00"                     # commit_timestamp ISO-8601 UTC ratifié
AUTHOR_NAME = "Frédérique Seror"
AUTHOR_EMAIL = "frederique@serorcreative.ch"
AUTH_TIME = "2026-09-13T10:00:00+00:00"              # instant du GO (autorisation git-mutation)


# --------------------------------------------------------------------- #
# Imports paresseux (production potentiellement absente au RED).
# --------------------------------------------------------------------- #
def _gw():
    from scc_brainai_bootstrap.builder import git_write
    return git_write


def _ba():
    from scc_brainai_bootstrap.builder import build_authorization
    return build_authorization


def _providers():
    from brainai_app import providers
    return providers


def _tool_store(tmp_path):
    from scc_brainai_bootstrap.builder.tool_invocations import ToolInvocationStore
    return ToolInvocationStore(tmp_path / "tinv.jsonl")


def _auth_store(tmp_path):
    from scc_brainai_bootstrap.builder.build_authorization import BuildAuthorizationStore
    return BuildAuthorizationStore(tmp_path / "auth.jsonl")


def _ident(name=AUTHOR_NAME, email=AUTHOR_EMAIL):
    return _gw().Identity(name=name, email=email)


# --------------------------------------------------------------------- #
# Échafaudage : dépôt Git throwaway (git réel, hors capacité).
# --------------------------------------------------------------------- #
def _run_git(args, cwd, check=True):
    r = subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=Test",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True)
    if check:
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


def _head(repo):
    return _run_git(["rev-parse", "HEAD"], repo).stdout.strip()


def _branch(repo):
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()


# --------------------------------------------------------------------- #
# Handles / grant.
# --------------------------------------------------------------------- #
def _branch_req(repo, name, start_point=None):
    return _gw().BranchCreateRequest(
        name=name, expected_branch=_branch(repo), expected_head=_head(repo), start_point=start_point)


def _commit_req(repo, message, paths, *, ts=TS):
    return _gw().CommitRequest(
        message=message, paths=tuple(paths), expected_branch=_branch(repo), expected_parent=_head(repo),
        commit_timestamp=ts, author=_ident(), committer=_ident())


def _write(cap, request, repo, tmp_path, auth_store, *, pursuit_ref="pursuit-1"):
    h = _providers().resolve_git_write(cap)
    return h.write(request=request, cwd=repo, allowed_root=repo, tool_store=_tool_store(tmp_path),
                   auth_store=auth_store, pursuit_ref=pursuit_ref, project_id="p", actor="tester", clock=CLOCK)


def _grant(auth_store, *, pursuit_ref, fingerprint, capability, decision="approved", as_of=AUTH_TIME):
    ba = _ba()
    fact = ba.git_mutation_authorization_fact(
        pursuit_ref=pursuit_ref,
        gate_fingerprint=fingerprint,
        decision=decision,
        as_of=as_of,
        actor="owner",
        capability=capability,
    )
    return auth_store.record(fact)


def _fp_via_refusal(cap, request, repo, tmp_path, auth_store, *, pursuit_ref="pursuit-1"):
    out = _write(cap, request, repo, tmp_path, auth_store, pursuit_ref=pursuit_ref)
    assert out["status"] == "refused" and out["ok"] is False
    fp = out["gate_fingerprint"]
    assert isinstance(fp, str) and fp
    return fp


def _authorized_write(cap, request, repo, tmp_path, auth_store, *, pursuit_ref="pursuit-1"):
    fp = _fp_via_refusal(cap, request, repo, tmp_path, auth_store, pursuit_ref=pursuit_ref)
    _grant(auth_store, pursuit_ref=pursuit_ref, fingerprint=fp, capability=cap)
    return _write(cap, request, repo, tmp_path, auth_store, pursuit_ref=pursuit_ref)


# =================================================================== #
# A. SURFACE TYPÉE / N1
# =================================================================== #
def test_exactly_two_write_capabilities_no_third():
    gw = _gw()
    assert gw.GIT_WRITE_CAPABILITIES == ("git.branch.create", "git.commit")
    assert _providers().GIT_WRITE_CAPABILITIES == ("git.branch.create", "git.commit")
    assert _providers().GIT_WRITE_PROVIDERS == ("local_git",)


def test_unknown_write_capability_and_provider_fail_closed():
    p = _providers()
    for bad in ("git.push", "git.fetch", "git.pull", "git.checkout", "git.switch",
                "git.reset", "git.add", "command.run", "git.status"):
        with pytest.raises(LookupError):
            p.resolve_git_write(bad)
    with pytest.raises(LookupError):
        p.resolve_git_write("git.commit", provider="inconnu")


def test_no_generic_command_run():
    p = _providers()
    assert not hasattr(p, "resolve_command_run")
    assert "command.run" not in p.GIT_WRITE_CAPABILITIES


def test_write_adapter_is_inert_and_handle_only_write(tmp_path):
    p, gw = _providers(), _gw()
    h = p.resolve_git_write(gw.GIT_COMMIT)
    assert h.name == "local_git" and h.contract()
    assert hasattr(h, "write")
    for attr in ("run", "_run", "build_argv", "_build_argv", "commit", "branch_create"):
        assert not hasattr(h, attr), attr
    a = h._adapter
    for attr in ("run", "_run", "build_argv"):
        assert not hasattr(a, attr), attr
    callables = {n for n in dir(a) if not n.startswith("__") and callable(getattr(a, n))}
    assert callables == {"contract"}, callables


def test_write_contract_network_posture_not_proven(tmp_path):
    gw = _gw()
    c = _providers().resolve_git_write(gw.GIT_BRANCH_CREATE).contract().to_dict()
    assert c["cost_report"] == {"mode": "unavailable", "fabricated": False}
    assert c["native_budget"] == {"usd_cap": "none", "call_cap": "none"}
    assert c["confinement"]["network"] == {"required": False, "isolation": "not_proven"}


# =================================================================== #
# B. N2 — AUTORISATION GIT-MUTATION ADDITIVE
# =================================================================== #
def test_git_mutation_fact_type_dedicated():
    ba = _ba()
    fact = ba.git_mutation_authorization_fact(
        pursuit_ref="p1", gate_fingerprint="fp_x", decision="approved", as_of="2026-09-13T00:00:00+00:00",
        actor="owner", capability="git.commit")
    assert fact["fact_type"] == "git_mutation_authorization"
    assert fact["gate_fingerprint"] == "fp_x" and fact["decision"] == "approved" and fact["pursuit_ref"] == "p1"


def test_build_authorization_cannot_authorize_git_mutation(tmp_path):
    ba = _ba()
    store = _auth_store(tmp_path)
    # un build_authorization avec le même fingerprint ne doit PAS autoriser une mutation git
    store.record({"fact_type": "build_authorization", "pursuit_ref": "p1", "gate_fingerprint": "fp_x",
                  "decision": "approved", "as_of": "2026-09-13T00:00:00+00:00"})
    rec = ba.git_mutation_authorization_record(store, pursuit_ref="p1", gate_fingerprint="fp_x")
    assert rec is None


def test_git_mutation_not_read_as_build_authorization(tmp_path):
    ba = _ba()
    store = _auth_store(tmp_path)
    store.record(ba.git_mutation_authorization_fact(
        pursuit_ref="p1", gate_fingerprint="fp_x", decision="approved", as_of="2026-09-13T00:00:00+00:00",
        actor="owner", capability="git.commit"))
    # authorization_status L8 (build_authorization) reste aveugle au fait git_mutation
    assert ba.authorization_status(store, pursuit_ref="p1", gate_fingerprint="fp_x") == "none"


def test_git_mutation_record_absent_declined_wrongkeys(tmp_path):
    ba = _ba()
    store = _auth_store(tmp_path)
    assert ba.git_mutation_authorization_record(store, pursuit_ref="p1", gate_fingerprint="fp_x") is None
    store.record(ba.git_mutation_authorization_fact(
        pursuit_ref="p1", gate_fingerprint="fp_x", decision="declined", as_of="2026-09-13T00:00:00+00:00",
        actor="owner", capability="git.commit"))
    rec = ba.git_mutation_authorization_record(store, pursuit_ref="p1", gate_fingerprint="fp_x")
    assert rec is not None and rec["decision"] == "declined"
    assert ba.git_mutation_authorization_record(store, pursuit_ref="AUTRE", gate_fingerprint="fp_x") is None
    assert ba.git_mutation_authorization_record(store, pursuit_ref="p1", gate_fingerprint="fp_AUTRE") is None


def test_git_mutation_latest_decision_wins(tmp_path):
    ba = _ba()
    store = _auth_store(tmp_path)
    store.record(ba.git_mutation_authorization_fact(pursuit_ref="p1", gate_fingerprint="fp_x", decision="approved",
                 as_of="2026-09-13T09:00:00+00:00", actor="o", capability="git.commit"))
    store.record(ba.git_mutation_authorization_fact(pursuit_ref="p1", gate_fingerprint="fp_x", decision="declined",
                 as_of="2026-09-13T10:00:00+00:00", actor="o", capability="git.commit"))
    rec = ba.git_mutation_authorization_record(store, pursuit_ref="p1", gate_fingerprint="fp_x")
    assert rec["decision"] == "declined"          # declined postérieur annule approved antérieur


def test_git_mutation_capability_validation():
    ba = _ba()
    # git.write (famille adaptateur) refusé ; capability inconnue refusée (fail-closed)
    for bad in ("git.write", "git.push", "command.run"):
        with pytest.raises(ValueError):
            ba.git_mutation_authorization_fact(pursuit_ref="p1", gate_fingerprint="fp_x", decision="approved",
                                               as_of=AUTH_TIME, actor="o", capability=bad)
    # None accepté (champ descriptif optionnel prévu par le contrat)
    f_none = ba.git_mutation_authorization_fact(pursuit_ref="p1", gate_fingerprint="fp_x", decision="approved",
                                                as_of=AUTH_TIME, actor="o", capability=None)
    assert f_none["capability"] is None
    # capability valide enregistrée dans le fait (provenance explicite)
    for good in ("git.branch.create", "git.commit"):
        f_ok = ba.git_mutation_authorization_fact(pursuit_ref="p1", gate_fingerprint="fp_x", decision="approved",
                                                  as_of=AUTH_TIME, actor="o", capability=good)
        assert f_ok["capability"] == good


# =================================================================== #
# C. git.branch.create
# =================================================================== #
def test_branch_create_success_authorized(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    head0 = _head(repo)
    out = _authorized_write(gw.GIT_BRANCH_CREATE, _branch_req(repo, "feature"), repo, tmp_path, store)
    assert out["ok"] and out["status"] == "succeeded"
    # branche pointe exactement sur le SHA40 résolu (== HEAD ici) ; branche courante inchangée ; pas de checkout
    assert _run_git(["rev-parse", "refs/heads/feature"], repo).stdout.strip() == head0
    assert _branch(repo) == "main" and _head(repo) == head0


def test_branch_create_refused_without_go(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    out = _write(gw.GIT_BRANCH_CREATE, _branch_req(repo, "feature"), repo, tmp_path, store)
    assert out["status"] == "refused" and out["ok"] is False
    r = _run_git(["rev-parse", "--verify", "refs/heads/feature"], repo, check=False)
    assert r.returncode != 0                      # aucune branche créée


def test_branch_create_existing_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    _run_git(["branch", "feature"], repo)
    store = _auth_store(tmp_path)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_BRANCH_CREATE, _branch_req(repo, "feature"), repo, tmp_path, store)


def test_branch_create_invalid_name_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    for bad in ("-x", "a..b", "a b", "@{", "refs/heads/x", "x/", "x.lock", " включ\x01"):
        with pytest.raises(gw.GitWriteError):
            _write(gw.GIT_BRANCH_CREATE, _branch_req(repo, bad), repo, tmp_path, store)


def test_branch_create_expected_branch_mismatch_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    req = gw.BranchCreateRequest(name="feature", expected_branch="WRONG", expected_head=_head(repo))
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_BRANCH_CREATE, req, repo, tmp_path, store)


def test_branch_create_expected_head_mismatch_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    req = gw.BranchCreateRequest(name="feature", expected_branch="main", expected_head="0" * 40)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_BRANCH_CREATE, req, repo, tmp_path, store)


def test_branch_create_bad_start_point_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_BRANCH_CREATE, _branch_req(repo, "feature", start_point="deadbeef" * 5), repo, tmp_path, store)


def test_branch_create_detached_head_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    _run_git(["checkout", "--detach", "HEAD"], repo)
    store = _auth_store(tmp_path)
    req = gw.BranchCreateRequest(name="feature", expected_branch="HEAD", expected_head=_head(repo))
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_BRANCH_CREATE, req, repo, tmp_path, store)


def test_branch_create_toctou_head_moved_after_go(tmp_path, monkeypatch):
    # Vrai TOCTOU post-gate : la dérive survient APRÈS que _gate() a résolu 'approved', AVANT la mutation.
    # Exerce réellement la revalidation branche/HEAD du seam (préconditions → fingerprint → GATE approved →
    # HEAD change → revalidation TOCTOU → STOP). Distinct du test 'expected_head mismatch' (précondition d'entrée).
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    req = _branch_req(repo, "feature")
    fp = _fp_via_refusal(gw.GIT_BRANCH_CREATE, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_BRANCH_CREATE)
    real_gate = gw._gate

    def _drifting_gate(auth_store, *, pursuit_ref, fp):
        rec = real_gate(auth_store, pursuit_ref=pursuit_ref, fp=fp)
        assert rec is not None and rec["decision"] == "approved"   # GO réellement résolu...
        (repo / "drift.txt").write_text("d\n", encoding="utf-8")   # ... puis dérive HEAD APRÈS le gate
        _run_git(["add", "-A"], repo)
        _run_git(["commit", "-q", "-m", "post-gate drift"], repo)
        return rec

    monkeypatch.setattr(gw, "_gate", _drifting_gate)
    with pytest.raises(gw.GitWriteError, match="TOCTOU"):
        _write(gw.GIT_BRANCH_CREATE, req, repo, tmp_path, store)
    assert _run_git(["rev-parse", "--verify", "refs/heads/feature"], repo, check=False).returncode != 0


# =================================================================== #
# D. FINGERPRINT branch.create — sensibilité
# =================================================================== #
def test_branch_fingerprint_sensitivity():
    gw = _gw()
    base = dict(capability="git.branch.create", policy_version=gw.POLICY_VERSION, toplevel="/r", allowed_root="/r",
                expected_branch="main", expected_head="a" * 40, name="feature", start_point="HEAD",
                resolved_start_point="b" * 40, network="not_proven", hooks_policy="disabled")
    ref = gw.compute_branch_fingerprint(base)
    for k, v in [("capability", "git.commit"), ("policy_version", "x"), ("toplevel", "/o"), ("allowed_root", "/o"),
                 ("expected_branch", "dev"), ("expected_head", "c" * 40), ("name", "other"),
                 ("start_point", "dev"), ("resolved_start_point", "d" * 40), ("network", "proven"),
                 ("hooks_policy", "enabled")]:
        m = dict(base); m[k] = v
        assert gw.compute_branch_fingerprint(m) != ref, k
    assert gw.compute_branch_fingerprint(dict(base)) == ref     # déterministe


# =================================================================== #
# E. git.commit — cas autorisés + STAGING
# =================================================================== #
def test_commit_modified_file(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nchanged\n", encoding="utf-8")
    parent = _head(repo)
    out = _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "edit readme", ["README.md"]), repo, tmp_path, store)
    assert out["ok"] and out["status"] == "succeeded"
    assert _run_git(["rev-parse", "HEAD^"], repo).stdout.strip() == parent
    files = _run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], repo).stdout.split()
    assert files == ["README.md"]


def test_commit_new_file(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "NEW.txt").write_text("new\n", encoding="utf-8")
    out = _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "add new", ["NEW.txt"]), repo, tmp_path, store)
    assert out["ok"] and out["status"] == "succeeded"
    assert _run_git(["cat-file", "-e", "HEAD:NEW.txt"], repo).returncode == 0


def test_commit_delete_tracked_file(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").unlink()                 # suppression worktree d'un fichier tracké
    out = _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "del readme", ["README.md"]), repo, tmp_path, store)
    assert out["ok"] and out["status"] == "succeeded"
    assert _run_git(["cat-file", "-e", "HEAD:README.md"], repo, check=False).returncode != 0


def test_commit_identity_and_timestamp_exact(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nx\n", encoding="utf-8")
    _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "edit", ["README.md"]), repo, tmp_path, store)
    an = _run_git(["show", "-s", "--format=%an", "HEAD"], repo).stdout.strip()
    ae = _run_git(["show", "-s", "--format=%ae", "HEAD"], repo).stdout.strip()
    cn = _run_git(["show", "-s", "--format=%cn", "HEAD"], repo).stdout.strip()
    ce = _run_git(["show", "-s", "--format=%ce", "HEAD"], repo).stdout.strip()
    assert (an, ae, cn, ce) == (AUTHOR_NAME, AUTHOR_EMAIL, AUTHOR_NAME, AUTHOR_EMAIL)
    ad = _run_git(["show", "-s", "--format=%aI", "HEAD"], repo).stdout.strip()
    assert ad.startswith("2026-09-13T12:00:00")     # commit_timestamp injecté (GIT_AUTHOR_DATE)


def test_commit_path_absolute_or_traversal_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\ny\n", encoding="utf-8")
    for bad in ("/etc/passwd", "../escape.txt", "a/../../x"):
        req = gw.CommitRequest(message="m", paths=(bad,), expected_branch="main", expected_parent=_head(repo),
                               commit_timestamp=TS, author=_ident(), committer=_ident())
        with pytest.raises(gw.GitWriteError):
            _write(gw.GIT_COMMIT, req, repo, tmp_path, store)


def test_commit_symlink_path_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "link").symlink_to(repo / "README.md")
    req = gw.CommitRequest(message="m", paths=("link",), expected_branch="main", expected_parent=_head(repo),
                           commit_timestamp=TS, author=_ident(), committer=_ident())
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)


def test_commit_foreign_staged_entry_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    # un staged préexistant étranger à l'allow-list ⇒ refus, aucun commit
    (repo / "FOREIGN.txt").write_text("f\n", encoding="utf-8")
    _run_git(["add", "FOREIGN.txt"], repo)
    (repo / "README.md").write_text("hello world\nz\n", encoding="utf-8")
    with pytest.raises(gw.GitWriteError):
        _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "edit", ["README.md"]), repo, tmp_path, store)


# =================================================================== #
# F. COMMIT — invariants
# =================================================================== #
def test_commit_empty_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    # allow-list = fichier identique à HEAD ⇒ diff staged vide ⇒ refus (jamais --allow-empty)
    (repo / "README.md").write_text("hello world\n", encoding="utf-8")   # inchangé
    with pytest.raises(gw.GitWriteError):
        _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "noop", ["README.md"]), repo, tmp_path, store)


def test_commit_empty_message_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nq\n", encoding="utf-8")
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, _commit_req(repo, "", ["README.md"]), repo, tmp_path, store)


def test_commit_message_with_nul_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nq\n", encoding="utf-8")
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, _commit_req(repo, "bad\x00msg", ["README.md"]), repo, tmp_path, store)


def test_commit_parent_mismatch_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nq\n", encoding="utf-8")
    req = gw.CommitRequest(message="m", paths=("README.md",), expected_branch="main", expected_parent="0" * 40,
                           commit_timestamp=TS, author=_ident(), committer=_ident())
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)


def test_commit_detached_head_refused(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    _run_git(["checkout", "--detach", "HEAD"], repo)
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nq\n", encoding="utf-8")
    req = gw.CommitRequest(message="m", paths=("README.md",), expected_branch="HEAD", expected_parent=_head(repo),
                           commit_timestamp=TS, author=_ident(), committer=_ident())
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)


def test_commit_message_starting_with_dash_ok(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\ndash\n", encoding="utf-8")
    out = _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "--not-an-option", ["README.md"]), repo, tmp_path, store)
    assert out["ok"] and out["status"] == "succeeded"
    assert _run_git(["show", "-s", "--format=%s", "HEAD"], repo).stdout.strip() == "--not-an-option"


def test_commit_hostile_hook_not_executed(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho HOSTILE > " + str(repo / "HOOK_RAN") + "\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (repo / "README.md").write_text("hello world\nhook\n", encoding="utf-8")
    out = _authorized_write(gw.GIT_COMMIT, _commit_req(repo, "edit", ["README.md"]), repo, tmp_path, store)
    assert out["ok"] and out["status"] == "succeeded"    # hook neutralisé (core.hooksPath=/dev/null)
    assert not (repo / "HOOK_RAN").exists()


# =================================================================== #
# G. FINGERPRINT commit — sensibilité
# =================================================================== #
def test_commit_fingerprint_sensitivity():
    gw = _gw()
    base = dict(capability="git.commit", policy_version=gw.POLICY_VERSION, toplevel="/r", allowed_root="/r",
                expected_branch="main", expected_parent="a" * 40,
                paths=[{"path": "f", "state": "modified", "head_blob": "b" * 40, "worktree": "c" * 40}],
                message_sha256="d" * 64, author="Frédérique Seror <frederique@serorcreative.ch>",
                committer="Frédérique Seror <frederique@serorcreative.ch>", commit_timestamp=TS,
                allow_empty=False, hooks_policy="disabled", network="not_proven")
    ref = gw.compute_commit_fingerprint(base)
    for k, v in [("capability", "git.branch.create"), ("policy_version", "x"), ("toplevel", "/o"),
                 ("allowed_root", "/o"), ("expected_branch", "dev"), ("expected_parent", "z" * 40),
                 ("message_sha256", "e" * 64), ("author", "X <x@x>"), ("committer", "Y <y@y>"),
                 ("commit_timestamp", "2026-01-01T00:00:00+00:00"), ("network", "proven")]:
        m = dict(base); m[k] = v
        assert gw.compute_commit_fingerprint(m) != ref, k
    m = dict(base); m["paths"] = [{"path": "f", "state": "modified", "head_blob": "b" * 40, "worktree": "DIFFERENT"}]
    assert gw.compute_commit_fingerprint(m) != ref, "worktree content"
    assert gw.compute_commit_fingerprint(dict(base)) == ref


def test_commit_fingerprint_mode_and_type_sensitivity():
    # F-D3-3 : preuve PERMANENTE que type/mode participent à l'empreinte commit (mode-seul et type-seul sensibles).
    gw = _gw()
    entry = {"path": "f", "state": "modified", "type": "regular", "mode": "100644",
             "head_blob": "b" * 40, "worktree": "c" * 40}
    base = dict(capability="git.commit", policy_version=gw.POLICY_VERSION, toplevel="/r", allowed_root="/r",
                expected_branch="main", expected_parent="a" * 40, paths=[entry],
                message_sha256="d" * 64, author="X <x@x>", committer="X <x@x>",
                commit_timestamp="2026-09-14T12:00:00+00:00", allow_empty=False, hooks_policy="disabled",
                network="not_proven")
    ref = gw.compute_commit_fingerprint(base)
    assert gw.compute_commit_fingerprint(dict(base)) == ref                  # même matériel ⇒ même empreinte
    m_mode = dict(base); m_mode["paths"] = [dict(entry, mode="100755")]      # SEUL le mode change
    assert gw.compute_commit_fingerprint(m_mode) != ref, "mode-seul doit changer l'empreinte (F-D3-3)"
    m_type = dict(base); m_type["paths"] = [dict(entry, type="absent")]      # SEUL le type change
    assert gw.compute_commit_fingerprint(m_type) != ref, "type-seul doit changer l'empreinte (F-D3-3)"


# =================================================================== #
# H. TOCTOU commit
# =================================================================== #
def test_commit_toctou_content_changed_after_go(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nv1\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    (repo / "README.md").write_text("hello world\nV2-DRIFT\n", encoding="utf-8")   # contenu change après GO
    out = _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert out["ok"] is False and out["status"] in ("refused",)
    assert _head(repo) == req.expected_parent      # aucun commit


# =================================================================== #
# K. N4 — provenance
# =================================================================== #
def test_provenance_recorded_on_success(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    ts = _tool_store(tmp_path)
    (repo / "README.md").write_text("hello world\nprov\n", encoding="utf-8")
    fp = _fp_via_refusal(gw.GIT_COMMIT, _commit_req(repo, "edit", ["README.md"]), repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    h = _providers().resolve_git_write(gw.GIT_COMMIT)
    out = h.write(request=_commit_req(repo, "edit", ["README.md"]), cwd=repo, allowed_root=repo, tool_store=ts,
                  auth_store=store, pursuit_ref="pursuit-1", project_id="p", actor="tester", clock=CLOCK)
    assert out["ok"]
    facts = ts.read_all()
    assert facts, "provenance obligatoire"
    f = facts[-1]
    assert f["tool"] == "local_git:git.commit"
    assert out["authorization"]["decision"] == "approved"
    assert out["gate_fingerprint"] == fp


def test_provenance_no_secret_leak(tmp_path):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    ts = _tool_store(tmp_path)
    token = "sk-COMMITSECRET1234567"
    (repo / "README.md").write_text("hello world\n" + token + "\n", encoding="utf-8")
    fp = _fp_via_refusal(gw.GIT_COMMIT, _commit_req(repo, "edit " + token, ["README.md"]), repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    h = _providers().resolve_git_write(gw.GIT_COMMIT)
    h.write(request=_commit_req(repo, "edit " + token, ["README.md"]), cwd=repo, allowed_root=repo, tool_store=ts,
            auth_store=store, pursuit_ref="pursuit-1", project_id="p", actor="tester", clock=CLOCK)
    for f in ts.read_all():
        assert token not in f.get("stdout", "") and token not in f.get("stderr", "")


# =================================================================== #
# L / M. contrat N6 + N5
# =================================================================== #
def test_no_bridge_to_cognitive_stack():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(_gw()))
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
    forbidden = ("reasoning", "decision", "execution", "cognition", "planning")
    for m in mods:
        assert not any(f in m for f in forbidden), m
    assert all(m.startswith("scc_brainai_bootstrap.builder") or m.startswith("scc_brainai_bootstrap.core")
               or m.startswith("brainai_app") is False and ("." not in m or m in ("__future__",))
               or m.startswith("scc_brainai_bootstrap.builder") for m in mods), mods


def test_argv_builders_no_remote_or_force(tmp_path):
    gw = _gw()
    bc = gw.branch_create_argv("feature", "a" * 40)
    assert "branch" in bc and "-f" not in bc and "--force" not in bc
    assert not any(t in bc for t in ("checkout", "switch", "push", "fetch", "remote"))
    ap = gw.add_paths_argv(("README.md",))
    assert ap[:2] != ["git", "add"] or "--" in ap        # add doit passer par -- <paths>
    assert "-A" not in ap and "." not in ap
    cm = gw.commit_argv("msg")
    assert "commit" in cm and "-a" not in cm and "--amend" not in cm and "--allow-empty" not in cm


# =================================================================== #
# N. NON-RÉGRESSION L10.1 (surface read intacte)
# =================================================================== #
def test_l10_1_read_surface_unchanged():
    p = _providers()
    assert p.GIT_READ_CAPABILITIES == ("git.status", "git.diff", "git.branches.list")
    assert p.GIT_READ_PROVIDERS == ("local_git",)
    h = p.resolve_git_read("git.status")
    assert hasattr(h, "read") and not hasattr(h, "write")


# =================================================================== #
# CORRECTIONS ARBITRAGE — F-D3-1 (provenance durable), F-D3-2 (blob/mode staged),
# F-D3-4 (TOCTOU commit post-gate), F-D3-5 (rollback / failed_dirty_index), F-D3-6 (postcondition).
# =================================================================== #
def _rev(repo):
    return _run_git(["rev-parse", "HEAD"], repo).stdout.strip()


def _is_add(argv):
    return argv[:3] == ["git", "--no-optional-locks", "--no-pager"] and "add" in argv


def _is_commit(argv):
    return argv[:3] == ["git", "--no-optional-locks", "--no-pager"] and "commit" in argv


def _index_clean(repo):
    return _run_git(["diff", "--cached", "--quiet"], repo, check=False).returncode == 0


# ---- F-D3-1 : provenance DURABLE corrélée (refused + commit_created) relue depuis le store ----
def test_provenance_durable_correlates_go(tmp_path):
    repo = _mkrepo(tmp_path)
    gw, ba = _gw(), _ba()
    store = _auth_store(tmp_path)
    ts = _tool_store(tmp_path)
    (repo / "README.md").write_text("hello world\ndur\n", encoding="utf-8")
    h = _providers().resolve_git_write(gw.GIT_COMMIT)

    def _w():
        return h.write(request=_commit_req(repo, "edit", ["README.md"]), cwd=repo, allowed_root=repo,
                       tool_store=ts, auth_store=store, pursuit_ref="pursuit-1", project_id="p",
                       actor="t", clock=CLOCK)

    out_ref = _w()
    assert out_ref["status"] == "refused"
    fp = out_ref["gate_fingerprint"]
    provs_ref = ba.git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    assert any(p["outcome"] == "refused" and p["authorization_ref"] is None
               and p["invocation_ref"] == out_ref["tool_ref"] for p in provs_ref)

    rec = store.record(ba.git_mutation_authorization_fact(
        pursuit_ref="pursuit-1", gate_fingerprint=fp, decision="approved", as_of=AUTH_TIME,
        actor="o", capability=gw.GIT_COMMIT))
    out = _w()
    assert out["ok"] and out["status"] == "succeeded"
    store2 = ba.BuildAuthorizationStore(store.path)          # relecture DURABLE (nouveau handle, même fichier)
    succ = [p for p in ba.git_mutation_provenance_records(store2, pursuit_ref="pursuit-1", gate_fingerprint=fp)
            if p["outcome"] == "commit_created"]
    assert len(succ) == 1
    s = succ[0]
    assert s["invocation_ref"] == out["tool_ref"]
    assert s["authorization_ref"] == rec["authorization_id"] == out["authorization"]["id"]
    assert s["decision"] == "approved" and s["authorization_as_of"] == AUTH_TIME
    assert s["capability"] == "git.commit" and s["pursuit_ref"] == "pursuit-1"


# ---- F-D3-2 : blob staged différent du matériel autorisé -> rollback + refus ----
def test_commit_staged_blob_mismatch_rolled_back(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nv1\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        if _is_add(argv):
            (repo / "README.md").write_text("hello world\nBLOB-DRIFT\n", encoding="utf-8")
        return real(argv, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert _rev(repo) == req.expected_parent
    assert _index_clean(repo)
    provs = _ba().git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    assert any(p["outcome"] == "failed_rolled_back" for p in provs)


# ---- F-D3-2 : mode staged différent -> rollback + refus ----
def test_commit_staged_mode_mismatch_rolled_back(tmp_path, monkeypatch):
    import os
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nmode\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        if _is_add(argv):
            os.chmod(repo / "README.md", 0o755)
        return real(argv, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert _rev(repo) == req.expected_parent
    assert _index_clean(repo)


# ---- F-D3-4 : vrai TOCTOU commit POST-GATE (drift contenu après approved, avant mutation) ----
def test_commit_toctou_post_gate(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nv1\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real_gate = gw._gate

    def drift_gate(auth_store, *, pursuit_ref, fp):
        rec = real_gate(auth_store, pursuit_ref=pursuit_ref, fp=fp)
        assert rec is not None and rec["decision"] == "approved"
        (repo / "README.md").write_text("hello world\nDRIFT-AFTER-GO\n", encoding="utf-8")
        return rec

    monkeypatch.setattr(gw, "_gate", drift_gate)
    with pytest.raises(gw.GitWriteError, match="TOCTOU"):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert _rev(repo) == req.expected_parent
    assert _index_clean(repo)


# ---- F-D3-5 : git add ERROR -> rollback + failed_rolled_back ----
def test_commit_git_add_error_rolled_back(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\nadderr\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        if _is_add(argv):
            return {"exit_code": 1, "stdout": "", "stderr": "add boom", "timed_out": False}
        return real(argv, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert _rev(repo) == req.expected_parent
    assert _index_clean(repo)
    provs = _ba().git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    assert any(p["outcome"] == "failed_rolled_back" for p in provs)


# ---- F-D3-5 : git add TIMEOUT -> rollback + failed_rolled_back ----
def test_commit_git_add_timeout_rolled_back(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\naddto\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        if _is_add(argv):
            return {"exit_code": 124, "stdout": "", "stderr": "", "timed_out": True}
        return real(argv, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert _rev(repo) == req.expected_parent
    assert _index_clean(repo)
    provs = _ba().git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    assert any(p["outcome"] == "failed_rolled_back" for p in provs)


# ---- F-D3-5 : git commit ERROR -> rollback + failed_rolled_back ----
def test_commit_git_commit_error_rolled_back(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\ncmterr\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        if _is_commit(argv):
            return {"exit_code": 1, "stdout": "", "stderr": "commit boom", "timed_out": False}
        return real(argv, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    with pytest.raises(gw.GitWriteError):
        _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert _rev(repo) == req.expected_parent
    assert _index_clean(repo)
    provs = _ba().git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    assert any(p["outcome"] == "failed_rolled_back" for p in provs)


# ---- F-D3-5 : rollback impossible -> failed_dirty_index (jamais masqué) ----
def test_commit_failed_dirty_index(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\ndirty\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        if _is_commit(argv):
            return {"exit_code": 1, "stdout": "", "stderr": "commit boom", "timed_out": False}
        return real(argv, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    monkeypatch.setattr(gw, "_rollback_index", lambda repo, paths, timeout: False)
    out = _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert out["ok"] is False and out["status"] == "failed_dirty_index"
    assert _rev(repo) == req.expected_parent
    provs = _ba().git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    assert any(p["outcome"] == "failed_dirty_index" for p in provs)


# ---- F-D3-6 : commit créé mais postcondition échoue -> aucun reset auto, SHA conservé ----
def test_commit_postcondition_failed_no_reset(tmp_path, monkeypatch):
    repo = _mkrepo(tmp_path)
    gw = _gw()
    store = _auth_store(tmp_path)
    (repo / "README.md").write_text("hello world\npostc\n", encoding="utf-8")
    req = _commit_req(repo, "edit", ["README.md"])
    fp = _fp_via_refusal(gw.GIT_COMMIT, req, repo, tmp_path, store)
    _grant(store, pursuit_ref="pursuit-1", fingerprint=fp, capability=gw.GIT_COMMIT)
    real = gw._safe_run

    def wrapped(argv, *, cwd, timeout, env=None):
        r = real(argv, cwd=cwd, timeout=timeout, env=env)
        if "diff-tree" in argv:
            return {**r, "stdout": "UNEXPECTED_FILE\n"}
        return r

    monkeypatch.setattr(gw, "_safe_run", wrapped)
    out = _write(gw.GIT_COMMIT, req, repo, tmp_path, store)
    assert out["status"] == "postcondition_failed_commit_created" and out["ok"] is False
    assert out["commit_sha"] and _rev(repo) == out["commit_sha"]
    assert _rev(repo) != req.expected_parent
    provs = _ba().git_mutation_provenance_records(store, pursuit_ref="pursuit-1", gate_fingerprint=fp)
    oc = [p["outcome"] for p in provs]
    assert "postcondition_failed_commit_created" in oc and "commit_created" not in oc
