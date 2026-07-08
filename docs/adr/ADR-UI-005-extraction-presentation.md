# ADR-UI-005 — Moment & modalités d'extraction de `SCC_BRAINAI_PRESENTATION`

- **Statut :** ✅ Accepté — **extraction différée, guidée par l'usage** (2026-07-08)
- **Phase :** Produit BrainAI — première interface
- **Principe cadre :** séparation **guidée par l'expérience**, pas par anticipation.

## Contexte

La couche `presentation/` (contrat + façade) vit aujourd'hui **dans** le Bootstrap, avec une
couture d'extraction propre (elle ne dépend que de l'API publique + stdlib). Le chantier UI
déclenche le **critère d'extraction** posé au BUILD-014. Contrainte forte : **le code réseau ne
doit jamais vivre dans le dépôt du cerveau**.

## Décision

**Différer l'extraction.** L'ordre retenu :

1. **Conserver temporairement `presentation/` dans `SCC_BRAINAI_BOOTSTRAP`** (contrat + façade),
   sans extraction.
2. **Construire une première UI de référence** consommant le contrat.
3. **Valider que le contrat est réellement stable** en utilisation réelle.
4. **Extraire ensuite `SCC_BRAINAI_PRESENTATION`** avec une connaissance concrète des besoins.

> Motivation : une séparation **guidée par l'expérience** vaut mieux qu'une séparation
> prématurée. On évite une synchronisation de versions inter-dépôts tant que le contrat n'a pas
> été éprouvé par une vraie interface.

### Conséquence clé — où vit le transport pendant la temporisation

Puisque `presentation/` **reste dans le cerveau** et que **le cerveau reste pur (sans réseau)**,
le **transport** (code réseau nouveau) **ne peut pas** vivre dans le Bootstrap. Il vit donc
**hors du cerveau**, côté **produit** (dépôt UI), et importe `presentation/` du Bootstrap via
`sys.path` (mécanique sibling existante), **API publique seule**.

```
SCC_BRAINAI_BOOTSTRAP   cerveau + presentation/ (contrat, pur, sans réseau)   — inchangé
        ▲ (import sys.path, API publique)
SCC_BRAINAI_UI          transport HTTP/JSON (Python, thin) + frontend (TS)     — dépôt produit
```

Le cerveau **ne gagne aucun code réseau**. À l'extraction future, **transport + contrat (+ CLI)**
se consolideront dans `SCC_BRAINAI_PRESENTATION`.

## Options considérées

| Option | Verdict |
|--------|---------|
| A. Extraire maintenant (contrat + CLI + transport) | Écartée — séparation prématurée |
| B. Transport temporaire dans le Bootstrap | **Rejetée** — injecte du réseau dans le cerveau |
| **E. Différer : garder le contrat dans le cerveau, transport côté UI, extraire après usage** | **Retenue** |

## Critères d'extraction future (l'un suffit)

1. Le contrat est **stabilisé** et éprouvé par ≥ 1 interface réelle ; **ou**
2. un **2ᵉ consommateur** a besoin de la couche indépendamment ; **ou**
3. un **versionnement indépendant** du contrat devient nécessaire.

## Conséquences

**Positives.** Pas de synchro inter-dépôts prématurée ; extraction informée par les besoins
réels ; cerveau intact ; réversible.
**Négatives / risques.** Le dépôt UI devient **polyglotte** (transport Python + frontend TS)
le temps de la temporisation → assumé et documenté ; à l'extraction, le transport migrera vers
`SCC_BRAINAI_PRESENTATION`. Veiller à ce que `CONTRACT_VERSION` reste la frontière de compat.

## Impact architecture

Topologie **transitoire à deux dépôts** (`BOOTSTRAP` + `UI` avec transport), convergeant vers la
topologie cible **à trois dépôts** une fois l'extraction justifiée par l'usage.

## Débloque / bloque

- **Débloque :** démarrage immédiat de l'UI de référence sans créer de dépôt Presentation.
- **Bloque :** rien d'irréversible ; l'extraction reste possible à tout moment dès qu'un critère
  est atteint.
