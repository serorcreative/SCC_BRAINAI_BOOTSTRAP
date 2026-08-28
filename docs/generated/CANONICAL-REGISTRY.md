# Registre canonique BrainAI — vue générée V0 (L0-D)

> **Généré par `scripts/generate_canonical_registry.py` — NE PAS ÉDITER À LA MAIN.**
> Source append-only : `registry/canonical/events.jsonl` (schéma `schema.json`).
> Comptages calculés. Nom de module != preuve. Preuves différenciées ; un hash documentaire
> est `artifact_evidence`, jamais `runtime_evidence`.

## Comptages (calculés)

- **Entrées totales** : 150
- **Doctrines** : 30  ·  **ADR** : 8

| Par kind | n |
|---|---|
| adr | 8 |
| amendment | 1 |
| audit | 5 |
| component | 21 |
| decision_owner | 11 |
| doctrine | 30 |
| evolution_record | 62 |
| invariant | 5 |
| milestone | 6 |
| ratification | 1 |

## Catégories de preuve utilisées (calculé)

| Catégorie | entrées |
|---|---|
| source_evidence | 134 |
| artifact_evidence | 5 |
| test_evidence | 5 |
| runtime_evidence | 5 |

| Par migration_state | n |
|---|---|
| adapter | 2 |
| archiver | 1 |
| banc_patrimoine | 2 |
| connecter | 9 |
| conserver | 3 |
| doctrine | 1 |
| ne_jamais_rebrancher | 2 |
| reecrire_partiel | 1 |

| Par lifecycle (état réel) | n |
|---|---|
| code | 3 |
| dormant | 2 |
| exerce_reellement | 1 |
| prototype | 3 |
| raccorde | 4 |
| teste | 8 |

## Entrées (triées par id)

