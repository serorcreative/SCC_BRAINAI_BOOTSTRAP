# ADR-UI-008 — Cible Mobile (Capacitor)

- **Statut :** ✅ **Conteneur accepté (Capacitor)** · ⏳ **Implémentation différée** (conditionnée à ADR-UI-004)
- **Phase :** Produit BrainAI — Mobile, chantier ultérieur
- **Principes cadres :** Doctrine n°6 (le transport n'expose qu'un contrat) · Doctrine n°7 (le shell ne porte jamais de logique métier).

## Contexte

Le socle Web + Desktop est livré : SPA (Vite/React/TS), client TypeScript reflétant le
Contrat, transport **loopback + jeton** (stdlib), lancé en sidecar (Desktop) ou via proxy
Vite (Web). On veut décider l'approche Mobile **sans l'implémenter**.

## Le problème central : le mobile ne peut pas utiliser la loopback

Toute l'architecture actuelle repose sur un **cerveau local** joignable en **loopback**
(`127.0.0.1`) : sur Desktop, le sidecar Python tourne sur la **même** machine que la webview.

Sur un **téléphone**, deux faits changent tout :

1. **Aucun cerveau local** : faire tourner le Bootstrap Python (interpréteur + arbre de
   composants chargés via `sys.path`) sur iOS/Android est impraticable (iOS interdit les
   interpréteurs arbitraires ; bundling très lourd).
2. **La loopback ne traverse pas les appareils** : `127.0.0.1` sur le téléphone désigne le
   téléphone lui-même — où il n'y a pas de cerveau.

⇒ **Le mobile impose un accès *réseau* au cerveau** (sur un ordinateur du réseau local, ou
un serveur distant). C'est précisément ce que le modèle loopback exclut volontairement
(ADR-UI-001). **Le point dur du mobile n'est pas Capacitor — c'est le réseau et sa sécurité.**

## Décision

- **Conteneur mobile : Capacitor — ACCEPTÉ.** Capacitor emballe **la SPA existante** (mêmes
  frontend, client, Contrat) en app iOS/Android — **aucun second codebase** (vs React Native).
  Cohérent avec « un codebase web → trois shells » (Web/Tauri/Capacitor).
- **Implémentation mobile : DIFFÉRÉE**, conditionnée à la résolution d'**ADR-UI-004**
  (authentification & accès réseau/distant sécurisé), car le téléphone ne peut ni utiliser la
  loopback ni exécuter le cerveau localement.

## Options de connectivité considérées

