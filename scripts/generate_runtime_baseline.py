#!/usr/bin/env python3
"""L0-F — Baseline runtime en LECTURE SEULE (aucune mutation d'état).

Inventorie les stores de faits sous data/ : chemin, taille, nb de lignes,
SHA-256, et **schéma de clés** (clés du 1er enregistrement JSON — JAMAIS les
valeurs). Compte les Pursuits distinctes si un champ d'id est présent.

N'écrit RIEN dans data/. Ne révèle aucune valeur (aucun secret, aucun contenu
de fait). Sorties dans le Core : registry/baseline/runtime.json + vue MD.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
DATA = CORE / "data"
OUT_JSON = CORE / "registry" / "baseline" / "runtime.json"
OUT_MD = CORE / "docs" / "generated" / "RUNTIME-BASELINE.md"

# Clés candidates d'identifiant de Pursuit (comptage distinct, sans valeur exposée)
PURSUIT_KEYS = ("pursuit_id", "pursuit_ref", "pursuitId")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_jsonl(path: Path) -> dict:
    n_lines = 0
    first_keys: list[str] = []
    pursuits: set[str] = set()
    parse_errors = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            try:
                obj = json.loads(line)
            except Exception:
                parse_errors += 1
                continue
            if i == 0 and isinstance(obj, dict):
                first_keys = sorted(obj.keys())
            if isinstance(obj, dict):
                for k in PURSUIT_KEYS:
                    v = obj.get(k)
                    if isinstance(v, str) and v:
                        # on ne stocke qu'un hachage court de l'id, jamais l'id brut
                        pursuits.add(hashlib.sha256(v.encode()).hexdigest()[:12])
    return {
        "records": n_lines,
        "schema_keys_first_record": first_keys,
        "distinct_pursuits": len(pursuits),
        "parse_errors": parse_errors,
    }


def main() -> None:
    stores = []
    if DATA.exists():
        for p in sorted(DATA.rglob("*.jsonl")):
            rel = str(p.relative_to(CORE))
            info = {
                "path_rel_core": rel,
                "size_bytes": p.stat().st_size,
                "sha256": sha256(p),
            }
            info.update(inspect_jsonl(p))
            stores.append(info)
        other = sorted(
            str(p.relative_to(CORE))
            for p in DATA.rglob("*")
            if p.is_file() and p.suffix != ".jsonl" and p.name != ".gitkeep"
        )
    else:
        other = []
    baseline = {
        "kind": "runtime_baseline",
        "lot": "L0-F",
        "data_dir": str(DATA),
        "data_dir_exists": DATA.exists(),
        "store_count": len(stores),
        "stores": stores,
        "non_jsonl_files": other,
        "note": "Lecture seule ; aucune valeur/contenu exposé ; ids de Pursuit hachés.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    lines = [
        "# Baseline runtime — stores de faits (L0-F, généré, lecture seule)",
        "",
        "> Généré par `scripts/generate_runtime_baseline.py`. NE PAS ÉDITER À LA MAIN.",
        "> Aucune valeur/contenu de fait n'est exposé ; les ids de Pursuit sont hachés.",
        f"> Machine-readable : `registry/baseline/runtime.json`. `data/` est gitignoré (non versionné).",
        "",
        f"- **Stores JSONL** : {len(stores)}",
        f"- **Répertoire data** : `data/` (existe = {baseline['data_dir_exists']})",
        "",
        "| Store | Enregistrements | Pursuits distinctes | SHA-256 (court) | Taille (o) | Clés (1er) |",
        "|---|---|---|---|---|---|",
    ]
    for s in stores:
        lines.append(
            f"| `{s['path_rel_core']}` | {s['records']} | {s['distinct_pursuits']} | "
            f"`{s['sha256'][:12]}` | {s['size_bytes']} | {', '.join(s['schema_keys_first_record']) or '—'} |"
        )
    if other:
        lines += ["", "## Fichiers non-JSONL sous data/ (chemins seulement)", ""]
        lines += [f"- `{o}`" for o in other]
    lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK — {len(stores)} stores. Écrit :\n  {OUT_JSON}\n  {OUT_MD}")


if __name__ == "__main__":
    main()