| id | kind | title | status | orig? | ratif? | preuve |
|---|---|---|---|---|---|---|
| `ADR-0000` | adr | ADR-0000 — Architecture générale de Seror Créative Core | Accepté | — | — | src |
| `ADR-0001` | adr | ADR-0001 — Découplage strict des moteurs par contrats de données | Accepté | — | — | src |
| `ADR-0002` | adr | ADR-0002 — Fondation commune SCC | Accepté | — | — | src |
| `ADR-0003` | adr | ADR-0003 — Runtime officiel SCC | Accepté | — | — | src |
| `ADR-0004` | adr | ADR-0004 — Orchestrateur transverse | Accepté | — | — | src |
| `ADR-0005` | adr | ADR-0005 — Gouvernance des Agents et règle T3 | Accepté | — | — | src |
| `ADR-0006` | adr | ADR-0006 — Meta Model officiel | Accepté | — | — | src |
| `ADR-0007` | adr | ADR-0007 — Readiness et critères d'entrée BrainAI | Accepté | — | — | src |
| `AMEND-ERRATA-AUDITS` | amendment | Errata des audits (réconciliation ClaudeC<->ClaudeS) — N'EST PAS un audit | pending_claudes | — | — | — |
| `AUDIT-CLAUDEC-RAPPORT` | audit | Rapport patrimonial BrainAI/SCC (ClaudeC) | present | — | — | artifact |
| `AUDIT-CLAUDEC-REGISTRE` | audit | Registre de couverture patrimoniale (ClaudeC) | present | — | — | artifact |
| `AUDIT-CLAUDES-RAPPORT` | audit | Rapport patrimonial ClaudeS | pending_absent | — | — | — |
| `AUDIT-CLAUDES-REGISTRE` | audit | Registre de couverture ClaudeS | pending_absent | — | — | — |
| `AUDIT-HUMAN-FIXTURE-REVIEW-2026-08-25` | audit | Revue humaine ciblée des fixtures de test (faux secrets potentiels) — PASS borné | human_fixture_review_pass_scoped | o | — | artifact |
| `COMP-00_SYSTEM_FOUNDATION` | component | foundation — Fondation universelle (SccObject/contrats/primitives) | actif-socle-non-adopte | — | — | src |
| `COMP-00_SYSTEM_ORCHESTRATOR` | component | orchestrator — Orchestrateur socle 5 moteurs (E2E) | actif-hors-produit | — | — | src |
| `COMP-01_INGESTION` | component | 01_INGESTION — Ingestion — lecteurs d'exports locaux | prototype-lecteur | — | — | src |
| `COMP-03_EXTRACTION` | component | 03_EXTRACTION — Extraction deterministe (8 extracteurs marqueurs) | actif-hors-produit | — | — | src |
| `COMP-04_KNOWLEDGE` | component | 04_KNOWLEDGE — Connaissance canonique (SHA1) | actif-hors-produit-recuperable | — | — | src |
| `COMP-05_MEMORY` | component | 05_MEMORY — Memoire d'objets valides (couche != 11) | actif-hors-produit | — | — | src |
| `COMP-06_REASONING` | component | 06_REASONING — Inference symbolique (!= delib 13) | actif-hors-produit | — | — | src |
| `COMP-07_RUNTIME` | component | 07_RUNTIME — Runtime gouverne (T3, jobs) ; handlers echo | actif-hors-produit | — | — | src |
| `COMP-08_API` | component | 08_API — Exposition REST (serve()=NotImplemented) | dormant | — | — | src |
| `COMP-09_CONTROL_PLANE` | component | 09_CONTROL_PLANE — Supervision / graphe de doctrines | actif-partiel | — | — | src |
| `COMP-10_BRAINAI` | component | 10_BRAINAI — Kernel orchestrant 07/08/09 (a archiver ulterieurement) | actif-a-archiver | — | — | src |
| `COMP-11_BRAINAI_MEMORY` | component | 11_BRAINAI_MEMORY — Memoire episodique append-only | actif-produit-partiel | — | — | src |
| `COMP-12_BRAINAI_LEARNING` | component | 12_BRAINAI_LEARNING — Apprentissage gouverne (non nourri par Pursuits) | actif-non-raccorde | — | — | src |
| `COMP-13_BRAINAI_REASONING` | component | 13_BRAINAI_REASONING — Deliberation structuree (cognition deterministe a encadrer) | actif-non-pilote | — | — | src |
| `COMP-14_BRAINAI_PLANNING` | component | 14_BRAINAI_PLANNING — Planification (Kahn reel, gabarit+additif) | actif-produit-partiel | — | — | src |
| `COMP-15_BRAINAI_DECISION` | component | 15_BRAINAI_DECISION — Decision gouvernee (manifeste, statuts) | actif-non-pilote | — | — | src |
| `COMP-16_BRAINAI_EXECUTION` | component | 16_BRAINAI_EXECUTION — Execution gouvernee (6 garde-fous ; effet=echo) | actif-produit-partiel | — | — | src |
| `COMP-17_BRAINAI_BOOTSTRAP` | component | 17_BRAINAI_BOOTSTRAP — CORE PRODUIT BrainAI (pursue/converse/realize + livraison J2) | actif-principal | — | — | src |
| `COMP-HERITAGE-BRAINAI-MVP` | component | brainai-mvp — generateur Blueprint (6 Blueprints reels + 1 copie) | patrimoine | — | — | src |
| `COMP-HERITAGE-BRAINAI-V1` | component | brainai-v1 — prototype TS event-source (journal pur, cognition prompt) | patrimoine | — | — | src |
| `COMP-SCC_BRAINAI_UI` | component | SCC_BRAINAI_UI — UI gouvernee complete (transport+AGC) archivee D2 | dormant-recuperable-owner | — | — | src |
| `DEC-01` | decision_owner | Le Core canonique de BrainAI est le produit 17_BRAINAI_BOOTSTRAP, enrichi progressiveme… | gelée | o | o | — |
| `DEC-02` | decision_owner | SCC = châssis souverain de services/contrats/connaissance/gouvernance/observabilité au … | gelée | o | o | — |
| `DEC-03` | decision_owner | Les facultés 11->16 sont récupérées et raccordées progressivement, faculté par faculté,… | gelée | o | o | — |
| `DEC-04` | decision_owner | 10_BRAINAI cessera d'être une orchestration produit concurrente ; conservé comme patrim… | gelée | o | o | — |
| `DEC-05` | decision_owner | 11_MEMORY, 05_MEMORY, 04_KNOWLEDGE ont des finalités distinctes ; 06_REASONING != 13_RE… | gelée | o | o | — |
| `DEC-06` | decision_owner | La pseudo-cognition déterministe de 13/15 ne doit jamais être reconnectée telle quelle … | gelée | o | o | — |
| `DEC-07` | decision_owner | BrainAI Owner = surface/édition distincte partageant le même Core et la même mémoire ca… | gelée | o | o | — |
| `DEC-08` | decision_owner | Owner n'est PAS une exception à l'invariant T3 (confirmation de portée, pas nouvelle rè… | gelée | o | o | — |
| `DEC-09` | decision_owner | Objectif septembre 2026 = pilote commercial accompagné, pas un self-service public complet | gelée | o | o | — |
| `DEC-10` | decision_owner | Réunification par lots atomiques (une seule implémentation active, tests, revue indépen… | gelée | o | o | — |
| `DEC-11` | decision_owner | Pursuit = unité cognitive durable canonique ; Dossier reste une unité distincte de corr… | gelée | o | — | — |
| `INV-APPEND-ONLY` | invariant | Faits append-only, immuables, tracés ; provenance/confiance/temporalité/révisions/révoc… | actif | — | — | src |
| `INV-COGNITION-PROMPT` | invariant | La cognition générative est louée (providers) et pilotée par l'identité/prompt ; les mo… | actif | — | — | src |
| `INV-PROVIDER-INTERCHANGEABLE` | invariant | Les LLM sont des ressources cognitives interchangeables ; jamais le siège de l'identité… | actif | — | — | src |
| `INV-SOUVERAINETE` | invariant | Souveraineté humaine finale (Frédérique) : l'appréciation de BrainAI ne déclenche jamai… | actif | — | — | src |
| `INV-T3` | invariant | Règle T3 immuable : toute action critique/irréversible/sortante exige validation humain… | actif | — | — | src |
| `MILESTONE-CI-OPTION-A-21-21-PASS-2026-08-26` | milestone | CI Option A — topologie patrimoniale 21/21 validée sur GitHub | ci_option_a_github_pass | — | — | runtime |
| `MILESTONE-L0-PROVISIONAL-CLOSURE-2026-08-24` | milestone | L0 — clôture provisoire du lot intégrité / source de vérité | provisionally_closed | — | — | artifact |
| `MILESTONE-L2-CLOSURE-2026-08-27` | milestone | L2 — clôture : store-safety / concurrence / vocabulaire (Memory-11 + Core 17 mergés, CI… | closed | — | — | runtime |
| `MILESTONE-L3-PURSUIT-MEMORY11-CONTINUITY-2026-08-27` | milestone | L3 — continuité durable Pursuit → Memory-11 à la livraison (enrichissement additif, mer… | merged | — | — | runtime |
| `MILESTONE-L4-PURSUIT-RETRIEVAL-2026-08-27` | milestone | L4 — rappel en lecture d'une Pursuit depuis Memory-11 (retrieve_pursuit ; premier chemi… | merged | — | — | runtime |
| `MILESTONE-L5-PURSUIT-LEARNING12-CONNECTION-2026-08-28` | milestone | L5 — connexion de l'expérience Pursuit (pursuit_delivered) à Learning-12 ; Core repinné… | merged | — | — | runtime |
| `RATIF-2026-08-24` | ratification | Ratification propriétaire — Réunification canonique BrainAI (Frédérique, 2026-08-24) | ratifiée | — | — | artifact |
| `RS-001` | evolution_record | events.jsonl non append-only (EventRecorder.dump→write_text tronquait à chaque processus) | résolue(7c065a5) | o | — | src |
| `RS-002` | evolution_record | Collision proposal_id (id indépendant du contenu du Brief) | résolue (déjà corrigé avant J0 : proposals.py inclut brief) | o | — | src |
| `RS-003` | evolution_record | D1 — la prose du modèle présume parfois du routage d'une inconnue (« phase suivante »),… | consignée | o | — | src |
| `RS-004` | evolution_record | D2 — porosité besoin/contrainte : une contrainte issue d'une solution peut migrer dans … | résolue partielle(J1) | o | — | src |
| `RS-005` | evolution_record | D3 — Art.7 : readiness=ready (appréciation) vs confirmation humaine | résolue (arbitrage Frédérique, 20 août) | o | — | src |
| `RS-006` | evolution_record | A2 (dette) — COGNITIVE_IDENTITY et CONDENSED_IDENTITY doivent rester sémantiquement syn… | consignée | o | — | src |
| `RS-007` | evolution_record | Tâche 3 — missions understanding/specification non exercées en réel (essence injectée n… | consignée | o | — | src |
| `RS-008` | evolution_record | M7 — understanding impose ses 7 champs dès le 1er contact du besoin (tension avec l'éco… | consignée | o | — | src |
| `RS-009` | evolution_record | A5 — aucun budget global de dialogue par Pursuit (plafond par appel seulement) | consignée | o | — | src |
| `RS-010` | evolution_record | UI Tauri legacy (SCC_BRAINAI_UI) — pilote la Surface legacy dormante. D2 (J3 T3) : ARCH… | archivée (D2, close) | o | — | src |
| `RS-011` | evolution_record | Auto-approbation brainai-human dans 10_kernel (scc_gateway.py:147) — approbation trompe… | archivée honnêtement (D1) — conservée | o | — | src |
| `RS-012` | evolution_record | OCOS — couche de gouvernance neutre au-dessus de BrainAI (multi-moteurs/agents). Table … | absorbée (table produite) | o | — | src |
| `RS-013` | evolution_record | Délibération multi-fournisseurs réelle (plusieurs LLM sous gouvernance ; providers = st… | planifiée(J5/J6) | o | — | src |
| `RS-014` | evolution_record | Atlas des outils / moteur d'aiguillage (catalogue outils-IA-MCP-API + sélection context… | planifiée(J1 noyau / J6 complet) | o | — | src |
| `RS-015` | evolution_record | Multi-tenant / orchestration souveraine BYOK-Managed-Mixte (credentials, facturation, R… | doctrine écrite(J3), impl. post-v1 | o | — | src |
| `RS-016` | evolution_record | Budget de build à plafond DUR (1re classe, par ToolInvocation, stoppe le build) — exige… | résolue partielle(J2, a1ba312) | o | — | src |
| `RS-017` | evolution_record | Boucle de retour terrain + Mémoire de DÉCISION (pourquoi A rejetée/B retenue ; contexte… | planifiée(J4) | o | — | src |
| `RS-018` | evolution_record | Clôture d'activités cognitives (statuts projet/tâche ; Continuation/Modification/Fork→p… | planifiée(J2/J4) | o | — | src |
| `RS-019` | evolution_record | BrainAI Core / BrainAI Lab (production bridée vs sandbox d'auto-amélioration validée) | absorbée(J7) + dette Lab post-v1 | o | — | src |
| `RS-020` | evolution_record | Patrimonial Event Bus + Service Registry/SLO/PRA/Runbook + Invariant 001D (aucune op cr… | consignée | o | — | src |
| `RS-021` | evolution_record | Grammaire cognitive (familles Doctrine/Décision/Règle/Architecture/Capacité/Projet ; 4 … | consignée (enrichie) | o | — | src |
| `RS-022` | evolution_record | Doctrine 11 (continuité sans pression) & Doctrine 14 (arbitrage explicite obligatoire d… | consignée | o | — | src |
| `RS-023` | evolution_record | Décor vide : ~120 sous-dossiers métier + 07_AGENTS/09_MONITORING/10_BACKUPS (0 fichier … | étiquetée honnêtement (D3) | o | — | src |
| `RS-024` | evolution_record | Dérive documentaire : rapports readiness (6-juillet) périmés ; SCC_ARCHITECTURE_MAP ign… | résolue partielle(J3) — compteurs README corrigés | o | — | src |
| `RS-025` | evolution_record | Modules 10-16 orphelins de la Surface produit (branchés au seul runtime legacy détermin… | consignée | o | — | src |
| `RS-026` | evolution_record | Socle 05_MEMORY / 06_REASONING orphelins du chemin conversationnel (vivants dans l'orch… | consignée | o | — | src |
| `RS-027` | evolution_record | Foundation non adoptée (RF-001..009 : 5 moteurs dupliquent config/horloge/id/SHA au lie… | consignée | o | — | src |
| `RS-028` | evolution_record | Aucun CI : 1000+ tests existent, rien ne les exécute automatiquement | consignée | o | — | src |
| `RS-029` | evolution_record | Identité de l'acteur non authentifiée (champ libre ; ADR-UI-004 non implémenté) | consignée | o | — | src |
| `RS-030` | evolution_record | Fuite de provenance runtime : l'outil claude injecte l'email du compte dans le contexte… | résolue (bornée, preuve cible PASS 2026-08-22) — mécanisme livré + cible prouvée, pattern générique  | o | — | src |
| `RS-031` | evolution_record | Implémentation multi-tenant / BYOK (cf. RS-015) | consignée | o | — | src |
| `RS-032` | evolution_record | Sandbox « Lab » d'auto-amélioration (cf. RS-019) | consignée | o | — | src |
| `RS-033` | evolution_record | Infra SLO/PRA/Runbook (cf. RS-020) | consignée | o | — | src |
| `RS-034` | evolution_record | Grammaire cognitive complète (cf. RS-021) | consignée | o | — | src |
| `RS-035` | evolution_record | Clients mobile / desktop | consignée | o | — | src |
| `RS-036` | evolution_record | Découverte Phase A : « exiger vs accepter » l'émission des statuts épistémiques | résolue(J1) — TRANCHÉ : émission réellement EXIGÉE (mission ajustée ; prouvé Étage 2) | o | — | src |
| `RS-037` | evolution_record | Découverte Phase A : statut vérifié | résolue(J2, a1ba312) — inémettable par le modèle (J1) + attribution SYSTÈME livrée (J2) : un fait Ve | o | — | src |
| `RS-038` | evolution_record | Provenance au niveau besoin_fondamental (chaîne) absente — D2 traité au niveau ELEMENT … | consignée | o | — | src |
| `RS-039` | evolution_record | Plafond USD non strictement dur avant invocation — le --max-budget-usd du fournisseur e… | résolue partielle(J3) — déclaration honnête dans le contrat | o | — | src |
| `RS-040` | evolution_record | Worker in-process (meurt avec l'application) — suffisant pour J2 ; un process OS séparé… | consignée | o | — | src |
| `RS-041` | evolution_record | Déploiement public (deploy.public) différé — Q4=A (preview locale). Descriptor présent … | planifiée(J3+) | o | — | src |
| `RS-042` | evolution_record | Réutilisation 15_DECISION HumanValidationPolicy/gate — vérifiée séparément (non « skip … | consignée | o | — | src |
| `RS-043` | evolution_record | Retries riches absents — J2 applique arrêt au premier échec, aucun retry (R6). Pas de p… | consignée | o | — | src |
| `RS-044` | evolution_record | Granularité future des vérifications — J2 livre kind=http (build/test comme kind gouver… | consignée | o | — | src |
| `RS-045` | evolution_record | Redondance compréhension — converse (dialogue) et l'arc understanding mûrissent le beso… | consignée | o | — | src |
| `RS-046` | evolution_record | (R1) Résiduel du confinement A1 — une écriture en chemin absolu HORS workspace est invi… | consignée | o | — | src |
| `RS-047` | evolution_record | (R4) Plafonds de livraison câblés en constantes → RÉSOLUE (J3 T2) : brainai_app/deliver… | résolue(J3) | o | — | src |
| `RS-048` | evolution_record | (R6) Vérification de citation D1 — la correction « jamais silencieux : R6 → RV-1 » est … | résolue (vérifiée) | o | — | src |
| `RS-049` | evolution_record | Échelle d'auth PREUVE-A/PREUVE-B non documentée dans l'arbre — seul le barreau B1 (trou… | consignée | o | — | src |
| `RS-050` | evolution_record | Chartes OCOS-001/002/003 hors arbre — texte introuvable ; la table d'absorption (Q5) es… | consignée | o | — | src |
| `RS-051` | evolution_record | Verrou des stores / écrivain unique — les stores append-only (check-then-append sans ve… | consignée (créée) | o | — | src |
| `RS-052` | evolution_record | NON CRÉÉE — la grammaire cognitive est déjà couverte par RS-021 (enrichie ci-dessus). A… | abandonnée(doublon RS-021) | o | — | src |
| `RS-053` | evolution_record | Architecture canonique persistante (MOAT #6) — représentation abstraite du projet indép… | consignée (créée) | o | — | src |
| `RS-054` | evolution_record | Objet Version + boucle économique modification→Spec v2→Version — « un client vit dans l… | consignée (créée) | o | — | src |
| `RS-055` | evolution_record | Canal gouverné d'alerte sécurité/conformité émis par le modèle — alerte_potentielle typ… | consignée (créée) | o | — | src |
| `RS-056` | evolution_record | Provisionnement du jeton d'auth cible non-autonome — claude setup-token exige un abonne… | levée (2026-08-22, preuve cible PASS bornée) | o | — | src |
| `RS-057` | evolution_record | Injectabilité token_var non traversante au niveau adaptateur — le paramètre token_var e… | consignée — frontière assumée, différée | o | — | src |
| `RS-058` | evolution_record | Croissance non bornée du contexte de Pursuit — à chaque tour, l'historique relu côté mo… | consignée — dette réelle, non résolue | o | — | src |
| `RS-059` | evolution_record | Distinction activité / blocage + annulation (solution cible du watchdog) — l'infra actu… | palier immédiat clôturé (validé réel + déterministe) ; cible planifiée, ouverte | o | — | src |
| `RS-060` | evolution_record | CADRAGE J4 — cerveau cumulatif (garde-fou anti-dilution). Révélé par l'audit produit (2… | consignée — cadrage protégé, non implémenté | o | — | src |
| `RS-061` | evolution_record | 05_MEMORY et 04_KNOWLEDGE non durcis en L2 actif — hardening store-safety différé jusqu… | consignée | o | — | — |
| `RS-062` | evolution_record | Risque externe Synology Drive : écrivain externe ne respectant pas les flock locaux — l… | consignée | o | — | — |
| `SCC-DOC-0001` | doctrine | SCC-DOC-0001 — Foundation First | Adoptée | — | — | src |
| `SCC-DOC-0002` | doctrine | SCC-DOC-0002 — Contrat de données | Adoptée | — | — | src |
| `SCC-DOC-0003` | doctrine | SCC-DOC-0003 — Aucun couplage direct | Adoptée | — | — | src |
| `SCC-DOC-0004` | doctrine | SCC-DOC-0004 — Architecture avant implémentation | Adoptée | — | — | src |
| `SCC-DOC-0005` | doctrine | SCC-DOC-0005 — Factorisation d'abord | Adoptée | — | — | src |
| `SCC-DOC-0006` | doctrine | SCC-DOC-0006 — Append Only | Adoptée | — | — | src |
| `SCC-DOC-0007` | doctrine | SCC-DOC-0007 — Lecture seule | Adoptée | — | — | src |
| `SCC-DOC-0008` | doctrine | SCC-DOC-0008 — Un composant = un dépôt | Adoptée | — | — | src |
| `SCC-DOC-0009` | doctrine | SCC-DOC-0009 — ADR obligatoire | Adoptée | — | — | src |
| `SCC-DOC-0010` | doctrine | SCC-DOC-0010 — Compatibilité ascendante | Adoptée | — | — | src |
| `SCC-DOC-0011` | doctrine | SCC-DOC-0011 — Migration progressive | Adoptée | — | — | src |
| `SCC-DOC-0012` | doctrine | SCC-DOC-0012 — Ressource commune avant duplication | Adoptée | — | — | src |
| `SCC-DOC-0013` | doctrine | SCC-DOC-0013 — Documentation avant livraison | Adoptée | — | — | src |
| `SCC-DOC-0014` | doctrine | SCC-DOC-0014 — Tests avant livraison | Adoptée | — | — | src |
| `SCC-DOC-0015` | doctrine | SCC-DOC-0015 — Gouvernance avant extension | Adoptée | — | — | src |
| `SCC-DOC-0016` | doctrine | SCC-DOC-0016 — Traçabilité complète | Adoptée | — | — | src |
| `SCC-DOC-0017` | doctrine | SCC-DOC-0017 — Versionnement des schémas | Adoptée | — | — | src |
| `SCC-DOC-0018` | doctrine | SCC-DOC-0018 — Séparation des responsabilités | Adoptée | — | — | src |
| `SCC-DOC-0019` | doctrine | SCC-DOC-0019 — Décisions immuables | Adoptée | — | — | src |
| `SCC-DOC-0020` | doctrine | SCC-DOC-0020 — Sans dépendance externe | Adoptée | — | — | src |
| `SCC-DOC-0021` | doctrine | SCC-DOC-0021 — Déterminisme et injectabilité | Adoptée | — | — | src |
| `SCC-DOC-0022` | doctrine | SCC-DOC-0022 — Fixtures uniquement (jamais de données réelles) | Adoptée | — | — | src |
| `SCC-DOC-0023` | doctrine | SCC-DOC-0023 — Aucun secret en dépôt | Adoptée | — | — | src |
| `SCC-DOC-0024` | doctrine | SCC-DOC-0024 — Protocols plutôt qu'héritage | Adoptée | — | — | src |
| `SCC-DOC-0025` | doctrine | SCC-DOC-0025 — Tolérance en lecture, rigueur en écriture | Adoptée | — | — | src |
| `SCC-DOC-0026` | doctrine | SCC-DOC-0026 — Extensibilité sans modification du cœur | Adoptée | — | — | src |
| `SCC-DOC-0027` | doctrine | SCC-DOC-0027 — Runtime hors versionnement | Adoptée | — | — | src |
| `SCC-DOC-0028` | doctrine | SCC-DOC-0028 — Gel des composants stables | Adoptée | — | — | src |
| `SCC-DOC-0029` | doctrine | SCC-DOC-0029 — Intelligence lourde optionnelle et branchable | Adoptée | — | — | src |
| `SCC-DOC-0030` | doctrine | SCC-DOC-0030 — Rien ne se perd | Adoptée | — | — | src |

