#!/usr/bin/env python3
"""L0-E.3 — Artefact de baseline de tests : TRANSFORMATEUR PUR.

Ne lance NI pytest, NI git, NI subprocess, NI reseau, NI LLM/provider.
Transforme deux entrees explicites en deux artefacts :

  argv[1] = JUnit-XML produit par le runner reel  -> comptages
  argv[2] = JSON de metadonnees explicites (commande L0-E.3) -> contexte

  ecritures (SEULES autorisees) :
    registry/baseline/tests.json
    docs/generated/TEST-BASELINE.md

Comptages issus EXCLUSIVEMENT des attributs <testsuite> JUnit. Les statuts non
derivables (xfailed/xpassed) ne sont JAMAIS inventes. Versions Python/pytest et
tout contexte d'execution proviennent d'argv[2], jamais de l'interpreteur courant.
Aucun secret, aucun contenu de Pursuit, aucune donnee metier.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
OUT_JSON = CORE / "registry" / "baseline" / "tests.json"
OUT_MD = CORE / "docs" / "generated" / "TEST-BASELINE.md"

SCOPE_INCLUDED = ("tests/ (suite deterministe locale : stdlib pur ; subprocess LOCAUX ; "
                  "loopback 127.0.0.1 ; frontieres externes piegees par monkeypatch)")
SCOPE_EXCLUDED = "test_real_claude_brief (test_builder_understanding.py) — appel LLM facturable"
OTHER_STATUSES = {
    "xfailed": "not_distinguishable_from_junit_suite_attributes",
    "xpassed": "not_distinguishable_from_junit_suite_attributes",
}
PROOF_NO_LLM = {
    "scope": "this_baseline_execution",
    "llm_gate": "BRAINAI_JALON_LLM unset",
    "excluded_test": "test_real_claude_brief",
    "exclusion_mechanism": "pytest skipif (apparait dans skipped)",
    "other_boundaries": "tests builder : run_confined piege par monkeypatch ; subprocess locaux ; loopback local",
    "claim": "aucun test LLM/provider volontairement active pendant cette execution",
    "limitation": "ne constitue PAS une preuve universelle d'impossibilite reseau du code",
}
KNOWN_LIMITS = ("'test passe' != 'capacite exercee en runtime reel' : cette baseline prouve la "
                "non-regression deterministe, pas l'exercice LLM reel (Etage 2, hors perimetre 0 euro). "
                "Snapshot date (duree variable) : non byte-reproductible ; la CI ne le regenere pas.")
PROVENANCE = "attributs <testsuite> du JUnit-XML du runner reel (parses) + metadonnees explicites (argv[2])"


def parse_junit(path: Path) -> dict:
    """Comptages issus EXCLUSIVEMENT des attributs <testsuite> ; passed calcule, jamais negatif."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not suites:
        raise SystemExit("JUnit XML : aucun <testsuite>")
    tests = failures = errors = skipped = 0
    time_total = 0.0
    has_time = False
    for ts in suites:
        tests += int(ts.get("tests", "0"))
        failures += int(ts.get("failures", "0"))
        errors += int(ts.get("errors", "0"))
        skipped += int(ts.get("skipped", "0"))
        t = ts.get("time")
        if t is not None:
            time_total += float(t)
            has_time = True
    passed = tests - failures - errors - skipped
    if passed < 0:
        raise SystemExit(f"passed negatif ({passed}) : attributs JUnit incoherents")
    return {
        "tests": tests, "passed": passed, "failed": failures,
        "errors": errors, "skipped": skipped,
        "duration_s": round(time_total, 2) if has_time else None,
    }


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: generate_test_baseline.py <junit.xml> <metadata.json>")
    counts = parse_junit(Path(sys.argv[1]))
    meta = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    commit = str(meta["core_commit"])
    baseline = {
        "lot": "L0-E",
        "date": meta["date"],
        "core_commit": commit,
        "core_commit_short": commit[:7],
        "branch": meta["branch"],
        "runtime": {"python_version": meta["python_version"], "pytest_version": meta["pytest_version"]},
        "framework": "pytest",
        "command": meta["command"],
        "scope_included": SCOPE_INCLUDED,
        "scope_excluded": SCOPE_EXCLUDED,
        "exclusion_reason": "gate BRAINAI_JALON_LLM absent -> appel LLM facturable non active",
        "results": counts,
        "other_statuses_available": OTHER_STATUSES,
        "proof_no_llm": PROOF_NO_LLM,
        "proof_data_unchanged": {
            "observed": bool(meta["data_unchanged"]),
            "method": "empreintes sha256 de data/ avant/apres identiques + garde conftest _guard_real_data_dir_unchanged",
        },
        "proof_git_unchanged": {
            "observed": bool(meta["git_unchanged"]),
            "method": "arbre Git compare avant/apres le run (aucun fichier cree/modifie par la suite)",
        },
        "known_limits": KNOWN_LIMITS,
        "provenance": PROVENANCE,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    r = counts
    dur = f"{r['duration_s']} s" if r["duration_s"] is not None else "non disponible"
    md = [
        "# Baseline de tests — Core BrainAI (L0-E, genere)",
        "",
        "> Genere par `scripts/generate_test_baseline.py` (transformateur pur) depuis la sortie",
        "> JUnit-XML reelle du runner + metadonnees explicites. NE PAS EDITER A LA MAIN.",
        "> Machine-readable : `registry/baseline/tests.json`.",
        "",
        f"- **Core commit teste** : `{baseline['core_commit_short']}` (branche `{baseline['branch']}`)",
        f"- **Runtime** : Python {meta['python_version']} · pytest {meta['pytest_version']}",
        f"- **Commande** : `{baseline['command']}`",
        "",
        "## Resultats (comptages issus des attributs <testsuite> JUnit)",
        "",
        f"- **passed** : {r['passed']}",
        f"- **failed** : {r['failed']}",
        f"- **errors** : {r['errors']}",
        f"- **skipped** : {r['skipped']} (inclut le test facturable exclu)",
        f"- **total collectes** : {r['tests']}",
        f"- **duree** : {dur} (snapshot, variable)",
        "- **xfailed / xpassed** : non distinguables des attributs `<testsuite>` (non inventes)",
        "",
        "## Garanties (bornees a cette execution)",
        "- **0 LLM (observe)** : gate `BRAINAI_JALON_LLM` unset ; `test_real_claude_brief` skippe ; "
        "frontieres externes locales/monkeypatchees. NE prouve pas une impossibilite reseau universelle.",
        f"- **data/ non modifie** : observe={baseline['proof_data_unchanged']['observed']}.",
        f"- **arbre Git non modifie** : observe={baseline['proof_git_unchanged']['observed']}.",
        "",
        f"> Limites : {KNOWN_LIMITS}",
        "",
    ]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"OK — baseline : {r['passed']} passed / {r['failed']} failed / {r['skipped']} skipped "
          f"/ {r['errors']} errors (total {r['tests']}, {dur})")


if __name__ == "__main__":
    main()
