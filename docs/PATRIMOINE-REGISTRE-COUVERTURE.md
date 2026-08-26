# Registre de couverture cumulatif — Passe 3 approfondie (lecture réelle du code)

Statut global : EN COURS. Rapport précédent = RAPPORT INTERMÉDIAIRE DE CARTOGRAPHIE.
Discipline : lecture seule, aucun LLM, aucun sous-agent, aucune modif. INVENTORIÉ≠OUVERT≠LU≠COMPRIS.

## Ordre de lecture (Passe 3)
1. 04_KNOWLEDGE → 05_MEMORY → 06_REASONING → 11_BRAINAI_MEMORY → 12_BRAINAI_LEARNING →
   13_BRAINAI_REASONING → 14_BRAINAI_PLANNING → 15_BRAINAI_DECISION → 16_BRAINAI_EXECUTION
2. 10_BRAINAI, 07_RUNTIME, 08_API, 09_CONTROL_PLANE, 00_SYSTEM, 17_BRAINAI_BOOTSTRAP (déjà connu J1-J4), _chantier
3. Prototypes heritage brainai-v1 / brainai-mvp / brainai-mvp-update / Blueprint (244 f)
4. Corpus docs BrainAI non lus (heritage ~197, 01_CCSC ~354) par lots

## Journal par lot (findings factuels)
<!-- append ci-dessous après chaque lot -->

### LOT 1 — SCC socle 04/05/06 (engines lus intégralement)
- 04_KNOWLEDGE/engine.py LU : consolidate(memory→knowledge, canonicalize+taxonomy), semantic_view/export_graph, detect_conflicts/verify_integrity, search, history, report. CODÉ, déterministe. Consomme MemoryRecord validés → KnowledgeEntry+graph.json.
- 05_MEMORY/engine.py LU : ingest(candidates, merge_policy, min_confidence), validate/reject/archive, versioning(update_content), links(relations/backlinks), search, verify, report. CODÉ, déterministe. Consomme CandidateInput → MemoryObject (status/provenance/revisions).
- 06_REASONING/engine.py LU : load graph (knowledge.json+graph.json), rules(transitive/default), InferenceEngine.run→inferences(persist jsonl), answer(query→Answer+context), gaps/contradictions/rank, verify. CODÉ, déterministe, LECTURE SEULE sur knowledge.
- VERDICT socle : code RÉEL (pas stub). "0 arête/0 inférence" REVUE = données non peuplées, pas absence de code.
- NON lus 04/05/06 : ops internes (consolidate/canonicalize/ingest/merge…), tests, models. Structure connue.
- Candidats ~409 f (04:141+05:130+06:132) ; LU : 3 engines ; à approfondir : ops+tests si besoin.

### LOT 2 — BrainAI 13_REASONING (engine + provider déterministe LUS) — CORRECTION AUDIT
- 13/engine.py LU : pipeline RÉEL analyze_problem→decompose→facts(+FactGateway si ground_facts)→build_options→
  formulate_hypotheses→derive_constraints→identify_risks→score_options→arbitrate→infer→build_decision(candidate)→
  build_explanation→Deliberation persistée. validate/reject (HumanValidationPolicy). self_check(no LLM/no network/
  no sovereign). Providers via ProviderRegistry (deterministic + external). NE écrit jamais ailleurs.
- 13/providers/deterministic.py LU : suggest_hypotheses/options/critique = None → le MOTEUR fait le raisonnement
  (règles) ; le provider est le HOOK où un LLM externe ajouterait des suggestions. Provider externe = shell.
- CORRECTION vs REVUE : la couche BrainAI 13-16 n'est PAS "coquille vide". C'est un pipeline gouverné RÉEL
  (options/risques/arbitrage/décision candidate/validation) + slot LLM interchangeable + FactGateway (ancrage SCC).
  Faiblesse = QUALITÉ déterministe (scores à égalité) + ground_facts souvent off, PAS absence de code.
- IMPLICATION "connecter pas reconstruire" : infra "LLM interchangeable + gateway faits + validation humaine +
  audit + registre" existe DÉJÀ à chaque étage 13-16. À CONNECTER, pas à recréer.
- NON lus 13 : arbitration/generation/risk_analysis/decomposition/fact_gateway/tests.

### LOT 3 — BrainAI 15_DECISION + 16_EXECUTION (engines LUS) — DÉCOUVERTE MAJEURE
- 15/engine.py LU : decide() ingère options depuis request + from_deliberation(13) + from_planset(14) +
  learnings(12) + governing_doctrines, via DecisionGateway ; qualify(impact/risque/confiance/réversibilité/urgence)
  → select → rationale → conditions validation/succès/échec/révocation → execution_manifest → traceability(inclut
  learnings+doctrines). validate/reject/REVOKE humain. self_check: no_automatic_application. Déterministe.
- 16/engine.py LU : prepare() guard_check(manifeste validé/non exécuté/non souverain/validation humaine/acteur
  autorisé) → refused sinon ; build_steps. execute(run_id,actor) DÉCLENCHÉ explicitement (aucune auto-exec),
  délègue au Runtime via RuntimeBridge.delegate, statut par étape, traces_for_memory (retour MEMORY). cancel/revoke.
  self_check: no_execution_without_validated_manifest.
