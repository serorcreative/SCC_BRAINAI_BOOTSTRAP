# Rapport patrimonial BrainAI / SCC — « Qu'avons-nous déjà construit que nous risquerions de reconstruire ? »

*Scan patrimonial exhaustif en **lecture seule** (aucune modification, aucun appel LLM métier, aucun code écrit).
Discipline stricte : **INVENTORIÉ ≠ OUVERT ≠ LU ≠ COMPRIS/CLASSÉ**. Tests **lus** (pas comptés). Registre de
couverture cumulatif : `scratchpad/patrimoine/00_REGISTRE_COUVERTURE.md`. Toute conclusion est référée à un chemin de
code/preuve. Le cadre gelé (Plan Directeur v1.0, R0–R12, I1→I9, Constitution) **prévaut**.*

---

## 0. Méthode & couverture (honnêteté épistémique)

- **01_CCSC — COUVERT (NON-LU pertinent = 0)** : 8 lots parallèles bornés (socle 00-06, chaîne 07-16, produit 17, UI) +
  2 relectures ciblées (A-bis, A-ter) + passe de consolidation session principale. Code métier **et** tests porteurs lus.
- **90_HERITAGE — COUVERT (NON-LU pertinent = 0)** : code des prototypes (brainai-v1/mvp) **jamais lu auparavant**,
  désormais lu ; 32 docx fondateurs (matrice J3 fiable, retenue) ; 4 docx « Suite avancement » ; 4 docx conceptuels
  INTERACTIONS ; inventaire des autres PROJETS IA.
- **Résidu borné assumé (visible)** : corps du corpus conversationnel intégral du « débrief 19 août » (décisions déjà
  extraites) ; hors périmètre technique : dossiers métier/admin de 90_HERITAGE (Contrats, Facturation, LITIGES…) et
  projets clients sans actif technique BrainAI (Domoo/DreamForge/Femivoz/Transalyn/Barry/dna photos).
- **Aucune contradiction inter-source résiduelle.** Là où des sources semblaient se contredire, la contradiction a été
  **tranchée par le code** (voir §5).

---

## 1. La chaîne « cerveau » reconstruite (état réel, preuve à l'appui)

**KNOWLEDGE → MEMORY → LEARNING → REASONING → PLANNING → DECISION → EXECUTION**

| Maillon | Existe ? | Nature réelle | Classement |
|---|---|---|---|
| KNOWLEDGE (04) | Oui, testé | Consolidation canonique déterministe (SHA1 domaine+sujet), graphe tags. 0 LLM | **CODÉ/TESTÉ/RÉCUPÉRABLE** |
| MEMORY (05 + 11) | Oui, testé | Append-only, validation/révocation humaine, versioning. 05 vs 11 = doublon (17 utilise 11) | **CODÉ/TESTÉ/RÉCUPÉRABLE** |
| LEARNING (12) | Oui, testé | Réel, monté optionnel dans CognitiveStack **mais non nourri par les Pursuits** | **CODÉ/TESTÉ, NON RACCORDÉ** |
| REASONING (06 + 13) | Oui, testé | Chaîne gouvernée réelle ; arbitrage **déterministe** (rédige une victoire même sur égalité de score) | **CODÉ/TESTÉ, cognition factice** |
| PLANNING (14) | Oui, testé | Gabarit 10 tâches fixe + tâches additives (learnings/decisions) ; Kahn réel | **CODÉ/TESTÉ/RÉCUPÉRABLE** |
| DECISION (15) | Oui, testé | Qualification 5 axes, manifeste `not_executed/not_sovereign/requires_human_validation` | **CODÉ/TESTÉ/RÉCUPÉRABLE** |
| EXECUTION (16) | Oui, testé | 6 garde-fous réels ; délègue au Runtime réel ; **action métier simulée** (`performed=False`) | **CODÉ/TESTÉ, exécution=echo** |

**Constat central** : le cerveau gouverné est **réellement construit et câblé** (chaîne 13→15→16→Runtime vérifiée en
code, validation humaine, révocation, audit). **Mais sa cognition déterministe n'est pas un jugement réel.** La **vraie
réflexion** vit dans l'**identité/prompt** (`cognitive_identity.py`, portée de l'héritage V1) — **confirmé par deux
sources indépendantes** : notre lecture du code 01_CCSC **et** la lecture du code héritage (Lot HC : « déterminisme
intelligent, pas réflexion ; la vraie cognition vit dans le prompt Claude »).

---

## 2. Quatre conceptions distinctes de « BrainAI » (ne pas les confondre)

1. **Socle SCC (00-06) + orchestrateur** : chaîne cognitive **déterministe** (0 LLM, lexicale). E2E réel testé dans
   `scc_orchestrator` **et** `07_RUNTIME/tests/test_integration_demo.py`.
