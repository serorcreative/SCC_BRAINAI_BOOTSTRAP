# Manifeste des dépôts Git — `01_CCSC` (L0-A, généré)

> **Vue générée par `scripts/generate_repo_manifest.py` — NE PAS ÉDITER À LA MAIN.**
> Source machine-readable : `registry/baseline/repos.json`. Lecture seule ; URLs de remote expurgées.

- **Dépôts découverts** : 19 (découverte dynamique, non présumée).
- **Racine** : `01_CCSC`. `00_SYSTEM` n'est pas lui-même un dépôt (voir L0-B).

| Dépôt (rel. 01_CCSC) | Branche | HEAD | Propre | Mod/Non-suivis | Tags | Stash | Version | Test | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `00_SYSTEM/foundation` | main | `f38539340` | oui | 0/0 | 0 | 0 | — | oui | actif-socle-non-adopte |
| `00_SYSTEM/orchestrator` | main | `8f4eff71b` | oui | 0/0 | 0 | 0 | — | oui | actif-hors-produit |
| `01_INGESTION` | main | `1205923b7` | oui | 0/0 | 0 | 0 | — | oui | prototype-lecteur |
| `03_EXTRACTION` | main | `19c5314cc` | oui | 0/0 | 0 | 0 | — | oui | actif-hors-produit |
| `04_KNOWLEDGE` | main | `6fdea077e` | oui | 0/0 | 0 | 0 | — | oui | actif-hors-produit-recuperable |
| `05_MEMORY` | main | `8e1678a75` | oui | 0/0 | 0 | 0 | — | oui | actif-hors-produit |
| `06_REASONING` | main | `2e7f2deab` | oui | 0/0 | 0 | 0 | — | oui | actif-hors-produit |
| `07_RUNTIME` | main | `018b2d1ad` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-hors-produit |
| `08_API` | main | `fd99488be` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | dormant |
| `09_CONTROL_PLANE` | main | `0706e408b` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-partiel |
| `10_BRAINAI` | main | `240e163c8` | **NON** | 0/1 | 0 | 0 | 1.0.0 | oui | actif-a-archiver |
| `11_BRAINAI_MEMORY` | main | `4e1efbcc0` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-produit-partiel |
| `12_BRAINAI_LEARNING` | main | `ebf00903d` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-non-raccorde |
| `13_BRAINAI_REASONING` | main | `3860ac15c` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-non-pilote |
| `14_BRAINAI_PLANNING` | main | `e9cdeae4a` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-produit-partiel |
| `15_BRAINAI_DECISION` | main | `fd5fcda21` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-non-pilote |
| `16_BRAINAI_EXECUTION` | main | `93437f33f` | oui | 0/0 | 0 | 0 | 1.0.0 | oui | actif-produit-partiel |
| `17_BRAINAI_BOOTSTRAP` | reunification/l0-integrity | `a798c6b93` | **NON** | 0/1 | 0 | 0 | 0.14.0 | oui | actif-principal |
| `SCC_BRAINAI_UI` | main | `d04fca5fe` | **NON** | 0/1 | 0 | 0 | 0.1.0 | — | dormant-recuperable-owner |

## Rôle architectural (cartographie déclarée)

| Dépôt | Rôle | Remotes |
|---|---|---|
| `00_SYSTEM/foundation` | Fondation universelle (SccObject/contrats/primitives) | `https://github.com/serorcreative/SCC_FOUNDATION.git` |
| `00_SYSTEM/orchestrator` | Orchestrateur socle 5 moteurs (E2E) | `https://github.com/serorcreative/SCC_ORCHESTRATOR.git` |
| `01_INGESTION` | Ingestion — lecteurs d'exports locaux | `https://github.com/serorcreative/SCC_INGESTION.git` |
| `03_EXTRACTION` | Extraction deterministe (8 extracteurs marqueurs) | `https://github.com/serorcreative/SCC_EXTRACTION.git` |
| `04_KNOWLEDGE` | Connaissance canonique (SHA1) | `https://github.com/serorcreative/SCC_KNOWLEDGE.git` |
| `05_MEMORY` | Memoire d'objets valides (couche != 11) | `https://github.com/serorcreative/SCC_MEMORY.git` |
| `06_REASONING` | Inference symbolique (!= delib 13) | `https://github.com/serorcreative/SCC_REASONING.git` |
| `07_RUNTIME` | Runtime gouverne (T3, jobs) ; handlers echo | `https://github.com/serorcreative/SCC_RUNTIME.git` |
| `08_API` | Exposition REST (serve()=NotImplemented) | `https://github.com/serorcreative/SCC_API.git` |
| `09_CONTROL_PLANE` | Supervision / graphe de doctrines | `https://github.com/serorcreative/SCC_CONTROL_PLANE.git` |
| `10_BRAINAI` | Kernel orchestrant 07/08/09 (a archiver ulterieurement) | `https://github.com/serorcreative/SCC_BRAINAI_KERNEL.git` |
| `11_BRAINAI_MEMORY` | Memoire episodique append-only | `https://github.com/serorcreative/SCC_BRAINAI_MEMORY.git` |
| `12_BRAINAI_LEARNING` | Apprentissage gouverne (non nourri par Pursuits) | `https://github.com/serorcreative/SCC_BRAINAI_LEARNING.git` |
| `13_BRAINAI_REASONING` | Deliberation structuree (cognition deterministe a encadrer) | `https://github.com/serorcreative/SCC_BRAINAI_REASONING.git` |
| `14_BRAINAI_PLANNING` | Planification (Kahn reel, gabarit+additif) | `https://github.com/serorcreative/SCC_BRAINAI_PLANNING.git` |
| `15_BRAINAI_DECISION` | Decision gouvernee (manifeste, statuts) | `https://github.com/serorcreative/SCC_BRAINAI_DECISION.git` |
| `16_BRAINAI_EXECUTION` | Execution gouvernee (6 garde-fous ; effet=echo) | `https://github.com/serorcreative/SCC_BRAINAI_EXECUTION.git` |
| `17_BRAINAI_BOOTSTRAP` | CORE PRODUIT BrainAI (pursue/converse/realize + livraison J2) | `https://github.com/serorcreative/SCC_BRAINAI_BOOTSTRAP.git` |
| `SCC_BRAINAI_UI` | UI gouvernee complete (transport+AGC) archivee D2 | `https://github.com/serorcreative/SCC_BRAINAI_UI.git` |

## Signaux (générés)

- Dépôts **non propres** : `10_BRAINAI`, `17_BRAINAI_BOOTSTRAP`, `SCC_BRAINAI_UI`
- Dépôts à **remotes multiples** : aucun
- Dépôts avec **stash** : aucun
- Dépôts **non cartographiés** : aucun