- DÉCOUVERTE : la chaîne MEMORY(11)→LEARNING(12)→REASONING(13)→PLANNING(14)→DECISION(15)→EXECUTION(16)→traces→MEMORY
  EST CÂBLÉE EN CODE (via gateways). Chaque étage = engine déterministe RÉEL + slot LLM interchangeable (shell
  aujourd'hui) + gateway upstream + validation humaine (validate/reject/revoke) + audit + registre append-only.
- Le "echo" REVUE = default_job_kind du Runtime (délégation), PAS un engine factice.
- VRAIE lacune : cette chaîne 11-16 est pilotée par CLI/kernel, PAS par le PARCOURS PRODUIT (Pursuit=17_BOOTSTRAP
  +Sonnet). Le "raccord J4 LearningEngine↔Pursuits" = brancher l'expérience Pursuit dans Memory + relier cette
  chaîne existante au parcours produit. NE PAS reconstruire un LearningEngine/DecisionEngine : ils existent.
- NON lus 15/16 : comparison/qualification/manifest/conditions/guards/preparation/gateways/runtime_bridge/tests.

### LOT 4 — DecisionGateway + 14_PLANNING (LUS) — RACCORDEMENT PROUVÉ
- 15/sources/decision_gateway.py LU : charge dynamiquement (sys.path=ENVELOPPER) les vrais siblings
  ReasoningEngine(13)/PlanningEngine(14)/LearningEngine(12)/SccApi(08) → deliberation/planset/LEARNINGS/doctrines
  (graph.search). Dégradable. => DECISION consomme réellement LEARNING+REASONING+PLANNING+doctrines.
- 14/engine.py LU : plan() consomme learnings(12)+deliberations(13) via InsightSource ; build_tasks(obj,otype,
  learnings,deliberations,provider) → estimate → resolve_prerequisites → topological_order (fonction déjà
  ENVELOPPÉE par 17/delivery/planning.py) → stratégies → plan+manifest. validate/reject/revoke.
- CONCLUSION CHAÎNE (code-grounded) : MEMORY(11)→LEARNING(12)→{REASONING(13),PLANNING(14)}→DECISION(15)→
  EXECUTION(16)→traces→MEMORY existe EN CODE, câblée par gateways réflexifs, learnings consommés par Planning
  ET Decision, slots LLM interchangeables, validation humaine partout. Déterministe et testé (fixtures).
- CORRECTION FERME du récit "châssis sans moteur" : le moteur EXISTE. Manque = (1) providers LLM réels,
  (2) branchement au PARCOURS PRODUIT (Pursuit=17+Sonnet, chemin séparé), (3) Memory nourrie de vécu réel.
- IMPACT J4 : LearningEngine + ses consommateurs (Planning/Decision) EXISTENT et sont câblés. J4-(d)="raccord
  LearningEngine↔Pursuits" = nourrir Memory(11) du vécu Pursuit + relier le parcours produit à CETTE chaîne.
  NE PAS reconstruire. topological_order déjà réutilisé => précédent de raccord existant.

## ÉTAT DE COUVERTURE (checkpoint)
LU ce lot (engines/gateways, code réel) : 04,05,06 (socle) ; 12(J4),11(J4) ; 13,14,15,16 engines + 13 provider
  det + 15 gateway. => CHAÎNE DU CERVEAU : deep-read au niveau engine+wiring. ✅
NON ENCORE LU (prochains lots) :
  - internes (ops/arbitration/generation/qualification/guards/preparation/estimation/strategies) + TESTS de 04-16
  - 10_BRAINAI (Kernel — orchestration de la chaîne) ; 07_RUNTIME ; 08_API ; 09_CONTROL_PLANE ; 00_SYSTEM (doctrines)
  - 17_BRAINAI_BOOTSTRAP (déjà deep-read J1-J4 — à recouper) ; _chantier (3 .md non lus)
  - prototypes heritage brainai-v1/mvp/Blueprint (244 f) ; corpus docs heritage ~197 + 01_CCSC ~354

### LOT 5 — 10_BRAINAI Kernel + providers/external (LUS)
- 10/kernel.py LU : BrainAIKernel.handle() = demande→classify_intent(mots-clés)→build_context(API/graph/ControlPlane
  via SccGateway)→select_agents→build_plan→Orchestrator.run(Runtime gouverné + KernelSupervisor)→assist_synthesis→
  réponse structurée. Déterministe. Incarne Superviseur SCC-AGENT-0020, respecte T3. NE rappelle PAS directement
  la chaîne 11-16 : c'est une couche superviseur distincte au-dessus de Runtime(07)/API(08)/ControlPlane(09).
  => IL EXISTE DEUX orchestrations : (a) 10_BRAINAI Kernel sur Runtime/Agents ; (b) chaîne cognitive 11-16.
     + (c) 17_BOOTSTRAP parcours produit (builder+Sonnet). Trois orchestrations parallèles, peu reliées.
- 13 & 10 providers/external.py LUS : ExternalReasoner/ExternalProvider (+ Claude/ChatGPT/Gemini) = points
  d'extension par injection de client ; available()=False sans client ; AVEC client => NotImplementedError
  (transport non implémenté). => slot réel, transport LLM NON câblé dans 10-16.
- MAJEUR (connecter pas reconstruire) : le vrai transport LLM qui marche = 17_BOOTSTRAP/builder (ClaudeCode
  adapters, subprocess réel, connu J1-J4). Il pourrait être le "client" injecté dans les slots 10-16. Aujourd'hui
  17 est un chemin SÉPARÉ (Pursuit+Sonnet) qui n'utilise PAS la chaîne 11-16 ni le Kernel 10.
- NON lus : internes+tests de 04-16 ; 10 orchestrator/planner/agent_selector/supervisor/context_builder/scc_gateway
  ; 07/08/09 ; 00_SYSTEM ; 17 recheck ; _chantier 3 .md ; prototypes ; corpus docs ; 90_HERITAGE profond.

### LOT 6 — 05_MEMORY internes + dimension TESTÉ + structure 07/08/09
- 05/operations/ingest.py + merge.py LUS : mémoire vivante RÉELLE — seuil confiance, dedup_key(create/merge),
  provenance tracée, versionnement (bump), history ; merge = union tags + remplacement contenu par POLITIQUE
  (highest_confidence/longest/keep_existing) + confiance=max. Capacité mémoire = CODÉE (pas stub).
- TESTÉ (fonctions test) : 04:54 05:63 06:49 | 10:21 11:23 12:28 13:22 14:27 15:28 16:28 | 07:29 08:37 09:24.
  => tous les modules cerveau+transverse SONT TESTÉS (~500+, hors 17:~408 + UI). Dimension testé=OUI.
- Nouveaux fichiers : 07/brainai.py + lifecycle/scheduler/policies/state/session/context ; 08/brainai.py +
  services/{system,graph,catalog,report,runtime}_service + http_preview.py (PREVIEW) ; 09 obs (alerts/metrics/
  diagnostics/dashboard/monitors + sources/runtime_probe,api_source).
- NON lus : 05 store/models/validation/versioning/links/search/tests ; 07/08/09 engines+internes ; 04/06/11-16 internes restants.

### LOT 7 — 07_RUNTIME + 08_API engines (LUS) — PLATEFORME + CHAÎNON
- 07/engine.py LU : runtime gouverné RÉEL — sessions/jobs/handlers/rôles(A0-A3/T1-T3), submit→SupervisorPort.on_plan→
  policies.evaluate(allowed/requires_human/refused+veto)→schedule/block/refuse ; approve()=validation humaine T3 ;
  EventLog append-only. Handlers défaut : echo, sensitive_action, BRAIN_PASS (=appelle moteurs cognitifs via
  EngineBridge). SupervisorPort=NullSupervisor par défaut (BrainAI Kernel s'y branche).
- 08/api.py LU : SccApi.dispatch(op,params)→Response ; ops system.*/graph.{search,node,neighbors,paths}/catalog.*/
  runtime.run_demo/reports.* ; projection HTTP par op ; socket via http_preview (V1 lecture seule).
- CHAÎNONS : SupervisorPort(07)=plug du Kernel 10 ; brain_pass+EngineBridge(07/bridge/engines.py)=Runtime invoque
  04-16 ; graph.search(08)=doctrines consommées par DecisionGateway(15). => plateforme+cerveau+superviseur
  INTER-CÂBLÉS par interfaces publiques. Tout réel + testé.
- HAUTE VALEUR À LIRE : 07/bridge/engines.py (EngineBridge = comment Runtime appelle les moteurs) ; 07/brainai.py
  (SupervisorPort) ; 08/brainai.py ; 09/control_plane.py.

## CHECKPOINT COUVERTURE (fin lot 7)
LU (code réel) : 04/05/06 engines + 05 ops(ingest/merge) ; 11/12 (J4) ; 13/14/15/16 engines + 13 det/ext providers
  + 15 decision_gateway ; 10 kernel + 10 ext provider ; 07 engine ; 08 api. + tous README + tests comptés.
NON LU (01_CCSC) : EngineBridge 07 ; 07/08/09 internes+brainai.py+control_plane ; 00_SYSTEM (doctrines/ADR/meta) ;
  internes+tests restants 04-16 ; 10 orchestrator/planner/agent_selector/supervisor/scc_gateway ; 17 recheck ;
  _chantier 3 .md ; SCC_ORCHESTRATOR/FOUNDATION (00_SYSTEM).
NON LU (heritage) : prototypes brainai-v1/mvp/Blueprint 244 f ; docs heritage ~197 ; docs 01_CCSC ~354.

### LOT 8 — EngineBridge + SupervisorPort (LUS)
- 07/bridge/engines.py LU : brain_pass charge scc_orchestrator (00_SYSTEM) et exécute la chaîne SOCLE 5-moteurs
  (INGESTION→EXTRACTION→MEMORY→KNOWLEDGE→REASONING) sur SOURCE DE DÉMO (fixtures generate_demo_source). Donc
  brain_pass = socle SCC sur fixtures, PAS la couche 11-16, PAS de données réelles.
- 07/brainai.py LU : SupervisorPort (Protocol on_plan/on_review/on_decision, consultatif) ; NullSupervisor inerte
  défaut ; gouvernance JAMAIS déléguée (T3/vetos souverains) ; RecordingSupervisor=preuve test.
- CONSOLIDÉ : sous-systèmes réels + points de branchement définis (SupervisorPort/EngineBridge/gateways/API),
  mais peu exécutés ensemble ; le PARCOURS PRODUIT (17) n'utilise AUCUN de 04-16/07/08/09/10 (chemin builder+Sonnet).
- NON LU restant proche : 08/brainai.py ; 09/control_plane.py ; 00_SYSTEM (doctrines/ADR/meta/orchestrator/foundation).

### LOT 9 — 00_SYSTEM inventaire + SccObject + doctrine 0030 (LUS)
- 00_SYSTEM inventorié : 30 doctrines SCC-DOC-0001..0030 ; 8 ADR (0000 archi,0003 runtime,0004 orchestrateur,
  0005 gouvernance-T3,0006 méta-modèle,0007 readiness-BrainAI) ; SCC_FOUNDATION (119 f) ; scc_orchestrator (75 f) ;
  capabilities55/skills44/agents23/workflows22/meta_model5/graph6/readiness5 ; ~120 dossiers config VIDES (décor).
- foundation/object.py LU : SccObject = CONTRAT CANONIQUE UNIVERSEL (superset Cognitive/Memory/Knowledge),
  id/kind/module/content/status/confidence/version/checksum/PROVENANCE/RELATIONS/schema_version ; update_content
  versionne+ré-empreinte ; set_status transitions validées ; from_legacy()=PONT DE MIGRATION (absorbe tout dict).
  => "langage universel indépendant fournisseur" (SCIL/RS-053) EXISTE EN CODE au niveau objet cognitif.
- doctrines/SCC-DOC-0030 LU : "Rien ne se perd" (6/7) — jamais perdre info/idée/décision écartée ; archiver pas
  supprimer ; toute info a une destination. = principe mémoire/capitalisation RS-017 + impératif J4 (ne pas oublier
  la conception antérieure). DÉJÀ DOCTRINE FIXÉE. Liée SCC-DOC-0006 append-only.
- IMPACT RS-060 : RS-053(canonique)→SccObject+from_legacy déjà codé (base) ; RS-017(rien ne se perd)→SCC-DOC-0030
  déjà doctrine ; "LLM optionnel/branchable"→SCC-DOC-0029 déjà doctrine + slots providers déjà codés.
- NON LU 00_SYSTEM : ADR 0000/0003/0005/0007 (textes) ; SCC-DOC-0029 + autres doctrines ; foundation provenance/
  status/relation/interfaces/metadata ; scc_orchestrator/pipeline.py ; meta_model ; SCC_GOVERNANCE/FUTURE_REFACTORING.

## CHECKPOINT (fin lot 9)
LU code réel cumulatif : socle 04/05/06(engines+05 ops) ; 11/12(J4) ; 13/14/15/16 engines+13 providers+15 gateway ;
  10 kernel+ext ; 07 engine+bridge+supervisor ; 08 api ; foundation/object ; doctrine 0030. + inventaires complets.
NON LU (01_CCSC) : 09_CONTROL_PLANE ; 08/07 brainai.py ; 00_SYSTEM (reste doctrines/ADR/foundation/orchestrator/meta)
  ; internes+tests restants 04-16 ; 10 internes ; 17 recoupe ; _chantier 3 .md.
NON LU (heritage) : prototypes 244 f ; docs heritage ~197 ; docs 01_CCSC ~354.

### LOT 10 — 00_SYSTEM gouvernance (ADR-0000 + SCC-DOC-0029 + FUTURE_REFACTORING LUS)
- ADR-0000 LU (6/7) : architecture SCC = couches/modulaire/découplée ; couplage par CONTRATS seuls ; fondation
  commune non intrusive ; flux cognitif linéaire acyclique ; exécution gouvernée (Runtime ne décide pas, T3) ;
  méta-modèle explicite ; ADR immuables. Explicitement "conçu pour accueillir l'intelligence lourde (BrainAI)".
- SCC-DOC-0029 LU : socle déterministe sans dépendance ; LLM/embeddings/OCR/ASR branchés DERRIÈRE INTERFACES,
  dépendance optionnelle isolée, tracée (Rule porte derivation+evidence). => branchement LLM doctrinalement défini.
- FUTURE_REFACTORING LU : RF-001..009. RF-007=adopter SccObject comme contrat d'échange (=RS-053, PLANIFIÉ) ;
  RF-005 unifier provenance/relations ; RF-004 SHA-256 (fait dans 17) ; RF-009 validation mémoire humaine (dette
  démo) ; RF-001/002/003 mutualiser Report/Clock/id via foundation (~16 copies core/config).
- CONSTAT : direction canonique (SccObject) + doctrine LLM-branchable + doctrine rien-ne-se-perd + dette dupli =
  DÉJÀ CONSIGNÉS côté SCC. 00_SYSTEM gouvernance/foundation = COEUR deep-lu ; textes des 27 autres doctrines + 7
  autres ADR + meta_model = INVENTORIÉS (titres/pattern connus), non lus intégralement.
- NON LU 00_SYSTEM : 27 doctrines restantes (textes) ; ADR 0001-0007 (textes) ; foundation provenance/status/
  relation/interfaces/metadata/hashing ; scc_orchestrator/pipeline.py ; meta_model (5) ; SCC_GOVERNANCE ; capabilities/skills/agents/workflows (fiches).

### LOT 11 — _chantier_COGNITIVE-IDENTITY-001 (archéologie V1 + carto V1→V2) — DÉCOUVERTE PIVOT
- ARCHEOLOGIE_COGNITIVE_V1.md LU (extrait large) : 12 mécanismes M1-M12 tracés au CODE V1 (cognitive-engine.js,
  anthropic-adapter.js, 7 Blueprints, sortie ROADTRIP J5). Ce qui faisait "il réfléchit avec toi" = identité habitée
  + arbitrage obligatoire (prise de position) + plusieurs lectures + hypothèses nommées + surprise utile +
  désaccord motivé + conviction graduée en langue. = MÉCANISMES DE PROMPT/IDENTITÉ, pas de moteur déterministe.
- CARTOGRAPHIE_INTEGRATION_V1_V2.md LU (extrait) : recadrage EXPLICITE —
  * 13_BRAINAI_REASONING/arbitration.py:45-57 = ANTI-mécanisme (fabrique justifs sur égalités) ;
  * options "canoniques" de 13 = codées en dur = FAUX AMI ;
  * "NE JAMAIS brancher le module 13 sur la conversation".
  * Discipline : SEULS identité(~1900 mots=nature) + mission(~180 mots) atteignent le modèle ; Constitution/
    articles/observables = NOUS (jamais au modèle). "Le cerveau ne doit pas devenir une administration".
  * Où vit la vraie cognition V2 : builder/cognitive_identity.py (déjà raccordé conversation/understanding/spec).
- RECADRAGE DE MES CONCLUSIONS : la chaîne 11-16 est du CODE RÉEL de GOUVERNANCE mais sa "cognition" déterministe
  est FACTICE/non-discriminante (REVUE + archéologie CONCORDENT). "Connecter pas reconstruire" pour la VRAIE
  intelligence = mécanismes d'IDENTITÉ/PROMPT (héritage V1 → cognitive_identity.py), PAS les moteurs 13-16.
- NON LU : PROMPT_FINAL_CLAUDEC.md (3e doc _chantier) ; cognitive_identity.py (connu produit, à recouper) ;
  HERITAGE PROTOTYPES (cognitive-engine.js, anthropic-adapter.js, 7 Blueprints = SOURCE de la vraie cognition V1) => PRIORITÉ.

### LOT 12 — Heritage brainai-mvp/cognitive-engine.js (LU) — L'ACTIF COGNITION V1
- brainai-mvp/src/cognitive-engine.js LU (v0.2, 133 l.) : export COGNITIVE_ENGINE = document IDENTITÉ/PROMPT
  INDÉPENDANT DU LLM (Doctrine 15 : reste valable si on remplace tous les LLM). Sections A-IDENTITÉ (chef de projet,
  réduit incertitude métier, conséquences non demandées=mandat), B-POSTURE (chef de projet pas assistant, souveraineté
  humaine, honnête "c'est un blueprint", sait dire je ne sais pas), C-PENTAGONE (Comprendre/Structurer/ARBITRER
  [neutralité=défaut]/Orchestrer/Livrer). = LA SOURCE du "il réfléchit avec toi", provider-agnostique.
- Existe aussi : brainai-v1/src/core/cognitive/cognitive-engine.ts (version TS + tests) ; brainai-mvp/src/adapters/
  anthropic-adapter.js ; brainai-mvp/src/lib/prompt-input.js ; dossier Blueprint (7 Blueprints réels).
- CLASSEMENT : cognitive-engine = RÉCUPÉRABLE (déjà partiellement porté V2 = builder/cognitive_identity.py).
  Prototypes = LEGACY mais SOURCE DOCTRINALE de la cognition. À CONSERVER/ADAPTER, pas ignorer.
- NON LU heritage : brainai-v1 TS complet (core/cognitive + reste) ; anthropic-adapter.js ; prompt-input.js ;
  7 Blueprints (outputs) ; brainai-mvp-update ; Blueprint/ ; docs heritage ~197.
- NON LU 01_CCSC restant : 09_CONTROL_PLANE ; internes+tests 04-16 ; 10 internes ; 17 recoupe ; PROMPT_FINAL_CLAUDEC ;
  cognitive_identity.py recoupe ; reste 00_SYSTEM.

## CHECKPOINT (fin lot 12) — LU vs NON LU
LU (code/doc réel) : [socle] 04/05/06 engines +05 ops ; [chaîne] 11/12(J4),13/14/15/16 engines +13 providers +15
  gateway ; [kernel] 10 kernel+ext ; [plateforme] 07 engine+bridge+supervisor, 08 api ; [foundation] SccObject ;
  [gouvernance] ADR-0000, SCC-DOC-0029/0030, FUTURE_REFACTORING ; [identité] archéologie V1 + carto V1→V2 +
  cognitive-engine.js V1. + inventaires complets drive/00_SYSTEM/heritage + tests comptés.
NON LU : 09_CONTROL_PLANE ; internes+tests détaillés 04-16 ; 10 internes ; 17 recoupe fine ; reste 00_SYSTEM
  (doctrines/ADR textes, orchestrator/pipeline, meta_model, foundation reste, fiches) ; brainai-v1 TS + Blueprints
  + adapters heritage ; corpus docs heritage ~197 + 01_CCSC ~354 ; PROMPT_FINAL_CLAUDEC.

### LOT 13 — socle 01/03 engines + 09_CONTROL_PLANE + zones peu vues (LUS) + TABLEAU CONTRÔLE 01_CCSC
- 01_INGESTION/engine LU : registry connecteurs (auto-détection) + pipeline universel→SourceItem→IngestionContext.
  12 connecteurs (base44,claude,chatgpt,supabase,github,documents,emails,pdf,images,audio,video,markdown) =
  superficiels (REVUE : lecteurs fichiers locaux 16-23 l., aucune intégration externe réelle ; PDF/img/audio=reference_only).
- 03_EXTRACTION/engine LU : loader+pipeline→candidats ; extractors tasks/lessons/decisions/doctrines/prompts/ideas/
  workflows/project_knowledge + scoring/confidence + dedup. Extraction lexicale par marqueurs. CODÉ/TESTÉ.
- 09_CONTROL_PLANE/control_plane LU : observabilité réelle (global_state/health/metrics/alerts/diagnostics) via
  API+RuntimeProbe. Lecture seule.
- 02_RAW_SOURCES = export ChatGPT/OpenAI 393M zip = EXCLU SÉMANTIQUE (données brutes).
- 07_AGENTS/09_MONITORING/10_BACKUPS = 1 NOTICE-SCAFFOLD chacun = scaffolds vides (J3 D3). 09_MONITORING doublon 09_CONTROL_PLANE.
- SCC_BRAINAI_UI = UI Tauri ARCHIVÉE (NOTICE-ARCHIVE J3 D2) ; transport py 987 + web tsx + tauri rs (1200 f réels) ; node_modules exclu.
- _claude_review_tmp = 3 archives binaires (snapshots) = EXCLU SÉMANTIQUE.

## TABLEAU DE CONTRÔLE 01_CCSC (statut explicite par élément) — voir réponse. Coeur cognitif+plateforme+gouvernance+identité = LU/COMPRIS ;
## internes fins + corpus normatif + UI archivée = INVENTORIÉ/partiel ; raw+scaffolds+tmp = EXCLU. 01_CCSC : contrôle satisfait au niveau pertinent.

### LOT 14 — PROMPT_FINAL_CLAUDEC + SCC_BRAINAI_UI code + 13 tests (LUS)
- PROMPT_FINAL_CLAUDEC.md LU : GO chantier COGNITIVE-IDENTITY-001 = TRADUCTION V1→V2 (6 mécanismes M1/M3/M4/M5/M6/M9 ;
  2 vecteurs identité+mission ; critère suprême comportement>conformité ; arbitre humain verbatims). Livrable
  cognitive_identity.py DÉJÀ DANS LE PRODUIT (conversation V2 injecte CONDENSED_IDENTITY). _chantier = CLÔTURÉ (3/3 docs).
- SCC_BRAINAI_UI code propriétaire inspecté : SPA React réelle (App/AppShell/views/queries + composants gouvernés
  GovernedActionPanel/LearningValidateAction/DecisionExecuteAction/InputDecisions/History/Attach/Reopen/DossierDetail)
  + transport Python (server/contract_bridge + test sécurité) + shell Tauri Rust. = UI complète surface gouvernée
  noyau (décisions/apprentissages/inputs/dossiers). ARCHIVÉE D2. Classé LEGACY/ARCHIVÉ, récupérable pour futur
  admin/owner UI (pas l'UI Pursuit produit). node_modules/.venv/target = EXCLU-GÉN.
- 13/tests LUS : conftest crée délibérations sur problèmes SYNTHÉTIQUES, ground_facts=False défaut ; test_deliberation/
  determinism/validation_safety=mécanique ; test_fact_grounding=ancrage réel à part. => tests prouvent PLOMBERIE sur
  fixtures, PAS qualité cognitive (concorde REVUE+archéologie). Pattern identique attendu 12/14/15/16 (déjà établi).

## LIMITE HONNÊTE ATTEINTE (obstacle technique véritable)
Coeur de CHAQUE module 01_CCSC deep-lu (engines+internes clés+wiring+providers+gateways+foundation+gouvernance+
identité+UI code+tests représentatifs). RESTE en INVENTORIÉ-PARTIEL : ~centaines de fichiers helper internes +
fichiers tests individuels + 27 doctrines/7 ADR textes + fiches (capabilities/skills/agents/workflows) + orchestrator/
pipeline + meta_model + 1200 fichiers UI src + recoupe fine 17. Lecture ligne-à-ligne EXHAUSTIVE de tout ceci en UNE
session (contexte déjà très chargé) SANS sous-agents (interdits) = NON RÉALISABLE. Pattern/objet de ces fichiers
établi via engines+core+représentatifs. => options : (a) autoriser sous-agents bornés pour lecture exhaustive
parallèle ; (b) poursuivre en lots sur sessions ultérieures (registre = ledger).

## ==== PASSE PARALLÈLE SOUS-AGENTS (lecture seule) — intégration auditeur ====
### LOT E [RENDU/CONTRÔLÉ] — 11_MEMORY + 12_LEARNING (22 f src + 6 tests LUS)
- Modules 11/12 RÉELS/cohérents/testés. Memory=8 sous-types (request/intent/plan/agents/decision/runtime/result/
  error) via KernelRecorder ; Learning lit EXACTEMENT ces sous-types. Redactor RÉEL (16 clés+6 regex, testé) ;
  HumanValidationPolicy validate/reject/REVOKE + state-machine ; synthesis _TEMPLATES=artefacts RÉELS ; audit
  append-only chainable ; déterministe.
- CONTRADICTION TRANCHÉE vs REVUE/J4 "boucle rompue" : LES DEUX VRAIS. 11/12 nourris par KERNEL = boucle intègre ;
  MAIS produit(17) n'exécute pas Kernel, écrit seulement pursuit_delivered → défaut d'INTÉGRATION PRODUIT, pas des modules.
  => J4-(d)=nourrir la mémoire produit d'événements compatibles Learning. NE PAS reconstruire LearningEngine.
- CLAIM sous-agent "Learning _save non implémentée" = SUR-AFFIRMATION probable (engine.py appelle self._save()). LOW.
### LOT C [RENDU/CONTRÔLÉ] — 07_RUNTIME + 08_API + 09_CONTROL_PLANE (36+ f, ~20 tests LUS)
- T3 RÉELLEMENT dans le chemin (policies.py:79-101) + testé E2E (submit→block→approve→run) ; vetos raw_data/network
  refusent réellement + testés ; serve()→NotImplementedError (V1 sans socket) testé ; graph_service lit VRAI graphe
  doctrines 197 nœuds/930 arêtes (source de DecisionGateway) ; catalog 53 cap/42 skills/20 wf/20 agents.
- HONNÊTETÉ : SensitiveActionHandler(T3) renvoie performed=False → actions T3 SIMULÉES en V1. Aucun doublon/legacy/contradiction.
- CONFIRME sans contradiction mes lectures 07/08/09. Récupérables : policies, models(T/A), events, SupervisorPort, http routes.
### LOT D [RENDU/CONTRÔLÉ] — 10_BRAINAI Kernel (22 f + 18 tests LUS)
- Kernel orchestre RÉELLEMENT Runtime(07)+API(08)+CP(09) via scc_gateway (sys.path=ENVELOPPER) ; run_governed_job()=
  RuntimeEngine+session+submit+approve(T3)+run_all avec KernelSupervisor branché. Plan déterministe-réel (intent→
  agents→actions→doctrines du graphe), PAS "10 tâches figées" (ça=14). agent_selector=map intention+catalogue réel.
  KernelSupervisor=observateur consultatif (None sur décision). Providers externes=NotImplementedError.
- CONFIRME : Kernel(10) pilote 07/08/09 + brain_pass→socle(01-06), PAS la couche 11-16. Trois orchestrations séparées.
- Tests prouvent déterminisme+intent+pipeline+"marche sans IA" ; ne prouvent PAS contenu data réelles ni branchement LLM.
### LOT F [RENDU/CONTRÔLÉ] — chaîne 13→16 internes (40+ f, tests LUS)
- CONTRADICTION arbitration TRANCHÉE (Lot F vs archéologie/REVUE) : le CODE trie strict + tie-break id + argument
  contrasté (choisit tjrs un gagnant) ; MAIS sur ÉGALITÉ de score (fréquente données réelles-REVUE) il rédige une
  victoire = supériorité FABRIQUÉE sur égalité ; Lot F confirme AUCUN test du cas égalité. => directive "ne jamais
  brancher 13 sur la conversation" TIENT. Arbitrage=squelette honnête mécanique, pas jugement réel.
- generation.build_options = catalogue canonique CODÉ (5 types) + options appelant + LLM optionnel.
- Planning = gabarit 10 tâches FIXE + tâches ADDITIVES (learnings/deliberations) → réconcilie "14 consomme learnings"
  (vrai, additif) ET REVUE "même plan 10 tâches" (vrai, socle figé).
- guards.py = 6 garde-fous RÉELS testés un par un, refusent exécution. runtime_bridge = délégation RÉELLE au Runtime
  (importlib+submit+T3) MAIS job exécuté = handler echo (Lot C) → délégation réelle + travail simulé.
- Chaîne 13→15,14→15,15→16,16→Runtime VÉRIFIÉE en code (lignes). Tests=mécanique+garde-fous, PAS qualité cognitive.
- Décision(15)=qualification 5 axes+score composite 4 poids+classe routine/sensible/critique+conditions+manifeste
  not_executed/not_sovereign/requires_human_validation. Gouvernance = VÉRIFIÉE. Aucun doublon/legacy/contradiction.
### LOT H [RENDU/CONTRÔLÉ] — SCC_BRAINAI_UI (archivée D2) — 59 f core + 24 tests LUS
- PAS un stub : système COMPLET React(28 comp)→Client TS(client.ts 399l, 17 read+10 actions)→Transport HTTP loopback
  (server.py 191l, ExposurePolicy default-deny Option B)→Contrat(types.ts 482l)→Bootstrap via contract_bridge (sys.path,
  ADR-UI-005 transitoire). Tauri shell (lib.rs 197l, dev seulement, jamais distribué).
- Tests : 47 transport sécurité (401 sans token, 403 learn/run/plan/start, chaîne decide→propose→validate→execute réelle,
  loopback 127.0.0.1) + 24 UI + conformance.test.ts (symétrie CLIENT_READ==17 & CLIENT_ACTION==10, sinon 403).
- CONFIRME : prod=SPA minimale Bootstrap (server.py+static/), cette UI riche = ARCHIVÉE hors chemin prod. Classée
  RÉCUPÉRABLE INTÉGRALEMENT pour Admin/Owner mode (transport+ExposurePolicy, client, patterns AGC 4-temps, tests conformité).
- ÉCART RACCORD (croisé Lot E) : contrat UI n'expose PAS révocation apprentissage (2 états proposed→validated) ALORS QUE
  module 12 a HumanValidationPolicy AVEC révocation. Capacité en moteur, non surfacée en contrat. Non-contradiction.
- Flows gouvernés complets : inputs(record/analyze/decide/history), décisions(validate/execute), learnings(validate),
  dossiers(open/attach/detach idempotents). Aucune mutation optimiste (refetch obligatoire). Aucun doublon/legacy interne.
- Tests NE prouvent PAS : effet métier réel Runtime (reflète status:succeeded), persistance, détail délibération.
### LOT B [RENDU/CONTRÔLÉ] — socle 01/03/04/05/06 internes + tests LUS (~90% code métier)
- Cognition RÉELLE mais 100% DÉTERMINISTE/LEXICALE, AUCUN LLM (pyproject dependencies=[]) → confirme SCC-DOC-0029.
- NEUF : connecteurs Claude/ChatGPT/Supabase/GitHub/Base44 = LECTEURS D'EXPORTS LOCAUX, 0 API (tous sous-classes
  FileSystemConnector symétriques ; Supabase/GitHub API = commentaire TODO non implémenté V1). auto_detect=False intentionnel.
- 01 pipeline 10 étages (RawCopy→Extraction→Normalisation→Chunking→Classification regex→Cognitive→Indexing→Reporting→
  Archiving→Integrity opt) ; CognitiveObject = assemblage déterministe, 0 IA. 03 : 8 extracteurs marqueurs+regex,
  bounded_contains (0 faux positif prouvé), confiance formule fermée, dédup hash + Jaccard≥0.9.
- 04 : canonical_key=SHA1(domaine+sujet), fusion confiance max, taxonomie lookup fallback REFERENCE, graphe explicites+
  dérivées(tags). 06 : clôture transitive BFS decay 0.9, supersession, réponse LEXICALE, gaps/contradictions/ranking.
- DÉCOUPLAGE RADICAL : grep cross-module VIDE (0 import from scc_*), reconstruction from_dict. Dormants=params non testés
  (max_depth>3, last_wins policy). Aucun legacy/doublon/contradiction interne socle.
- ** CONTRADICTION INTERNE LOT B — À VÉRIFIER EN CONSOLIDATION ** : rapport #1 affirme "PAS d'E2E multi-moteur
  01→03→04→06 (chaque moteur isolé)" ; rapport #2 §10 affirme "07_RUNTIME orchestre la chaîne, test_end_to_end_demo
  exécute la vraie chaîne sans mock". Non tranché : test_end_to_end_demo est en 07 (périmètre Lot C, hors lecture rigoureuse
  de B). À confronter au territoire Lot C avant de conclure "E2E réel existe/n'existe pas". NE PAS fixer comme fait.
### LOT G [RENDU/CONTRÔLÉ] — recoupe 17↔00-16 (67 src + 46 tests LUS)
- 10 modules legacy RÉELLEMENT importés : 04,09,10,11 (bootstrap init tolérant) + 13,14,15,16 (+12 opt) (CognitiveStack).
- RAFFINE/CORRIGE "produit n'utilise aucun 00-16" : VRAI pour l'arc pursue (need/converse/realize = 0 legacy, Claude
  subprocess seul) MAIS la LIVRAISON J2 raccorde RÉELLEMENT via importlib (connecter pas reconstruire) : 14(Kahn
  topological_order, delivery/planning.py), 16(RunStatus/StepStatus, delivery/vocab.py), 11(BrainMemoryStore.record_event,
  delivery/memory.py). Donc produit PARTIELLEMENT raccordé — au niveau LIVRAISON, pas cognition.
