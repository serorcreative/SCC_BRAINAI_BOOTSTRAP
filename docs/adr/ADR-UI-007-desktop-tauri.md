# ADR-UI-007 — Cible Desktop (Tauri)

- **Statut :** ✅ Accepté (2026-07-08)
- **Phase :** Produit BrainAI — Desktop, chantier ultérieur
- **Principe cadre :** Doctrine n°7 (ci-dessous) — le shell Desktop ne porte jamais de logique métier.

## Doctrine n°7 — Le shell Desktop ne porte jamais de logique métier

> **Le shell Desktop ne porte jamais de logique métier.**
> Il gère **uniquement le cycle de vie de l'application** (fenêtre, sidecar, intégration OS,
> lancement, arrêt).
> **Toute logique fonctionnelle reste dans le Bootstrap, la Presentation ou le Contrat.**

## Contexte

La SPA `overview` (lecture seule) est validée en navigateur réel. On veut un **shell Desktop
natif** : double-clic → cerveau + transport + UI démarrent, sans terminal. Le shell doit
**réutiliser la SPA telle quelle**, **lancer le transport en sidecar**, **préserver
loopback + jeton** et **ne toucher ni le transport, ni le client, ni la SPA, ni le Bootstrap**.

## Décision

**Adopter Tauri** comme shell Desktop, en **deux temps** :

1. **Shell Desktop local** (`tauri dev`) : réutilise la SPA ; le cœur Rust *spawn* le transport
   Python **local** en sidecar (env `SCC_BRAINAI_BOOTSTRAP_SRC` → Bootstrap local) ; il capture
   le **handshake** `(port, token)` sur stdout et l'expose au frontend (commande/event) ; le
   frontend injecte le **plugin HTTP de Tauri** comme `fetch` du `BrainAIClient` (requêtes côté
   Rust → **pas de CORS**), avec la `baseUrl`/`token` du handshake.
2. **Distribuable** (chantier ultérieur, lié à l'extraction `SCC_BRAINAI_PRESENTATION`) : freeze
   Python + bundling + signature/notarisation. **Différé.**

Décisions structurantes :
- **Tauri, pas Electron** (binaire léger, webview OS natif, cœur Rust, sidecar natif ; réutilise la SPA).
- **`fetch` injecté = plugin HTTP Tauri** ⇒ aucun CORS, **aucun changement** du transport / client / SPA / Bootstrap. (Le `fetch` injectable de `BrainAIClient`, conçu en amont, rend cela gratuit.)
- **loopback + jeton préservés** (et resserrés : la webview est le seul client, authentifié).
- **App Tauri dans `SCC_BRAINAI_UI/src-tauri/`** (monorepo pragmatique).
- **Cycle de vie du sidecar entièrement géré par Tauri** (démarrage + arrêt : Rust tue l'enfant à la fermeture ; le transport, sans état, libère le port sur SIGTERM → **aucun changement du transport**).
- **Bootstrap intact** : le sidecar lit `presentation/` via `sys.path` (env), en lecture seule.

## Options considérées

| Sujet | Options | Retenu |
|---|---|---|
| Shell | Electron / **Tauri** | **Tauri** |
| Accès transport | CORS transport / IPC Rust proxy / **plugin HTTP Tauri (fetch injecté)** | **plugin HTTP Tauri** |
| Sidecar (phase 1) | binaire gelé / **Python local via env** | **Python local** (freeze différé) |
| Emplacement | dépôt dédié / **`SCC_BRAINAI_UI/src-tauri/`** | **in-repo** |

## Conséquences

**Positives.** Expérience « un seul lancement » sans terminal ; fenêtre native ; aucun port
exposé / aucun navigateur (sécurité resserrée) ; fondation local-first ; **aucune logique
produit ajoutée** (shell pur) ; réutilisation intégrale de la SPA et du transport.
**Négatives / risques.** Voir tableau ci-dessous ; le distribuable (packaging Python, signature)
est un vrai chantier, volontairement **différé**.

## Risques

| Risque | Gravité | Mitigation |
|---|---|---|
| Packaging Python (freeze + `sys.path` des composants) | Élevé (distribuable) / Faible (dev) | différer ; dev local via venv |
| Chemins macOS (espaces, SynologyDrive, `.app`) | Moyen | quoting strict ; API Tauri |
| Signature / notarisation (Gatekeeper) | Élevé (distribution) | différée ; usage local non signé |
| Permissions Tauri (capabilities) | Moyen | capabilities minimales : sidecar + http scoped `127.0.0.1` |
| Sécurité | Moyen | plugin HTTP Rust scoped loopback + jeton ; CSP stricte ; aucun contenu distant |
| Logs (fuite du jeton) | Moyen | ne jamais logger le jeton |
| Arrêt du sidecar (orphelin) | Moyen | Rust tue l'enfant à la fermeture ; SIGTERM libère le port |
| Toolchain Rust requise | Faible | prérequis dev documenté (cargo/rustup) |

## Plan de chantier Desktop (séquencé — futur)

0. Valider cet ADR.
1. **Scaffold Tauri** dans `SCC_BRAINAI_UI/src-tauri/` : `devUrl`→Vite, `frontendDist`→`web/dist`. Aucune logique produit.
2. **Sidecar** : Rust spawn le transport (env `BOOTSTRAP_SRC`), capture stdout, tue l'enfant à la fermeture.
3. **Pont handshake** : commande/event Rust → frontend reçoit `(baseUrl, token)`.
4. **Adaptateur frontend** (additif) : runtime Tauri → injecter le `fetch` Tauri + config dans `BrainAIClient` ; sinon fallback navigateur.
5. **`tauri dev` de bout en bout** : fenêtre native, dashboard `overview` lecture seule, connecté au sidecar.
6. **Verify** : typecheck/test/build verts ; arrêt propre (aucun orphelin) ; loopback+jeton préservés ; Bootstrap inchangé.
7. **Différé (chantier séparé)** : distribuable (freeze, bundling, signature).

## Débloque / bloque

- **Débloque :** expérience Desktop local-first « un seul lancement » ; fondation d'une app distribuable.
- **Bloque / différé :** distribuable (packaging Python, signature) → chantier ultérieur, lié à l'extraction `SCC_BRAINAI_PRESENTATION`. Rien d'irréversible ; le Desktop reste un shell autour de la SPA.
