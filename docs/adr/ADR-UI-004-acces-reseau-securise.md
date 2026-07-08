# ADR-UI-004 — Accès réseau sécurisé

- **Statut :** ✅ **Principe & architecture de sécurité ACCEPTÉS** · ⏳ **Implémentation DIFFÉRÉE** · ❌ **Exposition publique par port REJETÉE (par défaut)**
- **Phase :** Produit BrainAI — accès réseau (verrou commun au distant et au mobile)
- **Principes cadres :** Doctrine n°6 (le transport n'expose qu'un contrat) · Doctrine n°7 (les shells ne portent aucune logique métier).

> **Portée :** cet ADR décide l'**architecture** de l'accès réseau. Il ne demande **aucune
> implémentation**, ne change **ni le Bootstrap ni le Transport**, et ne fige **aucun choix
> technologique** non justifié. Une section distingue explicitement *architecture* et
> *implémentation future*.

## 1. Pourquoi la loopback au départ

- **Surface d'attaque minimale** : aucune exposition réseau entrante (ADR-UI-001).
- **Report des problèmes durs** (auth, TLS, exposition) jusqu'à un besoin réel.
- **Local-first** : le cerveau tourne localement ; le Desktop l'atteint sur la même machine.
- **Transport minimal** (stdlib) suffisant (ADR-UI-003).

## 2. Pourquoi un accès réseau devient nécessaire

- **Mobile** (ADR-UI-008) : la loopback ne traverse pas les appareils ; le téléphone ne peut
  pas exécuter le cerveau → accès réseau **obligatoire**.
- **Distant** : utiliser BrainAI depuis un autre appareil pendant que le cerveau tourne sur une
  machine (domicile/bureau).
- **Autres clients futurs** : second ordinateur, tablette, intégrations, CLI réseau.

Le Desktop actuel (sidecar loopback) **n'a pas besoin** de ce mode : il reste inchangé.

## 3. Cas d'usage concernés

| Cas | Besoin réseau | Note |
|-----|---------------|------|
| **Accès distant** | Oui | autre appareil → cerveau sur un hôte, via LAN ou overlay |
| **Shell Desktop** | Non (défaut) / Oui (option) | loopback conservé ; mode réseau **optionnel** pour un cerveau distant |
| **Shell Mobile (Capacitor)** | Oui | **principal bénéficiaire** ; pairing LAN privilégié (ADR-008) |
| **Autres clients futurs** | Oui | mêmes garanties (Contrat + sécurité) |

## 4. Décision

**Accepter le *principe* d'un mode réseau sécurisé, opt-in**, avec l'architecture suivante —
sans figer les technologies :

1. **La loopback reste le DÉFAUT.** L'exposition réseau est un **opt-in explicite** (jamais
   accidentel, consentement requis). **Jamais de `0.0.0.0` aveugle** : bind à une interface
   précise (LAN ou overlay).