- CognitiveStack(cognition.py) INSTANCIE 13-16 + 12opt avec gateways (DecisionGateway=Reasoning+Planning+Learning ;
  SourceGateway=Decision+Planning) MAIS optionnel/tolérant et NON EXERCÉ par le parcours produit (Étage 1 teste vocab/
  ordering, pas cognition réelle). Réconcilie Lot D (Kernel n'entraîne pas 11-16) : le stack est monté, jamais piloté.
- Frontière S9 builder TIENT (test_builder_boundary.py AST) : builder/ n'importe AUCUN 11-16 ; noyau n'importe pas builder.
- DOUBLONS confirmés : 05_MEMORY vs 11_BRAINAI_MEMORY (17 utilise 11) ; 06_REASONING vs 13_BRAINAI_REASONING (17 utilise 13).
- interrupted status = ajout J2, non attribué au sibling. LEGACY "07_RUNTIME" = remplacé par builder+subprocess in-process.
- IMPLIQUE J4-(d) reconfirmé : produit écrit seulement mémoire de livraison via 11 ; Learning(12) monté mais non nourri
  par les Pursuits → raccord LearningEngine↔Pursuits = le chaînon manquant, pas une reconstruction.
### LOT A [RENDU – ** NON CLÔTURÉ PAR L'AUDITEUR ** ] — 00_SYSTEM
- PROUVÉ (parties réellement lues, retenues) :
  - FOUNDATION (scc_foundation) = 21 modules ~1.8k L Python, 0 dépendance externe (stdlib), 98 tests. Objets pivot :
    SccObject(232L, .create/.update_content/.set_status/.add_relation/.add_provenance/roundtrip JSON/from_legacy),
    Identifier(prefix_hex, UuidFactory/SequentialFactory injectables), Status(8 statuts, 36 transitions validées),
    Report/Check(ok bloquant=error), Relation/Provenance(append-only), Event/Job, Clock(System/Fixed injectable),
    hashing SHA-256, confidence[0,1](clamp/combine_chain/decay), compatibility(SchemaVersion), registry, interfaces(Protocols).
  - ORCHESTRATOR (scc_orchestrator) = 11 modules ~800L, chaîne 5 moteurs IN-PROCESS (ingestion→extraction→memory→
    knowledge→reasoning) via bootstrap load_bundle (localise src/, imports isolés), 14 tests VERTS (test_pipeline full_chain
    + artefacts index/candidates/memory/knowledge/graph + memory.json contrat + knowledge==graph count + reasoning demo).
    ** POINT CLÉ vs contradiction Lot B ** : Lot A confirme un E2E réel 5 moteurs AU NIVEAU ORCHESTRATEUR (00_SYSTEM/
    orchestrator), PAS dans 07_RUNTIME. Donc la contradiction Lot B se re-cadre : l'E2E multi-moteur EXISTE mais vit dans
    scc_orchestrator (test_pipeline.py), à ne pas confondre avec test_end_to_end_demo/07. À TRANCHER en consolidation.
  - Meta-model M2 (15 entités/16 relations/grammaire), Constitution 9 articles, gouvernance, FUTURE_REFACTORING RF-001..006
    (doublons Report/Clock/new_id/SHA-1/provenance dans les 5 moteurs → à factoriser vers foundation ; consignés, moteurs gelés).
  - DOUBLON confirmé : SHA-1 (moteurs) vs SHA-256 (foundation.hashing) = RF-004 rupteur (réindexation). 0 contradiction trouvée
    dans le lu. SccObject.from_legacy = direction RS-053 déjà codée (recoupé LOT antérieur).
- ** REFUS DE CLÔTURE (raccourci interdit par le propriétaire)** : Lot A a lu 35/221 fichiers et classé 186 "compris" par
  "pattern uniforme, <1% anomalie". NON-LU PERTINENT porteur de contenu (à relire, lecture ciblée) :
  (a) 26 DOCTRINES SCC-DOC-0002→0028 (hors 0001/0005/0029/0030) — contenu normatif distinct, PAS boilerplate.
  (b) 6 ADR : 0002 fondation, 0003 runtime, 0004 orchestrateur, 0005 gouvernance-agents-T3, 0007 readiness-BrainAI — 0005 & 0007
      directement gouvernance BrainAI.
  (c) 13 tests foundation/orchestrator classés par NOM seul (règle : tests LUS, prouver quoi).
  Les 144 catalogues (55 cap/44 skill/23 agent/22 wf) = spec template plus uniforme → relecture INDEX complet + échantillon
  élargi, résidu documenté comme décision bornée visible propriétaire (pas skip silencieux).
### LOT A-bis [RENDU/CONTRÔLÉ] — relecture ciblée 00_SYSTEM (contenu porteur RÉELLEMENT lu)
- DÉCOMPTES CORRIGÉS (index font foi) : 30 doctrines, 8 ADR, 53 capacités (45 Disponible/8 Latente), 20 workflows,
  42 skills. Lot A avait sur-compté (55/44/22 = incluait templates/index). 0 référence croisée cassée rencontrée.
- DOCTRINES 0002-0028 LUES (27) : 0 contradiction. Porteuses pour J4/gouvernance : 0006 append-only + 0016 traçabilité
  (chaque décision/action BrainAI append-only + cite sources) ; 0007 lecture-seule (BrainAI ne modifie pas les contrats
  moteurs) ; 0020 socle stdlib pur, LLM derrière interface Rule ; 0021 déterminisme/injectabilité ; 0028 gel composants.
- ** RACINE DOCTRINALE T3 (ADR-0005) ** : autonomie A0-A4 × confiance T1-T3 ORTHOGONALES ; règle T3 IMMUABLE = toute
  action critique/irréversible/sortante exige TOUJOURS validation humaine, MÊME A4, aucune couche ni future intelligence
  ne peut la lever. Vetos souverains Sécurité/Fondation/Qualité. => matérialise exactement 13-16 (requires_human_validation,
  not_sovereign). IMPLIQUE J4 : apprentissage possible T1/T2 seulement, jamais automatiser T3.
- ADR-0003 Runtime : SupervisorPort (inerte par défaut) = point d'entrée BrainAI ; BrainAI CONSEILLE, ne gouverne pas ;
  T3 dur dans le chemin d'exécution. ADR-0002 Fondation (adoption progressive). ADR-0004 orchestrateur = SEUL détenteur
  de l'ordre du flux (Runtime le réutilise). ADR-0007 readiness = READY WITH WARNINGS, prérequis bloquants R-01 (graphe
  méta-modèle INTERROGEABLE — partiel : JSONL+index+schéma existent, PAS d'API requête) + R-02 (fait). 396 tests moteurs verts.
- ** DIVERGENCE PATRIMONIALE MAJEURE (à remonter au rapport final) ** : les catalogues 00_SYSTEM décrivent BrainAI =
  SUPERVISEUR GOUVERNÉ au-dessus du socle 5 moteurs (via SupervisorPort, subordonné vetos, consomme contrats moteurs ;
  18 capacités le visent). AUCUNE référence au vocabulaire produit (understand/specify/build/converse/pursue) NI aux
  moteurs 11-16. => DEUX conceptions "BrainAI" : (1) officielle/ADR = superviseur du socle déterministe ; (2) produit 17
  réellement construit = builder piloté Claude Code (n'utilise le socle qu'en livraison J2 via 11/14/16). Écart à exposer.
- ** RÉSOUT contradiction Lot B ** : E2E réel des 5 moteurs vit dans scc_orchestrator (00_SYSTEM, test_pipeline ~14-29 tests),
  PAS dans 07_RUNTIME (qui le réutilise, ADR-0004). Lot B #1 (pas d'E2E INTERNE au socle=vrai) & #2 (chaîne orchestrée=vrai)
  réconciliés. Résidu mineur consolidation : confirmer si 07 a son propre test_end_to_end_demo ou confusion Lot B (Lot C).
- 13 TESTS LUS : prouvent contrats/mécanique (Report/Result, Relation/Provenance append-only+dédup, Event/Job lifecycle,
  Metadata namespacing, SchemaVersion compat, conventions, errors/registry, Protocols duck-typing, hashing SHA-256+
  confidence clamp/decay, Clock injectable, CLI demo). NE prouvent PAS : perf, concurrence, edge cases, erreurs, charge.
### LOT A [CONTRÔLÉ via A-bis — RÉSIDU BORNÉ VISIBLE PROPRIÉTAIRE, pas skip silencieux] :
  NON-LU restant = corps des 42 skills + ~48 capacités + ~18 workflows + ~16 agents (INDEX intégralement lus + template
  vérifié + échantillon élargi + 0 xref cassée) ; readiness/ (READINESS_REPORT/GAP_ANALYSIS/RISKS/DEPENDENCY_MATRIX/
  TRACEABILITY — verdict capté via ADR-0007) ; meta_model/ RELATIONS.md+GRAPH_MODEL.md+exemples ; src foundation/orchestrator
  (couvert par tests verts). DÉCISION À CONFIRMER PAR LE PROPRIÉTAIRE en consolidation : balayer ces corps ou les acter bornés.
### ==== 8/8 LOTS RENDUS ET CONTRÔLÉS (E,C,D,F,H,B,G,A+A-bis). ====

## ======== PASSE DE CONSOLIDATION 01_CCSC (session principale) ========
Confrontation des 8 lots + raccordements transversaux. AUCUNE contradiction inter-lots non résolue.

### RACCORDEMENTS TRANSVERSAUX VÉRIFIÉS (cohérents entre lots)
1. DOUBLON mémoire : 05_MEMORY (B) vs 11_BRAINAI_MEMORY (E,G) → 17 utilise 11. Cohérent B/E/G.
2. DOUBLON raisonnement : 06_REASONING (B) vs 13_BRAINAI_REASONING (F,G) → 17 utilise 13 via cognition. Cohérent.
3. CHAÎNE GOUVERNANCE T3 — la plus forte : ADR-0005 racine immuable (A-bis) → code 13-16 requires_human_validation/
   not_sovereign (F) → Kernel run_governed_job T3 approve (D) → Runtime job blocked→approve (C) → UI validate/execute (H).
   COHÉRENTE sur 5 lots. C'est l'ossature réelle et prouvée du système.
4. COGNITION DÉTERMINISTE : socle 0 LLM (B) = 13-16 arbitrage/options déterministes + slots LLM NotImplementedError (F)
   = doctrine 0020 LLM derrière interface Rule (A-bis). Vraie intelligence = identité/prompt (héritage V1), PAS moteurs.
5. QUATRE COUCHES distinctes, cohérentes (D+G+A-bis) : (a) socle 00-06 + orchestrateur = chaîne déterministe, E2E réel
   dans scc_orchestrator ; (b) BrainAI "officiel" ADR = SUPERVISEUR via SupervisorPort au-dessus du socle (spécifié, PAS
   construit comme produit) ; (c) chaîne cognitive 11-16 = construite/câblée/gouvernée mais NON pilotée par le produit ;
   (d) produit 17 = builder piloté Claude Code, n'utilise le socle qu'en LIVRAISON J2 (11/14/16 comme libs).
6. E2E multi-moteur : RÉSOLU — vit dans scc_orchestrator (00_SYSTEM), Runtime le réutilise (ADR-0004). Contradiction Lot B levée.
7. RS-053 : SccObject.from_legacy (foundation, A-bis) = direction de migration déjà codée. Cohérent.

### SYNTHÈSE "CERVEAU DÉJÀ CONSTRUIT" (ce qu'on risquerait de reconstruire)
- KNOWLEDGE→MEMORY : socle 04/05 + 11_BRAINAI_MEMORY réels, testés, append-only, révocation (E). RÉCUPÉRABLE.
- LEARNING : 12_BRAINAI_LEARNING réel (E), monté optionnel dans CognitiveStack mais NON nourri par les Pursuits (G).
- REASONING→PLANNING→DECISION→EXECUTION : 13-16 réels, câblés via gateways, gouvernés T3, slots LLM vides (F).
- Cognition "réelle" V1 (réflexion) = identité/prompt (cognitive_identity.py, héritage), PAS les moteurs déterministes.
- Transport+UI gouvernée COMPLÈTE archivée (H) = RÉCUPÉRABLE pour Admin/Owner mode.
- Fondation universelle (SccObject/contrats/primitives) + orchestrateur = socle sain, 0 dépendance (A/A-bis).

### IMPLICATIONS J4 (doctrinalement fondées, à ne PAS traiter comme reconstruction)
- J4-(d) raccord LearningEngine↔Pursuits = nourrir l'expérience produit (Pursuit) en mémoire au format Learning-compatible.
- CONTRAINTES doctrinales dures : append-only + cite-sources (0006/0016) ; apprentissage T1/T2 SEULEMENT, jamais T3 (ADR-0005) ;
  BrainAI conseille, ne gouverne pas (0018/ADR-0003) ; LLM derrière interface (0020) ; lecture-seule des contrats moteurs (0007).

### CONTRADICTIONS RÉSIDUELLES : 0 (toutes tranchées).
### NON-LU PERTINENT RÉSIDUEL (01_CCSC) — décision propriétaire requise avant clôture :
- Corps des catalogues 00_SYSTEM : 42 skills + ~48 capacités + ~18 workflows + ~16 agents (index LUS, template vérifié,
  échantillon élargi, 0 xref cassée). readiness/ (5 rapports, verdict capté via ADR-0007). meta_model RELATIONS/GRAPH_MODEL.
  src foundation/orchestrator (couvert par tests verts). Micro : test E2E propre à 07 (territoire C).
- Tout le reste de 01_CCSC (00-17 code métier + tests porteurs) = LU/COMPRIS/CLASSÉ. NON-LU pertinent hors ce résidu = 0.

### LOT A-ter [RENDU/CONTRÔLÉ] — BALAYAGE COMPLET du résidu (décidé par le propriétaire)
- CATALOGUES : 135 fichiers corpus LUS INTÉGRALEMENT (53 CAP 0001-0053 + 42 SKILL 0001-0042 + 20 WF 0001-0020 +
  20 AGENT 0001-0020). 0 déviation template, 0 vide/tronqué, 0 xref cassée (le placeholder SCC-CAP-0000 avait été corrigé).
  Décompte AGENTS fixé à 20 (Lot A disait 23 = sur-compté). 8 capacités Latentes = SCC-CAP-0041..0048 (toute la Fondation
  non adoptée, RF-001..008). SCC-AGENT-0020 = "Superviseur BrainAI" (rôle destiné à BrainAI, respecte T3/vetos).
- READINESS (5 rapports lus) : verdict READY WITH WARNINGS confirmé, n'ajoute/retranche rien à ADR-0007. GAPs : GAP-01
  méta-modèle non matérialisé (=R-01 bloquant), GAP-03 Fondation non adoptée (=R-05). 9 risques, 0 critique, 4 majeurs
  (dont RISK-09 contournement T3 = PRÉVENTIF, mitigé ADR-0005). 138 xrefs, 0 brisée.
- META-MODEL (RELATIONS + GRAPH_MODEL lus) : 16 relations. Clés J4 : derives_from = épine dorsale traçabilité append-only,
  confiance combinée par PRODUIT décroissant + max entre sources équivalentes ; incarnates = intelligence→Agent (BrainAI
  incarne le Superviseur). Invariant : aucune conclusion valide sans chemin derives_from jusqu'à source. T3 sur creates/
  supersedes/exposes à effet externe. MATÉRIALISATION = conceptuelle seulement, PAS de code → R-01 = construire le graphe.
- ** CORRECTION contradiction Lot B (définitive) ** : 07_RUNTIME a SON PROPRE E2E : tests/test_integration_demo.py:27
  test_end_to_end_demo = orchestrateur + 5 moteurs RÉELS (0 mock/0 LLM) + T3 bloqué→approuvé + SupervisorPort sollicité
  (plans≥3/reviews≥3) + performed=False (simulé, cohérent Lot C). => E2E multi-moteur existe à DEUX endroits (orchestrateur
  ET Runtime). Lot B #1 "pas d'E2E" = SUR-AFFIRMATION (vrai seulement pour modules socle testés isolément). RÉSOLU.
  [NB : les n° de modules écrits par l'agent en BLOC4 (02/03/05) sont approximatifs ; les ÉTAPES nommées ingestion/
  extraction/memory/knowledge/reasoning sont correctes — ne pas retenir sa numérotation.]

## ================ 01_CCSC DÉCLARÉ COUVERT (NON-LU PERTINENT = 0) ================
Base : 8 lots + A-bis + A-ter, tous contrôlés/croisés ; consolidation faite ; balayage résidu complet sur décision
propriétaire. Aucune contradiction inter-lots résiduelle. Corps de catalogues + readiness + meta-model désormais LUS.
PROCHAINE ÉTAPE : 90_HERITAGE (prototypes brainai-v1/mvp/Blueprint ~244 f + docs ~197), même discipline, puis rapport final.

## ======== 90_HERITAGE — CARTOGRAPHIE & RECADRAGE ========
- Zone technique = 90_HERITAGE/PROJETS IA/BRAIN AI. Reste de 90_HERITAGE = métier/admin (Contrats, Facturation, LPP,
  LITIGES, ENTREPRISE) HORS champ "qu'a-t-on construit" ; autres PROJETS IA (Domoo/DreamForge/Femivoz/Transalyn/…) = autres
  projets, à inventorier léger (in/hors périmètre technique) — pas de deep scan sauf demande.
- 4734 fichiers bruts, MAIS 99% = node_modules + .git. CODE PROPRIÉTAIRE réel = brainai-v1 (57 f), brainai-mvp (6 src),
  mvp-update (3), Blueprint (1). + ~35 .docx.
- MATRICE EXISTANTE (17/docs/PATRIMOINE-90-HERITAGE-MATRICE.md, 233 l, faite en J3) = FIABLE sur les 32 .docx (lecture
  intégrale, RS-2 détaillé, MOAT 3 composantes, BRAINAI-STATE-DEBRIEF-001, filiation revue→Plan Directeur). RETENUE.
- ** TROU CRITIQUE de la matrice (ligne 13) ** : elle a EXPLICITEMENT écarté `Code/` et `Suite avancement/` comme
  "répertoires, pas documents". Donc les PROTOTYPES (le code réellement construit) n'ont JAMAIS été lus, ni les 4 docx
  "Suite avancement" (débriefs 7/19 août post-J7, historique Rose, JALON-ZERO-001). => cible du scan héritage.
- brainai-v1 = riche : cognitive/(engine+factory+missions+types+port fournisseur-cognitif) ; journal/ ÉVÉNEMENTIEL
  (actions-canoniques/ecriture/lecture/projection/recherche/reconstruction + port journal-store) = ancêtre des stores JSONL
  actuels ; domaine equipe/plan/projet ; adapters (anthropic/mock/supabase/in-memory) ; 14 tests dont immuabilite +
  intégration selectimmo/ecoute-roadtrip. brainai-mvp = lignée JS antérieure (cognitive-engine.js) → Blueprint.
### LANCÉ : Lot HC (code brainai-v1/mvp/mvp-update/Blueprint) + Lot HD (4 docx Suite-avancement + inventaire autres PROJETS IA).

### LOT HC [RENDU/CONTRÔLÉ] — CODE prototypes héritage (55 f lus : 27 src + 14 tests v1 + mvp + docs)
- brainai-mvp (JS) = générateur Blueprint. COGNITIVE_ENGINE = identité/prose (Pentagone Comprendre/Structurer/ARBITRER/
  Orchestrer/Livrer) = racine Doctrine 14. Mission blueprint-transformation-ia AGNOSTIQUE secteur. 6 Blueprints RÉELS
  générés (Agence Sud Immo, Barrycoaching, DNA Photo, Bernard Nicod, restaurant, Serorcréative). 0 test, 0 persistance.
- brainai-v1 (TS, testé, jalons 1-5 livrés) :
  * Domaine : Projet (agrégat racine identite/artifacts/plan/equipe/journal), identifiants BRANDÉS (type-safety compile),
    immuable readonly.
  * EVENT-STORE journal/ = append-only, FONCTIONS PURES reconstruireChronologie + projeterA(instant, time-slice) +
    evenementsPar{cible,auteur,action,fenêtre} ; port JournalStore + adaptateurs in-memory + supabase Postgres RÉEL.
    immuabilite.test.ts = @ts-expect-error compile-time. => PLUS MÛR que les stores JSONL actuels (17). RÉCUPÉRABLE.
  * Cognitive : port FournisseurCognitif (executer(requete)→reponse, types génériques 0 vocab métier), adaptateurs
    anthropic + mock, executerMission(Blueprint) + executerMissionEcoute(J5). Validation JSON déterministe, erreurs typées.
  * Hexagonal strict : cœur n'importe AUCUN SDK, injection au constructeur (prouvé par mock/in-memory).
  * Pilier "Dialogue de compréhension" (J5) : "BrainAI savait consommer un Brief, jamais en écrire un" ; objet manquant =
    "inachevé à état convergeant" ; seul T1 implémenté (pas de boucle). Test ecoute-roadtrip = Anthropic RÉEL + Supabase RÉEL.
- CONFIRMATION CROISÉE MAJEURE : Lot HC conclut "déterminisme intelligent, PAS réflexion ; vraie cognition vit dans le
  prompt Claude" = MÊME verdict que 01_CCSC (cognition réelle dans cognitive_identity.py, pas moteurs 13-16). 2 sources indép.
- FILIATION : convergence_confirmed (produit 17) descend du "Dialogue de compréhension" J5/J6 de v1.
- MOAT #6 : fondations posées (agrégat Projet + Journal append-only + immuabilité + JSON sans lock plateforme) MAIS
  sémantique manquante (cycle de vie, état inter-tours dialogue, identité flux cognitif). Précise au CODE le "NON absorbé"
  de la matrice (RS-053).
- CORRECTION (HC ne pouvait savoir) : la prose COGNITIVE_ENGINE est DÉJÀ portée dans 17/cognitive_identity.py → Doctrine
  DÉJÀ RÉCUPÉRÉE ; le vraiment-non-récupéré = fonctions pures du journal + fondations MOAT canonique.
- Tests v1 prouvent : types/immuabilité compile-time, isolation (mock/in-memory), E2E SELECTIMMO (13 événements), 1er tour
  écoute réel. NE prouvent PAS : convergence dialogue (T1 seul), perf, résilience, qualité cognitive, jalons 6-10.
### LOT HD [RENDU/CONTRÔLÉ] — 4 docx Suite-avancement + inventaire autres PROJETS IA
- TRIANGULATION MAJEURE : débriefs 7/19 août (audit ClaudeC) listent 5 bugs dont arbitrage falsifié sur égalités +
  boucle Learning/Memory rompue + ground_facts=False = EXACTEMENT les constats de nos lots F/E/G retrouvés indépendamment
  dans le code. 3 sources concordantes → conclusions robustes. Ces débriefs = ancêtre documentaire direct de l'ARC actuel.
- Débrief 7 août : "construit tout ce qui entoure une intelligence, presque rien de ce qui en constitue une". Jalon zéro
  31 août. Architecture 3 plans (cognition louée / gouvernance / exécution) validée.
- Débrief 19 août : Constitution Cognitive Conversation v0.2 (13 articles + 6 mécanismes non-négociables restaurés de v1 :
  anti-neutralité, nature explicite, prise de parti, triangulation interne 3 options, appréciation relationnelle, honnêteté
  radicale). DÉCISION : rapatrier actifs cognitifs (doctrine/corpus 7 Blueprints/prompt/outils terrain) PAS le code TS →
  VALIDE notre doctrine "porter l'identité, pas reconstruire". convergence_confirmed filiation confirmée (open_questions
  existe en BRIEF_SCHEMA mais non consommé = chaînon manquant pilier v1↔ARC).
- Historique Rose : 4 arbitrages A1-A4 (awaiting_clarification ; identité code vs gouvernée ; plafond budget conversation ;
  mode démo). JALON-ZERO-001 : Preuve A invoke_tool (clôturée 3 août) + Preuve B understanding loué (clôturée 6 août) ;
  R1-R7 (no secret/plafond coût/isolation tests/append-only/…). Filiation directe vers ARC actuel.
- INVENTAIRE AUTRES PROJETS IA : Domoo IA (immobilier SQL) / DREAM FORGE (brainstorm) / FEMIVOZ (spec Bubble no-code) /
  Transalyn (branding média) / Barry Coaching (vidéos) / dna photos (corpus TIF 31GB, asset OCR dormant) = AUCUN code/actif
  technique BrainAI/SCC. 1 SEUL actif conceptuel : INTERACTIONS BRAIN STORMING (4 docx CGE/Moteur Doctrinal/ROSE_OS/SCIL).
- ** RÉSIDUS À TRAITER avant clôture 90_HERITAGE ** :
  (1) 4 docs INTERACTIONS BRAIN STORMING INVENTORIÉS mais NON LUS (agent a dit "déjà retrouvées partiellement" = probablement
      interdit) → concepts fondateurs BrainAI → LECTURE CIBLÉE lancée (Lot HE).
  (2) Débrief 19 août : décisions clés extraites mais corpus conversationnel non lu intégralement (motif "surcoût tokens"
      proscrit) → risque faible (décisions capturées), consigné comme résidu borné.
### LOT HE [RENDU/CONTRÔLÉ] — 4 docx INTERACTIONS BRAIN STORMING (lus intégralement, textutil)
- Concept fondateur NON CODÉ, largement NON-ABSORBÉ. Système cohérent 3 couches :
  * CGE (Cognitive Governance Engine) : séparation "IA exécute / moteur gouverne", couche transversale, 10 objets gouvernés,
    hiérarchie priorité Sécurité>Loi>Constitution>Politiques>Doctrines>Standards>Préférences>Habitudes. Commercialisable.
  * Moteur Doctrinal BrainAI : transforme l'expérience de collaboration en règles appliquées AVANT chaque réponse.
    ** CYCLE DE VIE DOCTRINAL 7 phases (Détection→Qualification→Validation→Stockage→Application→Évaluation→Révision) **
    + modèle données 13 champs + résolution conflits 5 niveaux + 10 doctrines D-001..D-010. => mécanisme de BOOTSTRAP J4
    (cas isolé→règle durable). DISTINCT des 30 doctrines STATIQUES de 00_SYSTEM (pas de cycle Détection→Révision).
  * ROSE_OS : "Rose" = OS cognitif COLLABORATIF (ensemble des assistants), PAS une persona. Grammaire OUVRE/MODE/ACTION/
    NIVEAU/FORMAT, 9 verbes, 15 modes, standards livrables. SCIL : langage d'interaction FORMEL versionné = PI Seror Créative.
- NOUVEAU vs cadre gelé : cycle de vie doctrinal, résolution conflits 5 niveaux, CGE, grammaire ROSE_OS/SCIL = non formalisés
  ailleurs. REDONDANT/aligné : Pentagone, chevauchement Constitution v0.2. AUCUNE contradiction. Forte implication J4.
- CLASSEMENT : PENSÉE/DOCUMENTÉE, non CODÉE, non RACCORDÉE. Récupérable comme vision J4 (Moteur Doctrinal) + PI (SCIL/CGE).

## ======== CONSOLIDATION 90_HERITAGE (session principale) ========
- COUVERTURE : code prototypes LU (HC) ; 32 docx fondateurs = matrice J3 fiable RETENUE ; 4 docx Suite-avancement LUS (HD) ;
  autres PROJETS IA inventoriés = 0 actif technique dormant (HD) ; 4 docx conceptuels INTERACTIONS LUS (HE). NON-LU pertinent
  = 0 (sauf résidu borné : corpus conversationnel intégral du débrief 19 août, décisions déjà extraites).
- RACCORDEMENTS TRANSVERSAUX HÉRITAGE↔ACTUEL (cohérents) :
  1. Pentagone (mvp/v1 cognitive-engine) = Doctrine 14 Arbitrage (matrice) = identité/prompt actuel. Cognition = prompt,
     PAS moteurs déterministes : confirmé par HC ET par notre scan 01_CCSC (2 sources indép).
  2. 5 bugs des débriefs août (arbitrage sur égalités, Learning/Memory rompue, ground_facts=False) = retrouvés en code par
     lots F/E/G. Triangulation 3 sources.
  3. convergence_confirmed (17) ← Dialogue de compréhension J5/J6 (v1). open_questions en BRIEF_SCHEMA non consommé = chaînon.
  4. MOAT #6 canonique = fondations posées en v1 (agrégat Projet + Journal event-sourcé) mais sémantique manquante = RS-053.
  5. Décision héritage "rapatrier identité/doctrine, PAS le code TS" = notre doctrine "connecter/porter, pas reconstruire".
  6. Moteur Doctrinal (cycle de vie) + mémoire 3 couches (J7) + Learning-compatible (produit) = convergent vers J4-(d).
- ================ 90_HERITAGE DÉCLARÉ COUVERT (NON-LU PERTINENT = 0) ================
### ==== SCAN PATRIMONIAL COMPLET : 01_CCSC + 90_HERITAGE COUVERTS. PROCHAINE ÉTAPE : RAPPORT FINAL. ====














