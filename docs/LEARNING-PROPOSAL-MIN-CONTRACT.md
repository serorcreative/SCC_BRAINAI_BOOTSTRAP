# LEARNING-PROPOSAL-MIN — contrat et point de reprise

24 octobre 2026. Branche `feat/learning-proposal-min`, base
`0e4e86a87ef70cbf66514816b17ad5de5a879bd0` (merge PR #30).
État de ce document : implémentation locale, publication non effectuée.

## Continuité du programme BrainAI

- TEST-RUN-SEAM-MIN : PR #28 intégrée.
- CORRECT-RETEST-MIN : PR #29 intégrée.
- RESUME-RECALL-MIN : PR #30 intégrée ; CI post-merge réussie sur la base exacte :
  https://github.com/serorcreative/SCC_BRAINAI_BOOTSTRAP/actions/runs/40094412970
- Ce lot réalise le raccord d'apprentissage proposé. Le suivant reste la
  recette BUILD-RUNTIME-E2E-MIN depuis l'interface, avec succès et échec.

**SAB aide à développer BrainAI ; SAB ne devient jamais une partie de BrainAI
ni sa mémoire canonique.** Aucun travail SAB ou Base44 dans ce lot.

## Surface et comportement

`brainai_app.composition.propose_learning()` analyse explicitement les
livraisons historiques admissibles de l'application. Le raccord utilise
`LearningLayer` et le véritable `LearningEngine` du composant 12, avec une
vue en lecture de la Memory-11 de l'application. Il ne reconstruit ni le moteur
d'apprentissage, ni ses règles, ni une mémoire parallèle.

Le moteur natif conserve son seuil de récurrence de deux livraisons. Aucune
baisse de seuil ni expérience synthétique pour produire un résultat : zéro
ou une livraison admissible renvoie `insufficient_evidence`. Une analyse
productive renvoie `proposed`, les items natifs, leurs références mémoire,
les recommandations et les audits. `applied=False` et
`needs_human_validation=True` sont explicites. L'horodatage d'analyse utilise
l'heure UTC de l'appel ; les identifiants dépendent du contenu natif.

Les décisions humaines déjà présentes dans le registre natif sont conservées
par le moteur lors d'une réanalyse. Les items renvoyés gardent leur véritable
statut, y compris `rejected` ou `revoked`. Le raccord n'appelle jamais les
méthodes de validation, rejet, révocation ou application.

## Preuves admissibles

La source est `BRAINAI_STATE_ROOT/memory`, sans écriture ni réparation.
L'audit natif de mémoire doit réussir ; une queue tronquée ou une mémoire à
réconcilier entraîne un refus. Seuls les événements `pursuit_delivered` avec
statut explicite `delivered` sont candidats.

Chaque événement doit se rattacher à une session existante et à des faits
persistés concordants : livraison, test passé, vérifications de test et HTTP
passées sur la même empreinte, dernier état du run réussi sur la même Pursuit,
références des étapes réussies correspondant aux preuves annoncées. Une
livraison comptée deux fois en mémoire ne constitue qu'une expérience.

Memory-11 caviarde les SHA-256 dans ses données. Cette protection reste intacte :
les IDs assurent la liaison, les empreintes sont comparées dans les journaux
sources, et le chemin relatif ainsi que la taille mémorisés doivent correspondre.
Les preuves absentes ou incohérentes sont exclues avec un motif explicite ;
les journaux JSONL mal formés et références ambiguës font refuser l'analyse.
Les livraisons anciennes sans preuve `test.run` ne sont donc pas comptées.

Il s'agit d'une expérience historique vérifiée par les faits conservés :
`artifact_revalidated=False`. Aucun fichier livré n'est réexécuté, aucune
preview n'est redémarrée. Cela ne prouve pas que le site fonctionne aujourd'hui.

## Persistance et panne

L'unique registre produit est `BRAINAI_STATE_ROOT/learning/learnings.jsonl`,
au format natif Learning-12. Aucun événement n'est ajouté à Memory-11 ou au
registre canonique du dépôt. Les sources de livraison, budgets et accords
restent inchangés. Aucun composant frère n'est modifié.

Le raccord refuse un registre corrompu, des identifiants incohérents, des
doublons, des preuves pendantes ou un audit natif défavorable. Il prend un
verrou POSIX non bloquant, analyse dans un dossier temporaire local, audite
le résultat puis remplace atomiquement le registre. Un échec avant remplacement
conserve le registre précédent ; les erreurs techniques sont rendues sans
leur contenu potentiellement sensible. Le fichier publié a le mode 0600.

Cette protection couvre les appels passant par ce raccord. Elle ne sérialise
pas les écritures d'un autre programme qui modifierait directement le registre
natif sans prendre ce verrou. Pas de garantie contre un acteur local capable
de modifier simultanément les chemins ou les preuves, ni de garantie complète
de durabilité après panne électrique. Une intégration future des validations
humaines devra partager la même coordination d'écriture.

## Validation

Les 14 premiers cas ont échoué avant l'implémentation, sur l'absence de la
surface `propose_learning`. Le banc dédié final compte 25 cas réussis :

- Deux livraisons passent par la chaîne applicative avec Memory-11, le
  validateur local et Learning-12 réels ; build factice, preview loopback,
  aucun LLM facturable. Les recommandations référencent les deux mémoires.
- Seuil inchangé, doublons non comptés, preuves manquantes ou contradictoires.
- Sources comparées avant/après, refus de mémoire tronquée sans réparation.
- Registre corrompu ou symlink refusé ; décision humaine préservée.
- Panne de publication et dépendance indisponible sans écrasement du registre.
- Appel concurrent refusé ; processus Python neuf retrouvant les preuves
  sans cache de session ni dépendance au PYTHONPATH du shell parent.

Validation globale : **1120 passed, 4 skipped en 64,59 s** avec
`env -u PYTHONPATH .venv/bin/python -m pytest -q -o addopts='' tests/`.
Registre canonique `--check` : vue à jour, 160 entrées. Syntaxe Python 3.9
des trois fichiers Python concernés et `git diff --check` : OK.
Relecture locale effectuée ; aucun audit indépendant réalisé pour ce lot.

## Limites et prochaine étape

Surface Python, sans nouvel endpoint ni bouton UI. Pas d'apprentissage à
partir d'échecs dans cette version : le détecteur natif réutilisé porte sur
les livraisons réussies récurrentes. Pas de modification du code, des règles
de BrainAI ou de ses autorisations à partir d'une recommandation.

Après revue, publication autorisée puis fusion vérifiée, poursuivre le lot
final BUILD-RUNTIME-E2E-MIN : raccord des surfaces nécessaires et recette
continue depuis l'interface (besoin, gouvernance, livraison, échec/correction,
reprise, Recall et proposition Learning). Ces tests backend ne constituent
pas à eux seuls la preuve de ce parcours utilisateur complet.
