# ADR-UI-002 — Protocole de transport

- **Statut :** ✅ Accepté (2026-07-08)
- **Phase :** Produit BrainAI — première interface, Étape 1 (transport)
- **Principe cadre :** Doctrine n°6 — *le transport n'expose jamais une implémentation, uniquement un contrat.*

## Contexte

Le transport doit véhiculer le contrat de présentation vers Web + Desktop + Mobile,
**simplement** et **universellement**, sans exposer plus que le contrat. Le contrat est de
nature **requête/réponse** (opérations `read` / `action`).

## Décision

- **HTTP/JSON** comme **protocole canonique**.
- **Dispatcher générique piloté par le contrat** :
  - `POST /v1/{operation}` — corps `{ …args }`, **uniforme** pour toutes les opérations ;
  - `GET /v1/contract` — introspection (`describe()` : version + opérations + genres).
- Le dispatcher **liste blanche** `operation` contre `OPERATIONS` et rejette tout le reste ;
  il appelle **uniquement** `Presentation.<operation>` et renvoie l'**enveloppe verbatim**.
- Le genre `read`/`action` reste porté par l'**enveloppe**, pas par le verbe HTTP (simplicité).

## Options considérées

| Option | Verdict |
|--------|---------|
| **A. HTTP/JSON** | **Retenue** — plus petit dénominateur commun des 3 cibles, natif navigateur |
| B. stdio JSON-RPC | Rejetée comme canonique (un navigateur ne peut pas le consommer) ; option Desktop |
| C. WebSocket / SSE | Différée — utile au **push** (rafraîchissement live d'`overview`), superflu aujourd'hui |
| D. HTTP + stdio | HTTP canonique ; stdio = optimisation Desktop non canonique |

## Conséquences

**Positives.** Universel, natif navigateur (`fetch`), outillé, prêt pour le distant ; une seule
surface à sécuriser et tester.
**Négatives / risques.** Pas de push natif → polling via TanStack Query en phase 1 ; le temps
réel (WS/SSE) fera l'objet d'un ADR ultérieur. Choix `POST` uniforme (vs `read→GET`) reporte
l'optimisation de cache HTTP.

## Impact architecture

Fige la forme d'endpoint et le **client TypeScript** (généré, `fetch`). `stdio` reste une
optimisation Desktop possible **sans** changer le contrat (Doctrine n°6 : le contrat est
indépendant du transport).

## Débloque / bloque

- **Débloque :** client TS généré, SPA de référence, sidecar Desktop.
- **Reste ouvert :** temps réel / push (`overview` live) → ADR ultérieur (WebSocket/SSE).
