# BrainAI Bootstrap — Architecture Snapshot v0.12.0

**Photographie officielle des fondations.** Ce document fige l'état de l'architecture du
Bootstrap BrainAI à l'issue des BUILD fondateurs 001 → 012, avant l'ouverture progressive
vers l'interface utilisateur. Il sert de référence stable.

> BUILD-013 ajoute l'agrégateur lecture seule `overview` (point d'entrée du futur UI) et
> ce document. Le socle décrit ici (v0.12.0) reste inchangé ; l'ajout est non structurant
> (version → v0.13.0).

---

## 1. Ce que BrainAI sait faire aujourd'hui

- **Démarrer** de façon déterministe (8 étapes) et en **mode dégradé** si un composant manque.
- **Traiter une demande** de bout en bout via un **point d'entrée unique** `run` qui **route
  automatiquement** : demande décisionnelle → boucle `decide` ; sinon → Kernel + mémorisation.
- **Délibérer et décider** sous gouvernance : `Reasoning → Decision → [validation humaine] →
  Execution → Runtime`, avec garde-fous (aucune exécution sans décision validée ni acteur autorisé).
- **Apprendre de son vécu** : `Memory → Learning` (signaux, patterns, leçons, recommandations,
  hypothèses), le tout **propositionnel** et soumis à validation humaine.
- **Refermer la boucle** : les apprentissages **validés** nourrissent Planning (recommandations
  → tâches) et Decision (traçabilité).
- **Se souvenir entre invocations** : continuité de **session** persistante (identité, démarrages,
  totaux d'activité).
- **Se connaître** : **registre d'agents** déclaratif orienté **capacités** (`domaine.action`),
  index capacité → fournisseur(s), résolution à liaison paresseuse.
- **Se diagnostiquer** : `doctor` (patrimoine, disponibilité, santé, audits) et `overview`
  (instantané agrégé lecture seule).

---

## 2. Les BUILD fondateurs (001 → 012)

| BUILD | Version | Apport |
|------|---------|--------|
| 001 | 0.1.0 | Premier bootstrap exécutable : config, Control Plane, Patrimony, Memory, Knowledge, Event Bus, premiers Agents, « BrainAI READY ». |
| 002 | 0.2.0 | Première boucle cognitive `run` : bootstrap → Kernel (10) → Memory (11). |
| 003 | 0.3.0 | Event Bus **vivant** : abonnés d'observabilité (EventRecorder, LifecycleWatcher). |
| 004 | 0.4.0 | Grande boucle cognitive gouvernée : Reasoning → Decision → [humain] → Execution → Runtime. |
| 005 | 0.5.0 | Ingestion des **traces d'exécution** dans Memory (boucle vécu → mémoire sur l'exécution). |
| 006 | 0.6.0 | `doctor` : diagnostic complet en une passe (patrimoine, disponibilité, santé, audits). |
| 007 | 0.7.0 | `run` **intelligent** : routage auto décisionnel → `decide`, sinon → Kernel. |
| 008 | 0.8.0 | **Chaîne apprenante** : Memory → Learning (12), apprentissages propositionnels gouvernés. |
| 009 | 0.9.0 | **Boucle fermée** : apprentissages validés → Planning / Decision (`plan`). |
| 010 | 0.10.0 | **Continuité de session** (mode « live ») : manifeste persistant, compteurs d'activité. |
| 011 | 0.11.0 | **Registre d'agents** déclaratif orienté capacités (descripteur, sources, adaptateurs, resolver). |
| 012 | 0.12.0 | **Mapping capacités** des fiches SCC : `agent_id → domaine.action`, déclaratif, V1 non figé. |

---

## 3. Doctrine permanente

Quatre règles gouvernent BrainAI et **s'appliquent à tous les BUILD futurs** :

1. **Le registre décrit** les agents (métadonnées, capacités) — jamais leur logique.
2. **Le Bootstrap orchestre** — il route, coordonne, agrège ; il ne porte pas de logique métier.
3. **Les moteurs exécutent** — la logique vit dans les moteurs, atteints via adaptateurs.
4. **Les capacités sont des données gouvernées, pas du code** — mapping explicite, aucune
   inférence, taxonomie **V1 évolutive** tant que la gouvernance SCC ne l'a pas figée.

Le chemin d'accès à un agent est toujours : **`Bootstrap → Registry → Adapter → Agent`**.
Jamais d'import direct d'un moteur par le Bootstrap ou le registre.

---

## 4. Invariants d'architecture

| Invariant | Garantie |
|-----------|----------|
| **Déterminisme** | `as_of` figé, ids dérivés du contenu, itérations triées, aucune horloge murale ; prouvé cross-process. |
| **Aucun réseau / dépendance externe** | stdlib pur ; aucun appel réseau, aucun daemon. |
| **Aucun composant modifié** | réutilisation via interfaces publiques seules. |
| **Mode dégradé** | un composant absent n'arrête pas le démarrage. |
| **Découplage agents** | `Bootstrap → Registry → Adapter → Agent` ; aucun import direct des moteurs. |
| **Extensibilité** | ajouter un agent = ajouter une description (manifeste) ; ajouter une capacité = éditer une donnée. |
| **Gouvernance** | décisions/plans/apprentissages restent des **propositions** jusqu'à validation humaine. |
| **Traçabilité** | chaque étape publie un événement sur l'Event Bus (journal append-only). |

---

## 5. Flux principaux

