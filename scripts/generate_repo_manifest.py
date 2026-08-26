#!/usr/bin/env python3
"""L0-A — Manifeste des dépôts Git sous 01_CCSC (généré, jamais saisi à la main).

Découvre dynamiquement TOUS les dépôts Git présents sous 01_CCSC (ne présume
pas leur nombre), collecte leur état réel par plomberie git, et produit :
  - registry/baseline/repos.json        (machine-readable, trié, déterministe)
  - docs/generated/REPO-MANIFEST.md     (vue Markdown générée)

Lecture seule sur les dépôts inventoriés. Aucun appel réseau, aucun LLM.
Les URLs de remote sont expurgées de tout userinfo (aucun secret émis).

Usage : python3 scripts/generate_repo_manifest.py
Le script se localise via son propre chemin ; il n'écrit que dans le Core (17).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# --- Localisation : ce script vit dans 17_BRAINAI_BOOTSTRAP/scripts/ ---
CORE = Path(__file__).resolve().parent.parent          # .../17_BRAINAI_BOOTSTRAP
CCSC = CORE.parent                                       # .../01_CCSC
OUT_JSON = CORE / "registry" / "baseline" / "repos.json"
OUT_MD = CORE / "docs" / "generated" / "REPO-MANIFEST.md"

# Rôle architectural + statut : cartographie DÉCLARÉE (auditable ici), jamais
# saisie dans la sortie. Clé = chemin relatif à 01_CCSC. Tout dépôt non listé
# ressort en "unknown" (le script ne masque jamais une découverte).
ROLE = {
    "00_SYSTEM/foundation": ("Fondation universelle (SccObject/contrats/primitives)", "actif-socle-non-adopte"),
    "00_SYSTEM/orchestrator": ("Orchestrateur socle 5 moteurs (E2E)", "actif-hors-produit"),
    "01_INGESTION": ("Ingestion — lecteurs d'exports locaux", "prototype-lecteur"),
    "03_EXTRACTION": ("Extraction deterministe (8 extracteurs marqueurs)", "actif-hors-produit"),
    "04_KNOWLEDGE": ("Connaissance canonique (SHA1)", "actif-hors-produit-recuperable"),
    "05_MEMORY": ("Memoire d'objets valides (couche != 11)", "actif-hors-produit"),
    "06_REASONING": ("Inference symbolique (!= delib 13)", "actif-hors-produit"),
    "07_RUNTIME": ("Runtime gouverne (T3, jobs) ; handlers echo", "actif-hors-produit"),
    "08_API": ("Exposition REST (serve()=NotImplemented)", "dormant"),
    "09_CONTROL_PLANE": ("Supervision / graphe de doctrines", "actif-partiel"),
    "10_BRAINAI": ("Kernel orchestrant 07/08/09 (a archiver ulterieurement)", "actif-a-archiver"),
    "11_BRAINAI_MEMORY": ("Memoire episodique append-only", "actif-produit-partiel"),
    "12_BRAINAI_LEARNING": ("Apprentissage gouverne (non nourri par Pursuits)", "actif-non-raccorde"),
    "13_BRAINAI_REASONING": ("Deliberation structuree (cognition deterministe a encadrer)", "actif-non-pilote"),
    "14_BRAINAI_PLANNING": ("Planification (Kahn reel, gabarit+additif)", "actif-produit-partiel"),
    "15_BRAINAI_DECISION": ("Decision gouvernee (manifeste, statuts)", "actif-non-pilote"),
    "16_BRAINAI_EXECUTION": ("Execution gouvernee (6 garde-fous ; effet=echo)", "actif-produit-partiel"),
    "17_BRAINAI_BOOTSTRAP": ("CORE PRODUIT BrainAI (pursue/converse/realize + livraison J2)", "actif-principal"),
    "SCC_BRAINAI_UI": ("UI gouvernee complete (transport+AGC) archivee D2", "dormant-recuperable-owner"),
}

_USERINFO = re.compile(r"://[^/@\s]*@")


def redact(url: str) -> str:
    """Retire tout userinfo (user:token@) d'une URL de remote."""
    return _USERINFO.sub("://", url.strip())


def git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(repo),
            capture_output=True, text=True, timeout=60,
        )
        return r.stdout.strip()
    except Exception as exc:  # obstacle documente, jamais fabrique
        return f"<ERREUR:{type(exc).__name__}>"


def discover_repos() -> list[Path]:
    """Tous les dossiers .git sous 01_CCSC (dynamique, ne presume pas 19)."""
    repos = []
    for gitdir in CCSC.rglob(".git"):
        # ignore les .git internes aux node_modules / venv
        p = str(gitdir)
        if "/node_modules/" in p or "/.venv/" in p or "/venv/" in p:
            continue
        if gitdir.is_dir() or gitdir.is_file():  # dir=repo, file=worktree/submodule
            repos.append(gitdir.parent)
    return sorted(set(repos), key=lambda x: str(x).lower())


