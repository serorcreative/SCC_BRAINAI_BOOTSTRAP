"""Capacités **Git en MUTATION LOCALE** typées (L10.2) — Software Control Plane, classe M (MUTATE, locale).

EXACTEMENT deux capacités : ``git.branch.create`` et ``git.commit``. CONNECTER, PAS RECONSTRUIRE : réutilise le
**même** sous-processus confiné (:func:`run_confined` via :func:`_safe_run`), les primitives de safety/confinement
factorisées (:mod:`git_common`), la provenance N4 (:class:`ToolInvocationStore` + fait durable
``git_mutation_provenance``), la redaction RV-1 (:func:`redact`) et le journal d'autorisation N2
(``git_mutation_authorization_*``). Aucun ``command.run`` générique, aucune remote, aucun réseau, aucun shell.

**Gate N2 co-localisé (un-bypassable).** L'unique lieu d'exécution mutante est :func:`produce_git_write` ; le gate
(relecture de l'autorisation à l'instant exact, exige ``approved``) y est **immédiatement avant** la première
mutation. Ni l'adaptateur (INERTE), ni le provider, ni l'UI ne peuvent muter directement.

**Provenance durable (F-D3-1).** Chaque issue significative (refused / failed_rolled_back / failed_dirty_index /
branch_created / commit_created / postcondition_failed_commit_created) est **persistée** via
``git_mutation_provenance_fact`` dans le journal de gouvernance, corrélant ``invocation_ref`` (ToolInvocation) à
l'autorisation consommée (``authorization_ref``/``gate_fingerprint``/``decision``).

**Staging exact (F-D3-2).** Après ``git add -- <paths>`` et AVANT commit : vérification objective du **name-set**,
du **mode** et du **blob** staged (``ls-files --stage``) contre le matériel autorisé (blob = ``hash-object
--no-filters``, aucun filtre externe). Toute divergence ⇒ rollback + refus.

**Empreinte (F-D3-3).** Le matériel de chaque chemin couvre ``path/state/type/mode/head_blob/worktree`` : un
changement de mode seul modifie l'empreinte.

**Durcissement :** ``-c core.hooksPath=/dev/null`` (aucun hook), ``-c commit.gpgsign=false`` ; identité de commit
**explicite** (``GIT_AUTHOR_*``/``GIT_COMMITTER_*`` — jamais la config globale/HOME) ; ``commit_timestamp`` ISO-8601
UTC injecté (``GIT_AUTHOR_DATE``/``GIT_COMMITTER_DATE``). Staging allow-list exacte (jamais ``-A``/``.``/``-a``).
Commit vide INTERDIT (jamais ``--allow-empty``). ``--amend`` interdit.

**N6 :** ``network_required=false`` ≠ ``network_isolation=proven``. Import-isolé : ``builder`` + ``core`` + stdlib
(aucun pont 13/15/16 — N5).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract
from scc_brainai_bootstrap.builder.build_authorization import (
    git_mutation_authorization_record, git_mutation_provenance_fact)
from scc_brainai_bootstrap.builder.claude_code_runtime import DIAG_MAX, redact
from scc_brainai_bootstrap.builder.git_common import (
    GIT_PREFIX, git_env, confined_repo as _common_confined_repo,
    reject_content_filters as _common_reject_content_filters)
from scc_brainai_bootstrap.builder.tool_runner import DEFAULT_WATCHDOG_S, run_confined
from scc_brainai_bootstrap.core.clock import digest

PROVIDER_NAME = "local_git"
GIT_BRANCH_CREATE = "git.branch.create"
GIT_COMMIT = "git.commit"
GIT_WRITE_CAPABILITIES = (GIT_BRANCH_CREATE, GIT_COMMIT)
POLICY_VERSION = "l10.2/v1"
MESSAGE_MAX_BYTES = 4096                             # borne explicite du message (politique L10.2)

# Préfixe **mutant** durci : hooks + signature neutralisés (au-delà du prefixe lecture L10.1).
GIT_WRITE_PREFIX = GIT_PREFIX + ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false"]

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
# Caractères/motifs interdits dans un nom de branche (v1, least-privilege). Le "/" est refusé séparément.
_BAD_BRANCH = re.compile(r"[\x00-\x20~^:?*\[\\]|@\{|\.\.|\.lock$|^\.|\.$")


class GitWriteError(ValueError):
    """Refus **fail-closed** d'une mutation git (confinement, préconditions, TOCTOU, staging, index sale, git absent)."""


class GitWriteGateError(GitWriteError):
    """Refus **N2** : aucune autorisation USER GO valide pour l'empreinte matérielle courante (sous-type dédié)."""


# --------------------------------------------------------------------- #
# Requêtes typées (immuables).
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class Identity:
    name: str
    email: str


DEFAULT_IDENTITY = Identity("Frédérique Seror", "frederique@serorcreative.ch")


@dataclass(frozen=True)
class BranchCreateRequest:
    name: str
    expected_branch: str
    expected_head: str
    start_point: Optional[str] = None          # None ⇒ HEAD (SHA40 résolu et figé dans l'empreinte)


@dataclass(frozen=True)
class CommitRequest:
    message: str
    paths: Tuple[str, ...]                     # allow-list EXACTE (repo-relative)
    expected_branch: str
    expected_parent: str
    commit_timestamp: str                      # ISO-8601 UTC (figé, participe à l'empreinte)
    author: Identity = DEFAULT_IDENTITY
    committer: Identity = DEFAULT_IDENTITY