| Flux | Commande | Chaîne de données (résumé) |
|------|----------|----------------------------|
| **start** | `scc-brainai start` | 8 étapes → événements bus → session `record_boot` → « BrainAI READY ». |
| **run** | `scc-brainai run "<q>"` | routeur lexical → `decide` (décisionnel) **ou** Kernel + mémorisation. |
| **session** | `scc-brainai session` | lecture du manifeste persistant (identité, démarrages, totaux). |
| **agents** | `scc-brainai agents` | catalogue déclaratif (manifests BrainAI + fiches SCC), filtrable. |
| **capabilities** | `scc-brainai capabilities` | index `capacité → fournisseur(s)` (many-to-many). |
| **resolve** | `scc-brainai resolve <cap>` | capacité → fournisseur retenu (politique déterministe + liaison paresseuse). |
| **learning** | `scc-brainai learn` | Memory → Learning : apprentissages proposés. |
| **validation** | `scc-brainai learn-validate <id> --by <acteur>` | validation humaine d'un apprentissage. |
| **cognition** | `scc-brainai decide` / `plan` / `validate` / `execute` | délibérer → décider → [humain] → exécuter, apprentissages validés réinjectés. |
| **overview** | `scc-brainai overview` | agrégat **lecture seule** de tout ce qui précède (voir §7). |
| **doctor** | `scc-brainai doctor` | diagnostic complet (patrimoine, disponibilité, santé, audits). |
| **events** | `scc-brainai events` | journal d'observabilité (Event Bus). |

---

## 6. Limites actuelles

- **Agents SCC non exécutables** : les 4 pivots sont *décrits* et entrent dans l'index de
  capacités, mais n'ont pas d'adaptateur/moteur → `available: false` (routables, non exécutables).
- **Taxonomie de capacités V1** : non figée ; les slugs ne sont pas des identifiants métier immuables.
- **16 fiches SCC** encore non cataloguées (seuls les 4 pivots le sont).
- **Aucun mode réseau, aucun daemon** : exécution one-shot par invocation (la continuité passe
  par l'état persistant, pas par un service résident).
- **Knowledge minimal** : suffisant pour démarrer, pas encore exploité en profondeur.
- **Providers IA externes** (Claude/ChatGPT/Gemini) : emplacements prévus dans les schémas mais
  indisponibles (aucun réseau) ; la cognition reste **déterministe** sans IA externe.

---

## 7. Préparation interface

Le futur UI de BrainAI s'appuiera en priorité sur l'agrégateur **lecture seule** `overview`
(`bootstrap.overview()` / `scc-brainai overview`). Neuf panneaux prioritaires, chacun alimenté
par une lecture **déjà existante** :

| Panneau | Contenu | Source de données |
|---------|---------|-------------------|
| **État BrainAI** | verdict, bannière, patrimoine, disponibilité | `overview.state` (← `doctor` en lecture) |
| **Session active** | identité, n° de démarrage, totaux d'activité | `overview.session` (← `session_summary`) |
| **Agents disponibles** | comptes, namespaces | `overview.agents` (← `agents_catalog`) |
| **Capacités** | index capacité → fournisseur(s) | `overview.capabilities` (← `capability_index`) |
| **Décisions ouvertes** | décisions proposées en attente | `overview.open_decisions` (← `decision.search("proposed")`) |
| **Apprentissages** | proposés / validés (comptes + aperçu) | `overview.learnings` (← `learnings`) |
| **Journal d'événements** | N derniers événements | `overview.recent_events` (← journal Event Bus) |
| **Diagnostics** | verdict + problèmes | `overview.diagnostics` (← `doctor`) |
| **Prochaine action recommandée** | 1 suggestion déterministe | `overview.recommended_next_action` |

**Règle « prochaine action recommandée »** (déterministe, documentée ; l'overview *suggère*,
il ne décide **jamais** à la place des moteurs). Première règle vraie :

1. pile dégradée → `doctor` ;
2. décision(s) ouverte(s) → `validate` ;
3. apprentissage(s) proposé(s) → `learnings --status proposed` ;
4. aucune session → `start` ;
5. sinon → `run "…"`.

### Mock textuel du tableau de bord

```
┌─ BrainAI OVERVIEW ────────────────────────────────────
│ état       : BrainAI HEALTHY  (21/21 composants)
│ session    : ses_f868104ff8de · démarrage n°4
│ agents     : 9  ·  capacités : 21  ·  namespaces : brainai, scc
│ décisions  : 1 ouverte(s) (ex. dec_40cf2cb35f32)
│ apprentis. : 22 proposé(s) · 2 validé(s)
│ diagnostic : healthy
│ événements : 10 récents au journal
├─ prochaine action recommandée ───────────────────────
│ → valider une décision (1 décision en attente de validation)
│   scc-brainai validate dec_40cf2cb35f32 --by <acteur>
└──────────────────────────────────────────────────────
```

**Contrat de l'overview** : lecture seule stricte — n'écrit aucun enregistrement, ne persiste
aucun événement, n'ouvre/n'incrémente aucune session, ne démarre pas BrainAI, ne décide rien.
Il **compose** des vues existantes ; ce n'est **jamais** un moteur de workflow.

---

## 8. Prochains chantiers possibles

- Cataloguer les 16 autres fiches SCC (étendre `FicheSource`) + leurs capacités.
- Figer la taxonomie des capacités (V1 → stable) une fois la gouvernance SCC prononcée.
- Métadonnées d'orchestration réelles (coût, latence, fiabilité) pour un routage multi-fournisseurs.
- Première interface réelle (web/desktop) branchée sur `overview`.
- Mode « live » réseau (démon/service) — **décision d'architecture (ADR) requise** avant tout code.
