# ADR-UI-010 — Le Contrat comme axe architectural explicite

- **Statut :** ✅ Accepté (2026-07-08) — **modèle conceptuel adopté ; réalisation physique différée**
- **Phase :** Produit BrainAI — fondation conceptuelle de la frontière
- **Principe cadre :** Doctrine n°6 — *le transport n'expose jamais une implémentation, uniquement un contrat.*

## Contexte

La frontière cerveau ↔ visages était pensée comme une chaîne linéaire
`Presentation → Transport → Client`. À l'usage, le **Contrat** n'est pas un maillon *en aval*
de Presentation : c'est l'**axe** que tout référence. Le rendre explicite clarifie les
responsabilités, affûte Doctrine n°6 et prépare une extraction nette — sans imposer de refactor
prématuré.

## Décision

**Le Contrat est un axe architectural explicite et la source de vérité.**

```
                 ┌───────────── Contrat (spec) ─────────────┐
                 │ opérations · genres · enveloppe · version │  ← SOURCE DE VÉRITÉ
                 │ describe() = sa sérialisation             │
                 └───────────────────────────────────────────┘
                    ▲ implémente     ▲ sert          ▲ reflète        ▲ consomme
              Presentation        Transport         Client            UI
             (sur Bootstrap)   (HTTP/stdio/gRPC)   (TS)          (SPA/Desktop/Mobile)
```

- **Le Contrat est la source de vérité.**
- **Presentation implémente** le Contrat (façade sur le Bootstrap).
- **Le Transport sert** le Contrat (porteur interchangeable : HTTP, stdio, gRPC…).
- **Le Client reflète** le Contrat (miroir typé généré/conforme).
- **L'UI consomme** le Contrat.
- **OpenAPI, s'il apparaît, n'est qu'un export** du Contrat — jamais la source (cf. ADR-UI-006).

### Adoption conceptuelle maintenant, réalisation physique différée

- **Maintenant (par discipline, sans code)** : `contract.py` (`OPERATIONS`, enveloppe,
  `describe`) **est** la couche Contrat, en germe. Le futur transport dispatchera **sur la spec
  du Contrat** (liste blanche `OPERATIONS`) avec une `Presentation` **injectée** — jamais un
  accès à l'implémentation (Bootstrap/Registry/Adapters/Engines).
- **Plus tard (à l'extraction)** : le Contrat pourra devenir un **artefact autonome neutre**
  (spec + `describe` + enveloppe + version), distinct du presenter, du transport et du client —
  au **même moment** que l'extraction de `SCC_BRAINAI_PRESENTATION` (ADR-UI-005).
- **Aucune modification du Bootstrap** n'est faite par cet ADR : l'axe est adopté comme **modèle
  de référence**, pas comme refactor.

## Avantages

- Source unique = artefact réel (`describe()`) → codegen, tests de conformité, export OpenAPI.
- **Doctrine n°6 devient structurelle** : le transport transporte un contrat, il n'« expose »
  jamais une implémentation.
- Transport **interchangeable** sans toucher le Contrat.
- Client **découplé** du transport et du presenter.
- **Testabilité** : transport testable avec une implémentation *mock* du Contrat, sans le cerveau.
- **Extraction nette** : coutures évidentes le jour venu.

## Inconvénients / risques

- Indirection conceptuelle supplémentaire → maîtrisée en **différant** toute matérialisation.
- Risque de formalisme prématuré si on figeait un artefact avant stabilisation → **écarté** par
  la réalisation différée.
- Les schémas `data` restent à formaliser plus tard : l'axe **donne un foyer** à ce typage sans
  le résoudre d'un coup.

## Conséquences architecturales

- **Modèle de référence** : `UI → Client → Transport → Contrat ← Presentation → Bootstrap`
  (le Contrat est l'axe ; le sens de dépendance *physique* reste `UI → Transport → Presentation
  → Bootstrap`).
- Le transport se cale sur la **spec** ; Presentation reste l'**implémentation** injectée.
- Le Contrat, transport et client sont des **préoccupations de contrat** (à terme côté
  `SCC_BRAINAI_PRESENTATION`), distinctes du **produit UI**.

## Position sur l'organisation des dépôts (pragmatisme assumé)

**Les concepts précèdent les dépôts.** On **n'anticipe pas** de séparation interne complexe du
futur `SCC_BRAINAI_UI` (pas de découpage « invité contrat / produit » imposé d'avance). Les
frontières internes et les dépôts **suivront naturellement** lorsque l'usage réel aura stabilisé
les responsabilités. La première interface nous apprendra où placer les frontières.

## Débloque / bloque

- **Débloque :** un modèle mental clair pour le transport et le client (dispatch sur la spec,
  client conforme au Contrat).
- **Bloque :** rien ; aucune matérialisation n'est imposée. L'artefact Contrat autonome et la
  séparation physique restent différés (ADR-UI-005).