| Option | Description | Verdict |
|--------|-------------|---------|
| **A. Pairing LAN** | Téléphone ↔ ordinateur du réseau local exécutant cerveau+transport, exposé au-delà de la loopback (IP LAN), appairage par QR/mDNS | **Piste privilégiée** (garde l'esprit local-first) — nécessite ADR-004 |
| **B. Serveur distant** | Cerveau en cloud/self-hosted ; mobile = client SaaS | Écartée par défaut (rompt le local-first) ; possible plus tard sur décision explicite |
| **C. Pyodide-in-webview** | Cerveau (stdlib pur) exécuté en **WASM Python** dans la webview mobile → aucun réseau | Recherche, différée (lourd, FS virtuel à bundler, perf) |
| **D. Différer le mobile** | Ne rien faire tant que le réseau n'est pas cadré | **Retenue pour l'implémentation** |

## Comment Mobile consommera la Presentation Layer / le Transport

Inchangé dans son principe — **le mobile ne parle jamais au Bootstrap** :
`Mobile → Client → Transport → Contrat ← Presentation ← Bootstrap`.

- Le transport tourne sur un **hôte joignable** (ordinateur LAN ou serveur), exposé **au-delà
  de la loopback avec TLS + jeton** (ADR-004). Le téléphone n'importe ni ne connaît le cerveau.
- Le client injecte le **`fetch` du plugin HTTP Capacitor** (requêtes natives → contourne
  CORS/mixed-content de la webview), avec `baseUrl` (adresse de l'hôte) + `token`. **Le `fetch`
  injectable du `BrainAIClient`, déjà utilisé pour Tauri, rend cela gratuit.**
- **Appairage** : la remise `(baseUrl, token)` ne peut plus passer par stdout (le téléphone
  n'est pas le parent) → flux dédié : **QR code** (l'hôte affiche baseUrl+token, le téléphone
  scanne), ou mDNS/Bonjour, ou saisie manuelle. À définir avec ADR-004.

## Contraintes spécifiques mobile

| Contrainte | Détail |
|-----------|--------|
| **Loopback impossible** | `127.0.0.1` = le téléphone ; le cerveau est ailleurs → accès réseau obligatoire |
| **Sécurité du jeton** | stockage sécurisé (Keychain iOS / Keystore Android via Capacitor Secure Storage), **jamais** en localStorage ; transmis sur le réseau → **TLS requis** hors LAN de confiance ; jamais loggé |
| **Réseau local fragile** | ordinateur allumé + découvrable, IP changeante, changement de réseau, pare-feu ; iOS 14+ exige la permission « Réseau local » |
| **Packaging** | build natif iOS/Android, App Store / Play Store, signature (Apple Developer / Google Play), provisioning |
| **Permissions** | Réseau local (iOS), Internet, caméra (si appairage QR) |
| **Offline éventuel** | le téléphone ne calcule pas le cerveau → offline = **instantané `overview` mis en cache** (données figées, lecture seule) + indicateur « hors ligne » ; **aucune mutation offline** |

## Impacts

- **Web** : aucun. Inchangé.
- **Desktop** : aucun. Capacitor est un shell **additionnel**.
- **Transport** : aucun **maintenant**. Le mobile exigera plus tard un **mode d'exposition
  réseau opt-in** (bind au-delà de la loopback + TLS + auth), défini par ADR-004 — **sans**
  toucher le défaut loopback actuel.
- **Client TypeScript** : `createClient()` gagnera plus tard une branche **Capacitor** (injecter
  le `fetch` HTTP Capacitor) ; le design `fetch` injectable le permet déjà. Aucun changement maintenant.
- **Contrat** : aucun. Le mobile consomme le **même Contrat** (source de vérité) ; le test de
  conformité garantit l'absence de dérive.

## Risques & garde-fous

| Risque | Garde-fou |
|--------|-----------|
| Complexité réseau/sécurité (TLS LAN, confiance des certificats, jeton sur le réseau) | Ne pas démarrer le mobile avant qu'ADR-004 définisse l'accès sécurisé ; **TLS obligatoire hors LAN** ; jeton en stockage sécurisé |
| Fragilité de l'appairage/découverte | Concevoir un appairage simple et sûr (QR) dans le chantier mobile/ADR-004 |
| Dérive vers un produit serveur (SaaS) par accident | Décision **explicite** LAN-first vs distant dans un ADR dédié ; ne pas glisser vers un serveur sans le décider |
| Attentes d'offline | Offline = instantané en cache + indicateur « hors ligne » ; **aucune mutation offline** |
| Le shell mobile ajoute de la logique | **Doctrine n°7** s'étend au shell Capacitor : cycle de vie / packaging uniquement, aucune logique métier |
| Le mobile parle au cerveau directement | Impossible par construction (JS ↔ Python) ; le mobile ne consomme que le Contrat (Doctrine n°6) |

## Conditions d'adoption (pour lever le « différé »)

L'implémentation mobile devient réalisable **quand toutes** sont réunies :

1. **ADR-UI-004 résolu** : transport avec **mode réseau sécurisé** (bind au-delà de la loopback,
   TLS, authentification par jeton, appairage/découverte).
2. **Modèle de connectivité choisi** : pairing LAN (privilégié) vs serveur distant — via un ADR dédié.
3. **Réutilisation du `fetch` injectable** : plugin HTTP Capacitor (comme Tauri), **sans** changer
   transport/client/SPA/Bootstrap.
4. **Contrat inchangé** : le mobile consomme le Contrat verbatim.

## Étapes futures possibles

1. Résoudre **ADR-UI-004** (transport réseau sécurisé + appairage).
2. ADR de **modèle de connectivité** (LAN-first vs distant).
3. Chantier Mobile : shell **Capacitor** autour de la SPA + injection du `fetch` Capacitor +
   flux d'appairage + stockage sécurisé du jeton.
4. Stratégie **offline** (instantané en cache) — chantier séparé.
5. (Recherche) **Pyodide-in-webview** — évaluer un mobile réellement autonome, sans réseau.

## Conclusion

- **Capacitor : ACCEPTÉ** comme conteneur mobile (un seul codebase, réutilise SPA/Client/Contrat).
- **Mobile : DIFFÉRÉ** — **bloqué par le réseau**, pas par Capacitor. Réalisable une fois
  **ADR-UI-004** résolu et un **modèle de connectivité** choisi (pairing LAN privilégié).
- Rien n'est irréversible ; le mobile reste un **shell autour de la SPA**, consommant le Contrat.
