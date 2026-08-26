# L0-G — Hygiène bornée : action réalisée + dettes consignées (non corrigées)

## Action réalisée (seul nettoyage autorisé en L0)
- **Suppression du token loopback résiduel** `SCC_BRAINAI_UI/transport/.brainai-transport.local.json`
  (jeton d'auth loopback du transport UI archivé D2).
  - Précondition vérifiée : **serveur transport mort**, fichier **gitignoré + non suivi**.
  - Métadonnées enregistrées **sans exposer la valeur** : 158 o, sha256 `ae2a0f8b…`.
  - **Fait d'audit** : `registry/baseline/hygiene-audit.jsonl`.
  - **Réversible** : le fichier est régénéré automatiquement au prochain démarrage du transport.

## Dettes périphériques CONSIGNÉES (à NE PAS corriger en L0)
- **LICENSE SC_CLI** : `SC_CLI` **introuvable sous `01_CCSC` accessible** — item référencé par
  l'audit ClaudeS (indisponible). À sourcer quand ClaudeS/le chemin exact sera fourni. **Non corrigé.**
- **Chemin SQLite SCRINMO** : **aucun remote/chemin `SCRINMO` détecté dans les 19 dépôts de `01_CCSC`**
  (voir `registry/baseline/repos.json`). Item ClaudeS — probable dépôt hors-CCSC. À sourcer via ClaudeS.
  **Non corrigé.**

## Obstacle documenté
- Aucune ambiguïté finale sur le token (identifié et traité). Les deux dettes ci-dessus **dépendent
  des audits ClaudeS** (hors drive accessible — voir L0-C en attente).
