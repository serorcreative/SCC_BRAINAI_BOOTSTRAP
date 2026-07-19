# Perception — pilier d'entrée de BrainAI

> Statut : **socle de lecture livré (INPUT-READ-001)**. Aucune acquisition réelle à ce stade.
> Référence d'architecture : INPUT-001 (Entrées BrainAI).

## Positionnement

**Perception** est le pilier fonctionnel par lequel BrainAI reçoit le monde extérieur.
**Input / Entrée** est l'objet technique canonique enregistré par ce pilier.

L'Entrée se place **en amont** des moteurs cognitifs et **latéralement** à la gouvernance :
c'est une *source d'information*, jamais une étape du cycle décisionnel. Le cerveau ne
raisonne **jamais** sur un média — uniquement sur une **Entrée normalisée**. Le média n'est
qu'un mécanisme d'acquisition ; l'Entrée est l'information exploitable.

```
Monde extérieur → [acquisition, à venir] → ENTRÉE (fait normalisé, immuable)
                                              │ lecture (observation)
                                              ▼
                        Moteurs cognitifs  →  Gouvernance INCHANGÉE (decide → validate → execute)
```

## Ce qu'est une Entrée

Une Entrée est un **fait acquis et normalisé** — pas sa signification. Elle :

- est **immuable** ; toute interprétation future est un *enrichissement* séparé (chantier ultérieur),
  jamais une modification de l'Entrée d'origine ;
- **ne décide, ne valide, n'exécute jamais** ; elle ne devient **jamais automatiquement** une
  connaissance ni un apprentissage ;
- conserve une **provenance explicite** ; son contenu normalisé est **indépendant du média** d'origine.

## Modèle canonique minimal

| Champ | Rôle |
|---|---|
| `id` | identifiant stable, **adressé-contenu** (`in_<digest12>`), dérivé du contenu **+ contexte d'acquisition** |
| `modality` | type d'origine (ex. `text`) |
| `content` | contenu **normalisé** (indépendant du média) |
| `provenance` | source explicite (dict non vide) |
| `observed_at` | instant observé, si connu (sinon `null`) |
| `ingested_at` | instant d'ingestion (défaut : `as_of`, déterministe) |
| `as_of` | référentiel temporel de BrainAI |
| `session_id` | référence de session éventuelle |
| `actor` | référence d'acteur éventuelle |
| `context` | métadonnées contextuelles strictement nécessaires (projet, etc.) |
| `integrity.content_digest` | intégrité du contenu (sha256) |
| `fidelity` | fidélité déclarative éventuelle (ex. transcription — non utilisée à ce stade) |

Le modèle reste **extensible par ajouts futurs** sans devenir générique. Aucun champ spéculatif
(pas d'`enrichments` tant que l'enrichissement n'existe pas).

## Stockage

Store **append-only** (`data/inputs.jsonl`) porté par un **collaborateur dédié**
`PerceptionService` — le Bootstrap **orchestre et délègue**. On **ajoute** des Entrées
immuables ; on n'en modifie ni n'en supprime aucune. `record()` est **idempotent par id**
(adressage-contenu).

## Écriture — première acquisition (INPUT-WRITE-001)

Une **unique action** enregistre une Entrée **texte** :

| Opération | Genre | Effet |
|---|---|---|
| `record_input` | `action` | normalise le texte (trim des bords, **sans interprétation ni perte de sens**), crée l'Entrée canonique `modality:"text"`, l'ajoute (append-only, id adressé-contenu, `as_of` figé, provenance conservée). Renvoie `{ok, input_id, input}` ; texte vide / provenance invalide → `{ok:false, error}`. |

Paramètres **strictement nécessaires** : `text` + `provenance`. Le Bootstrap **délègue
entièrement** à `PerceptionService.record_text` ; la Présentation est un simple passthrough.
Un événement `input.recorded` est publié (observabilité). **Aucune** interprétation,
enrichissement, décision ni apprentissage. Une seule modalité : le texte.

## Analyse — première circulation dans le cerveau (INPUT-ANALYZE-001)

Une **action** fait circuler une Entrée existante dans le pipeline cognitif **existant** :

| Opération | Genre | Effet |
|---|---|---|
| `analyze_input` | `action` | récupère l'Entrée (`input_id`), fait délibérer **Reasoning seul** (déterministe, **sans IA/LLM**) sur son contenu, et renvoie un **reflet d'analyse transitoire** `{deliberation_id, provider, as_of, elements, recommendation_status}`. Id inconnu → `{ok:false, error}`. |

Le Bootstrap **orchestre et délègue** (`cognition.reasoning.reason`) ; aucune logique cognitive
dans le Bootstrap. **Aucune** mutation de l'Entrée, aucun enrichissement définitif, aucune
écriture en **Mémoire**, aucun apprentissage, **aucune décision** gouvernée (le moteur Decision
n'est jamais appelé), aucune exécution. La recommandation reste **candidate** ; le résultat
n'est **pas** persisté comme enrichissement de l'Entrée. Événement `input.analyzed` (observabilité).

## Lectures du Contrat (additives, v1.0)

| Opération | Genre | Effet |
|---|---|---|
| `inputs` | `read` | liste **projetée** des Entrées (`{count, items}`) — légère, déterministe |
| `input` | `read` | détail d'une Entrée par identifiant ; id inconnu → reflet `{ok:false, error}` |
| `input_history` | `read` | **histoire événementielle** d'une Entrée (`{input_id, events}`) ; id inconnu → `{ok:false, error}` |

Une **projection minimale** des Entrées est aussi présente dans `overview.inputs`
(`{count, items}`, plafonnée), en lecture seule.

## Cycle de vie = événements (INPUT-HISTORY-001)

L'Entrée **n'a aucun état mutable** et **aucune machine à états** : son cycle de vie **est**
le **journal append-only existant** (approche D+C). `input_history(input_id)` restitue, en
**lecture seule** et dans l'**ordre chronologique déterministe** (`seq`), les événements du
journal reliés à l'Entrée (`payload.input_id == input_id`) — **tels quels** (schéma réel
`seq/topic/actor/timestamp/payload`, réutilisé sans nouveau format). Aucune mutation, aucune
déduplication, aucun label synthétique (`analyzed`/`available`/…). Les analyses répétées
apparaissent comme **plusieurs** `input.analyzed` distincts. Si un état devient un jour
nécessaire, il sera une **projection** calculée depuis cette histoire — jamais un champ porté
par l'Entrée.

**Principe (INPUT-STATE-CORE-001 — résolu par principe).** Une Entrée est un **fait observé
immuable**. Elle ne possède **pas d'état par nature**. Les états appartiennent aux **objets
gouvernés** produits à partir des faits, **jamais aux faits eux-mêmes**.

## Politique d'exposition (Transport)

La politique officielle est **default-deny** et expose **toutes les opérations `read`** du
Contrat ; `inputs` et `input` sont donc autorisées par construction (aucune ouverture
spécifique requise), tandis que toute opération non déclarée reste refusée (403). **Aucun
média binaire** ne traverse le Contrat ni le Transport.

## Hors périmètre (chantiers ultérieurs)

Autres modalités (audio, PDF, image, e-mail, API, flux), transcription / OCR / ASR,
adaptateurs externes, enrichissements cognitifs, cycle de vie gouverné des Entrées,
rendu SPA des Entrées, gouvernance de consentement / rétention / oubli.
