# ADR — Décisions d'architecture (phase Produit BrainAI)

Registre des décisions d'architecture (Architecture Decision Records) de la phase
« Produit BrainAI » — la première interface. Chaque ADR fige une décision, son contexte
et ses conséquences. Voir la direction d'ensemble : [`../ARCHITECTURE_UI.md`](../ARCHITECTURE_UI.md).

## Statut des ADR

| ADR | Sujet | Statut |
|-----|-------|--------|
| [ADR-UI-001](ADR-UI-001-reseau-loopback.md) | Réseau / loopback | ✅ Accepté |
| [ADR-UI-002](ADR-UI-002-protocole-transport.md) | Protocole de transport | ✅ Accepté |
| [ADR-UI-003](ADR-UI-003-dependances-transport-python.md) | Dépendances transport Python | ✅ Accepté |
| [ADR-UI-005](ADR-UI-005-extraction-presentation.md) | Extraction de `SCC_BRAINAI_PRESENTATION` | ✅ Accepté (différée, guidée par l'usage) |
| [ADR-UI-006](ADR-UI-006-client-typescript.md) | Client TypeScript (hybride) | ✅ Accepté |
| [ADR-UI-010](ADR-UI-010-contrat-axe-architectural.md) | Le Contrat comme axe architectural | ✅ Accepté (conceptuel ; réalisation différée) |
| ADR-UI-004 | Authentification & accès distant | ⏳ Ouvert (bloque le distant/mobile-hors-machine) |
| ADR-UI-007 | Packaging Desktop (Tauri + sidecar) | ⏳ Ouvert |
| ADR-UI-008 | Stratégie Mobile (Capacitor) | ⏳ Ouvert |
| ADR-UI-009 | État & offline | ⏳ Ouvert |

## Doctrine permanente de BrainAI

Ces règles s'appliquent à **tous** les BUILD et chantiers futurs :

1. **Le registre décrit** les agents.
2. **Le Bootstrap orchestre.**
3. **Les moteurs exécutent.**
4. **`overview` observe** — il n'agit jamais.
5. **L'interface présente** — elle n'agit jamais d'elle-même ; l'humain valide les actions gouvernées.
6. **Le transport n'expose jamais une implémentation — il expose uniquement un contrat.**
   (Vrai quels que soient les transports futurs : HTTP, stdio, gRPC, etc.)

**Le Contrat est l'axe architectural** (ADR-UI-010) et la **source de vérité** :

```
        Contrat (source de vérité : opérations · enveloppe · version · describe())
      ▲ implémente     ▲ sert          ▲ reflète        ▲ consomme
 Presentation       Transport         Client            UI
```

Sens de dépendance *physique*, strict et non contournable :

```
UI  →  Transport  →  Presentation (implémente le Contrat)  →  Bootstrap (cerveau)
```

Le cerveau reste **pur** : aucune dépendance réseau/UI ne remonte jamais dedans.
OpenAPI, s'il apparaît un jour, n'est qu'un **export** du Contrat — jamais la source.