2. **BrainAI « officiel » (ADR)** : **superviseur gouverné** au-dessus du socle, branché par `SupervisorPort` (ADR-0003/
   0007), subordonné à la règle T3 et aux vetos. **Spécifié (18 capacités le visent), pas construit comme produit.**
3. **Chaîne cognitive 11-16** : construite, câblée via gateways, gouvernée — **mais non pilotée par le produit**.
4. **Produit 17 (le réel)** : builder piloté par **Claude Code** (pursue/converse/realize), qui **n'utilise aucun 00-16**
   sur l'arc cognitif ; il **ne raccorde le socle qu'en LIVRAISON J2** (14 Kahn, 16 vocabulaire, 11 mémoire, via `importlib`).

> La divergence #2↔#4 est le fait patrimonial majeur : le « BrainAI » spécifié (superviseur du socle) **n'est pas** le
> « BrainAI » livré (builder Claude Code). Les catalogues 00_SYSTEM n'ont **aucune** référence au vocabulaire produit.

---

## 3. Classification patrimoniale (la réponse directe à la question)

### 3.1 RÉCUPÉRABLE — déjà bâti, à connecter/porter, **jamais à reconstruire**
- **Cerveau gouverné 11-16** : châssis de gouvernance réel + slots LLM interchangeables + validation humaine + audit.
- **Stores mémoire** (11) + **consolidation knowledge** (04) : append-only, révocation, versioning — testés.
- **UI gouvernée complète** (`SCC_BRAINAI_UI`, archivée D2) : transport loopback + ExposurePolicy default-deny + patterns
  AGC 4-temps + tests de conformité → **récupérable intégralement pour Admin/Owner mode**.
- **Fondation universelle** `scc_foundation` (SccObject/contrats/primitives, 0 dépendance) + orchestrateur.
- **Héritage v1 — event-store `journal/`** : fonctions pures `reconstruireChronologie` / `projeterA(instant)` /
  recherche typée + immuabilité **prouvée à la compilation**. **Plus mûr que les stores JSONL actuels.** Idées à récupérer.
- **Identifiants brandés (TS)** et architecture **ports & adapters** hexagonale de v1.

### 3.2 DÉJÀ-RÉCUPÉRÉ (ne pas re-porter)
- **Doctrine cognitive / Pentagone (Comprendre/Structurer/Arbitrer/Orchestrer/Livrer)** : déjà portée dans
  `17/…/cognitive_identity.py`. Décision héritage explicite : « rapatrier l'identité/doctrine, **PAS le code TS** ».
- **`convergence_confirmed`** : descend du « Dialogue de compréhension » (J5/J6 de v1).

### 3.3 CHAÎNON MANQUANT (le vrai travail restant — J4)
- **Learning (12) ↔ Pursuits (17)** : le produit n'écrit qu'une **mémoire de livraison** ; Learning est monté mais **non
  nourri** par l'expérience produit. → **J4-(d)** = nourrir l'expérience Pursuit en mémoire **au format Learning-compatible**.
- **`open_questions`** existe dans `BRIEF_SCHEMA` mais **n'est pas consommé** = chaînon entre le pilier v1 et l'ARC actuel.
- **MOAT #6 — architecture canonique persistante** : fondations posées en v1 (agrégat `Projet` + `Journal` event-sourcé,
  JSON sans lock plateforme) **mais sémantique manquante** (cycle de vie, état inter-tours, identité du flux). = **RS-053**.

### 3.4 CONCEPTUEL NON-BÂTI (pensé/documenté, non codé, non absorbé — vision J4)
- **Moteur Doctrinal BrainAI** : **cycle de vie doctrinal 7 phases** (Détection→Qualification→Validation→Stockage→
  Application→Évaluation→Révision) + modèle 13 champs + résolution de conflits 5 niveaux. = **mécanisme de bootstrap J4**
  (cas isolé → règle durable). **Distinct** des 30 doctrines **statiques** de 00_SYSTEM.
- **CGE** (Cognitive Governance Engine), **ROSE_OS** (grammaire opérationnelle), **SCIL** (langage d'interaction formel,
  PI Seror Créative). Alignés, sans contradiction ; non implémentés.

