#!/usr/bin/env python3
"""L0-D — Validation fail-closed + rendu du registre canonique (vue reproductible).

Lit registry/canonical/events.jsonl, VALIDE contre registry/canonical/schema.json
(validateur pur-python), applique des gardes sémantiques fail-closed, puis rend
docs/generated/CANONICAL-REGISTRY.md de façon DÉTERMINISTE (comptages calculés).

Gardes fail-closed :
  - schéma (required, enums, additionalProperties, pattern id) ;
  - ids uniques ; aucune référence cassée (dependencies/supersedes/refs internes) ;
  - aucun secret ; runtime_evidence ne peut JAMAIS être un hash documentaire.
N'écrit JAMAIS events.jsonl. Usage : [--check] pour la CI.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
SCHEMA = CORE / "registry" / "canonical" / "schema.json"
EVENTS = CORE / "registry" / "canonical" / "events.jsonl"
OUT_MD = CORE / "docs" / "generated" / "CANONICAL-REGISTRY.md"

_SECRET = re.compile(r"(sk-ant|Bearer\s|eyJ[A-Za-z0-9_-]{10,}\.)")
_HASHISH = re.compile(r"sha-?256|[0-9a-f]{64}", re.I)
_INTERNAL_REF = re.compile(r"^(SCC-DOC-\d+|ADR-\d+|RS-\d+|INV-|DEC-|COMP-|AUDIT-|AMEND-|RATIF-)")


def validate(e: dict, schema: dict, ln: int) -> list[str]:
    errs, props = [], schema["properties"]
    for req in schema["required"]:
        if e.get(req) in (None, "") and req != "verified_at":
            errs.append(f"L{ln}: requis manquant '{req}'")
    for k in e:
        if k not in props:
            errs.append(f"L{ln}: propriété inconnue '{k}'")
    if e.get("kind") not in props["kind"]["enum"]:
        errs.append(f"L{ln}: kind invalide '{e.get('kind')}'")
    for f in ("migration_state", "lifecycle"):
        if e.get(f) not in props[f]["enum"]:
            errs.append(f"L{ln}: {f} invalide '{e.get(f)}'")
    if e.get("id") and not re.match(r"^[A-Z][A-Z0-9_.-]+$", e["id"]):
        errs.append(f"L{ln}: id non conforme '{e['id']}'")
    # garde secret
    for k, v in e.items():
        if isinstance(v, str) and _SECRET.search(v):
            errs.append(f"L{ln}: valeur suspecte (secret ?) dans '{k}'")
    # garde evidence : un hash n'est jamais runtime_evidence/test_evidence
    for k in ("runtime_evidence", "test_evidence"):
        v = e.get(k)
        if isinstance(v, str) and _HASHISH.search(v):
            errs.append(f"L{ln}: {k} contient un hash documentaire (doit être artifact_evidence)")
    return errs


def check_refs(entries: list[dict]) -> list[str]:
    ids = {e["id"] for e in entries}
    errs = []
    for e in entries:
        for dep in e.get("dependencies", []):
            if dep not in ids:
                errs.append(f"{e['id']}: dépendance cassée '{dep}'")
        for f in ("supersedes", "superseded_by"):
            v = e.get(f)
            if v and v not in ids:
                errs.append(f"{e['id']}: {f} cassé '{v}'")
        for ref in e.get("doctrine_refs", []):
            if _INTERNAL_REF.match(ref) and ref not in ids:
                errs.append(f"{e['id']}: doctrine_ref interne cassée '{ref}'")
    return errs


def load_entries(schema: dict) -> list[dict]:
    entries, errs, ids = [], [], []
    for i, line in enumerate(EVENTS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception as exc:
            errs.append(f"L{i}: JSON invalide ({exc})")
            continue
        errs += validate(e, schema, i)
        entries.append(e)
        ids.append(e.get("id"))
    dups = sorted({x for x in ids if ids.count(x) > 1})
    if dups:
        errs.append(f"ids dupliqués : {dups}")
    errs += check_refs(entries)
    if errs:
        print("VALIDATION ÉCHOUÉE (fail-closed) :", file=sys.stderr)
        for x in errs:
            print("  -", x, file=sys.stderr)
        sys.exit(4)
    entries.sort(key=lambda e: e["id"])
    return entries


def render(entries: list[dict]) -> str:
    by_kind = Counter(e["kind"] for e in entries)
    by_mig = Counter(e["migration_state"] for e in entries if e.get("migration_state") not in (None, "n_a"))
    by_life = Counter(e["lifecycle"] for e in entries if e.get("lifecycle") not in (None, "n_a"))
    ev = {f: sum(1 for e in entries if e.get(f)) for f in
          ("source_evidence", "artifact_evidence", "test_evidence", "runtime_evidence")}
    n_doc = by_kind.get("doctrine", 0)
    n_adr = by_kind.get("adr", 0)
    L = [
        "# Registre canonique BrainAI — vue générée V0 (L0-D)",
        "",
        "> **Généré par `scripts/generate_canonical_registry.py` — NE PAS ÉDITER À LA MAIN.**",
        "> Source append-only : `registry/canonical/events.jsonl` (schéma `schema.json`).",
        "> Comptages calculés. Nom de module != preuve. Preuves différenciées ; un hash documentaire",
        "> est `artifact_evidence`, jamais `runtime_evidence`.",
        "",
        "## Comptages (calculés)",
        "",
        f"- **Entrées totales** : {len(entries)}",
        f"- **Doctrines** : {n_doc}  ·  **ADR** : {n_adr}",
        "",
        "| Par kind | n |", "|---|---|",
    ]
    L += [f"| {k} | {by_kind[k]} |" for k in sorted(by_kind)]
    L += ["", "## Catégories de preuve utilisées (calculé)", "", "| Catégorie | entrées |", "|---|---|"]
    L += [f"| {k} | {ev[k]} |" for k in ("source_evidence", "artifact_evidence", "test_evidence", "runtime_evidence")]
    L += ["", "| Par migration_state | n |", "|---|---|"]
    L += [f"| {k} | {by_mig[k]} |" for k in sorted(by_mig)]
    L += ["", "| Par lifecycle (état réel) | n |", "|---|---|"]
    L += [f"| {k} | {by_life[k]} |" for k in sorted(by_life)]
    L += ["", "## Entrées (triées par id)", "",
          "| id | kind | title | status | orig? | ratif? | preuve |", "|---|---|---|---|---|---|---|"]
    for e in entries:
        title = e["title"].replace("|", "\\|")
        if len(title) > 90:
            title = title[:87] + "…"
        evtag = "src" if e.get("source_evidence") else "—"
        if e.get("artifact_evidence"):
            evtag = "artifact"
        if e.get("runtime_evidence"):
            evtag = "runtime"
        L.append(
            f"| `{e['id']}` | {e['kind']} | {title} | {e['status']} | "
            f"{'o' if e.get('origin') else '—'} | {'o' if e.get('ratification') else '—'} | {evtag} |"
        )
    L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    check = "--check" in sys.argv
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    entries = load_entries(schema)
    rendered = render(entries)
    if check:
        current = OUT_MD.read_text(encoding="utf-8") if OUT_MD.exists() else ""
        if current != rendered:
            print("CANONICAL-REGISTRY.md N'EST PAS À JOUR.", file=sys.stderr)
            sys.exit(5)
        print(f"OK (check) — vue à jour, {len(entries)} entrées.")
        return
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(rendered, encoding="utf-8")
    print(f"OK — {len(entries)} entrées validées et rendues → {OUT_MD}")


if __name__ == "__main__":
    main()
