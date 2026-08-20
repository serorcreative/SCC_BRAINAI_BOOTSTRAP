# Registre d'évolution — BrainAI (RS-2)

> Mécanisme **RS-2** du Plan Directeur BrainAI v1.0 (gelé le 20 août 2026). Toute idée, dette ou évolution
> de périmètre passe par ce registre. La **séquence du Plan Directeur (J0→J7) n'est modifiable que via une
> entrée de ce registre** (statut `planifiée`/`absorbée`/`abandonnée`), jamais en silence. Fonction inaugurale
> (Jalon 0) : **rendre visible toute dette qui n'était écrite nulle part ailleurs** — doctrine SCC-DOC-0030
> « rien ne se perd ».

**Statuts** : `consignée` (enregistrée, sans jalon) · `planifiée(jalon)` (rattachée à un jalon) ·
`absorbée` (intégrée ailleurs) · `abandonnée(motif)` · `résolue(commit)`.
**Créé** : Jalon 0, 2026-08-20. Ce registre est append-friendly (on ajoute/ré-statue, on ne réécrit pas l'histoire).

---

## 1. Résolues pendant le Jalon 0
| ID | Dette | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-001 | `events.jsonl` non append-only (`EventRecorder.dump`→`write_text` tronquait à chaque processus) | 2026-08-06 | REVUE_01_CCSC.md | **résolue(7c065a5)** | — (test append-only ajouté) |
| RS-002 | Collision `proposal_id` (id indépendant du contenu du Brief) | 2026-08-06 | REVUE_01_CCSC.md | **résolue** (déjà corrigé avant J0 : `proposals.py` inclut `brief`) | — |

## 2. Dettes consignées à la clôture COGNITIVE-IDENTITY-001 (jamais listées hors du rapport de clôture)
| ID | Dette | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-003 | **D1** — la prose du modèle présume parfois du routage d'une inconnue (« phase suivante »), contraire à D5/A2 | 2026-08-20 | CLOTURE_COGNITIVE-IDENTITY-001.md | `consignée` | Backlog cognition — surveiller sur plusieurs cas avant tout durcissement de mission |
| RS-004 | **D2** — porosité besoin/contrainte : une contrainte issue d'une solution peut migrer dans `besoin_fondamental` | 2026-08-20 | idem | `planifiée(EPISTEMIC-PROVENANCE)` | Porter provenance/statut d'un élément via l'extension additive de `ELEMENT` |
| RS-005 | **D3** — Art.7 : `readiness=ready` (appréciation) émis avant confirmation humaine ; non-conformité à l'observable littéral (substance préservée) | 2026-08-20 | idem | `planifiée(EPISTEMIC-PROVENANCE, en tête)` | Réconciliation de gouvernance `ready`(appréciation) vs `realize`(confirmation) — **sans modifier la Constitution sans arbitrage** |
| RS-006 | **A2 (dette)** — `COGNITIVE_IDENTITY` et `CONDENSED_IDENTITY` doivent rester sémantiquement synchrones ; aucun test ne le vérifie | 2026-08 | PROMPT_FINAL / clôture | `consignée` | À couvrir lors de la migration identité en donnée gouvernée |
| RS-007 | **Tâche 3** — missions understanding/specification non exercées en réel (essence injectée non validée sur modèle) | 2026-08-20 | clôture | `consignée` | Chantier corpus |
| RS-008 | **M7** — `understanding` impose ses 7 champs dès le 1er contact du besoin (tension avec l'écoute libre) | 2026-08 | CARTOGRAPHIE_INTEGRATION_V1_V2.md | `consignée` | Chantier corpus (trancher sur preuves) |
| RS-009 | **A5** — aucun budget global de dialogue par Pursuit (plafond par appel seulement) | 2026-08 | PROMPT_FINAL | `consignée` | Voir RS-016 (budget de première classe) |

## 3. Décisions de jalon proches (à trancher aux jalons indiqués)
| ID | Objet | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-010 | **UI Tauri legacy** (`SCC_BRAINAI_UI`) — pilote la Surface legacy dormante | 2026-08-20 | archéologie globale | `consignée` — **archive par défaut** | Réorientation **seulement si J3** démontre une réutilisation directement rentable pour le Workspace final |
| RS-011 | **Auto-approbation `brainai-human`** dans 10_kernel (`scc_gateway`) — approbation trompeuse (non-humaine réelle) | 2026-08-20 | archéologie (agent modules) | `consignée` | **Décision en J3** |

## 4. Concepts PERDUS de l'archéologie V1 (Phase 0) — à placer ou différer explicitement (rien ne se perd)
| ID | Concept perdu | Date source | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-012 | **OCOS** — couche de gouvernance neutre au-dessus de BrainAI (multi-moteurs/agents) | Phase 0 (CHARTER-OCOS-001/002/003) | archéologie A4 | `consignée` | **Arbitrage de gouvernance requis** : absorbé dans « Gouvernance » / renommé / différé |
| RS-013 | **Délibération multi-fournisseurs réelle** (plusieurs LLM sous gouvernance ; providers = stubs) | 3 août / Phase 0 | archéologie | `consignée` | ADAPTER-CHANNELS (canal) **+ décision** sur la délibération concurrente |
| RS-014 | **Atlas des outils / moteur d'aiguillage** (catalogue outils-IA-MCP-API + sélection contextuelle) | Phase 0 (J1/J4) | archéologie | `consignée` — **sans épic** | À jalonner (probable dépendance du plan d'Exécution) |
| RS-015 | **Multi-tenant / orchestration souveraine BYOK-Managed-Mixte** (credentials, facturation, RGPD, OWNER) | Phase 0 (J4/positionnement) | archéologie | `consignée` | Post-v1 produit |
| RS-016 | **Budget de build à plafond DUR** (1re classe, par ToolInvocation, stoppe le build) — exigence de souveraineté | 3 août / JALON-ZERO | archéologie | `consignée` | **À jalonner dans le plan d'Exécution** (ancrage : champ `cost` du descriptor) |
| RS-017 | **Boucle de retour terrain + Mémoire de DÉCISION** (pourquoi A rejetée/B retenue ; contextes de mauvais arbitrage) | Phase 0 (Débriefe/J7) | archéologie | `consignée` | MEMORY-GOVERNED |
| RS-018 | **Clôture d'activités cognitives** (statuts projet/tâche ; Continuation/Modification/**Fork**→parent ; Session Transition) | Phase 0 (J1/J2) | archéologie | `consignée` | À jalonner (gouvernance de fin d'étape) |
| RS-019 | **BrainAI Core / BrainAI Lab** (production bridée vs sandbox d'auto-amélioration validée) | Phase 0 (J7) | archéologie | `consignée` | Post-v1 |
| RS-020 | **Patrimonial Event Bus + Service Registry/SLO/PRA/Runbook + Invariant 001D** (aucune op critique ne dépend d'un humain) | Phase 0 (SCC-INFRASTRUCTURE) | archéologie | `consignée` | Post-v1 (exploitation/résilience) |
| RS-021 | **Grammaire cognitive** (familles Doctrine/Décision/Règle/Architecture/Capacité/Projet) + **retraçabilité d'impact** | Phase 0 (SCC-KNOWLEDGE) | archéologie | `consignée` | MEMORY-GOVERNED / EPISTEMIC-PROVENANCE |
| RS-022 | **Doctrine 11** (continuité sans pression) & **Doctrine 14** (arbitrage explicite obligatoire dans chaque livrable) | Phase 0 (J5/J7) | archéologie | `consignée` | À codifier (posture produit) |

## 5. Dettes techniques réelles du dépôt (état à HEAD `7c065a5`)
| ID | Dette | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-023 | **Décor vide** : ~120 sous-dossiers métier + `07_AGENTS`/`09_MONITORING`/`10_BACKUPS` (0 fichier) — un dépôt qui affiche des structures vides ment sur son état | 2026-08-06 | REVUE + archéologie | `consignée` | Passe d'honnêteté/nettoyage (archiver) — cf. CAPABILITY-HONESTY |
| RS-024 | **Dérive documentaire** : rapports readiness (6-juillet) périmés ; `SCC_ARCHITECTURE_MAP` ignore Runtime/API ; compteurs README faux | 2026-08 | REVUE + archéologie | `consignée` | Passe d'honnêteté |
| RS-025 | **Modules 10-16 orphelins** de la Surface produit (branchés au seul runtime legacy déterministe, gelés 7-juillet) | 2026-08-20 | archéologie | `consignée` | Décision : reconnecter comme greffiers d'une cognition louée / archiver |
| RS-026 | **Socle 05_MEMORY / 06_REASONING** orphelins du chemin conversationnel (vivants dans l'orchestrateur-démo seulement) | 2026-08-20 | archéologie | `consignée` | À arbitrer (le produit utilise 11_MEMORY, pas 05) |
| RS-027 | **Foundation non adoptée** (RF-001..009 : 5 moteurs dupliquent config/horloge/id/SHA au lieu de `SCC_FOUNDATION`) | 2026-07 | 00_SYSTEM/FUTURE_REFACTORING.md | `consignée` | Dette mécanique post-v1 |
| RS-028 | **Aucun CI** : 1000+ tests existent, rien ne les exécute automatiquement | 2026-08 | REVUE | `consignée` | CI minimal post-jalon |
| RS-029 | **Identité de l'acteur non authentifiée** (champ libre ; ADR-UI-004 non implémenté) | 2026-08 | ARCHITECTURE_UI / clôture | `consignée` | Post-septembre |
| RS-030 | **Fuite de provenance runtime** : l'outil `claude` injecte l'email du compte dans le contexte modèle (hors Pursuit) ; étanchéité informationnelle de l'adaptateur incomplète (RV-2 ne couvre pas l'injection fournisseur→modèle) | 2026-08-19 | Forensique Tour 3 (campagne) | `consignée` | ADAPTER-CHANNELS / CAPABILITY-HONESTY |

## 6. Dettes post-v1 de la matrice du Plan Directeur
| ID | Dette | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-031 | Implémentation multi-tenant / BYOK (cf. RS-015) | 2026-08-20 | Plan Directeur | `consignée` | Post-v1 |
| RS-032 | Sandbox « Lab » d'auto-amélioration (cf. RS-019) | 2026-08-20 | Plan Directeur | `consignée` | Post-v1 |
| RS-033 | Infra SLO/PRA/Runbook (cf. RS-020) | 2026-08-20 | Plan Directeur | `consignée` | Post-v1 |
| RS-034 | Grammaire cognitive complète (cf. RS-021) | 2026-08-20 | Plan Directeur | `consignée` | MEMORY-GOVERNED |
| RS-035 | Clients mobile / desktop | 2026-08-20 | Plan Directeur | `consignée` | Post-v1 |

---

*Toute nouvelle idée/dette est ajoutée ici avec un ID `RS-0xx`, une date, une origine, un statut et une destination.
Une évolution de la séquence du Plan Directeur exige une entrée `planifiée`/`absorbée`/`abandonnée` explicite.*