def pkg_version_and_test(repo: Path) -> tuple[str | None, str | None]:
    """Version de paquet + commande de test connue (detectees, non saisies)."""
    version = None
    test_cmd = None
    pyproject = repo / "pyproject.toml"
    pkgjson = repo / "package.json"
    if pyproject.exists():
        txt = pyproject.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']', txt)
        if m:
            version = m.group(1)
        test_cmd = "pytest"
    if pkgjson.exists():
        try:
            data = json.loads(pkgjson.read_text(encoding="utf-8", errors="replace"))
            version = version or data.get("version")
            scripts = data.get("scripts", {})
            if "test" in scripts:
                test_cmd = f"npm test  ({scripts['test']})"
        except Exception:
            pass
    return version, test_cmd


def collect(repo: Path) -> dict:
    rel = str(repo.relative_to(CCSC))
    porcelain = git(repo, "status", "--porcelain")
    modified, untracked = [], []
    for line in porcelain.splitlines():
        if line.startswith("??"):
            untracked.append(line[3:])
        elif line.strip():
            modified.append(line)
    remotes_raw = git(repo, "remote", "-v")
    remotes = sorted({redact(l.split("\t")[1].split(" ")[0])
                      for l in remotes_raw.splitlines() if "\t" in l})
    tags = [t for t in git(repo, "tag").splitlines() if t]
    stashes = [s for s in git(repo, "stash", "list").splitlines() if s]
    version, test_cmd = pkg_version_and_test(repo)
    role, status = ROLE.get(rel, ("UNKNOWN (dépôt non cartographié — a classer)", "unknown"))
    return {
        "path_rel_ccsc": rel,
        "logical_name": repo.name,
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": git(repo, "rev-parse", "HEAD"),
        "remotes": remotes,
        "clean": not porcelain,
        "modified": modified,
        "untracked": untracked,
        "modified_count": len(modified),
        "untracked_count": len(untracked),
        "tags": tags,
        "stashes": stashes,
        "package_version": version,
        "known_test_command": test_cmd,
        "architectural_role": role,
        "lifecycle_status": status,
    }


def render_md(manifest: dict) -> str:
    repos = manifest["repos"]
    lines = [
        "# Manifeste des dépôts Git — `01_CCSC` (L0-A, généré)",
        "",
        "> **Vue générée par `scripts/generate_repo_manifest.py` — NE PAS ÉDITER À LA MAIN.**",
        "> Source machine-readable : `registry/baseline/repos.json`. Lecture seule ; URLs de remote expurgées.",
        "",
        f"- **Dépôts découverts** : {manifest['repo_count']} (découverte dynamique, non présumée).",
        f"- **Racine** : `01_CCSC`. `00_SYSTEM` n'est pas lui-même un dépôt (voir L0-B).",
        "",
        "| Dépôt (rel. 01_CCSC) | Branche | HEAD | Propre | Mod/Non-suivis | Tags | Stash | Version | Test | Statut |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in repos:
        lines.append(
            f"| `{r['path_rel_ccsc']}` | {r['branch']} | `{r['head'][:9]}` | "
            f"{'oui' if r['clean'] else '**NON**'} | {r['modified_count']}/{r['untracked_count']} | "
            f"{len(r['tags'])} | {len(r['stashes'])} | {r['package_version'] or '—'} | "
            f"{'oui' if r['known_test_command'] else '—'} | {r['lifecycle_status']} |"
        )
    lines += ["", "## Rôle architectural (cartographie déclarée)", "",
              "| Dépôt | Rôle | Remotes |", "|---|---|---|"]
    for r in repos:
        rem = ", ".join(f"`{x}`" for x in r["remotes"]) or "—"
        lines.append(f"| `{r['path_rel_ccsc']}` | {r['architectural_role']} | {rem} |")
    # Signaux notables (dépôts sales, remotes multiples, stashes) — généré
    dirty = [r["path_rel_ccsc"] for r in repos if not r["clean"]]
    multi = [r["path_rel_ccsc"] for r in repos if len(r["remotes"]) > 1]
    stashed = [r["path_rel_ccsc"] for r in repos if r["stashes"]]
    unknown = [r["path_rel_ccsc"] for r in repos if r["lifecycle_status"] == "unknown"]
    lines += ["", "## Signaux (générés)", ""]
    lines.append(f"- Dépôts **non propres** : {', '.join(f'`{d}`' for d in dirty) or 'aucun'}")
    lines.append(f"- Dépôts à **remotes multiples** : {', '.join(f'`{d}`' for d in multi) or 'aucun'}")
    lines.append(f"- Dépôts avec **stash** : {', '.join(f'`{d}`' for d in stashed) or 'aucun'}")
    lines.append(f"- Dépôts **non cartographiés** : {', '.join(f'`{d}`' for d in unknown) or 'aucun'}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    repos = [collect(r) for r in discover_repos()]
    manifest = {
        "kind": "repo_manifest_baseline",
        "lot": "L0-A",
        "ccsc_root": str(CCSC),
        "repo_count": len(repos),
        "repos": repos,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    OUT_MD.write_text(render_md(manifest) + "\n", encoding="utf-8")
    print(f"OK — {len(repos)} dépôts. Écrit :\n  {OUT_JSON}\n  {OUT_MD}")


if __name__ == "__main__":
    main()
