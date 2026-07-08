# BrainAI — Architecture de la première interface (phase « Produit »)

**Statut : direction validée — figée avant implémentation.**
Document d'architecture officiel. Aucune interface n'est encore développée ; ce texte
**fige la direction** que toute implémentation devra suivre. Il ne modifie pas
l'architecture existante du Bootstrap.

---

## 0. Changement de phase : du Bootstrap au Produit

Les BUILD-001 → BUILD-014 constituent les **fondations officielles du cerveau** de BrainAI :
mémoire, cognition, apprentissage, boucle fermée, continuité de session, registre d'agents
orienté capacités, ViewModel (`overview()`) et **couche de présentation** (contrat v1.0).

Le Bootstrap est désormais considéré comme **stable**. Nous quittons la phase « Bootstrap »
et ouvrons la phase « **Produit BrainAI** ». L'objectif n'est plus de développer le cerveau,
mais de construire son **premier visage**.

**Principe fondateur de la nouvelle phase :** l'interface est un **consommateur** du cerveau,
jamais son propriétaire. Elle ne développe aucune logique cognitive. Elle **présente** ce que
le cerveau expose, et **transfère** les actions gouvernées à valider par l'humain.

---

## 1. La règle absolue : `UI → Presentation → Bootstrap`

Le sens de dépendance est **strict, unidirectionnel et non contournable** :

```
UI  ──►  Presentation Layer (contrat)  ──►  Bootstrap (cerveau)
```

- L'UI **ne dépend jamais** du Bootstrap directement.
- L'UI **ne connaît que le contrat** de présentation (opérations + enveloppe + version).
- Le Bootstrap **ne dépend jamais** de la Presentation ni de l'UI.
- La Presentation **ne décide jamais** — elle présente (lectures) et transfère (actions).

Cette règle est **structurellement garantie** : l'UI est en TypeScript/natif et ne peut pas
importer le Python du cerveau. La seule porte d'entrée est le **contrat servi sur un fil**.

Doctrine permanente de BrainAI (6 règles) :

> 1. le registre décrit · 2. le Bootstrap orchestre · 3. les moteurs exécutent ·
> 4. `overview` observe · 5. **l'interface présente — elle n'agit jamais d'elle-même** ·
> 6. **le transport n'expose jamais une implémentation — uniquement un contrat**
>    (vrai quels que soient les transports futurs : HTTP, stdio, gRPC, …) ·
> 7. **le shell Desktop ne porte jamais de logique métier** — il gère uniquement le cycle de
>    vie de l'app (fenêtre, sidecar, intégration OS, lancement, arrêt) ; toute logique reste
>    dans le Bootstrap, la Presentation ou le Contrat.

Les décisions de transport sont figées dans les [ADR](adr/README.md) (ADR-UI-001/002/003/005).

---

## 2. Architecture cible en couches

```
┌─────────────────────────────────────────────────────────────┐
│ SCC_BRAINAI_BOOTSTRAP — le cerveau (Python, pur, sans réseau) │
│   moteurs · registre · overview() · Presentation Layer v1.0   │  contrat déjà bâti
└───────────────▲───────────────────────────────────────────────┘
                │ in-process (import Python)
┌───────────────┴───────────────────────────────────────────────┐
│ Transport Adapter — expose le contrat sur HTTP/JSON            │  1er composant réseau
│   dispatcher générique  POST /v1/{operation} → Presentation    │  loopback par défaut
│                         GET  /v1/contract    → describe()      │
└───────────────▲───────────────────────────────────────────────┘
                │ HTTP/JSON — enveloppes {contract_version, operation, kind, data}
┌───────────────┴───────────────────────────────────────────────┐
│ Client de contrat généré (TypeScript typé)                     │  source unique : describe()
└───────────────▲───────────────────────────────────────────────┘
                │ import TS
┌───────────────┴───────────────────────────────────────────────┐
│ Application UI — un seul codebase web                          │
│   Web (SPA)  ·  Desktop (Tauri + sidecar)  ·  Mobile (Capacitor)│
└─────────────────────────────────────────────────────────────────┘
```

