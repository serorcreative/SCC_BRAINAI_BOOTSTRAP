# ADR-UI-006 — Stratégie de génération du client TypeScript

- **Statut :** ✅ Accepté (2026-07-08)
- **Phase :** Produit BrainAI — première interface, Étape 1 (client)
- **Principe cadre :** le **Contrat** est la source de vérité (cf. [ADR-UI-010](ADR-UI-010-contrat-axe-architectural.md)).

## Contexte

`describe()` formalise aujourd'hui les **noms d'opérations**, leur **genre** (read/action) et
l'**enveloppe** — **pas les schémas de `data`** (charges utiles, encore des dicts Python).
Or `data` va **évoluer** à mesure que la première UI exerce le contrat. Figer `data` trop tôt
contredirait l'esprit d'ADR-UI-005 (« guidé par l'usage »). Le client TS doit refléter le
contrat sans le figer prématurément ni dériver de lui.

## Décision

**Approche hybride, convergeant vers le codegen `describe()`.**

1. **Itération 1 — client manuel strict, en forme de code généré** : type `Envelope<T>`,
   constante `CONTRACT_VERSION` (miroir du Python), **garde runtime** rejetant un
   `contract_version` incompatible, et un **test de conformité** qui récupère
   `GET /v1/contract` et **assert que le client couvre exactement les opérations de
   `describe()`**. Typage `data` **seulement** pour les opérations réellement affichées
   (`overview` d'abord), `unknown` ailleurs.
2. **Itération 2 — codegen `describe()`** : remplacer la couche « opérations » du client par
   une génération depuis `describe()`, une fois la surface d'opérations + l'enveloppe éprouvées.
3. **Plus tard — OpenAPI en EXPORT uniquement** : OpenAPI, s'il apparaît, sera une
   **projection générée du Contrat**, pour l'interopérabilité et le typage `data` bout-en-bout.
   **Jamais la source de vérité** — la source reste le Contrat BrainAI (`describe()`).

## Options considérées

| Option | Verdict |
|--------|---------|
| 1. Codegen maison depuis `describe()` | Cible structurelle (Itération 2) ; laisse `data` ouvert |
| 2. OpenAPI comme source | **Rejetée comme source** — prématuré, pression sur un contrat non stabilisé, tension ADR-003 ; **retenu comme export futur** |
| 3. Client manuel libre | Rejeté comme référence — risque de **dérive** (double définition) |
| **4. Hybride : manuel strict → codegen** | **Retenue** — démarrage sans outillage, apprentissage des formes `data` par l'usage |

## Conséquences

**Positives.** Démarrage rapide, aligné éthos ; le **test de conformité vs `describe()`**
donne l'enforcement « source unique » **sans** codegen (neutralise la dérive) ; garde de version
dès J1 ; le client manuel est structuré pour que le codegen s'y substitue sans rupture.
**Négatives / risques.** Fenêtre de dérive temporaire (mitigée par le test de conformité) ;
`data` partiellement typé au départ ; discipline requise pour ne pas laisser le manuel s'éterniser.

## Impact

- **Stabilité du contrat** : pression faible ; `data` se stabilise par l'usage réel.
- **Transport** : minimal — sert déjà `GET /v1/contract`.
- **Extraction `SCC_BRAINAI_PRESENTATION`** : excellente — l'entrée du codegen (`describe()`)
  voyage avec le Contrat ; le client migrera avec lui le moment venu.

## Débloque / bloque

- **Débloque :** client TS de l'itération 1, SPA de référence.
- **Reste ouvert :** typage `data` bout-en-bout (codegen enrichi / OpenAPI export) — plus tard.
