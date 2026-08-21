# Registre d'évolution — BrainAI (RS-2)

> Mécanisme **RS-2** du Plan Directeur BrainAI v1.0 (gelé le 20 août 2026). Toute idée, dette ou évolution
> de périmètre passe par ce registre. La **séquence du Plan Directeur (J0→J7) n'est modifiable que via une
> entrée de ce registre** (statut `planifiée`/`absorbée`/`abandonnée`), jamais en silence. Fonction inaugurale
> (Jalon 0) : **rendre visible toute dette qui n'était écrite nulle part ailleurs** — doctrine SCC-DOC-0030
> « rien ne se perd ».

**Statuts** : `consignée` (enregistrée, sans jalon) · `planifiée(jalon)` (rattachée à un jalon) ·
`absorbée` (intégrée ailleurs) · `abandonnée(motif)` · `résolue(commit)`.
**Créé** : Jalon 0, 2026-08-20. Ce registre est append-friendly (on ajoute/ré-statue, on ne réécrit pas l'histoire).
**Aligné T0 (Jalon 1, 2026-08-20)** : statuts re-statués sur les destinations **gelées** du Plan Directeur (D2/D3→J1 ;
budget de build→J2 ; Atlas→J1 noyau/J6 complet ; multi-fournisseurs→J5/J6 ; mémoire de décision→J4 ; clôture
cognitive→J2/J4 ; multi-tenant→doctrine J3/impl. post-v1 ; OCOS→absorbée, table J3 ; Core/Lab→absorbée J7 + Lab
post-v1 ; brainai-human→J3). **Aucune destination rouverte, aucun arbitrage modifié.**

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
| RS-004 | **D2** — porosité besoin/contrainte : une contrainte issue d'une solution peut migrer dans `besoin_fondamental` | 2026-08-20 | idem | `résolue partielle(J1)` | Provenance émise **par élément** livrée (`ELEMENT.source`) ; provenance au niveau `besoin_fondamental` (chaîne) = résiduel **RS-038** |
| RS-005 | **D3** — Art.7 : `readiness=ready` (appréciation) vs confirmation humaine | 2026-08-20 | idem | **`résolue` (arbitrage Frédérique, 20 août)** | Mécanisme livré (J1) **+ Art.7 amendé** : `ready` = appréciation ; confirmation = fait `convergence_confirmed` attribué (déclaratif/non vérifié). **Dette fermée sur le plan de gouvernance.** |
| RS-006 | **A2 (dette)** — `COGNITIVE_IDENTITY` et `CONDENSED_IDENTITY` doivent rester sémantiquement synchrones ; aucun test ne le vérifie | 2026-08 | PROMPT_FINAL / clôture | `consignée` | À couvrir lors de la migration identité en donnée gouvernée |
| RS-007 | **Tâche 3** — missions understanding/specification non exercées en réel (essence injectée non validée sur modèle) | 2026-08-20 | clôture | `consignée` | Chantier corpus |
| RS-008 | **M7** — `understanding` impose ses 7 champs dès le 1er contact du besoin (tension avec l'écoute libre) | 2026-08 | CARTOGRAPHIE_INTEGRATION_V1_V2.md | `consignée` | Chantier corpus (trancher sur preuves) |
| RS-009 | **A5** — aucun budget global de dialogue par Pursuit (plafond par appel seulement) | 2026-08 | PROMPT_FINAL | `consignée` | Voir RS-016 (budget de première classe) |

## 3. Décisions de jalon proches (à trancher aux jalons indiqués)
| ID | Objet | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-010 | **UI Tauri legacy** (`SCC_BRAINAI_UI`) — pilote la Surface legacy dormante | 2026-08-20 | archéologie globale | `consignée` — **archive par défaut** | Réorientation **seulement si J3** démontre une réutilisation directement rentable pour le Workspace final |
| RS-011 | **Auto-approbation `brainai-human`** dans 10_kernel (`scc_gateway`) — approbation trompeuse (non-humaine réelle) | 2026-08-20 | archéologie (agent modules) | `planifiée(J3)` | **Décision en J3** |

## 4. Concepts PERDUS de l'archéologie V1 (Phase 0) — à placer ou différer explicitement (rien ne se perd)
| ID | Concept perdu | Date source | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-012 | **OCOS** — couche de gouvernance neutre au-dessus de BrainAI (multi-moteurs/agents) | Phase 0 (CHARTER-OCOS-001/002/003) | archéologie A4 | `absorbée` (arbitrage propriétaire du 20 août) | Absorbée dans le plan de Gouvernance ; **table de correspondance OCOS↔V2 en J3** |
| RS-013 | **Délibération multi-fournisseurs réelle** (plusieurs LLM sous gouvernance ; providers = stubs) | 3 août / Phase 0 | archéologie | `planifiée(J5/J6)` | ADAPTER-CHANNELS (canal) **+ décision** sur la délibération concurrente |
| RS-014 | **Atlas des outils / moteur d'aiguillage** (catalogue outils-IA-MCP-API + sélection contextuelle) | Phase 0 (J1/J4) | archéologie | `planifiée(J1 noyau / J6 complet)` | Descriptors noyau en J1 ; Atlas riche (aiguillage contextuel) en J6 |
| RS-015 | **Multi-tenant / orchestration souveraine BYOK-Managed-Mixte** (credentials, facturation, RGPD, OWNER) | Phase 0 (J4/positionnement) | archéologie | `doctrine planifiée(J3), impl. post-v1` | Doctrine en J3 ; implémentation post-v1 produit |
| RS-016 | **Budget de build à plafond DUR** (1re classe, par ToolInvocation, stoppe le build) — exigence de souveraineté | 3 août / JALON-ZERO | archéologie | **`résolue partielle(J2, a1ba312)`** | `BudgetLedger` append-only livré : **plafond du nombre d'appels = garde DURE** ; **plafond USD = best-effort borné** (pré-check `spent+enveloppe<=plafond`) — résidu **RS-039** (le `--max-budget-usd` fournisseur est un arrêt agrégé, pas une garantie a priori) |
| RS-017 | **Boucle de retour terrain + Mémoire de DÉCISION** (pourquoi A rejetée/B retenue ; contextes de mauvais arbitrage) | Phase 0 (Débriefe/J7) | archéologie | `planifiée(J4)` | MEMORY-GOVERNED (J4) |
| RS-018 | **Clôture d'activités cognitives** (statuts projet/tâche ; Continuation/Modification/**Fork**→parent ; Session Transition) | Phase 0 (J1/J2) | archéologie | `planifiée(J2/J4)` | Gouvernance de fin d'étape (J2/J4) |
| RS-019 | **BrainAI Core / BrainAI Lab** (production bridée vs sandbox d'auto-amélioration validée) | Phase 0 (J7) | archéologie | `absorbée(J7) + dette Lab post-v1` | Core absorbé en J7 ; sandbox Lab = dette post-v1 |
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

## 7. Jalon 1 — découvertes tranchées et résiduels
| ID | Dette / découverte | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-036 | Découverte Phase A : « **exiger vs accepter** » l'émission des statuts épistémiques | 2026-08-20 | Phase A J1 | `résolue(J1)` — **TRANCHÉ : émission réellement EXIGÉE** (mission ajustée ; prouvé Étage 2) | — |
| RS-037 | Découverte Phase A : statut **`vérifié`** | 2026-08-20 | Phase A J1 | **`résolue(J2, a1ba312)`** — inémettable par le modèle (J1) **+ attribution SYSTÈME livrée (J2)** : un fait `Verification verdict=passed` **lié au sha256** confère « vérifié » (un octet change → non couvert ; aucune propagation implicite) | — (granularité future des vérifications = RS-044) |
| RS-038 | Provenance au niveau **`besoin_fondamental`** (chaîne) absente — D2 traité au niveau `ELEMENT` seulement | 2026-08-20 | Phase B J1 | `consignée` | À jalonner (provenance du besoin fondamental) — extension additive future |
| RS-029↺ | Identité de l'acteur non authentifiée — le fait `convergence_confirmed` la représente honnêtement (`declared`/`verified:false`), **ne la résout pas** | 2026-08-20 | J1 | `consignée` (inchangée) | ADAPTER-CHANNELS / post-septembre |

## 8. Jalon 2 — livraison réelle (Phase B) : dettes tranchées et résiduels
| ID | Dette / découverte | Date | Origine | Statut | Destination |
|---|---|---|---|---|---|
| RS-039 | **Plafond USD non strictement dur avant invocation** — le `--max-budget-usd` du fournisseur est un **arrêt agrégé entre appels**, pas une garantie qu'un appel déjà lancé ne dépasse pas légèrement. La propriété **réellement dure** est le **compteur d'appels** ; le plafond monétaire est **best-effort borné** (pré-check `spent+enveloppe<=plafond`). | 2026-08-21 | Phase B J2 (A4 + condition Rose) | `consignée` | ADAPTER-CHANNELS / API fournisseur — n'affirmer un plafond USD dur que si le fournisseur l'offre nativement |
| RS-040 | **Worker in-process** (meurt avec l'application) — suffisant pour J2 ; un **process OS séparé** (survie à la mort de l'app, isolation renforcée) n'est pas livré. Le run interrompu est **constaté** (`run_interrupted`), jamais repris en silence. | 2026-08-21 | Phase B J2 (T1/T2/A2) | `consignée` | Post-v1 / J3+ (exécution hors-processus) |
| RS-041 | **Déploiement public** (`deploy.public`) **différé** — Q4=A (preview locale). Descriptor présent mais `unavailable`/non lié : prouve la **substituabilité** `LOCAL_PREVIEW→DEPLOY_PUBLIC` sans réaliser aucun déploiement public en J2. | 2026-08-21 | Phase B J2 (Q4 / T6) | `planifiée(J3+)` | **J3+ après traitement des mitigations RS-030** (fuite de provenance) |
| RS-042 | **Réutilisation 15_DECISION `HumanValidationPolicy`/gate** — vérifiée séparément (non « skip » par défaut) : **redondante** en J2 avec le fait `convergence_confirmed` (acteur déclaré) + gate déterministe `_realize` (chronologie des tours, A6). L'intégrer créerait **deux sources de vérité** pour une **même** autorisation humaine et réécrirait le mécanisme D3 validé (Rose). | 2026-08-21 | Phase B J2 (recyclage 15_DECISION) | `consignée` | **J3+** — quand apparaît une **2e décision humaine distincte** (rendre la livraison « officielle » ; `validate`/`reject`/`revoke` par run) → enveloppe `HumanValidationPolicy` |
| RS-043 | **Retries riches absents** — J2 applique **arrêt au premier échec, aucun retry** (R6). Pas de politique de reprise fine (backoff, reprise partielle d'étape). | 2026-08-21 | Phase B J2 (T2) | `consignée` | Post-v1 (politique de reprise gouvernée) |
| RS-044 | **Granularité future des vérifications** — J2 livre `kind=http` (build/test comme `kind` gouvernés, non exercés en réel). Vérifications plus fines (tests unitaires du site, accessibilité, liens) à jalonner. | 2026-08-21 | Phase B J2 (T3/A3) | `consignée` | J3+ (catalogue de `kind` de vérification) |
| RS-045 | **Redondance compréhension** — converse (dialogue) **et** l'arc `understanding` mûrissent le besoin (héritage J1). En J2 c'est assumé (double preuve) ; à rationaliser pour éviter un double coût. | 2026-08-21 | Phase B J2 (Étage 2) | `consignée` | J4 (mémoire de décision / rationalisation de l'arc) |

---

*Toute nouvelle idée/dette est ajoutée ici avec un ID `RS-0xx`, une date, une origine, un statut et une destination.
Une évolution de la séquence du Plan Directeur exige une entrée `planifiée`/`absorbée`/`abandonnée` explicite.*
