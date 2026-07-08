# ADR-UI-003 — Dépendances du transport Python

- **Statut :** ✅ Accepté (2026-07-08)
- **Phase :** Produit BrainAI — première interface, Étape 1 (transport)
- **Principe cadre :** éthos BrainAI — simplicité, auditabilité, peu de dépendances.

## Contexte

L'adaptateur de transport est un composant Python qui **importe le contrat** (`presentation/`)
et l'expose en HTTP/JSON (ADR-UI-002), en loopback (ADR-UI-001). Il vit **hors du cerveau** ;
ses dépendances ne polluent donc pas le Bootstrap. Le dispatcher est **générique** (un seul
endpoint piloté par le contrat) : la valeur d'un framework à routes typées est en grande partie
**redondante** avec le codegen dérivé de `describe()`.

## Décision

- **stdlib `http.server` d'abord** : dispatcher générique, loopback-only, zéro dépendance.
- **Chemin de migration documenté** vers **Starlette + uvicorn** (ASGI), déclenché **uniquement**
  par un **besoin objectif** : accès distant, concurrence réelle, TLS, ou WebSocket/SSE
  (lié à ADR-UI-004). Pas de sécurité HTTP « faite main » au-delà du loopback.
- Le **contrat reste l'unique source de schéma** ; aucun framework ne le redéclare.

## Options considérées

| Option | Verdict |
|--------|---------|
| **A. stdlib `http.server`** | **Retenue** — zéro dép, aligné éthos, auditable, surface minimale |
| B. FastAPI + uvicorn | Différée — OpenAPI redondant avec `describe()` ; deps ; utile si besoin objectif |
| C. Starlette + uvicorn | Cible de migration si distant/TLS/WS |
| D. Flask | Non retenue |

## Conséquences

**Positives.** Transport minimal et auditable ; cohérent avec l'éthique BrainAI ; aucune dette
tant que le besoin reste local.
**Négatives / risques.** `http.server` est mono-thread et sans TLS/validation intégrés →
**acceptable parce que loopback-only** ; toute sortie du loopback impose la migration ASGI
(critère explicite, non une dette silencieuse).

## Impact architecture

Le transport démarre **léger**. La migration vers une pile ASGI est un **critère** documenté,
pas une réécriture : le contrat et le dispatcher générique sont préservés.

## Débloque / bloque

- **Débloque :** transport local léger immédiatement (dev Web + Desktop).
- **Bloque :** production/distant → ADR d'upgrade (Starlette/uvicorn + TLS + auth, ADR-UI-004).