Chaque flèche montante est infranchissable : le cerveau n'est atteint que par l'adaptateur,
l'adaptateur n'expose que le contrat, l'UI ne parle qu'au client généré.

---

## 3. La frontière de transport (HTTP/JSON)

La Presentation Layer est une **API Python en-process**. Pour qu'une interface non-Python la
consomme, on ajoute un **adaptateur de transport** — le **premier composant réseau** de
BrainAI. Le **Bootstrap reste pur** (stdlib, déterministe, sans réseau) ; le réseau vit
**uniquement** dans l'adaptateur.

**Dispatcher générique piloté par le contrat** (aucune route par opération, zéro duplication) :

```
POST /v1/{operation}    body: { …args }   →   Presentation.<operation>(**args)   →   envelope
GET  /v1/contract                          →   describe()  (introspection + version)
```

- L'adaptateur **valide** `operation` contre `OPERATIONS`, respecte le genre `read`/`action`,
  appelle la méthode du `Presentation` et renvoie l'enveloppe **verbatim**.
- Le contrat demeure l'**unique source** ; le transport ne fait que le véhiculer.
- **Liaison locale (127.0.0.1) par défaut** : aucune surface réseau exposée tant que l'ADR
  d'accès distant n'est pas tranché.

---

## 4. Le contrat unique (mécanisme anti-dérive)

- **Source unique** : `describe()` (Python) → `contract_version` + opérations + genres.
- **Codegen** : un script transforme `describe()` en **types + client TypeScript** ; le client
  embarque `CONTRACT_VERSION`.
- **Garde-fou runtime** : chaque réponse porte `contract_version` ; le client **refuse** un
  contrat incompatible.
- **Enveloppe stable** : `{contract_version, operation, kind, generated_as_of, data}` où `data`
  réutilise telle quelle la sortie du Bootstrap.

Résultat : **une seule définition du contrat**, dérivée mécaniquement côté UI. Deux contrats
divergents deviennent impossibles.

---

## 5. Choix de framework

Objectif : **Web + Desktop + Mobile depuis un seul codebase UI**, durable et recrutable.

| Couche | Choix | Justification |
|--------|-------|---------------|
| **Frontend** | **Vite + React + TypeScript** (SPA) | écosystème le plus pérenne, portable vers Desktop/Mobile ; pas de SSR nécessaire (tableau de bord). |
| **État serveur** | **TanStack Query** | tout est lecture/action sur le contrat ; cache/refetch/invalidation ; `overview()` = requête pivot. |
| **Design** | **design system maison** (tokens + primitives) | partagé multi-shell ; longévité supérieure à une lib UI éphémère. |

Alternatives écartées : Next.js (SSR inutile), Electron (lourd), React Native comme socle
principal (2ᵉ codebase). Svelte/Solid valables mais React maximise la pérennité et le
recrutement — critère « plusieurs années ».

### 5.1 Cible Desktop — Tauri

- **Tauri** (et non Electron) : binaire léger, sécurisé, réutilise **le même** frontend web.
- Le cerveau tourne en **sidecar** : Tauri lance le processus Python (Bootstrap + adaptateur)
  en local, sur un port **loopback** (ou stdio). Expérience **local-first**, sans serveur distant.
- Un seul frontend sert à la fois le Web et le Desktop.

### 5.2 Cible Mobile — Capacitor (ultérieure)

