"""Couche **delivery** — orchestration de la LIVRAISON réelle d'une Pursuit confirmée (JALON 2).

Cette couche vit **hors** de ``builder/`` (dont l'isolation d'imports est un invariant testé) : elle a donc
le droit de **raccorder** les vrais moteurs siblings (``14_BRAINAI_PLANNING`` pour l'ordonnancement…) sans
violer la frontière du ``builder``. Elle **connecte** des briques existantes, n'en reconstruit aucune :

* build réel confiné → :mod:`scc_brainai_bootstrap.builder.site` (le fournisseur écrit de vrais fichiers) ;
* ordonnancement des étapes → :mod:`.planning` **enveloppe** le vrai ``topological_order`` (Kahn) de
  ``14_PLANNING`` (aucune recopie de l'algorithme) ;
* budget réellement borné → :mod:`.budget` (``BudgetLedger`` append-only) ;
* vérification liée au hash → :mod:`.verify` (serveur loopback + GET + ``Verification``) ;
* fait ``delivered`` + écriture mémoire minimale → :mod:`.delivered` (écriture seule, jamais de récupération).

Vocabulaire d'états **repris** de ``16_EXECUTION`` (statuts run/step) : un run et ses étapes ne prolifèrent
pas de statuts ad hoc.
"""

from __future__ import annotations

__all__ = []
