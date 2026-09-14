"""Primitives Git **communes** de safety/confinement — factorisées de L10.1 **sans changement sémantique**.

**Runner INJECTÉ** (paramètre ``run``) : ces helpers ne *bindent* JAMAIS ``run_confined``. Le module appelant
(``git_read`` — et, ultérieurement, un module de mutation gouverné) **gouverne** le chemin d'exécution
subprocess et fournit explicitement son **runner** (``run``) et son **type d'erreur** (``err``). Ceci préserve
strictement : le seam de monkeypatch des tests L10.1, F-6.1 (aucun nouveau chemin d'exécution ici), et le
comportement observable de L10.1 (mêmes ``argv``, même env durci, même politique alternates/filtres).

Import-isolé : stdlib uniquement (aucun pont 13/15/16 — N5). N6 : ``network_required=false`` ≠
``network_isolation=proven`` (confinement best-effort, jamais une sandbox noyau).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List

# Env Git durci : minimal + neutralisation des surfaces de config externes. AUCUN ``HOME`` (aucun gitconfig
# global), système/global via /dev/null, pas de pager, pas d'invite credential. Pas une isolation OS (N6).
GIT_ENV = {
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
GIT_PREFIX = ["git", "--no-optional-locks", "--no-pager", "-c", "core.fsmonitor=false"]
# Préfixe pour ``git config`` (lecture) — sans -c fsmonitor inutile.
GIT_CONFIG_PREFIX = ["git", "--no-optional-locks", "--no-pager", "config"]


def git_env() -> Dict[str, str]:
    return dict(GIT_ENV)


def rev_parse_path(args: List[str], *, cwd: Path, timeout: float,
                   run: Callable[..., Dict[str, Any]], err: type, label: str) -> Path:
    """Lit un chemin **absolu/canonique** du dépôt via ``git rev-parse`` (argv **construit en interne** à partir de
    ``args``, jamais contrôlable par un caller/LLM), RC capturé, puis ``resolve()``. Les requêtes de chemins de
    dépôt utilisent ``--path-format=absolute`` afin de **ne jamais** résoudre un chemin relatif implicitement depuis
    le cwd du processus Python."""
    res = run(["git", "--no-optional-locks", "rev-parse", *args], cwd=cwd, timeout=timeout)
    if res["timed_out"] or res["exit_code"] != 0 or not (res["stdout"] or "").strip():
        raise err(f"{label} indéterminé (dépôt git invalide)")
    return Path(res["stdout"].strip()).resolve()


def confined_repo(cwd: Any, *, allowed_root: Any, timeout: float,
                  run: Callable[..., Dict[str, Any]], err: type) -> Dict[str, Path]:
    """Valide **avant toute lecture** que ``cwd`` est un dépôt git réel, et confine ``cwd`` + ``toplevel`` +
    ``git-dir`` + ``git-common-dir`` + ``object-dir`` à ``allowed_root``. **``allowed_root`` est OBLIGATOIRE** (F-6.2)
    : absent/``None`` / non absolu / répertoire inexistant ⇒ fail-closed. Refuse en outre tout **object store
    alternate** (:func:`reject_alternates`). Fail-closed : chemin non absolu, hors racine (traversal / symlink /
    ``.git``-file externe / worktree à gitdir externe / ``core.worktree`` / common-dir externe), répertoire
    inexistant, dépôt invalide, alternate présent."""
    if allowed_root is None:
        raise err("allowed_root obligatoire (confinement) — aucune lecture sans racine autorisée (F-6.2)")
    root_p = Path(allowed_root)
    if not root_p.is_absolute():
        raise err("allowed_root non absolu (confinement)")
    try:
        root = root_p.resolve()
    except OSError as exc:
        raise err(f"allowed_root irrésoluble : {exc}") from exc
    if not root.is_dir():
        raise err("allowed_root n'est pas un répertoire existant")
    p = Path(cwd)
    if not p.is_absolute():
        raise err("cwd non absolu (confinement)")
    try:
        resolved = p.resolve()
    except OSError as exc:
        raise err(f"cwd irrésoluble : {exc}") from exc
    if not resolved.is_dir():
        raise err("cwd n'est pas un répertoire existant")
    probe = run(["git", "--no-optional-locks", "rev-parse", "--is-inside-work-tree"],
                cwd=resolved, timeout=timeout)
    if probe["timed_out"] or probe["exit_code"] != 0 or (probe["stdout"] or "").strip() != "true":
        raise err("cwd n'est pas un dépôt git valide")
    toplevel = rev_parse_path(["--show-toplevel"], cwd=resolved, timeout=timeout, run=run, err=err, label="toplevel")
    gitdir = rev_parse_path(["--absolute-git-dir"], cwd=resolved, timeout=timeout, run=run, err=err, label="git-dir")
    common_dir = rev_parse_path(["--path-format=absolute", "--git-common-dir"],
                                cwd=resolved, timeout=timeout, run=run, err=err, label="git-common-dir")
    object_dir = rev_parse_path(["--path-format=absolute", "--git-path", "objects"],
                                cwd=resolved, timeout=timeout, run=run, err=err, label="object-dir")
    for label, path in (("cwd", resolved), ("toplevel", toplevel), ("git-dir", gitdir),
                        ("git-common-dir", common_dir), ("object-dir", object_dir)):
        if path != root and root not in path.parents:
            raise err(f"{label} hors de la racine autorisée (confinement)")
    reject_alternates(object_dir, err=err)      # aucun object store alternate / http-alternate (lecture hors dépôt confiné)
    return {"cwd": resolved, "toplevel": toplevel, "gitdir": gitdir,
            "common_dir": common_dir, "object_dir": object_dir}


def reject_alternates(object_dir: Path, *, err: type) -> None:
    """Refuse fail-closed tout **object store alternate** (``info/alternates`` / ``info/http-alternates``) présent
    et non vide sous l'**object_dir réel** (résolu via ``git rev-parse --git-path objects``) : L10.1 ne lit **aucun**
    objet hors du dépôt confiné et **aucun** alternate HTTP. Un fichier d'alternates symlinké est refusé (jamais suivi)."""
    objects_info = object_dir / "info"
    for name in ("alternates", "http-alternates"):
        f = objects_info / name
        try:
            if f.is_symlink():
                raise err(f"object store alternate symlinké ({name}) — refusé fail-closed (L10.1)")
            content = f.read_text(encoding="utf-8", errors="replace").strip() if f.is_file() else ""
        except OSError as exc:
            raise err(f"détection alternates : lecture impossible ({exc})") from exc
        if content:
            raise err(f"alternate object store présent ({name}) — refusé fail-closed (L10.1)")