- **Capacitor** emballe **exactement** la SPA web en application mobile — **aucun second codebase**.
- Le mobile parle au contrat via HTTP/JSON (transport distant authentifié → dépend de l'ADR réseau).
- Étape volontairement **différée** : elle vient après la stabilisation Web + Desktop.

---

## 6. Architecture de composants de l'UI

L'**architecture informationnelle est déjà donnée par `overview()`** : l'écran d'accueil est le
tableau de bord `overview` (ses 9 panneaux). Organisation en couches, dirigée par le contrat :

```
transport/      client généré (typé) depuis le contrat — seule porte vers le cerveau
domain/         types du contrat (générés) : Envelope, Overview, Agent, Decision, …
state/          hooks TanStack Query : useOverview(), useAgents(), useResolve(), …
panels/         un composant par section overview :
                State · Session · Agents · Capabilities · OpenDecisions ·
                Learnings · Journal · Diagnostics · NextAction
commands/       actions du contrat (run, decide, plan, validate…) : formulaires + confirmations
design-system/  tokens & primitives (partagé Web/Desktop/Mobile)
shells/         web/ (Vite)   ·   desktop/ (Tauri)   ·   mobile/ (Capacitor)
```

Miroir de la doctrine : les **panneaux présentent** (`read`), les **commandes transfèrent** une
action gouvernée. L'UI affiche la « prochaine action recommandée » d'`overview` mais **laisse
toujours l'humain valider** — elle n'agit jamais d'elle-même.

---

## 7. Stratégie Git progressive

**Décision : ne pas mettre l'UI dans le Bootstrap.** Le cerveau est Python pur, déterministe,
stdlib-only ; y injecter `node_modules`, Vite, Tauri/Rust, un second langage et un autre CI
**diluerait la pureté** protégée depuis 14 BUILD.

**Topologie cible — trois dépôts, sens de dépendance strict :**

```
SCC_BRAINAI_BOOTSTRAP      cerveau pur (Python)                              — inchangé
SCC_BRAINAI_PRESENTATION   contrat (extrait de presentation/) + transport    — Python
SCC_BRAINAI_UI             web/desktop/mobile (TypeScript) → client généré   — TypeScript
```

`PRESENTATION` importe `BOOTSTRAP` ; `UI` ne dépend que du **contrat** (HTTP/JSON + client
généré), jamais du Python du cerveau.

**Topologie transitoire — décision ADR-UI-005 (extraction différée, guidée par l'usage) :**

L'extraction est **différée** jusqu'à ce qu'une interface réelle ait éprouvé le contrat. D'ici
là, le contrat reste dans le Bootstrap, et le **transport vit côté produit** (dépôt UI) — jamais
dans le cerveau :

```
SCC_BRAINAI_BOOTSTRAP   cerveau + presentation/ (contrat, pur, sans réseau)   — inchangé
        ▲ import sys.path (API publique seule)
SCC_BRAINAI_UI          transport HTTP/JSON (Python, thin) + frontend (TS)     — dépôt produit
```

**Approche progressive (séparation d'abord architecturale, physique ensuite) :**

- **Étape 0** — *(ce document + ADR)* figer la direction et les décisions de transport.
- **Étape 1** — créer `SCC_BRAINAI_UI` ; y ajouter le **transport** (loopback HTTP/JSON, stdlib)
  important `presentation/` du Bootstrap via `sys.path` ; **client généré** + **SPA Web de
  référence** (accueil = dashboard `overview`). *`presentation/` reste dans le Bootstrap.*
- **Étape 2** — **Desktop Tauri** : même frontend + sidecar Python.
- **Étape 3** — **Mobile Capacitor** : emballage de la SPA.
- **Étape 4 (quand un critère d'extraction est atteint)** — extraire `presentation/` (+ CLI +
  transport) vers `SCC_BRAINAI_PRESENTATION` ; convergence vers la topologie cible à 3 dépôts.

Chaque étape est livrable et testable indépendamment ; **aucune ne touche le cerveau**.

> Aucun dépôt n'est créé à ce stade. La création de dépôts et l'extraction feront l'objet de
> chantiers dédiés, validés séparément.

---

## 8. Extraction future de `SCC_BRAINAI_PRESENTATION`

La couche `presentation/` vit aujourd'hui **dans le Bootstrap** (couture d'extraction propre :
elle ne dépend que de l'API publique du Bootstrap + stdlib). Par décision **ADR-UI-005**,
l'extraction est **différée et guidée par l'usage** : on la justifiera par les besoins réels
d'une première interface, pas par anticipation.

**Plan d'extraction (chantier dédié futur, quand un critère est atteint) :**

1. Déplacer `src/scc_brainai_bootstrap/presentation/` (+ `cli.py` + transport) → `SCC_BRAINAI_PRESENTATION`.
2. `PRESENTATION` charge le Bootstrap comme composant sibling (`sys.path`), via son **API publique uniquement**.
3. Conserver `CONTRACT_VERSION` comme frontière de compatibilité ; le déplacement **n'est pas**
   une rupture de contrat (mêmes opérations, même enveloppe).

**Critère d'extraction (l'un suffit)** : contrat éprouvé par ≥ 1 interface réelle ; 2ᵉ consommateur ;
besoin de versionnement indépendant. Tant que l'extraction n'est pas faite, la séparation reste
**architecturale** avant d'être **physique** (cf. [ADR-UI-005](adr/ADR-UI-005-extraction-presentation.md)).

---

## 9. Décisions d'architecture — ADR

Décisions figées et sujets ouverts. Détail : [`docs/adr/`](adr/README.md).

| ADR | Sujet | Statut / décision |
|-----|-------|-------------------|
| [**ADR-UI-001**](adr/ADR-UI-001-reseau-loopback.md) | Réseau / loopback | ✅ **Accepté** — loopback `127.0.0.1` + port éphémère + jeton ; jamais `0.0.0.0` |
| [**ADR-UI-002**](adr/ADR-UI-002-protocole-transport.md) | Protocole de transport | ✅ **Accepté** — HTTP/JSON canonique, `POST /v1/{operation}` |
| [**ADR-UI-003**](adr/ADR-UI-003-dependances-transport-python.md) | Dépendances transport | ✅ **Accepté** — stdlib `http.server` d'abord ; migration ASGI sur besoin objectif |
| [**ADR-UI-005**](adr/ADR-UI-005-extraction-presentation.md) | Extraction Presentation | ✅ **Accepté** — **différée**, guidée par l'usage ; transport côté produit d'ici là |
| [**ADR-UI-007**](adr/ADR-UI-007-desktop-tauri.md) | Cible Desktop (Tauri) | ✅ **Accepté** — shell local d'abord ; sidecar via env ; fetch = plugin HTTP Tauri ; distribuable différé |
| [**ADR-UI-008**](adr/ADR-UI-008-mobile-capacitor.md) | Cible Mobile (Capacitor) | ✅ **Conteneur accepté · impl. différée** — bloqué par le réseau (loopback impossible sur mobile), conditionné à ADR-UI-004 |
| [**ADR-UI-004**](adr/ADR-UI-004-acces-reseau-securise.md) | Accès réseau sécurisé | ✅ **Architecture acceptée · impl. différée** — mode réseau opt-in (LAN TLS+pairing / overlay chiffré) ; exposition publique rejetée par défaut ; débloque distant **et** mobile |
| [**ADR-UI-009**](adr/ADR-UI-009-etat-cache-offline.md) | État, cache & offline | ✅ **Architecture acceptée · impl. différée** — l'UI reflète (jamais ne possède) ; cache non autoritatif ; offline = instantané lecture seule ; aucune techno de persistance choisie |
| [**ADR-UI-011**](adr/ADR-UI-011-actions-distantes-gouvernees.md) | Actions à distance gouvernées | ✅ **Cadre accepté · impl. différée** — l'UI *demande*, le cerveau *gouverne* ; 6 étapes (affichage/intention/demande/validation/exécution/résultat) ; remote actions désactivées (prérequis ADR-004) ; idempotence + audit exigés |

---

## 10. Invariants de la phase Produit (à ne jamais violer)

1. `UI → Transport → Presentation → Bootstrap` — unidirectionnel, jamais court-circuité.
2. Le Bootstrap reste **pur** : aucune dépendance UI/réseau ne remonte dans le cerveau.
3. **Un seul contrat**, dérivé mécaniquement de `describe()` ; versionné (`CONTRACT_VERSION`).
4. L'UI **présente et transfère** ; elle **ne décide jamais** ; l'humain valide les actions gouvernées.
5. **Le transport n'expose jamais une implémentation — uniquement un contrat** (Doctrine n°6) :
   liste blanche des opérations, aucun accès à Bootstrap/Registry/Adapters/Engines. Vrai pour
   tout transport futur (HTTP, stdio, gRPC…).
6. Un codebase UI unique → trois shells (Web / Desktop / Mobile).
7. Chaque évolution passe par un **ADR** lorsqu'elle touche réseau, sécurité, transport ou packaging.

---

*Fin du document. Rien n'est implémenté à ce stade : la direction est figée, prête pour des
chantiers d'implémentation validés un par un.*
