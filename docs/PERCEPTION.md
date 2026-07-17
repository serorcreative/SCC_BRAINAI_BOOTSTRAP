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

## Lectures du Contrat (additives, v1.0)

| Opération | Genre | Effet |
|---|---|---|
| `inputs` | `read` | liste **projetée** des Entrées (`{count, items}`) — légère, déterministe |
| `input` | `read` | détail d'une Entrée par identifiant ; id inconnu → reflet `{ok:false, error}` |

Une **projection minimale** des Entrées est aussi présente dans `overview.inputs`
(`{count, items}`, plafonnée), en lecture seule.

## Politique d'exposition (Transport)

La politique officielle est **default-deny** et expose **toutes les opérations `read`** du
Contrat ; `inputs` et `input` sont donc autorisées par construction (aucune ouverture
spécifique requise), tandis que toute opération non déclarée reste refusée (403). **Aucun
média binaire** ne traverse le Contrat ni le Transport.

## Hors périmètre (chantiers ultérieurs)

Autres modalités (audio, PDF, image, e-mail, API, flux), transcription / OCR / ASR,
adaptateurs externes, enrichissements cognitifs, cycle de vie gouverné des Entrées,
rendu SPA des Entrées, gouvernance de consentement / rétention / oubli.
