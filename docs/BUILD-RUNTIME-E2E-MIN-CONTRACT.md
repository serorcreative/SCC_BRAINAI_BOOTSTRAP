# BUILD-RUNTIME-E2E-MIN — raccord du parcours utilisateur

État au 2026-10-24 : implémentation locale, non publiée. Base :
`fcb5739c0bce5882a95e3f9109d6bfe3e61f36ae` (PR #31, Learning Proposal).
Ce lot poursuit les PR #28 (test), #29 (correction), #30 (reprise/Recall)
et #31 (propositions Learning). Il ne crée pas de nouveau jalon canonique.

## Comportement

L'utilisateur dialogue, prépare une proposition, consulte sa spécification,
ses choix et son coût, puis donne un accord. Cet accord ne lance rien :
un clic distinct déclenche construction, tests et vérification. Une préparation
en mode réel peut appeler la cognition facturable ; le bouton l'annonce.
Le budget affiché n'est pas un plafond cumulatif de toute la conversation.
Le mode démo conserve son parcours de démonstration, sans accord réel.

Une livraison ratée reste visible. L'utilisateur consigne une correction,
précise le besoin corrigé, prépare et approuve une nouvelle proposition,
autorise la tentative corrective, puis l'exécute séparément. L'artefact initial
est conservé. La reprise relit le dialogue, les runs et Memory 11 sans relancer
les outils. Learning 12 propose des recommandations avec leurs preuves ; aucune
application automatique n'est ajoutée.

## Raccord applicatif

`POST /v1/pursue`, avec le jeton de session existant et `kind: workflow` :

| Action | Champs spécifiques |
|---|---|
| prepare | pursuit_ref, budget_usd facultatif, build_provider facultatif |
| authorize | pursuit_ref, presentation_ref, decision |
| deliver | pursuit_ref, presentation_ref |
| propose_correction | pursuit_ref, parent_run_ref, test_result_ref, suggestion |
| authorize_correction | pursuit_ref, presentation_ref, correction_ref, decision |
| execute_correction | pursuit_ref, presentation_ref, correction_ref |
| resume | pursuit_ref |
| learning | aucun |

`mode: real` est obligatoire pour la préparation et l'exécution réelles.
Les champs inattendus, références invalides et budgets non finis sont refusés.
Les services métier existants restent responsables des accords, tests,
corrections, livraison, mémoire et apprentissage.

La présentation est enregistrée dans `interface_events.jsonl`, liée au dernier
tour, à la spécification, à l'empreinte du cost gate, au budget et au constructeur.
Son identifiant est revérifié sur son contenu avant usage. Un nouveau dialogue
ou une nouvelle présentation invalide l'ancienne. Ce contrôle n'est pas une
signature cryptographique contre un attaquant ayant accès au disque.

Un verrou par Pursuit sérialise les actions de ce raccord. Une intention de
livraison initiale est persistée avant l'appel aux outils. Après interruption,
aucun rejeu automatique n'est possible ; la reprise indique la réconciliation
nécessaire. Une erreur ambiguë est « non confirmée », jamais présentée comme
une preuve d'absence d'effets. Les anciennes routes restent compatibles et ne
partagent pas toutes ce verrou : aucune garantie globale de concurrence entre
clients différents n'est revendiquée.

## Vérification et limites de preuve

Validation locale du 2026-10-24 : suite complète **1132 passed, 5 skipped**
(67,88 s). Les 12 nouveaux cas HTTP passent ; le cinquième skip est la
recette navigateur opt-in, les quatre autres préexistent au lot. Vue canonique
`--check` à jour (160 entrées), syntaxe Python 3.9 et JavaScript vérifiée,
`git diff --check` sans erreur. Aucune CI de ce lot n'a encore été déclenchée.
Après les ajustements de largeur et de remise à zéro de l'écran : **38 tests
ciblés passent** (12,46 s). Le YAML du workflow a été analysé et les syntaxes
Python/JavaScript revérifiées. Ces contrôles ne remplacent pas le rendu navigateur.

`tests/test_runtime_interface.py` exerce un véritable serveur HTTP avec jeton,
les services de livraison et le constructeur local, les tests et la vérification
HTTP, Memory 11 et Learning 12. Seules les capacités cognitives sont remplacées
par des réponses de test. Le scénario négatif injecte volontairement un HTML
invalide, puis vérifie la correction explicite et la conservation de l'original.
Il couvre aussi refus de coût, présentation périmée ou altérée, interruption,
double lancement et requêtes invalides.

La recette navigateur `tests/test_runtime_browser.py` est opt-in :

```sh
BRAINAI_UI_BROWSER_TEST=1 .venv/bin/python -m pytest -q -o addopts='' tests/test_runtime_browser.py
```

Elle nécessite Node, Playwright et Chromium installé par Playwright, ou
`BRAINAI_CHROMIUM` pointant vers un exécutable compatible. Elle prévoit les clics
du parcours positif, de correction, de rechargement/reprise et de Learning,
ainsi que des captures bureau/mobile. **Elle n'a pas pu être exécutée dans
l'environnement de préparation** : Chromium échoue à créer une socket locale
(`Operation not permitted`) ; le navigateur distant ne peut joindre le serveur
loopback (`ERR_CONNECTION_REFUSED`). Elle ne constitue donc pas une preuve verte.

Le workflow L0-E prépare désormais Node 22, Playwright **1.62.1** (version
confirmée dans le registre npm), puis Chromium et ses dépendances. Après la
suite déterministe et le registre, il active explicitement cette recette :
un échec du navigateur fait échouer le job. Les captures PNG synthétiques
de succès ou d'échec sont conservées sept jours ; aucun journal de session
ni jeton n'est publié en artefact. Les dépendances navigateur restent dans
le répertoire temporaire du runner, sans dépendance ajoutée au Core.
Installation conforme au [guide CI officiel Playwright](https://playwright.dev/docs/ci).
Ce workflow est seulement préparé localement : publication et première preuve
CI restent à obtenir avant de déclarer la recette validée.

Une recette avec fournisseur cognitif réel et budget autorisé reste également
à effectuer. Aucun appel facturable n'a été lancé pour cette validation.
Le preview local est arrêté après la vérification : le rapport est une preuve
historique, pas une promesse d'hébergement actif. Pas de déploiement public,
pas d'Owner Mode, pas de changement SAB/Structura. SECURITY NOT PROVEN ;
network_isolation=NOT_PROVEN. Ce lot ne suffit pas à déclarer BrainAI prêt
pour la production.