2. **Deux modes**, du plus sûr au plus large :
   - **Mode LAN** — TLS (certificat auto-signé **épinglé à l'appairage**) + jeton + appairage
     (QR/mDNS). Aucune exposition Internet.
   - **Mode distant** — via un **réseau overlay chiffré** (classe WireGuard/Tailscale) : l'hôte
     et les clients rejoignent un réseau privé authentifié ; le transport bind l'interface
     overlay. **Pas de port public**, pas de gestion de certificat public, NAT traversé.
3. **Exposition publique par reverse-proxy + TLS public : REJETÉE par défaut** (surface, ops,
   rupture du local-first). Réservée à une décision explicite ultérieure si un vrai besoin produit.
4. **Le Contrat ne change pas** (Doctrine n°6) : **le même Contrat**, servi sur un canal
   **sécurisé**. La sécurité est une préoccupation du **transport**, pas du contrat.
5. **Client inchangé dans son cœur** : réutilise le **`fetch` injectable** (plugin HTTP
   Tauri/Capacitor) ; ne reçoit que `baseUrl` + credential + confiance (issus de l'appairage).
6. **Défense en profondeur — remote = lecture seule** : tant qu'une décision **gouvernée**
   séparée n'expose pas les actions à distance, les clients réseau n'accèdent qu'aux opérations
   `read`. Les **actions restent locales/gouvernées**.

**Conclusion de principe : ACCEPTÉE (architecture) · DIFFÉRÉE (implémentation) · exposition
publique REJETÉE par défaut.**

## 5. Exigences de sécurité

- **Aucun trafic BrainAI non chiffré ne quitte la machine** (TLS en LAN, chiffrement overlay en distant).
- **Bind explicite** à une interface choisie ; loopback par défaut ; opt-in consenti.
- **Isolation** : le mode réseau ne change rien au cerveau (pur, sans réseau) ; le transport
  reste le **seul** composant réseau, hors du Bootstrap.
- **Limitation de débit / anti-DoS** dès qu'on est en réseau (détail d'implémentation).

## 6. Authentification & gestion du jeton

- **Credential par appareil** émis à l'**appairage** (révocable individuellement), plutôt qu'un
  jeton unique partagé.
- **Entropie forte**, transmis **uniquement** sur canal chiffré, **jamais loggé**.
- **Stockage sécurisé côté client** : Keychain (iOS) / Keystore (Android) / stockage sécurisé
  Tauri ; **jamais** `localStorage`. *(Un client navigateur distant est contraint sur ce point —
  voir §11.)*
- **Cycle de vie** (expiration, rotation, révocation) : principe retenu, **modalités différées**.

## 7. Chiffrement des communications

| Portée | Chiffrement |
|--------|-------------|
| Loopback (même machine) | non requis |
| LAN | **TLS** (auto-signé + **épinglage au pairing**) |
| Distant | **overlay chiffré** (WireGuard-class) — préféré ; évite TLS public et NAT |
| Public Internet | reverse-proxy + TLS réel — **rejeté par défaut** |

## 8. Appairage initial des clients

L'appairage établit **trois choses** : `baseUrl` (adresse de l'hôte), **credential** (jeton par
appareil), **confiance** (empreinte de certificat ou appartenance à l'overlay).

- **QR code (recommandé)** : l'hôte affiche un QR (adresse + credential + empreinte cert) ; le
  client scanne → confiance établie **hors-bande**.
- **mDNS/Bonjour** (découverte LAN) + confirmation ; ou **saisie manuelle**.

## 9. Contraintes réseau

| Contexte | Contrainte | Réponse architecturale |
|----------|-----------|------------------------|
| **LAN** | découverte, pare-feu, IP changeante, permission « Réseau local » iOS | mDNS + pairing QR ; TLS épinglé |
| **Internet / NAT** | pas de port entrant, IP dynamique | **overlay/VPN** (pas de port public) — préféré |
| **VPN / overlay** | appartenance, identité | fournit chiffrement + identité + traversée NAT en une fois |
| **Reverse-proxy public** | certificats, exposition, ops | **rejeté par défaut** |

## 10. Architecture vs implémentation

**Relève de l'ARCHITECTURE (décidé ici) :**
- Principe du mode réseau **opt-in** ; loopback par défaut.
- Invariants de sécurité (chiffrement obligatoire hors-machine ; credential par appareil ;
  stockage sécurisé ; jamais de jeton loggé ; **remote = read-only** pour l'instant).
- Deux modes (LAN TLS+pairing ; distant overlay) ; exposition publique rejetée par défaut.
- **Contrat inchangé** ; client réutilise le `fetch` injectable ; **shells sans logique** (n°7).

**Relève de l'IMPLÉMENTATION future (différé) :**
- Montée du transport vers une pile **ASGI** (Starlette/uvicorn) pour TLS/concurrence
  (déclencheur documenté en ADR-UI-003) — **choix non figé**.
- Gestion TLS/certificats + épinglage ; flux d'appairage (QR) ; émission/révocation de credentials.
- Intégration overlay (WireGuard **vs** Tailscale **vs** autre — **non figé**, à justifier).
- Cycle de vie du jeton (expiration/rotation) ; limitation de débit.

## 11. Impacts

- **Transport** : gagne un **mode sécurisé opt-in** (bind LAN/overlay + chiffrement) ; loopback
  reste le défaut. Migration probable stdlib → ASGI (implémentation, différée). Reste le **seul**
  composant réseau, **hors du cerveau**, servant **uniquement le Contrat**.
- **Contrat** : **aucun**. Doctrine n°6 préservée — même `describe()`, même enveloppe, canal sécurisé.
- **Client TypeScript** : **cœur inchangé**. `createClient()` gagne des sources de config réseau
  (baseUrl + credential + confiance issus du pairing) et réutilise le `fetch` injectable
  (Tauri/Capacitor pour TLS natif/épinglage). Le test de conformité protège toujours le Contrat.
- **Shells** :
  - **Web** : reste local/loopback (dev) ; un client **navigateur distant** est **contraint**
    (TLS auto-signé, stockage du jeton, CORS) → **non prioritaire**, à traiter à part.
  - **Desktop** : loopback par défaut inchangé ; mode réseau **optionnel**.
  - **Mobile** : **principal bénéficiaire** (LAN pairing) — déverrouille ADR-UI-008.
  - Tous : **Doctrine n°7** — les shells gèrent l'**UX d'appairage** (cycle de vie), pas de logique.

## 12. Risques & garde-fous

| Risque | Garde-fou |
|--------|-----------|
| Vol de jeton | credential par appareil, révocable, stockage sécurisé, jamais loggé, seulement sur canal chiffré |
| MITM (sans TLS) | chiffrement **obligatoire** hors-machine (TLS épinglé LAN / overlay) |
| Exposition publique / DoS | **pas de port public** par défaut (overlay) ; bind explicite ; limitation de débit |
| `0.0.0.0` accidentel | bind à une interface **précise** ; opt-in consenti |
| Confiance certificat (auto-signé) | **épinglage à l'appairage** (QR hors-bande) |
| Abus d'actions à distance | **remote = read-only** jusqu'à une décision gouvernée séparée |
| Dérive vers produit serveur | exposition publique rejetée par défaut ; décision explicite requise |
| Shell qui prend de la logique | Doctrine n°7 : appairage = UX/cycle de vie, pas de logique métier |

## 13. Prérequis (pour lever le « différé »)

1. Choix d'une **pile transport sécurisée** (ASGI + TLS/auto-signé + épinglage) — chantier d'implémentation.
2. **Flux d'appairage** (QR) + émission/révocation de credentials par appareil + stockage sécurisé.
3. Pour le distant : choix d'un **overlay** (à justifier).

## 14. Scénarios d'évolution

1. **Mode LAN d'abord** (TLS+pairing) → déverrouille le Mobile (ADR-008) sur le réseau local + le distant-sur-LAN.
2. **Overlay/VPN** pour le distant inter-réseaux.
3. **Actions à distance gouvernées** (ADR séparé) : exposer les opérations `action` à distance,
   avec validation humaine — **pas** dans cet ADR.
4. **Exposition publique** seulement sur besoin produit réel + ADR explicite.

## 15. Conclusion

- **Décision finale : ACCEPTÉE** pour le *principe* et l'*architecture de sécurité* d'un mode
  réseau **opt-in** ; **DIFFÉRÉE** pour toute l'implémentation ; **exposition publique par port
  REJETÉE par défaut** (au profit de LAN-TLS-pairing et d'un overlay chiffré).
- **Conséquences sur l'architecture BrainAI** : le cerveau reste **pur** et **inchangé** ; le
  **Contrat reste l'unique source de vérité** (n°6) ; seuls le **transport** (mode sécurisé
  opt-in) et l'**UX d'appairage** des shells (n°7) évoluent, plus tard.
- **Feuille de route** : (1) pile transport sécurisée + TLS/épinglage ; (2) appairage QR +
  credentials par appareil ; (3) mode LAN → déverrouille Mobile ; (4) overlay pour le distant ;
  (5) plus tard, actions à distance gouvernées (ADR dédié).

ADR-UI-004 **ne lance aucun chantier**. Il fixe les invariants de sécurité et la trajectoire
qui permettront, le moment venu, d'ouvrir le distant **et** le mobile — sans jamais toucher le
cerveau ni le Contrat.