# --------------------------------------------------------------------- #
# Constructeurs d'argv typés (N1).
# --------------------------------------------------------------------- #
def branch_create_argv(name: str, resolved_start_point: str) -> List[str]:
    """``git branch <name> <SHA40>`` — création **sans checkout/switch**, jamais ``-f``/``--force``."""
    return GIT_WRITE_PREFIX + ["branch", name, resolved_start_point]


def add_paths_argv(paths: Tuple[str, ...]) -> List[str]:
    """``git add -- <paths exacts>`` — allow-list stricte ; jamais ``-A``/``.``/pathspec large."""
    return GIT_PREFIX + ["add", "--", *paths]


def commit_argv(message: str) -> List[str]:
    """``git commit --no-verify -m <message>`` (argv séparé — message commençant par ``-`` non ambigu) ;
    jamais ``-a``/``--amend``/``--allow-empty``. Hooks/signature neutralisés par :data:`GIT_WRITE_PREFIX`."""
    return GIT_WRITE_PREFIX + ["commit", "--no-verify", "-m", message]


# --------------------------------------------------------------------- #
# Empreintes matérielles (pures). digest() canonique réutilisé (build_authorization).
# --------------------------------------------------------------------- #
def compute_branch_fingerprint(material: Dict[str, Any]) -> str:
    canon = {k: material.get(k) for k in (
        "capability", "policy_version", "toplevel", "allowed_root", "expected_branch", "expected_head",
        "name", "start_point", "resolved_start_point", "network", "hooks_policy")}
    return "gbfp_" + digest(canon)


def compute_commit_fingerprint(material: Dict[str, Any]) -> str:
    canon = {k: material.get(k) for k in (
        "capability", "policy_version", "toplevel", "allowed_root", "expected_branch", "expected_parent",
        "message_sha256", "author", "committer", "commit_timestamp", "allow_empty", "hooks_policy", "network")}
    paths = sorted((material.get("paths") or []), key=lambda d: str(d.get("path")))
    canon["paths"] = [{"path": d.get("path"), "state": d.get("state"), "type": d.get("type"),
                       "mode": d.get("mode"), "head_blob": d.get("head_blob"),
                       "worktree": d.get("worktree")} for d in paths]
    return "gcfp_" + digest(canon)


