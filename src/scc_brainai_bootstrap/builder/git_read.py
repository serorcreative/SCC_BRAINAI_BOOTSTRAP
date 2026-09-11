"""Capacités **Git en LECTURE SEULE** typées (L10.1) — Software Control Plane, classe R (READ).

CONNECTER, PAS RECONSTRUIRE : trois capacités **sémantiques** (``git.status`` / ``git.diff`` /
``git.branches.list``) qui construisent **elles-mêmes** leur ``argv`` à partir d'arguments **strictement
validés** et l'exécutent via le **même** sous-processus confiné
:func:`~scc_brainai_bootstrap.builder.tool_runner.run_confined`. BrainAI ne reçoit **jamais** un terminal
générique : aucun ``argv`` git arbitraire issu d'un LLM n'est exécutable (N1). Classe R uniquement — aucune
mutation, aucune remote, aucune credential (N6) :

* aucune remote, aucun ``fetch``/``pull``/``push``/``ls-remote`` ;
* aucune écriture intentionnelle (``add``/``commit``/``branch create``/``switch``/``reset``/``stash``…) ;
* ``network_required=false``.

**N6 : ``network_required=false`` ≠ ``network_isolation=proven``.** Aucune isolation réseau/OS n'est prétendue —
seules les opérations autorisées n'exigent aucune remote. Le confinement est *best-effort*, jamais une sandbox noyau.

Durcissement Git : ``--no-optional-locks`` (aucun refresh d'index), ``--no-pager`` + ``GIT_PAGER=cat``,
``-c core.fsmonitor=false``, ``--ignore-submodules=all`` (status/diff — aucun sous-dépôt inspecté), env **sans
HOME** (aucun gitconfig global), ``GIT_CONFIG_NOSYSTEM=1`` + ``GIT_CONFIG_SYSTEM``/``GIT_CONFIG_GLOBAL=/dev/null``
(ni alias, ni external-diff, ni textconv, ni filtre hérités du système/global), ``GIT_TERMINAL_PROMPT=0``. Pour
``git.diff`` : ``--no-ext-diff`` + ``--no-textconv``.

Vecteurs d'exécution externe, par commande (honnêteté — aucune sur-promesse) :
* ``git.status`` : fsmonitor → **neutralisé** ; submodules → **ignorés** ; **filtres de contenu**
  ``filter.<d>.clean``/``.process`` (via config locale, ``core.attributesFile``, ou ``.gitattributes`` **récursifs**
  / ``.git/info/attributes``) → un ``clean`` filter PEUT être invoqué par ``status`` : **détecté et REFUSÉ
  fail-closed** (:func:`_reject_content_filters`). Aucun hook, aucune remote.
* ``git.diff``  : external diff / textconv → **neutralisés** (``--no-ext-diff``/``--no-textconv``) ; fsmonitor
  neutralisé ; submodules ignorés ; **filtres clean/process** → **détectés et REFUSÉS fail-closed**
  (``--no-ext-diff``/``--no-textconv`` NE les désactivent PAS).
* ``git.branches.list`` : ``for-each-ref`` sur ``refs/heads/`` — aucune lecture de contenu worktree, aucun filtre
  applicable, aucun programme externe, aucun hook, aucune remote (aucun contrôle de filtre requis).

NON DÉMONTRÉ : isolation réseau/OS (N6). La config **locale** du dépôt reste une entrée NON FIABLE : elle n'est
neutralisée QUE pour les vecteurs ci-dessus ; les dépôts à **filtre de contenu** sont **refusés** (non supportés
en L10.1 — cette stratégie peut volontairement refuser certains dépôts complexes/worktrees légitimes : least
privilege > compatibilité). Import-isolé : ``builder`` + ``core`` + stdlib (aucun pont 13/15/16 — N5).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract
from scc_brainai_bootstrap.builder.claude_code_runtime import DIAG_MAX, redact
from scc_brainai_bootstrap.builder.tool_runner import DEFAULT_WATCHDOG_S, run_confined

# Identifiant de l'exécutant (registre L10.1) — local, déterministe, sans réseau ni credential.
PROVIDER_NAME = "local_git"

# Slugs de capacité (``domaine.action``) — vocabulaire typé, classe R (READ). EXACTEMENT trois (aucune 4ᵉ).
GIT_STATUS = "git.status"
GIT_DIFF = "git.diff"
GIT_BRANCHES = "git.branches.list"
GIT_READ_CAPABILITIES = (GIT_STATUS, GIT_DIFF, GIT_BRANCHES)

# Env Git durci : minimal + neutralisation des surfaces de config externes. AUCUN ``HOME`` (aucun gitconfig
# global), système/global via /dev/null, pas de pager, pas d'invite credential. Pas une isolation OS (N6).
_GIT_ENV = {
    "PATH": "/usr/bin:/bin:/usr/local/bin",
    "LANG": "C.UTF-8",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_PAGER": "cat",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    # Interdit toute récupération réseau IMPLICITE d'un objet manquant (dépôt partiel/promisor) pendant une
    # lecture (N6 : network_required=false imposé, sans prétendre à network_isolation=proven). Aucun
    # GIT_ALTERNATE_OBJECT_DIRECTORIES hérité (whitelist explicite ci-dessus).
    "GIT_NO_LAZY_FETCH": "1",
}

# Préfixe commun (options **top-level** git, avant toute sous-commande) : lecture, sans pager, sans fsmonitor.
_GIT_PREFIX = ["git", "--no-optional-locks", "--no-pager", "-c", "core.fsmonitor=false"]
# Préfixe pour ``git config`` (lecture) — sans -c fsmonitor inutile.
_GIT_CONFIG_PREFIX = ["git", "--no-optional-locks", "--no-pager", "config"]


class GitReadError(ValueError):
    """Refus **fail-closed** d'une lecture git (confinement, dépôt invalide/filtré, argument/capacité invalide, git absent)."""