def reject_if_filter_file(path: Path, *, err: type, refuse_symlink: bool = False) -> None:
    """Refuse fail-closed si ``path`` (fichier d'attributs git) déclare ``filter=``. Ne suit jamais un symlink
    (``refuse_symlink`` : un fichier d'attributs symlinké est refusé). Ne lit pas plus que le texte du fichier."""
    try:
        if not path.is_file():
            return
        if refuse_symlink and path.is_symlink():
            raise err(f"fichier d'attributs symlinké ({path.name}) — refusé fail-closed (L10.1)")
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise err(f"détection filtre : lecture attributs impossible ({exc})") from exc
    if "filter=" in content:
        raise err(f"attribut 'filter=' détecté ({path.name}) — dépôt refusé fail-closed (L10.1)")


def reject_content_filters(info: Dict[str, Path], *, timeout: float,
                           run: Callable[..., Dict[str, Any]], err: type) -> None:
    """Refuse fail-closed tout dépôt susceptible de déclencher un **filtre de contenu externe** (``clean``/
    ``process``). ``git.status``/``git.diff`` peuvent invoquer un ``clean`` filter — que ``--no-ext-diff``/
    ``--no-textconv`` NE désactivent PAS. Vérifie, **sans jamais exécuter le filtre ni une commande susceptible de
    le déclencher** : (a) clés locales ``filter.*`` ; (b) ``core.attributesFile`` ; (c) ``.git/info/attributes`` ;
    (d) tous les ``.gitattributes`` **récursifs** sous le toplevel confiné (``.git`` élagué, symlinks non suivis)."""
    repo, toplevel, gitdir = info["cwd"], info["toplevel"], info["gitdir"]
    # (a) config locale : toute clé filter.* (noms seuls — secret-safe)
    cfg = run(GIT_CONFIG_PREFIX + ["--name-only", "--get-regexp", r"^filter\."], cwd=repo, timeout=timeout)
    if cfg["timed_out"] or cfg["exit_code"] not in (0, 1):
        raise err("détection filtre : échec lecture config (fail-closed)")
    if cfg["exit_code"] == 0 and (cfg["stdout"] or "").strip():
        raise err("dépôt avec filter.<driver>.clean/process — refusé fail-closed (L10.1)")
    # (b) fichier d'attributs externe déclaré
    af = run(GIT_CONFIG_PREFIX + ["--get", "core.attributesFile"], cwd=repo, timeout=timeout)
    if af["timed_out"] or af["exit_code"] not in (0, 1):
        raise err("détection filtre : échec lecture core.attributesFile (fail-closed)")
    if af["exit_code"] == 0 and (af["stdout"] or "").strip():
        raise err("dépôt avec core.attributesFile externe — refusé fail-closed (L10.1)")
    # (c) attributs du dépôt (git-dir/info/attributes) — symlink sortant refusé fail-closed
    reject_if_filter_file(gitdir / "info" / "attributes", err=err, refuse_symlink=True)

    # (d) .gitattributes récursifs sous toplevel (élaguer .git ; symlinks non suivis ; onerror fail-closed)
    def _onerror(walk_err: OSError) -> None:
        raise err(f"scan .gitattributes : parcours impossible ({walk_err})")

    for dirpath, dirnames, filenames in os.walk(toplevel, followlinks=False, onerror=_onerror):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if ".gitattributes" in filenames:
            reject_if_filter_file(Path(dirpath) / ".gitattributes", err=err, refuse_symlink=True)


__all__ = ["GIT_ENV", "GIT_PREFIX", "GIT_CONFIG_PREFIX", "git_env", "rev_parse_path",
           "confined_repo", "reject_alternates", "reject_if_filter_file", "reject_content_filters"]
