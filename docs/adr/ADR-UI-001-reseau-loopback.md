# ADR-UI-001 — Réseau / loopback

- **Statut :** ✅ Accepté (2026-07-08)
- **Phase :** Produit BrainAI — première interface, Étape 1 (transport)
- **Principe cadre :** Doctrine n°6 — *le transport n'expose jamais une implémentation, uniquement un contrat.*

## Contexte

Le transport est le **premier composant réseau** de BrainAI. Le Bootstrap (cerveau) reste
pur, déterministe, sans réseau. Il faut permettre aux UIs **locales** (dev Web, Desktop
sidecar) d'atteindre le contrat, tout en minimisant la surface d'attaque et en différant les
sujets lourds (authentification, TLS, accès distant).

## Décision

- **Liaison `127.0.0.1` (loopback) uniquement**, **port éphémère**.
- **Jeton de session** généré au démarrage du transport, transmis à l'UI via un handshake
  (trivial pour le sidecar Desktop ; fichier/env local pour le dev Web).
- **Jamais de liaison `0.0.0.0`** en phase Produit 1.
- Variante d'isolation renforcée retenue comme possibilité : **socket de domaine Unix (UDS)**
  (à confirmer selon le support Windows) — n'ouvre aucun port TCP.

## Options considérées

| Option | Verdict |
|--------|---------|
| A. Loopback nu `127.0.0.1` | Base, mais tout process local peut appeler le port |
| **B. Loopback + port éphémère + jeton** | **Retenue** — barrière contre les autres process locaux |
| C. Socket de domaine Unix (UDS) | Variante forte ; support Windows plus récent |
| D. `0.0.0.0` + auth/TLS | Rejetée en phase 1 (→ ADR-UI-004) |

## Conséquences

**Positives.** Surface d'attaque minimale ; aucun port entrant exposé ; aligné « local-first » ;
diffère auth/TLS ; le cerveau reste totalement isolé du réseau.
**Négatives / risques.** Sur une machine multi-utilisateurs, le loopback est joignable par les
autres process locaux → mitigé par le **jeton**. Gestion du jeton en contexte navigateur (dev
Web) à soigner. Conflits de port → port éphémère + handshake de découverte.

## Impact architecture

Le transport bind loopback et publie un couple `(port, token)` via handshake. Le Bootstrap est
**inchangé**. Aucun code réseau n'entre dans le cerveau.

## Débloque / bloque

- **Débloque :** développement local Web + Desktop (sidecar).
- **Bloque :** accès distant et Mobile-hors-machine, tant qu'**ADR-UI-004** (auth/sécurité)
  n'est pas tranché.