# --------------------------------------------------------------------- #
# Runner confiné (env durci par défaut ; env explicite pour commit). Monkeypatch seam : run_confined module-global.
# --------------------------------------------------------------------- #
def _safe_run(argv: List[str], *, cwd: Path, timeout: float, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    try:
        return run_confined(argv, cwd=cwd, timeout=timeout, env=env if env is not None else git_env())
    except (FileNotFoundError, OSError) as exc:
        raise GitWriteError(f"git introuvable ou non exécutable : {exc}") from exc


def _head_sha(repo: Path, timeout: float) -> str:
    r = _safe_run(["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=repo, timeout=timeout)
    if r["timed_out"] or r["exit_code"] != 0 or not (r["stdout"] or "").strip():
        raise GitWriteError("HEAD indéterminé (dépôt git invalide)")
    return r["stdout"].strip()


def _current_branch(repo: Path, timeout: float) -> Optional[str]:
    """Branche courante via ``symbolic-ref -q HEAD`` : nom court si attaché, ``None`` si **detached HEAD**."""
    r = _safe_run(["git", "--no-optional-locks", "symbolic-ref", "-q", "HEAD"], cwd=repo, timeout=timeout)
    if r["timed_out"]:
        raise GitWriteError("symbolic-ref HEAD timeout (fail-closed)")
    if r["exit_code"] == 0:
        ref = (r["stdout"] or "").strip()
        return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
    return None


def _provenance(tool_store: Any, *, project_id: str, capability: str, argv: List[str], cwd: Path,
                status: str, res: Optional[Dict[str, Any]], as_of: str) -> Dict[str, Any]:
    """Fait ToolInvocation (N4), **secret-safe** : argv/stdout/stderr redactés + bornés."""
    exit_code: Any = None
    stdout = stderr = ""
    timed_out = False
    if res is not None:
        exit_code = res.get("exit_code")
        timed_out = bool(res.get("timed_out"))
        stdout = (redact(res.get("stdout") or "") or "")[:DIAG_MAX]
        stderr = (redact(res.get("stderr") or "") or "")[:DIAG_MAX]
    return tool_store.record(
        project_id=project_id, tool=f"{PROVIDER_NAME}:{capability}",
        argv=[redact(a) for a in argv], cwd=str(cwd), status=status, exit_code=exit_code,
        stdout=stdout, stderr=stderr, timed_out=timed_out, as_of=as_of)


def _persist_provenance(auth_store: Any, *, invocation_id: str, pursuit_ref: str, fp: str, capability: str,
                        outcome: str, authorization: Optional[Dict[str, Any]], as_of: str) -> None:
    """Persiste (F-D3-1) le fait DURABLE ``git_mutation_provenance`` corrélant ``invocation_ref`` à l'autorisation
    consommée et à l'issue. Pour toute issue POST-GO, ``authorization`` (dict ``{id, decision, as_of}`` du GO
    approuvé) est obligatoire côté ``git_mutation_provenance_fact`` (fail-closed)."""
    fact = git_mutation_provenance_fact(
        invocation_ref=invocation_id, pursuit_ref=pursuit_ref, gate_fingerprint=fp, capability=capability,
        outcome=outcome, as_of=as_of,
        authorization_ref=(authorization["id"] if authorization else None),
        decision=(authorization["decision"] if authorization else None),
        authorization_as_of=(authorization["as_of"] if authorization else None))
    auth_store.record(fact)


def _authorization(rec: Dict[str, Any], *, pursuit_ref: str, fp: str) -> Dict[str, Any]:
    return {"id": rec.get("authorization_id"), "decision": rec.get("decision"),
            "as_of": rec.get("as_of"), "pursuit_ref": pursuit_ref, "gate_fingerprint": fp}


# --------------------------------------------------------------------- #
# Validation nom de branche / chemins / timestamp / mode.
# --------------------------------------------------------------------- #
def _validate_branch_name(name: str, *, cwd: Path, timeout: float) -> None:
    if not isinstance(name, str) or not name:
        raise GitWriteError("nom de branche vide (fail-closed)")
    if name != name.strip():
        raise GitWriteError("nom de branche à espaces de bord (fail-closed)")
    if name.startswith("-"):
        raise GitWriteError(f"nom de branche commençant par '-' interdit : {name!r}")
    if "/" in name:
        raise GitWriteError(f"'/' interdit dans un nom de branche v1 (ref ambiguë) : {name!r}")
    if _BAD_BRANCH.search(name):
        raise GitWriteError(f"nom de branche invalide : {name!r}")
    r = _safe_run(["git", "--no-optional-locks", "check-ref-format", "refs/heads/" + name],
                  cwd=cwd, timeout=timeout)
    if r["timed_out"] or r["exit_code"] != 0:
        raise GitWriteError(f"check-ref-format rejette le nom : {name!r} (fail-closed)")


def _validate_commit_path(rel: str, *, toplevel: Path) -> None:
    if not isinstance(rel, str) or not rel:
        raise GitWriteError("chemin vide (fail-closed)")
    if "\x00" in rel:
        raise GitWriteError("chemin contenant un octet nul (fail-closed)")
    if rel.startswith("/"):
        raise GitWriteError(f"chemin absolu interdit : {rel!r}")
    if rel != rel.strip():
        raise GitWriteError(f"chemin à espaces de bord : {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise GitWriteError(f"chemin avec traversal/segment vide interdit : {rel!r}")
    cur = toplevel
    for p in parts:                                    # aucun symlink dans la chaîne d'ancêtres ni la cible
        cur = cur / p
        if cur.is_symlink():
            raise GitWriteError(f"symlink dans le chemin interdit : {rel!r}")
    target = toplevel / rel
    if target.exists():
        if target.is_symlink():
            raise GitWriteError(f"cible symlink interdite : {rel!r}")
        if target.is_dir():
            raise GitWriteError(f"chemin est un répertoire (non régulier) : {rel!r}")
        if not target.is_file():
            raise GitWriteError(f"chemin de type non régulier interdit : {rel!r}")


def _validate_timestamp(ts: str) -> None:
    if not isinstance(ts, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)", ts):
        raise GitWriteError(f"commit_timestamp invalide (ISO-8601 UTC requis) : {ts!r}")


def _expected_mode(target: Path) -> str:
    """Mode git attendu d'un fichier régulier du worktree : ``100755`` si exécutable, sinon ``100644``."""
    return "100755" if (target.stat().st_mode & 0o111) else "100644"


# --------------------------------------------------------------------- #
# Contrat T2 (classe M locale) + adaptateur INERTE + handle (voie publique unique).
# --------------------------------------------------------------------- #
def _git_write_contract() -> AdapterContract:
    return AdapterContract(
        capabilities_served=GIT_WRITE_CAPABILITIES,
        auth_channel={"kind": "none", "explicit": True, "leaks_identity": False,
                      "detail": "mutation git locale — identité de commit explicite, aucun fournisseur externe"},
        inbound_channels=(),
        cost_report={"mode": "unavailable", "fabricated": False},
        native_budget={"usd_cap": "none", "call_cap": "none"},
        confinement={"workspace": True, "tools_allowed": ["git:mutating-local"],
                     "tools_disallowed": ["git:remote", "git:read-arbitrary", "shell",
                                          "git:content-filter", "git:hooks", "git:gpg"],
                     "permission_mode": "local+confined+gated+no-hooks+no-gpg", "env_mode": "none",
                     "network": {"required": False, "isolation": "not_proven"}},
    )


class LocalGitWriteAdapter:
    """Exécutant **INERTE** (L10.2, F-6.1) : aucune méthode d'exécution. Seul ``contract()`` est callable ;
    l'exécution mutante vit exclusivement dans :func:`produce_git_write` / :meth:`GitWriteHandle.write`."""

    capability = "git.write"
    name = PROVIDER_NAME
    model = "git"

    def __init__(self) -> None:
        self.max_budget_usd = 0.0

    def contract(self) -> AdapterContract:
        return _git_write_contract()


class GitWriteHandle:
    """**Voie d'exécution PUBLIQUE unique** d'une capacité git-write (F-6.1). N'expose aucun ``run``/``_run`` :
    la seule mutation possible est :meth:`write`, qui passe **obligatoirement** par :func:`produce_git_write`."""

    def __init__(self, adapter: LocalGitWriteAdapter, capability: str) -> None:
        self._adapter = adapter
        self.capability = capability
        self.provider = adapter.name
        self.name = adapter.name

    def contract(self) -> AdapterContract:
        return self._adapter.contract()

    def write(self, *, request: Any, cwd: Any, allowed_root: Any, tool_store: Any, auth_store: Any,
              pursuit_ref: str, project_id: str, actor: Any = None, clock: Callable[[], str],
              timeout: float = DEFAULT_WATCHDOG_S) -> Dict[str, Any]:
        return produce_git_write(capability=self.capability, adapter=self._adapter, request=request, cwd=cwd,
                                 allowed_root=allowed_root, tool_store=tool_store, auth_store=auth_store,
                                 pursuit_ref=pursuit_ref, project_id=project_id, actor=actor, clock=clock,
                                 timeout=timeout)


# --------------------------------------------------------------------- #
# Seam mutant UNIQUE.
# --------------------------------------------------------------------- #
def produce_git_write(*, capability: str, adapter: LocalGitWriteAdapter, request: Any, cwd: Any, allowed_root: Any,
                      tool_store: Any, auth_store: Any, pursuit_ref: str, project_id: str, actor: Any = None,
                      clock: Callable[[], str], timeout: float = DEFAULT_WATCHDOG_S) -> Dict[str, Any]:
    """Chemin **normal unique** d'une mutation git locale typée. Ordre : confinement (allowed_root obligatoire) →
    préconditions READ fail-closed → empreinte matérielle → **gate N2** (relecture instantanée ; ``approved``
    exigé, sinon ``refused`` sans mutation) → re-vérification TOCTOU → mutation confinée UNIQUE → provenance N4
    durable → postconditions. ``allowed_root``/``auth_store``/``pursuit_ref`` sont **obligatoires**."""
    if capability not in GIT_WRITE_CAPABILITIES:
        raise GitWriteError(f"capacité git-write inconnue : {capability!r} (admis ∈ {GIT_WRITE_CAPABILITIES})")
    if not isinstance(pursuit_ref, str) or not pursuit_ref.strip():
        raise GitWriteError("pursuit_ref obligatoire (chaîne non vide) — fail-closed")
    info = _common_confined_repo(cwd, allowed_root=allowed_root, timeout=timeout, run=_safe_run, err=GitWriteError)
    root_str = str(Path(allowed_root).resolve())
    if capability == GIT_BRANCH_CREATE:
        return _do_branch_create(request, info, root_str, tool_store=tool_store, auth_store=auth_store,
                                 pursuit_ref=pursuit_ref, project_id=project_id, clock=clock, timeout=timeout)
    return _do_commit(request, info, root_str, tool_store=tool_store, auth_store=auth_store,
                      pursuit_ref=pursuit_ref, project_id=project_id, clock=clock, timeout=timeout)


def _gate(auth_store: Any, *, pursuit_ref: str, fp: str) -> Optional[Dict[str, Any]]:
    """Relecture N2 à l'instant exact : renvoie le fait d'autorisation SI ``approved``, sinon ``None`` (refus)."""
    rec = git_mutation_authorization_record(auth_store, pursuit_ref=pursuit_ref, gate_fingerprint=fp)
    if rec is None or rec.get("decision") != "approved":
        return None
    return rec


def _refused(capability: str, fp: str, *, tool_store: Any, auth_store: Any, project_id: str, pursuit_ref: str,
             cwd: Path, clock: Callable[[], str]) -> Dict[str, Any]:
    as_of = clock()
    tf = _provenance(tool_store, project_id=project_id, capability=capability, argv=[], cwd=cwd,
                     status="refused", res=None, as_of=as_of)
    _persist_provenance(auth_store, invocation_id=tf["invocation_id"], pursuit_ref=pursuit_ref, fp=fp,
                        capability=capability, outcome="refused", authorization=None, as_of=as_of)
    return {"capability": capability, "provider": PROVIDER_NAME, "ok": False, "status": "refused",
            "gate_fingerprint": fp, "authorization": None, "created_ref": None, "commit_sha": None,
            "tool_ref": tf["invocation_id"], "as_of": as_of}


def _branch_material(request: Any, info: Dict[str, Path], root_str: str, sp: str, resolved_sp: str) -> Dict[str, Any]:
    return {"capability": GIT_BRANCH_CREATE, "policy_version": POLICY_VERSION,
            "toplevel": str(info["toplevel"]), "allowed_root": root_str,
            "expected_branch": request.expected_branch, "expected_head": request.expected_head,
            "name": request.name, "start_point": sp, "resolved_start_point": resolved_sp,
            "network": "not_proven", "hooks_policy": "disabled"}


def _resolve_start_point(sp: str, *, repo: Path, timeout: float) -> str:
    r = _safe_run(["git", "--no-optional-locks", "rev-parse", "--verify", "--end-of-options", sp + "^{commit}"],
                  cwd=repo, timeout=timeout)
    val = (r["stdout"] or "").strip()
    if r["timed_out"] or r["exit_code"] != 0 or not _HEX40.match(val):
        raise GitWriteError(f"start_point invalide/irrésoluble : {sp!r}")
    return val


def _branch_absent_or_fail(repo: Path, name: str, timeout: float) -> None:
    r = _safe_run(["git", "--no-optional-locks", "show-ref", "--verify", "--quiet", "refs/heads/" + name],
                  cwd=repo, timeout=timeout)
    if r["timed_out"]:
        raise GitWriteError("show-ref timeout (fail-closed)")
    rc = r["exit_code"]
    if rc == 0:
        raise GitWriteError(f"branche déjà existante : {name!r}")
    if rc != 1:
        raise GitWriteError(f"show-ref RC={rc} inattendu (fail-closed — jamais 'absente' générique)")


def _do_branch_create(request: Any, info: Dict[str, Path], root_str: str, *, tool_store: Any, auth_store: Any,
                      pursuit_ref: str, project_id: str, clock: Callable[[], str], timeout: float) -> Dict[str, Any]:
    repo = info["cwd"]
    # (1) préconditions READ fail-closed
    cur = _current_branch(repo, timeout)
    if cur is None:
        raise GitWriteError("detached HEAD interdit pour git.branch.create (L10.2 v1)")
    if cur != request.expected_branch:
        raise GitWriteError(f"branche courante {cur!r} != expected_branch {request.expected_branch!r}")
    head = _head_sha(repo, timeout)
    if head != request.expected_head:
        raise GitWriteError("HEAD != expected_head (fail-closed)")
    _validate_branch_name(request.name, cwd=repo, timeout=timeout)
    _branch_absent_or_fail(repo, request.name, timeout)
    sp = request.start_point if request.start_point is not None else "HEAD"
    resolved_sp = _resolve_start_point(sp, repo=repo, timeout=timeout)
    # (2) empreinte matérielle
    fp = compute_branch_fingerprint(_branch_material(request, info, root_str, sp, resolved_sp))
    # (3) gate N2
    rec = _gate(auth_store, pursuit_ref=pursuit_ref, fp=fp)
    if rec is None:
        return _refused(GIT_BRANCH_CREATE, fp, tool_store=tool_store, auth_store=auth_store, project_id=project_id,
                        pursuit_ref=pursuit_ref, cwd=repo, clock=clock)
    auth = _authorization(rec, pursuit_ref=pursuit_ref, fp=fp)
    # (4) re-vérification TOCTOU immédiate
    if _current_branch(repo, timeout) != request.expected_branch or _head_sha(repo, timeout) != request.expected_head:
        raise GitWriteError("TOCTOU : branche/HEAD modifiés après autorisation — STOP sans mutation")
    _branch_absent_or_fail(repo, request.name, timeout)
    if _resolve_start_point(sp, repo=repo, timeout=timeout) != resolved_sp:
        raise GitWriteError("TOCTOU : start_point re-résolu différent — STOP sans mutation")
    # (5) mutation UNIQUE
    argv = branch_create_argv(request.name, resolved_sp)
    res = _safe_run(argv, cwd=repo, timeout=timeout)
    as_of = clock()
    status = "timeout" if res["timed_out"] else ("succeeded" if res["exit_code"] == 0 else "failed")
    tf = _provenance(tool_store, project_id=project_id, capability=GIT_BRANCH_CREATE, argv=argv, cwd=repo,
                     status=status, res=res, as_of=as_of)
    base = {"capability": GIT_BRANCH_CREATE, "provider": PROVIDER_NAME, "gate_fingerprint": fp,
            "authorization": auth, "tool_ref": tf["invocation_id"], "as_of": as_of, "commit_sha": None}
    if status != "succeeded":
        # échec de la commande git branch (post-gate, aucune branche créée) : ToolInvocation trace l'échec.
        return {**base, "ok": False, "status": status, "created_ref": None}
    # (6) postconditions
    chk = _safe_run(["git", "--no-optional-locks", "rev-parse", "--verify", "refs/heads/" + request.name],
                    cwd=repo, timeout=timeout)
    created = (chk["stdout"] or "").strip()
    if chk["exit_code"] != 0 or created != resolved_sp \
            or _current_branch(repo, timeout) != request.expected_branch or _head_sha(repo, timeout) != head:
        _persist_provenance(auth_store, invocation_id=tf["invocation_id"], pursuit_ref=pursuit_ref, fp=fp,
                            capability=GIT_BRANCH_CREATE, outcome="postcondition_failed_branch_created",
                            authorization=auth, as_of=as_of)
        return {**base, "ok": False, "status": "postcondition_failed_branch_created",
                "created_ref": {"name": request.name, "sha": created}}
    _persist_provenance(auth_store, invocation_id=tf["invocation_id"], pursuit_ref=pursuit_ref, fp=fp,
                        capability=GIT_BRANCH_CREATE, outcome="branch_created", authorization=auth, as_of=as_of)
    return {**base, "ok": True, "status": "succeeded", "created_ref": {"name": request.name, "sha": resolved_sp}}


def _commit_paths_material(request: Any, info: Dict[str, Path], *, repo: Path, timeout: float) -> List[Dict[str, Any]]:
    toplevel = info["toplevel"]
    entries: List[Dict[str, Any]] = []
    for rel in request.paths:
        _validate_commit_path(rel, toplevel=toplevel)
        tracked = _safe_run(["git", "--no-optional-locks", "cat-file", "-e", "HEAD:" + rel],
                            cwd=repo, timeout=timeout)["exit_code"] == 0
        head_blob = None
        if tracked:
            hb = _safe_run(["git", "--no-optional-locks", "rev-parse", "HEAD:" + rel], cwd=repo, timeout=timeout)
            head_blob = (hb["stdout"] or "").strip() if hb["exit_code"] == 0 else None
        target = toplevel / rel
        exists = target.exists() and not target.is_symlink()
        if exists:
            state = "modified" if tracked else "new"
            mode = _expected_mode(target)
            # blob git attendu, SANS filtre externe (F-D3-2/F-6.9) : hash-object --no-filters
            hobj = _safe_run(["git", "--no-optional-locks", "hash-object", "--no-filters", rel],
                             cwd=repo, timeout=timeout)
            worktree = (hobj["stdout"] or "").strip()
            if hobj["timed_out"] or hobj["exit_code"] != 0 or not _HEX40.match(worktree):
                raise GitWriteError(f"hash-object échec pour {rel!r} (fail-closed)")
            entries.append({"path": rel, "state": state, "type": "regular", "mode": mode,
                            "head_blob": head_blob, "worktree": worktree})
        else:
            if not tracked:
                raise GitWriteError(f"chemin absent et non tracké dans HEAD (rien à committer) : {rel!r}")
            entries.append({"path": rel, "state": "deleted", "type": "absent", "mode": None,
                            "head_blob": head_blob, "worktree": "<deleted>"})
    return entries


def _commit_material(request: Any, info: Dict[str, Path], root_str: str, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"capability": GIT_COMMIT, "policy_version": POLICY_VERSION, "toplevel": str(info["toplevel"]),
            "allowed_root": root_str, "expected_branch": request.expected_branch,
            "expected_parent": request.expected_parent, "paths": entries,
            "message_sha256": hashlib.sha256(request.message.encode("utf-8")).hexdigest(),
            "author": f"{request.author.name} <{request.author.email}>",
            "committer": f"{request.committer.name} <{request.committer.email}>",
            "commit_timestamp": request.commit_timestamp, "allow_empty": False,
            "hooks_policy": "disabled", "network": "not_proven"}


def _index_clean_or_fail(repo: Path, timeout: float, *, label: str) -> None:
    r = _safe_run(["git", "--no-optional-locks", "diff", "--cached", "--quiet"], cwd=repo, timeout=timeout)
    if r["timed_out"] or r["exit_code"] not in (0, 1):
        raise GitWriteError(f"{label} : diff --cached --quiet RC inattendu (fail-closed)")
    if r["exit_code"] == 1:
        raise GitWriteError(f"{label} : index non propre (staged étranger à l'entrée) — fail-closed")


def _verify_staged(repo: Path, entries: List[Dict[str, Any]], timeout: float) -> List[str]:
    """F-D3-2 : vérifie objectivement, APRÈS ``git add`` et AVANT commit, que le staged correspond EXACTEMENT au
    matériel autorisé : **name-set** (``diff --cached --name-status``) + **mode** + **blob** (``ls-files --stage``)
    pour les présents ; **absence** de l'entrée staged pour les suppressions. Retourne la liste des divergences
    (vide = conforme)."""
    reasons: List[str] = []
    ns_res = _safe_run(["git", "--no-optional-locks", "diff", "--cached", "--name-status", "-z"],
                       cwd=repo, timeout=timeout)
    if ns_res["timed_out"] or ns_res["exit_code"] != 0:
        return ["diff --cached --name-status RC inattendu"]
    toks = [t for t in (ns_res["stdout"] or "").split("\x00") if t != ""]
    ns: Dict[str, str] = {}
    for i in range(0, len(toks) - 1, 2):               # tokens NUL = [status, path, status, path, ...]
        ns[toks[i + 1]] = toks[i][0]
    expected = {e["path"] for e in entries}
    if set(ns.keys()) != expected:
        reasons.append(f"staged name-set {sorted(ns)} != allow-list {sorted(expected)}")
    present = [e for e in entries if e["state"] != "deleted"]
    lsst: Dict[str, Tuple[str, str]] = {}
    if present:
        ls_res = _safe_run(["git", "--no-optional-locks", "ls-files", "--stage", "-z", "--",
                            *[e["path"] for e in present]], cwd=repo, timeout=timeout)
        if ls_res["timed_out"] or ls_res["exit_code"] != 0:
            return reasons + ["ls-files --stage RC inattendu"]
        for line in (ls_res["stdout"] or "").split("\x00"):
            if not line:
                continue
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) >= 2:
                lsst[path] = (parts[0], parts[1])          # (mode, blob)
    for e in entries:
        p = e["path"]
        if e["state"] == "deleted":
            if p in lsst:
                reasons.append(f"{p}: présent au staged alors que suppression attendue")
            if ns.get(p) != "D":
                reasons.append(f"{p}: name-status {ns.get(p)!r} != 'D'")
        else:
            if p not in lsst:
                reasons.append(f"{p}: absent du staged")
                continue
            mode, blob = lsst[p]
            if mode != e["mode"]:
                reasons.append(f"{p}: mode staged {mode} != attendu {e['mode']}")
            if blob != e["worktree"]:
                reasons.append(f"{p}: blob staged {blob} != attendu {e['worktree']}")
            if ns.get(p) not in ("A", "M"):
                reasons.append(f"{p}: name-status {ns.get(p)!r} inattendu")
    return reasons


def _rollback_index(repo: Path, paths: Tuple[str, ...], timeout: float) -> bool:
    """Tente de restaurer l'index (unstage exact des paths, ramené à HEAD). Retourne True si l'index redevient
    propre (``diff --cached --quiet`` RC 0). Suffisant car l'index était exigé propre en pré-staging."""
    _safe_run(GIT_PREFIX + ["reset", "-q", "--", *paths], cwd=repo, timeout=timeout)
    r = _safe_run(["git", "--no-optional-locks", "diff", "--cached", "--quiet"], cwd=repo, timeout=timeout)
    return (not r["timed_out"]) and r["exit_code"] == 0


def _do_commit(request: Any, info: Dict[str, Path], root_str: str, *, tool_store: Any, auth_store: Any,
               pursuit_ref: str, project_id: str, clock: Callable[[], str], timeout: float) -> Dict[str, Any]:
    repo = info["cwd"]
    # (1) préconditions READ fail-closed
    _common_reject_content_filters(info, timeout=timeout, run=_safe_run, err=GitWriteError)
    cur = _current_branch(repo, timeout)
    if cur is None:
        raise GitWriteError("detached HEAD interdit pour git.commit (L10.2 v1)")
    if cur != request.expected_branch:
        raise GitWriteError(f"branche courante {cur!r} != expected_branch {request.expected_branch!r}")
    head = _head_sha(repo, timeout)
    if head != request.expected_parent:
        raise GitWriteError("HEAD != expected_parent (fail-closed)")
    msg = request.message
    if not isinstance(msg, str) or not msg.strip():
        raise GitWriteError("message de commit vide (fail-closed)")
    if "\x00" in msg:
        raise GitWriteError("message de commit contenant un octet nul (fail-closed)")
    if len(msg.encode("utf-8")) > MESSAGE_MAX_BYTES:
        raise GitWriteError(f"message de commit trop long (> {MESSAGE_MAX_BYTES} octets)")
    _validate_timestamp(request.commit_timestamp)
    if not request.paths:
        raise GitWriteError("aucun chemin (allow-list vide) — fail-closed")
    _index_clean_or_fail(repo, timeout, label="pré-staging")
    entries = _commit_paths_material(request, info, repo=repo, timeout=timeout)
    # (2) empreinte matérielle
    fp = compute_commit_fingerprint(_commit_material(request, info, root_str, entries))
    # (3) gate N2
    rec = _gate(auth_store, pursuit_ref=pursuit_ref, fp=fp)
    if rec is None:
        return _refused(GIT_COMMIT, fp, tool_store=tool_store, auth_store=auth_store, project_id=project_id,
                        pursuit_ref=pursuit_ref, cwd=repo, clock=clock)
    auth = _authorization(rec, pursuit_ref=pursuit_ref, fp=fp)
    # (4) re-vérification TOCTOU immédiate (branche + HEAD + index + matériel ; empreinte recomputée == autorisée)
    if _current_branch(repo, timeout) != request.expected_branch or _head_sha(repo, timeout) != request.expected_parent:
        raise GitWriteError("TOCTOU : branche/HEAD modifiés après autorisation — STOP sans mutation")
    _index_clean_or_fail(repo, timeout, label="TOCTOU pré-staging")
    entries2 = _commit_paths_material(request, info, repo=repo, timeout=timeout)
    if compute_commit_fingerprint(_commit_material(request, info, root_str, entries2)) != fp:
        raise GitWriteError("TOCTOU : matériel modifié après autorisation — STOP sans mutation")
    # (5) STAGING exact — allow-list uniquement
    addr = _safe_run(add_paths_argv(request.paths), cwd=repo, timeout=timeout)
    if addr["timed_out"] or addr["exit_code"] != 0:
        return _fail_after_index(GIT_COMMIT, repo, request.paths, timeout, fp=fp, auth=auth, tool_store=tool_store,
                                 auth_store=auth_store, pursuit_ref=pursuit_ref, project_id=project_id, clock=clock,
                                 argv=add_paths_argv(request.paths), res=addr, reason="git add échec")
    mism = _verify_staged(repo, entries2, timeout)     # F-D3-2 : vérif contre le matériel POST-GO revalidé (entries2)
    if mism:
        return _fail_after_index(GIT_COMMIT, repo, request.paths, timeout, fp=fp, auth=auth, tool_store=tool_store,
                                 auth_store=auth_store, pursuit_ref=pursuit_ref, project_id=project_id, clock=clock,
                                 argv=[], res=None, reason="; ".join(mism[:3]))
    q = _safe_run(["git", "--no-optional-locks", "diff", "--cached", "--quiet"], cwd=repo, timeout=timeout)
    if q["timed_out"] or q["exit_code"] not in (0, 1):
        return _fail_after_index(GIT_COMMIT, repo, request.paths, timeout, fp=fp, auth=auth, tool_store=tool_store,
                                 auth_store=auth_store, pursuit_ref=pursuit_ref, project_id=project_id, clock=clock,
                                 argv=[], res=None, reason="diff --cached RC inattendu")
    if q["exit_code"] == 0:                              # RC=0 ⇒ aucun changement staged ⇒ commit vide INTERDIT
        return _fail_after_index(GIT_COMMIT, repo, request.paths, timeout, fp=fp, auth=auth, tool_store=tool_store,
                                 auth_store=auth_store, pursuit_ref=pursuit_ref, project_id=project_id, clock=clock,
                                 argv=[], res=None, reason="commit vide interdit (jamais --allow-empty)")
    # (6) COMMIT (identité + dates explicites, hooks/gpg neutralisés)
    env = dict(git_env())
    env.update({"GIT_AUTHOR_NAME": request.author.name, "GIT_AUTHOR_EMAIL": request.author.email,
                "GIT_COMMITTER_NAME": request.committer.name, "GIT_COMMITTER_EMAIL": request.committer.email,
                "GIT_AUTHOR_DATE": request.commit_timestamp, "GIT_COMMITTER_DATE": request.commit_timestamp})
    cargv = commit_argv(msg)
    cres = _safe_run(cargv, cwd=repo, timeout=timeout, env=env)
    as_of = clock()
    if cres["timed_out"] or cres["exit_code"] != 0:
        return _fail_after_index(GIT_COMMIT, repo, request.paths, timeout, fp=fp, auth=auth, tool_store=tool_store,
                                 auth_store=auth_store, pursuit_ref=pursuit_ref, project_id=project_id, clock=clock,
                                 argv=cargv, res=cres, reason="git commit échec", as_of=as_of)
    tf = _provenance(tool_store, project_id=project_id, capability=GIT_COMMIT, argv=cargv, cwd=repo,
                     status="succeeded", res=cres, as_of=as_of)
    base = {"capability": GIT_COMMIT, "provider": PROVIDER_NAME, "gate_fingerprint": fp, "authorization": auth,
            "tool_ref": tf["invocation_id"], "as_of": as_of, "created_ref": None}
    # (7) postconditions — commit CRÉÉ : JAMAIS de reset/rewrite automatique si une postcondition échoue
    new_head = _head_sha(repo, timeout)
    parent = _safe_run(["git", "--no-optional-locks", "rev-parse", "HEAD^"], cwd=repo, timeout=timeout)
    files = _safe_run(["git", "--no-optional-locks", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
                      cwd=repo, timeout=timeout)
    committed = {x for x in (files["stdout"] or "").split() if x}
    ok_post = (parent["exit_code"] == 0 and (parent["stdout"] or "").strip() == request.expected_parent
               and _current_branch(repo, timeout) == request.expected_branch
               and committed == set(request.paths))
    outcome = "commit_created" if ok_post else "postcondition_failed_commit_created"
    _persist_provenance(auth_store, invocation_id=tf["invocation_id"], pursuit_ref=pursuit_ref, fp=fp,
                        capability=GIT_COMMIT, outcome=outcome, authorization=auth, as_of=as_of)
    if not ok_post:
        return {**base, "ok": False, "status": "postcondition_failed_commit_created", "commit_sha": new_head}
    return {**base, "ok": True, "status": "succeeded", "commit_sha": new_head}


def _fail_after_index(capability: str, repo: Path, paths: Tuple[str, ...], timeout: float, *, fp: str,
                      auth: Dict[str, Any], tool_store: Any, auth_store: Any, pursuit_ref: str, project_id: str,
                      clock: Callable[[], str], argv: List[str], res: Optional[Dict[str, Any]], reason: str,
                      as_of: Optional[str] = None) -> Dict[str, Any]:
    """Échec après début de staging : tente le rollback contrôlé de l'index. Rollback OK ⇒ provenance durable
    ``failed_rolled_back`` puis **raise** fail-closed (index restauré). Rollback impossible ⇒ provenance durable
    ``failed_dirty_index`` puis **return** (état résiduel jamais masqué)."""
    restored = _rollback_index(repo, paths, timeout)
    stamp = as_of or clock()
    if restored:
        tf = _provenance(tool_store, project_id=project_id, capability=capability, argv=argv, cwd=repo,
                         status="failed", res=res, as_of=stamp)
        _persist_provenance(auth_store, invocation_id=tf["invocation_id"], pursuit_ref=pursuit_ref, fp=fp,
                            capability=capability, outcome="failed_rolled_back", authorization=auth, as_of=stamp)
        raise GitWriteError(f"mutation refusée après staging (index restauré) : {reason}")
    tf = _provenance(tool_store, project_id=project_id, capability=capability, argv=argv, cwd=repo,
                     status="failed_dirty_index", res=res, as_of=stamp)
    _persist_provenance(auth_store, invocation_id=tf["invocation_id"], pursuit_ref=pursuit_ref, fp=fp,
                        capability=capability, outcome="failed_dirty_index", authorization=auth, as_of=stamp)
    return {"capability": capability, "provider": PROVIDER_NAME, "ok": False, "status": "failed_dirty_index",
            "gate_fingerprint": fp, "authorization": auth, "created_ref": None, "commit_sha": None,
            "reason": reason, "tool_ref": tf["invocation_id"], "as_of": stamp}


__all__ = ["PROVIDER_NAME", "GIT_BRANCH_CREATE", "GIT_COMMIT", "GIT_WRITE_CAPABILITIES", "POLICY_VERSION",
           "GitWriteError", "GitWriteGateError", "Identity", "DEFAULT_IDENTITY",
           "BranchCreateRequest", "CommitRequest", "branch_create_argv", "add_paths_argv", "commit_argv",
           "compute_branch_fingerprint", "compute_commit_fingerprint",
           "LocalGitWriteAdapter", "GitWriteHandle", "produce_git_write"]