def _git_env() -> Dict[str, str]:
    return dict(_GIT_ENV)


# --------------------------------------------------------------------- #
# Constructeurs d'argv — chaque capacité fabrique son propre argv (N1) ; aucune sous-commande arbitraire externe.
# --------------------------------------------------------------------- #
def status_argv() -> List[str]:
    """``git status`` machine-readable et déterministe (porcelain v1 + en-tête de branche) : sans rename, sans
    lock, **submodules ignorés** (``--ignore-submodules=all``)."""
    return _GIT_PREFIX + ["status", "--porcelain=v1", "--branch", "--untracked-files=all",
                          "--no-renames", "--ignore-submodules=all"]


def diff_argv(staged: bool = False) -> List[str]:
    """``git diff`` **borné** : aucun programme externe (``--no-ext-diff``/``--no-textconv``), aucune couleur,
    **submodules ignorés**. Seul argument accepté : ``staged`` (bool strict → ``--staged``). Aucune pathspec
    exposée en L10.1 (surface minimale). ``staged`` non booléen ⇒ :class:`GitReadError` (N1)."""
    if not isinstance(staged, bool):
        raise GitReadError("argument 'staged' invalide (booléen strict requis)")
    argv = _GIT_PREFIX + ["diff", "--no-ext-diff", "--no-textconv", "--no-color", "--ignore-submodules=all"]
    if staged:
        argv.append("--staged")
    return argv


def branches_list_argv() -> List[str]:
    """Liste **locale** des branches (``refs/heads/`` uniquement) via ``for-each-ref``, format stable
    (séparateur TAB — interdit dans un nom de ref). **Jamais** de ``refs/remotes/``, jamais de fetch."""
    return _GIT_PREFIX + ["for-each-ref",
                          "--format=%(refname:short)\t%(objectname)\t%(HEAD)", "refs/heads/"]


