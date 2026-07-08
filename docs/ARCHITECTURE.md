# Architecture du bootstrap BrainAI

## 1. Rôle

Le bootstrap (`17`) est **le point d'entrée exécutable** de BrainAI : il **démarre**
l'ensemble en câblant les composants existants via leurs interfaces publiques. Il
n'ajoute aucune logique cognitive ; il **initialise et déclare prêt**.

```
   scc-brainai start
        │
   ▶ BrainAIBootstrap.run()
        │  1 config → 2 Control Plane → 3 Patrimony → 4 Memory
        │  → 5 Knowledge → 6 Event Bus → 7 Agents → 8 READY
        ▼
   « BrainAI READY »   (+ rapport structuré + événements de cycle de vie)
```

## 2. Réutilisation, jamais duplication

| Étape | Composant réutilisé | Interface publique |
|-------|---------------------|--------------------|
| Control Plane | `09_CONTROL_PLANE` | `ControlPlane().health()` |
| Memory | `11_BRAINAI_MEMORY` | `BrainMemoryStore` |
| Knowledge | `04_KNOWLEDGE` | `KnowledgeEngine` |
| Agents | `00_SYSTEM/agents` | fiches de catalogue (lecture) |

Chaque composant est localisé dynamiquement (ajout de son `src/` à `sys.path`) et
**jamais modifié**. Deux sous-systèmes sont **neufs** ici : le **Patrimony Manager**
et l'**Event Bus**.

## 3. Composants

```
core/        config (as_of, premiers agents) · errors · clock (digest)
event_bus    EventBus (publish/subscribe, append-only, déterministe)
subscribers  EventRecorder (journal JSONL) · LifecycleWatcher (alertes)
patrimony    PatrimonyManager (inventaire du patrimoine, lecture seule)
components   adaptateurs Control Plane / Memory / Knowledge / Kernel (bootstrap dynamique)
cognition    CognitiveStack (Reasoning / Planning / Decision / Execution câblés ;
             moteur Learning partagé injecté → boucle apprenante fermée)
learning     LearningLayer (Learning branché sur la mémoire vivante → propositions)
session      SessionStore (manifeste persistant : identité, démarrages, totaux d'activité)
registry/    Registre d'agents déclaratif & orienté capacités :
               descriptor (données pures) · capability (slugs domaine.action) ·
               sources (manifests JSON + adaptation des fiches + mapping capacités) ·
               registry (index, gouvernance) · adapter (liaison paresseuse + CapabilityResolver)
               mappings/scc-capabilities.json : capacités des fiches SCC (déclaratif, V1, non figé)
router       routage lexical déterministe (décision → decide ; sinon → Kernel)
doctor       Doctor (diagnostic : patrimoine, disponibilité, santé, audits)
presentation/ Couche de présentation : frontière unique cerveau ↔ interfaces
               contract (version, opérations, enveloppe) · presenter (façade sans logique)
bootstrap    BrainAIBootstrap (8 étapes · run_query · decide/plan/validate/execute · learn ·
             agents_catalog/capability_index/resolve_capability · overview · doctor · session)
cli          scc-brainai — 1ʳᵉ interface, passe exclusivement par la Presentation Layer
             (start / run / decide / plan / validate / execute / learn / learnings / learn-validate /
             agents / capabilities / resolve / overview / doctor / events / session / status / contract)
```

## 4. Invariants tenus

| Invariant | Comment |
|-----------|---------|
| Aucun composant modifié | initialisation via interfaces publiques seules |
| Fonctionne même partiellement | mode dégradé si un composant manque |
| Aucun réseau / dépendance externe | stdlib pur |
| Déterminisme | `as_of` figé + séquences + composants déterministes (prouvé cross-process) |
| Traçabilité | chaque étape publie un événement sur l'Event Bus |
| Découplage agents | `Bootstrap → Registry → Adapter → Agent` ; aucun import direct des moteurs |
| Frontière interfaces | `Bootstrap → Presentation → interfaces` ; Presentation dépend du Bootstrap, jamais l'inverse |
| Extensibilité | ajouter un agent = ajouter une description (manifeste), sans toucher le Bootstrap |

## 5. Prochaines incréments (backlog)

- Cataloguer les 16 autres fiches SCC (étendre FicheSource au-delà des pivots) + leurs capacités.
- Figer la taxonomie des capacités (V1 → stable) une fois la gouvernance SCC prononcée.
- Métadonnées d'orchestration réelles (coût, latence, fiabilité) pour un routage multi-fournisseurs.
- Première interface réelle branchée sur la Presentation Layer (voir `docs/ARCHITECTURE_SNAPSHOT_v0.12.0.md`).
- Extraction de `presentation/` vers `SCC_BRAINAI_PRESENTATION` une fois le contrat éprouvé (≥ 1 interface réelle / 2ᵉ consommateur).
- Exposer un mode « live » réseau (démon/service) une fois l'API réseau décidée (ADR).
