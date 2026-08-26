#!/usr/bin/env python3
"""L0-D — Amorçage (seed) V0 du registre canonique append-only (révisé 2026-08-24).

Construit registry/canonical/events.jsonl à partir de :
  - la ratification propriétaire du 2026-08-24 (kind=ratification) ;
  - invariants + décisions gelées (origine analytique distincte de la ratification) ;
  - audits ClaudeC (artifact_evidence=sha) ; ClaudeS pending ; errata=amendment ;
  - composants depuis registry/baseline/repos.json (+ patrimoine v1/mvp) ;
  - doctrines (30) + ADR (8) générés depuis 00_SYSTEM@da87aee (comptés, non saisis) ;
  - RS-001..060 depuis docs/REGISTRE-EVOLUTION.md en kind=evolution_record
    (statut/origine/destination d'origine préservés — aucune taxonomie inventée).

APPEND-ONLY : refuse d'écraser un events.jsonl existant (après bootstrap accepté).
Déterministe. Aucune valeur secrète. Aucun comptage saisi à la main.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
CCSC = CORE.parent
SYS = CCSC / "00_SYSTEM"
REPOS = CORE / "registry" / "baseline" / "repos.json"
REGISTRE = CORE / "docs" / "REGISTRE-EVOLUTION.md"
EVENTS = CORE / "registry" / "canonical" / "events.jsonl"
DATE = "2026-08-24"
SYS_COMMIT = "da87aee"  # baseline L0-B du corpus normatif 00_SYSTEM


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry(**kw) -> dict:
    base = {
        "id": None, "kind": None, "title": None, "status": None,
        "source_paths": [], "provenance": None, "origin": None, "ratification": None,
        "git_repo": None, "git_commit": None, "doctrine_refs": [], "test_refs": [],
        "dependencies": [], "supersedes": None, "superseded_by": None,
        "migration_state": None, "lifecycle": None,
        "source_evidence": None, "artifact_evidence": None, "test_evidence": None,
        "runtime_evidence": None, "original_status": None, "destination": None,
        "known_limits": None, "created_at": DATE, "verified_at": None,
    }
    base.update(kw)
    return base


# ---------------- RATIFICATION PROPRIÉTAIRE (2026-08-24) ----------------
# Artefact propriétaire physique et versionné : la ratification est prouvable
# depuis le patrimoine, indépendamment de la conversation d'origine.
OWNER_RATIF_DOC = "docs/governance/OWNER-RATIFICATION-REUNIFICATION-CANONIQUE-2026-08-24.md"
RATIF = entry(
    id="RATIF-2026-08-24", kind="ratification",
    title="Ratification propriétaire — Réunification canonique BrainAI (Frédérique, 2026-08-24)",
    status="ratifiée", provenance="propriétaire (Frédérique)",
    source_paths=[OWNER_RATIF_DOC],
    source_evidence=OWNER_RATIF_DOC,
    artifact_evidence=f"sha256={sha256(CORE / OWNER_RATIF_DOC)}",
    known_limits="NON ratifié par cet acte : hiérarchie doctrinale détaillée ; migration SHA-1->SHA-256 ; RS-042 ; tous les autres arbitrages ouverts restent ouverts jusqu'à leur jalon.",
)

# ---------------- INVARIANTS ----------------
INVARIANTS = [
    ("INV-T3", "Règle T3 immuable : toute action critique/irréversible/sortante exige validation humaine, même A4 ; aucune couche ni future intelligence ne peut la lever",
     "01_CCSC/00_SYSTEM/decisions/ADR-0005-gouvernance-agents-regle-t3.md", ["ADR-0005"]),
    ("INV-SOUVERAINETE", "Souveraineté humaine finale (Frédérique) : l'appréciation de BrainAI ne déclenche jamais rien",
     "docs/CONSTITUTION_CONVERSATION_v0.2.md", ["CONSTITUTION-CONV-v0.2-Art11"]),
    ("INV-APPEND-ONLY", "Faits append-only, immuables, tracés ; provenance/confiance/temporalité/révisions/révocations conservées",
     "01_CCSC/00_SYSTEM/doctrines/SCC-DOC-0006-append-only.md", ["SCC-DOC-0006", "SCC-DOC-0016"]),
    ("INV-PROVIDER-INTERCHANGEABLE", "Les LLM sont des ressources cognitives interchangeables ; jamais le siège de l'identité ni de la mémoire de BrainAI",
     "docs/REGISTRE-EVOLUTION.md", ["RS-060", "SCC-DOC-0020"]),
    ("INV-COGNITION-PROMPT", "La cognition générative est louée (providers) et pilotée par l'identité/prompt ; les moteurs déterministes 13-16 gouvernent, ne pensent pas",
     "docs/RAPPORT-PATRIMONIAL-BRAINAI.md", []),
]

# ---------------- DÉCISIONS GELÉES (origine analytique distincte de la ratification) ----------------
# (id, titre, origine_analytique, ratif_point)
DECISIONS = [
    ("DEC-01", "Le Core canonique de BrainAI est le produit 17_BRAINAI_BOOTSTRAP, enrichi progressivement (aucune 5e verticale)",
     "analyse ClaudeC §3 + Rose H16 (convergence)", "pt.1"),
    ("DEC-02", "SCC = châssis souverain de services/contrats/connaissance/gouvernance/observabilité au service du Core, pas un 2e produit",
     "analyse ClaudeC §2 + Rose H1 (convergence)", "pt.2"),
    ("DEC-03", "Les facultés 11->16 sont récupérées et raccordées progressivement, faculté par faculté, jamais en bloc",
     "Rose H3 + analyse ClaudeC §6 (convergence)", "pt.3"),
    ("DEC-04", "10_BRAINAI cessera d'être une orchestration produit concurrente ; conservé comme patrimoine/rôles/sources récupérables ; aucune suppression en L0",
     "intention propriétaire + consignation RS-011/RS-025", "pt.4"),
    ("DEC-05", "11_MEMORY, 05_MEMORY, 04_KNOWLEDGE ont des finalités distinctes ; 06_REASONING != 13_REASONING ; aucune fusion par similitude de nom",
     "Rose H5/H6 (correction de ClaudeC)", "pt.5"),
    ("DEC-06", "La pseudo-cognition déterministe de 13/15 ne doit jamais être reconnectée telle quelle ; structures/gouvernance adaptables",
     "Rose H3 + analyse ClaudeC §6 (convergence)", "pt.6"),
    ("DEC-07", "BrainAI Owner = surface/édition distincte partageant le même Core et la même mémoire canonique ; aucun fork Owner",
     "analyse ClaudeC §7 (choix C) + Rose H10 (convergence)", "pt.7"),
    ("DEC-09", "Objectif septembre 2026 = pilote commercial accompagné, pas un self-service public complet",
     "intention propriétaire (JALON-ZERO 31 août)", "pt.9"),
    ("DEC-10", "Réunification par lots atomiques (une seule implémentation active, tests, revue indépendante, STOP/GO, rollback) ; aucun big-bang",
     "cadre de méthode L0 (propriétaire)", "pt.10"),
]

# DEC-08 reformulée : confirmation, pas nouvelle règle T3
DEC08 = entry(
    id="DEC-08", kind="decision_owner",
    title="Owner n'est PAS une exception à l'invariant T3 (confirmation de portée, pas nouvelle règle)",
    status="gelée", provenance="ratification propriétaire 2026-08-24",
    origin="invariant préexistant INV-T3 / ADR-0005 (aucune règle nouvelle créée)",
    ratification="RATIF-2026-08-24 pt.8", dependencies=["INV-T3"], doctrine_refs=["ADR-0005"],
    source_paths=["ratification propriétaire 2026-08-24 pt.8"],
    known_limits="Ne recrée pas T3 comme choix d'architecture autonome ; INV-T3 reste l'invariant source. Confirme seulement que la surface Owner n'y fait pas exception.",
)


def audit_entries() -> list[dict]:
    rep = CORE / "docs" / "RAPPORT-PATRIMONIAL-BRAINAI.md"
    reg = CORE / "docs" / "PATRIMOINE-REGISTRE-COUVERTURE.md"
    return [
        entry(id="AUDIT-CLAUDEC-RAPPORT", kind="audit", title="Rapport patrimonial BrainAI/SCC (ClaudeC)",
              status="present", provenance="ClaudeC", source_paths=["docs/RAPPORT-PATRIMONIAL-BRAINAI.md"],
              git_repo="17_BRAINAI_BOOTSTRAP", git_commit="a798c6b",
              source_evidence="docs/RAPPORT-PATRIMONIAL-BRAINAI.md@a798c6b",
              artifact_evidence=f"sha256={sha256(rep)}",
              known_limits="Périmètre = système de fichiers (code+docs) ; N'A PAS couvert Git/runtime/cloud/conversations (errata)."),
        entry(id="AUDIT-CLAUDEC-REGISTRE", kind="audit", title="Registre de couverture patrimoniale (ClaudeC)",
              status="present", provenance="ClaudeC", source_paths=["docs/PATRIMOINE-REGISTRE-COUVERTURE.md"],
              git_repo="17_BRAINAI_BOOTSTRAP", git_commit="a798c6b",
              source_evidence="docs/PATRIMOINE-REGISTRE-COUVERTURE.md@a798c6b",
              artifact_evidence=f"sha256={sha256(reg)}",
              known_limits="Bandeau 'EN COURS' résiduel ; qualifications 'doublon' 05/11 & 06/13 trop larges (errata)."),
        entry(id="AUDIT-CLAUDES-RAPPORT", kind="audit", title="Rapport patrimonial ClaudeS",
              status="pending_absent", provenance="ClaudeS",
              source_paths=["docs/audits/BRAINAI-AUDIT-PATRIMONIAL-CLAUDES.md (attendu)"],
              known_limits="Hors drive accessible ; à déposer dans docs/audits/. Aucun hash fabriqué."),
        entry(id="AUDIT-CLAUDES-REGISTRE", kind="audit", title="Registre de couverture ClaudeS",
              status="pending_absent", provenance="ClaudeS",
              source_paths=["docs/audits/BRAINAI-AUDIT-REGISTRE-COUVERTURE.md (attendu)"],
              known_limits="Hors drive accessible ; à déposer dans docs/audits/. Aucun hash fabriqué."),
        entry(id="AMEND-ERRATA-AUDITS", kind="amendment",
              title="Errata des audits (réconciliation ClaudeC<->ClaudeS) — N'EST PAS un audit",
              status="pending_claudes", provenance="mission L0-C",
              source_paths=["docs/audits/AUDIT-ERRATA-2026-08-23.md (L0-C, à créer)"],
              known_limits="L0-C BLOQUÉ : items ClaudeS-only (00_ADMIN, 35999/36000, SCRINMO) non sourçables sans les fichiers ClaudeS."),
    ]


# migration_state (matrice §6) ; lifecycle (état RÉEL §2)
COMP = {
    "00_SYSTEM/foundation": ("doctrine", "teste", "Fondation universelle (SccObject) — non adoptee par moteurs (RF-001..009)"),
    "00_SYSTEM/orchestrator": ("connecter", "teste", "Orchestrateur 5 moteurs ; E2E reel scc_orchestrator"),
    "01_INGESTION": ("banc_patrimoine", "prototype", "Lecteurs d'exports locaux (0 API)"),
    "03_EXTRACTION": ("adapter", "teste", "8 extracteurs marqueurs deterministes"),
    "04_KNOWLEDGE": ("connecter", "teste", "Connaissance canonique SHA1"),
    "05_MEMORY": ("connecter", "teste", "Memoire d'objets valides (couche != 11)"),
    "06_REASONING": ("conserver", "teste", "Inference symbolique (!= delib 13)"),
    "07_RUNTIME": ("connecter", "teste", "Gouvernance T3 reelle ; handlers metier=echo (NE JAMAIS rebrancher tels quels)"),
    "08_API": ("reecrire_partiel", "dormant", "serve()=NotImplementedError"),
    "09_CONTROL_PLANE": ("connecter", "teste", "Graphe doctrines + health reels"),
    "10_BRAINAI": ("adapter", "raccorde", "Kernel orchestrant 07/08/09 (patrimoine/roles recuperables, DEC-04) ; ne pilote pas 11-16"),
    "11_BRAINAI_MEMORY": ("connecter", "raccorde", "Journal episodique ; produit=livraison J2 seulement"),
    "12_BRAINAI_LEARNING": ("connecter", "code", "Reel mais NON nourri par les Pursuits (chainon J4-d)"),
    "13_BRAINAI_REASONING": ("ne_jamais_rebrancher", "code", "Deliberation ; arbitrage deterministe rédige une victoire sur egalite (DEC-06)"),
    "14_BRAINAI_PLANNING": ("connecter", "raccorde", "Kahn reel utilise en livraison J2"),
    "15_BRAINAI_DECISION": ("ne_jamais_rebrancher", "code", "Manifeste/statuts recuperables ; scoring deterministe non (DEC-06)"),
    "16_BRAINAI_EXECUTION": ("connecter", "raccorde", "6 garde-fous reels ; effet metier=echo a remplacer"),
    "17_BRAINAI_BOOTSTRAP": ("conserver", "exerce_reellement", "CORE produit BrainAI (pursue/converse/realize) — DEC-01"),
    "SCC_BRAINAI_UI": ("conserver", "dormant", "UI gouvernee complete archivee D2 — base Owner (DEC-07)"),
}


def component_entries(repos: dict) -> list[dict]:
    out = []
    for r in repos["repos"]:
        rel = r["path_rel_ccsc"]
        mig, life, note = COMP.get(rel, ("n_a", None, "non cartographie"))
        out.append(entry(
            id="COMP-" + re.sub(r"[^A-Z0-9]", "_", rel.upper()),
            kind="component", title=f"{r['logical_name']} — {r['architectural_role']}",
            status=r["lifecycle_status"], source_paths=[f"01_CCSC/{rel}"],
            provenance="repos.json (L0-A)", git_repo=r["logical_name"], git_commit=r["head"],
            migration_state=mig, lifecycle=life,
            source_evidence=f"01_CCSC/{rel}@{r['head'][:9]}",
            known_limits=note,
        ))
    return out


HERITAGE = [
    ("COMP-HERITAGE-BRAINAI-V1", "brainai-v1 — prototype TS event-source (journal pur, cognition prompt)",
     "banc_patrimoine", "prototype", "90_HERITAGE/PROJETS IA/BRAIN AI/Code/brainai-v1",
     "Fonctions pures journal (reconstruction/projection) plus mures que stores JSONL actuels ; MOAT #6 fondations seules"),
    ("COMP-HERITAGE-BRAINAI-MVP", "brainai-mvp — generateur Blueprint (6 Blueprints reels + 1 copie)",
     "archiver", "prototype", "90_HERITAGE/PROJETS IA/BRAIN AI/Code/brainai-mvp",
     "Anthropic SDK + Node (PAS Base44) ; 0 test ; remplace par v1 puis 17"),
]


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _status_doctrine(text: str) -> str:
    m = re.search(r"\*\*Statut\*\*\s*\|\s*([^|]+?)\s*\|", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\*\*Statut\*\*\s*:\s*(.+)", text)
    return m.group(1).strip() if m else "unknown"


def corpus_entries(subdir: str, id_re: str, kind: str) -> list[dict]:
    d = SYS / subdir
    out = []
    for f in sorted(d.glob("*.md")):
        m = re.match(id_re, f.name)
        if not m:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        cid = m.group(1)
        title = _first_heading(text) or cid
        status = _status_doctrine(text)
        out.append(entry(
            id=cid, kind=kind, title=title, status=status,
            source_paths=[f"01_CCSC/00_SYSTEM/{subdir}/{f.name}"],
            provenance="corpus normatif 00_SYSTEM (L0-B)", git_repo="00_SYSTEM", git_commit=SYS_COMMIT,
            source_evidence=f"01_CCSC/00_SYSTEM/{subdir}/{f.name}@{SYS_COMMIT}",
        ))
    return out


def rs_entries() -> list[dict]:
    """RS-0xx en evolution_record : statut/origine/destination d'origine préservés."""
    if not REGISTRE.exists():
        return []
    seen, out = set(), []
    for line in REGISTRE.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("| RS-"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 7 or not cells[1].startswith("RS-"):
            continue
        base = re.match(r"(RS-\d+)", cells[1])
        if not base:
            continue
        rid = base.group(1)
        if rid in seen:
            continue
        seen.add(rid)
        clean = lambda s: re.sub(r"\s+", " ", re.sub(r"[*`]", "", s)).strip()
        title = clean(cells[2])[:160]
        origin = clean(cells[4])[:120] or None
        status = clean(cells[5])[:100] or "unknown"
        dest = clean(cells[6])[:160] or None
        out.append(entry(
            id=rid, kind="evolution_record", title=title, status=status,
            original_status=status, destination=dest, origin=origin,
            source_paths=["docs/REGISTRE-EVOLUTION.md"], provenance="REGISTRE-EVOLUTION (RS-2)",
            source_evidence="docs/REGISTRE-EVOLUTION.md",
        ))
    return out


def main() -> None:
    if EVENTS.exists() and EVENTS.stat().st_size > 0:
        print(f"REFUS (append-only) : {EVENTS} existe déjà. Ne pas régénérer ; appendre.", file=sys.stderr)
        sys.exit(2)
    repos = json.loads(REPOS.read_text(encoding="utf-8"))
    entries: list[dict] = [RATIF]
    for iid, title, src, drefs in INVARIANTS:
        entries.append(entry(id=iid, kind="invariant", title=title, status="actif",
                             source_paths=[src], provenance="cadre gelé", doctrine_refs=drefs,
                             source_evidence=src))
    for did, title, origin, pt in DECISIONS:
        entries.append(entry(id=did, kind="decision_owner", title=title, status="gelée",
                             provenance="ratification propriétaire 2026-08-24", origin=origin,
                             ratification=f"RATIF-2026-08-24 {pt}",
                             source_paths=[f"ratification propriétaire 2026-08-24 {pt}"]))
    entries.append(DEC08)
    entries += audit_entries()
    entries += component_entries(repos)
    for hid, title, mig, life, path, note in HERITAGE:
        entries.append(entry(id=hid, kind="component", title=title, status="patrimoine",
                             source_paths=[path], provenance="scan 90_HERITAGE",
                             migration_state=mig, lifecycle=life, source_evidence=path, known_limits=note))
    entries += corpus_entries("doctrines", r"(SCC-DOC-\d+)", "doctrine")
    entries += corpus_entries("decisions", r"(ADR-\d+)", "adr")
    entries += rs_entries()

    ids = [e["id"] for e in entries]
    dups = sorted({x for x in ids if ids.count(x) > 1})
    if dups:
        print(f"ERREUR ids dupliqués : {dups}", file=sys.stderr)
        sys.exit(3)
    entries.sort(key=lambda e: e["id"])
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"OK — {len(entries)} entrées écrites dans {EVENTS}")


if __name__ == "__main__":
    main()