# --------------------------------------------------------------------- #
# Parseurs déterministes — sortie git → structure typée. SEC-3 : ``git.diff`` peut porter du contenu de fichiers →
# JAMAIS de texte brut ni de fingerprint brut exposé (redaction RV-1, sortie bornée). Les champs **user-controlled**
# de ``status`` (chemins, en-tête de branche) et ``branches`` (nom de branche) sont eux aussi **redactés** (F-6.9) ;
# ``sha`` (objectname) et ``current`` ne sont PAS user-controlled et ne sont pas redactés (préserve le contrat).
# --------------------------------------------------------------------- #
def _parse_status(stdout: str) -> Dict[str, Any]:
    branch: Optional[str] = None
    entries: List[Dict[str, str]] = []
    for line in (stdout or "").splitlines():
        if line.startswith("## "):
            branch = redact(line[3:])                          # SEC-3 : en-tête de branche user-controlled
        elif line:
            path = line[3:] if len(line) > 3 else ""
            entries.append({"xy": line[:2], "path": redact(path)})   # SEC-3 : chemin user-controlled
    return {"branch": branch, "entries": entries, "clean": len(entries) == 0}


def _parse_branches(stdout: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in (stdout or "").splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            flag = parts[2] if len(parts) > 2 else ""
            # SEC-3 : ``name`` est user-controlled → redacté (RV-1). ``sha``/``current`` non user-controlled, non redactés.
            out.append({"name": redact(parts[0]), "sha": parts[1], "current": flag.strip() == "*"})
    return out


def _parse_diff(stdout: str) -> Dict[str, Any]:
    """SEC-3 fail-closed : ne renvoie **jamais** le diff brut ni un fingerprint du brut. RV-1 :func:`redact`
    appliqué au brut AVANT exposition ; sortie bornée à ``DIAG_MAX`` caractères ; seuls des dérivés du **redacté**
    (taille/hash/texte borné) sont retournés. ``changed`` = booléen (aucune donnée)."""
    raw = stdout or ""
    redacted = redact(raw) or ""
    return {"changed": bool(raw.strip()),
            "redacted_byte_size": len(redacted.encode("utf-8")),
            "redacted_sha256": hashlib.sha256(redacted.encode("utf-8")).hexdigest(),
            "text_redacted": redacted[:DIAG_MAX],
            "truncated": len(redacted) > DIAG_MAX}


def _parse(capability: str, stdout: str) -> Any:
    if capability == GIT_STATUS:
        return _parse_status(stdout)
    if capability == GIT_DIFF:
        return _parse_diff(stdout)
    if capability == GIT_BRANCHES:
        return _parse_branches(stdout)
    raise GitReadError(f"capacité git-read inconnue : {capability!r}")


def _git_read_contract(*, capabilities) -> AdapterContract:
    """Contrat T2 **complet** d'une lecture git locale (défini inline — ``adapter_contract.py`` non modifié à ce
    stade). Aucun fournisseur externe, aucune credential, coût ``unavailable`` (I6). Déclare la **posture réseau**
    (N6) : ``required=False`` mais ``isolation='not_proven'`` — jamais de fausse promesse d'isolation OS."""
    return AdapterContract(
        capabilities_served=tuple(capabilities),
        auth_channel={"kind": "none", "explicit": True, "leaks_identity": False,
                      "detail": "lecture git locale — aucun fournisseur externe, aucune credential"},
        inbound_channels=(),
        cost_report={"mode": "unavailable", "fabricated": False},
        native_budget={"usd_cap": "none", "call_cap": "none"},
        confinement={"workspace": True, "tools_allowed": ["git:read-only"],
                     "tools_disallowed": ["git:mutating", "git:remote", "shell", "git:content-filter"],
                     "permission_mode": "local+confined+read-only", "env_mode": "none",
                     "network": {"required": False, "isolation": "not_proven"}},
    )


def _safe_run(argv: List[str], *, cwd: Path, timeout: float) -> Dict[str, Any]:
    """``run_confined`` (``shell=False``, env git durci) + conversion **fail-closed** d'un git absent/non
    exécutable en :class:`GitReadError`. Aucun fallback."""
    try:
        return run_confined(argv, cwd=cwd, timeout=timeout, env=_git_env())
    except (FileNotFoundError, OSError) as exc:                # git introuvable / non exécutable
        raise GitReadError(f"git introuvable ou non exécutable : {exc}") from exc


def _rev_parse_path(args: List[str], *, cwd: Path, timeout: float, label: str) -> Path:
    """Lit un chemin **absolu/canonique** du dépôt via ``git rev-parse`` (argv **construit en interne** à partir de
    ``args``, jamais contrôlable par un caller/LLM), RC capturé, puis ``resolve()``. Les requêtes de chemins de
    dépôt utilisent ``--path-format=absolute`` afin de **ne jamais** résoudre un chemin relatif implicitement depuis
    le cwd du processus Python."""
    res = _safe_run(["git", "--no-optional-locks", "rev-parse", *args], cwd=cwd, timeout=timeout)
    if res["timed_out"] or res["exit_code"] != 0 or not (res["stdout"] or "").strip():
        raise GitReadError(f"{label} indéterminé (dépôt git invalide)")
    return Path(res["stdout"].strip()).resolve()


def _confined_repo(cwd: Any, *, allowed_root: Any, timeout: float) -> Dict[str, Path]:
    """Valide **avant toute lecture** que ``cwd`` est un dépôt git réel, et confine ``cwd`` + ``toplevel`` +
    ``git-dir`` + ``git-common-dir`` + ``object-dir`` à ``allowed_root``. **``allowed_root`` est OBLIGATOIRE** (F-6.2)
    : absent/``None`` / non absolu / répertoire inexistant ⇒ fail-closed. Refuse en outre tout **object store
    alternate** (:func:`_reject_alternates`). Fail-closed : chemin non absolu, hors racine (traversal / symlink /
    ``.git``-file externe / worktree à gitdir externe / ``core.worktree`` / common-dir externe), répertoire
    inexistant, dépôt invalide, alternate présent."""
    if allowed_root is None:
        raise GitReadError("allowed_root obligatoire (confinement) — aucune lecture sans racine autorisée (F-6.2)")
    root_p = Path(allowed_root)
    if not root_p.is_absolute():
        raise GitReadError("allowed_root non absolu (confinement)")
    try:
        root = root_p.resolve()
    except OSError as exc:
        raise GitReadError(f"allowed_root irrésoluble : {exc}") from exc
    if not root.is_dir():
        raise GitReadError("allowed_root n'est pas un répertoire existant")
    p = Path(cwd)
    if not p.is_absolute():
        raise GitReadError("cwd non absolu (confinement)")
    try:
        resolved = p.resolve()
    except OSError as exc:
        raise GitReadError(f"cwd irrésoluble : {exc}") from exc
    if not resolved.is_dir():
        raise GitReadError("cwd n'est pas un répertoire existant")
    probe = _safe_run(["git", "--no-optional-locks", "rev-parse", "--is-inside-work-tree"],
                      cwd=resolved, timeout=timeout)
    if probe["timed_out"] or probe["exit_code"] != 0 or (probe["stdout"] or "").strip() != "true":
        raise GitReadError("cwd n'est pas un dépôt git valide")
    toplevel = _rev_parse_path(["--show-toplevel"], cwd=resolved, timeout=timeout, label="toplevel")
    gitdir = _rev_parse_path(["--absolute-git-dir"], cwd=resolved, timeout=timeout, label="git-dir")
    common_dir = _rev_parse_path(["--path-format=absolute", "--git-common-dir"],
                                 cwd=resolved, timeout=timeout, label="git-common-dir")
    object_dir = _rev_parse_path(["--path-format=absolute", "--git-path", "objects"],
                                 cwd=resolved, timeout=timeout, label="object-dir")
    for label, path in (("cwd", resolved), ("toplevel", toplevel), ("git-dir", gitdir),
                        ("git-common-dir", common_dir), ("object-dir", object_dir)):
        if path != root and root not in path.parents:
            raise GitReadError(f"{label} hors de la racine autorisée (confinement)")
    _reject_alternates(object_dir)      # aucun object store alternate / http-alternate (lecture hors dépôt confiné)
    return {"cwd": resolved, "toplevel": toplevel, "gitdir": gitdir,
            "common_dir": common_dir, "object_dir": object_dir}


def _reject_alternates(object_dir: Path) -> None:
    """Refuse fail-closed tout **object store alternate** (``info/alternates`` / ``info/http-alternates``) présent
    et non vide sous l'**object_dir réel** (résolu via ``git rev-parse --git-path objects``) : L10.1 ne lit **aucun**
    objet hors du dépôt confiné et **aucun** alternate HTTP. Un fichier d'alternates symlinké est refusé (jamais suivi)."""
    objects_info = object_dir / "info"
    for name in ("alternates", "http-alternates"):
        f = objects_info / name
        try:
            if f.is_symlink():
                raise GitReadError(f"object store alternate symlinké ({name}) — refusé fail-closed (L10.1)")
            content = f.read_text(encoding="utf-8", errors="replace").strip() if f.is_file() else ""
        except OSError as exc:
            raise GitReadError(f"détection alternates : lecture impossible ({exc})") from exc
        if content:
            raise GitReadError(f"alternate object store présent ({name}) — refusé fail-closed (L10.1)")


def _walk_onerror(err: OSError) -> None:
    """``onerror`` de :func:`os.walk` — **fail-closed** : toute erreur de parcours/scandir/permission empêchant une
    inspection complète des ``.gitattributes`` lève :class:`GitReadError` (jamais un skip silencieux)."""
    raise GitReadError(f"scan .gitattributes : parcours impossible ({err})")


def _reject_if_filter_file(path: Path, *, refuse_symlink: bool = False) -> None:
    """Refuse fail-closed si ``path`` (fichier d'attributs git) déclare ``filter=``. Ne suit jamais un symlink
    (``refuse_symlink`` : un fichier d'attributs symlinké est refusé). Ne lit pas plus que le texte du fichier."""
    try:
        if not path.is_file():
            return
        if refuse_symlink and path.is_symlink():
            raise GitReadError(f"fichier d'attributs symlinké ({path.name}) — refusé fail-closed (L10.1)")
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise GitReadError(f"détection filtre : lecture attributs impossible ({exc})") from exc
    if "filter=" in content:
        raise GitReadError(f"attribut 'filter=' détecté ({path.name}) — dépôt refusé fail-closed (L10.1)")


def _reject_content_filters(info: Dict[str, Path], *, timeout: float) -> None:
    """Refuse fail-closed tout dépôt susceptible de déclencher un **filtre de contenu externe** (``clean``/
    ``process``). ``git.status``/``git.diff`` peuvent invoquer un ``clean`` filter — que ``--no-ext-diff``/
    ``--no-textconv`` NE désactivent PAS. Vérifie, **sans jamais exécuter le filtre ni une commande susceptible de
    le déclencher** : (a) clés locales ``filter.*`` ; (b) ``core.attributesFile`` ; (c) ``.git/info/attributes`` ;
    (d) tous les ``.gitattributes`` **récursifs** sous le toplevel confiné (``.git`` élagué, symlinks non suivis)."""
    repo, toplevel, gitdir = info["cwd"], info["toplevel"], info["gitdir"]
    # (a) config locale : toute clé filter.* (noms seuls — secret-safe)
    cfg = _safe_run(_GIT_CONFIG_PREFIX + ["--name-only", "--get-regexp", r"^filter\."], cwd=repo, timeout=timeout)
    if cfg["timed_out"] or cfg["exit_code"] not in (0, 1):
        raise GitReadError("détection filtre : échec lecture config (fail-closed)")
    if cfg["exit_code"] == 0 and (cfg["stdout"] or "").strip():
        raise GitReadError("dépôt avec filter.<driver>.clean/process — refusé fail-closed (L10.1)")
    # (b) fichier d'attributs externe déclaré
    af = _safe_run(_GIT_CONFIG_PREFIX + ["--get", "core.attributesFile"], cwd=repo, timeout=timeout)
    if af["timed_out"] or af["exit_code"] not in (0, 1):
        raise GitReadError("détection filtre : échec lecture core.attributesFile (fail-closed)")
    if af["exit_code"] == 0 and (af["stdout"] or "").strip():
        raise GitReadError("dépôt avec core.attributesFile externe — refusé fail-closed (L10.1)")
    # (c) attributs du dépôt (git-dir/info/attributes) — symlink sortant refusé fail-closed
    _reject_if_filter_file(gitdir / "info" / "attributes", refuse_symlink=True)
    # (d) .gitattributes récursifs sous toplevel (élaguer .git ; symlinks non suivis ; onerror fail-closed)
    for dirpath, dirnames, filenames in os.walk(toplevel, followlinks=False, onerror=_walk_onerror):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if ".gitattributes" in filenames:
            _reject_if_filter_file(Path(dirpath) / ".gitattributes", refuse_symlink=True)


def _argv_for(capability: str, *, staged: bool = False) -> List[str]:
    """Construit l'``argv`` **typé** (non-exécutable) d'une capacité admise. Capacité inconnue ⇒ fail-closed (N1).
    Fonction module (aucune exécution) : l'exécution réelle vit **uniquement** dans :func:`produce_git_read`."""
    if capability == GIT_STATUS:
        return status_argv()
    if capability == GIT_DIFF:
        return diff_argv(staged)
    if capability == GIT_BRANCHES:
        return branches_list_argv()
    raise GitReadError(f"capacité git-read inconnue : {capability!r} (admis ∈ {GIT_READ_CAPABILITIES})")


class LocalGitReadAdapter:
    """Exécutant **INERTE** (L10.1, F-6.1). Ne possède **AUCUNE** méthode d'exécution Git (ni publique ni « privée »
    ``_``) : impossible de lancer Git via l'adaptateur, **même** en accédant à ``h._adapter``. Expose uniquement du
    non-exécutable : identité (``name``/``capability``/``model``) et ``contract()`` (T2). L'exécution réelle vit
    exclusivement dans :func:`produce_git_read` / :meth:`GitReadHandle.read` (confinement + ``allowed_root`` +
    refus filtres/alternates + provenance N4 + SEC-3). La sécurité ne dépend pas de la discipline de l'appelant."""

    capability = "git.read"                 # famille (le contrat déclare les 3 slugs réellement servis)
    name = PROVIDER_NAME
    model = "git"

    def __init__(self) -> None:
        self.max_budget_usd = 0.0           # lecture locale : aucun coût facturable (jamais fabriqué, I6)

    def contract(self) -> AdapterContract:
        """Contrat complet (T2) — lecture git locale confinée, réseau non requis (isolation non prouvée, N6)."""
        return _git_read_contract(capabilities=GIT_READ_CAPABILITIES)


def produce_git_read(*, capability: str, adapter: LocalGitReadAdapter, cwd: Any, tool_store: Any,
                     project_id: str, clock: Any, allowed_root: Any,
                     timeout: float = DEFAULT_WATCHDOG_S, staged: bool = False) -> Dict[str, Any]:
    """**Chemin normal unique** d'une lecture git typée. ``allowed_root`` est **OBLIGATOIRE** (F-6.2 : mot-clé sans
    défaut ; absent ⇒ ``TypeError`` ; ``None``/invalide ⇒ ``GitReadError``). Étapes : (1) confinement fail-closed
    (cwd + toplevel + git-dir + common-dir + object-dir, tous ⊆ ``allowed_root``) ; (1bis) refus des dépôts à filtre
    de contenu pour ``status``/``diff`` ; (2) construction argv typée (:func:`_argv_for`) + **exécution confinée
    UNIQUE** (:func:`_safe_run`, APRÈS confinement — seul lieu d'exécution Git) ; (3) horodatage +
    **fait ToolInvocation** append-only obligatoire (provenance N4, stdout/stderr redactés+bornés) ; (4) résultat
    **typé** (diff + status/branches redactés, SEC-3). Réutilise ``run_confined``/``ToolInvocationStore`` existants."""
    if capability not in GIT_READ_CAPABILITIES:
        raise GitReadError(f"capacité git-read inconnue : {capability!r} (admis ∈ {GIT_READ_CAPABILITIES})")
    info = _confined_repo(cwd, allowed_root=allowed_root, timeout=timeout)      # (1) fail-closed (allowed_root obligatoire)
    if capability in (GIT_STATUS, GIT_DIFF):                                    # (1bis) filtres de contenu
        _reject_content_filters(info, timeout=timeout)
    repo = info["cwd"]
    argv = _argv_for(capability, staged=staged)                                # argv typé (non-exécutable)
    res = _safe_run(argv, cwd=repo, timeout=timeout)                           # (2) exécution confinée — UNIQUE lieu (APRÈS confinement)
    as_of = clock()                                                           # (3)
    exit_code = res["exit_code"]
    timed_out = res["timed_out"]
    status = "timeout" if timed_out else ("succeeded" if exit_code == 0 else "failed")
    tool_fact = tool_store.record(
        project_id=project_id, tool=f"{adapter.name}:{capability}", argv=argv, cwd=str(repo),
        status=status, exit_code=exit_code,
        stdout=(redact(res["stdout"] or "") or "")[:DIAG_MAX],
        stderr=(redact(res["stderr"] or "") or "")[:DIAG_MAX],
        timed_out=timed_out, as_of=as_of)
    result = _parse(capability, res["stdout"]) if status == "succeeded" else None      # (4) diff/status/branches redactés (SEC-3)
    return {"capability": capability, "provider": adapter.name, "ok": status == "succeeded",
            "status": status, "exit_code": exit_code, "timed_out": timed_out, "argv": argv,
            "result": result, "tool_ref": tool_fact["invocation_id"], "as_of": as_of}


class GitReadHandle:
    """**Voie d'exécution PUBLIQUE unique** d'une capacité git-read (F-6.1). Renvoyée par
    :func:`brainai_app.providers.resolve_git_read`. N'expose **aucun** ``run()``/``_run`` nu : la seule exécution
    possible est :meth:`read`, qui passe **obligatoirement** par :func:`produce_git_read` (confinement +
    ``allowed_root`` obligatoire + refus filtres/alternates + provenance N4 + SEC-3). L'adaptateur interne reste
    **privé** ; la sécurité ne dépend pas de la discipline de l'appelant."""

    def __init__(self, adapter: LocalGitReadAdapter, capability: str) -> None:
        self._adapter = adapter
        self.capability = capability
        self.provider = adapter.name
        self.name = adapter.name            # compat résolution (nom de provider) — aucune voie d'exécution exposée

    def contract(self) -> AdapterContract:
        """Contrat T2 de l'exécutant sous-jacent (délégué)."""
        return self._adapter.contract()

    def read(self, *, cwd: Any, allowed_root: Any, tool_store: Any, project_id: str, clock: Any,
             timeout: float = DEFAULT_WATCHDOG_S, staged: bool = False) -> Dict[str, Any]:
        """Unique exécution publique. ``allowed_root`` **obligatoire** (mot-clé sans défaut, F-6.2). Délègue à
        :func:`produce_git_read` — confinement + provenance **toujours** appliqués."""
        return produce_git_read(capability=self.capability, adapter=self._adapter, cwd=cwd,
                                allowed_root=allowed_root, tool_store=tool_store, project_id=project_id,
                                clock=clock, timeout=timeout, staged=staged)


__all__ = ["PROVIDER_NAME", "GIT_STATUS", "GIT_DIFF", "GIT_BRANCHES", "GIT_READ_CAPABILITIES",
           "GitReadError", "status_argv", "diff_argv", "branches_list_argv",
           "LocalGitReadAdapter", "GitReadHandle", "produce_git_read"]