### 3.5 LEGACY / DOUBLON / REMPLACÉ (acté)
- **05_MEMORY vs 11_BRAINAI_MEMORY** ; **06_REASONING vs 13_BRAINAI_REASONING** : doublons, 17 utilise les 11/13.
- **« 07_RUNTIME » legacy** : remplacé par builder + subprocess in-process pour l'arc produit.
- **brainai-mvp (JS)** : remplacé par v1 (TS testé) puis par le produit 17 ; les **6 Blueprints réels** restent un
  **corpus de référence** (banc d'essai).
- **8 « moteurs cognitifs construits »** (revendiqués KNOWLEDGE-002) → révélés **non producteurs** → remplacés par la
  cognition **louée**. Remplacement historique acté.

---

## 4. Le MOAT (3 composantes indissociables, per J7) — état réel

1. **Architecture canonique persistante (#6)** : fondations v1 posées, sémantique manquante → **RS-053, différé**.
2. **Capitalisation cumulative (mémoire transversale/décision)** : mémoire projet ✓ ; transversale/décision manquantes → **RS-017**.
3. **Arbitrage explicite (Doctrine 14)** : posture présente, **non enforced** (aucun invariant n'exige que tout livrable
   structurant tranche) → **RS-022**.

> **Aucune des trois n'est pleinement incarnée.** Le socle de gouvernance + une verticale de livraison réelle existent ;
> le moat proprement dit reste **différé** — c'est la découverte patrimoniale la plus importante, et elle est **cohérente**
> entre la matrice J3 et la lecture du code héritage.

---

## 5. Contradictions apparentes — toutes tranchées par le code

- **« Boucle Learning rompue » (revue) vs « modules cohérents » (lecture)** → **défaut d'intégration produit**, pas défaut
  de module : 11/12 sont réels ; le produit 17 n'exécute pas le Kernel.
- **« Arbitrage réel » (Lot F) vs « justifications fabriquées sur égalités » (archéologie)** → le code **choisit** toujours
  un gagnant (tri + tie-break), **mais sur une égalité de score il rédige une victoire** ; aucun test ne couvre le cas
  d'égalité. La directive « ne jamais brancher 13 sur la conversation » **tient**.
- **« Pas d'E2E multi-moteur » (Lot B #1) vs « chaîne orchestrée » (Lot B #2)** → l'E2E existe à **deux** endroits
  (`scc_orchestrator` **et** `07_RUNTIME/test_integration_demo.py`) ; les modules du socle sont testés isolément.
- **5 bugs des débriefs d'août** (arbitrage sur égalités, Learning/Memory rompue, ground_facts=False) → **retrouvés
  indépendamment dans le code** par nos lots F/E/G. **Triangulation à 3 sources.**

---

## 6. Confrontation aux 4 axes J4 (RS-060) — anti-dilution

J4 **ne doit pas** être réduit à « réduction/fenêtrage/résumé du contexte ». Le patrimoine confirme les 4 axes :
- **(a) Mémoire épisodique/sémantique** : socle réel (04/11), à **connecter**.
- **(b) Capitalisation cumulative** : composante MOAT #2, différée (RS-017).
- **(c) Gouvernance de l'apprentissage** : **contrainte doctrinale dure** — apprentissage **T1/T2 seulement**, jamais T3
  (ADR-0005 immuable) ; append-only + cite-sources (0006/0016) ; BrainAI conseille, ne gouverne pas.
- **(d) Raccord expérience→mémoire** : **le chaînon manquant** = Learning ↔ Pursuits, au format Learning-compatible ; le
  **Moteur Doctrinal** (cycle de vie 7 phases) en est le patron conceptuel disponible.

---

## 7. Ce qu'on risquerait de reconstruire — et qu'il ne faut PAS

1. Le **cerveau gouverné 11-16** (existe, câblé, testé) — à connecter, pas recréer.
2. Les **stores append-only + révocation + versioning** (04/11) — existent, testés.
3. L'**UI gouvernée** (transport + ExposurePolicy + AGC) — archivée, récupérable pour Owner mode.
4. L'**event-store à fonctions pures** de v1 (reconstruction/projection/immuabilité prouvée) — plus mûr que l'actuel.
5. La **Doctrine cognitive / Pentagone** — déjà portée dans `cognitive_identity.py`.
6. Le **contrat universel / ports & adapters / isolation provider** — déjà incarné (providers/registry + adaptateurs).

**À bâtir réellement (non existant)** : le **raccord Learning↔Pursuits (J4-d)**, le **MOAT canonique migratable (RS-053)**,
la **capitalisation transversale/décision (RS-017)**, l'**enforcement de l'arbitrage explicite (RS-022)**, et — si retenu —
le **Moteur Doctrinal à cycle de vie** comme moteur d'apprentissage gouverné.

---

## 8. Recommandation (sans lancer J4)

Ouvrir J4 par **le chaînon manquant (d)** : nourrir l'expérience Pursuit dans la mémoire au **format Learning-compatible**,
en respectant les contraintes doctrinales dures (T1/T2 only, append-only, cite-sources, BrainAI conseille). **Ne rien
reconstruire** de la chaîne 11-16 ni des stores : les connecter. Traiter le **MOAT canonique (RS-053)** et la **mémoire de
décision (RS-017)** comme jalons distincts, non comme de la réduction de contexte. Le **Moteur Doctrinal** (héritage
conceptuel) est le patron de référence pour la gouvernance de l'apprentissage.

*Fin de rapport. Base : registre de couverture cumulatif (01_CCSC 8 lots + A-bis/A-ter ; 90_HERITAGE HC/HD/HE + matrice J3).
Aucune modification, aucun appel LLM métier, aucun code écrit pendant le scan.*
