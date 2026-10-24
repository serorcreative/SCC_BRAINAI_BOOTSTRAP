# CORRECT-RETEST-MIN — contrat et point de reprise

Actualisé le 24 octobre 2026. Implémentation locale, non publiée.
Branche : `feat/correct-retest-min` ; base : `aa53254660be1ae3e82b285396f4b74017b06ea7`.

## Acquis avant ce lot

TEST-RUN-SEAM-MIN est intégré par PR #28 : implémentation
`94dc988d8a89422176840fd9bd1c3951e865bd9e`, merge `aa532546…`.
CI post-merge : https://github.com/serorcreative/SCC_BRAINAI_BOOTSTRAP/actions/runs/40029861931
— succès. Suite locale antérieure : 1034 passed, 4 skipped.
Registre canonique : 160 entrées. Aucun événement ajouté pour le présent lot.

Le plan P0 du 23 octobre prévoit CORRECT-RETEST-MIN, puis
RESUME-RECALL-MIN, LEARNING-PROPOSAL-MIN et la recette depuis l'interface.
Ces noms sont des lots de travail, pas des numéros de jalon canonisés.

## Périmètre réalisé

Reconstruire un site initial dont le build a réussi mais dont `test.run` a
échoué, à partir d'une spécification matériellement corrigée, déjà produite
et autorisée. Une suggestion textuelle n'est jamais exécutée comme du code.
Le lot ne génère pas automatiquement la correction : il raccorde sa proposition,
son autorisation et son exécution à la chaîne de livraison existante.

Trois surfaces Python dans `brainai_app.composition` :

1. `propose_delivery_correction` relit les journaux run/build/test et le hash
   de l'artefact, puis ajoute une proposition inerte. Elle ne crée pas de session
   absente, ne résout pas de fournisseur et ne lance aucun outil.
2. `authorize_delivery_correction` relit la proposition et le Cost Gate avec
   son GO de build courant. Elle enregistre une décision distincte liée à la
   correction, à la spécification, au fingerprint, au plafond cumulatif,
   au nombre maximal d'appels et au sélecteur de fournisseur.
3. `execute_delivery_correction` retrouve la spécification et le manifeste
   persistés, revalide les accords puis appelle `_deliver` et `run_delivery`.
   Il n'y a ni nouveau runner ni nouvelle mémoire canonique.

Le diagnostic est caviardé avant bornage ; la cause reste `not_established`.
L'acteur est déclaré, pas authentifié par ces fonctions Python.

## Conservation, arrêt et budget

- L'original reste dans `delivery_exec/workspaces/site`. La reconstruction
  utilise `correction_exec/<correction_id>/workspaces/site` et un nouveau run
  relié explicitement au run échoué. Le fait delivered porte aussi cette
  provenance et le chemin relatif du nouveau workspace.
- Un verrou POSIX sérialise les tentatives correctives. L'accord est consommé
  par une écriture synchronisée avant tout outil. Une soumission répétée ou
  simultanée de la même correction ne relance pas le build.
- Une interruption conserve la consommation de l'accord ; aucun retry
  automatique après crash. Une nouvelle décision sur cette même correction
  consommée est refusée. La récupération explicite reste hors de ce lot.
- Le journal de budget est partagé avec l'échec initial et lu strictement.
  Aucun compteur n'est remis à zéro. Modifier le plafond ou le nombre d'appels
  invalide l'accord correctif ; augmenter ces limites exige une décision
  explicite, sans effacer les dépenses passées.
- Le nouveau test et la vérification HTTP/hash conditionnent la livraison.
  Un test échoué ou expiré interdit preview et delivered. Le raccord Memory-11
  reste celui de la composition existante après livraison réussie.

Les journaux sont prolongés, pas réécrits. Les sources absentes, ambiguës,
corrompues, rattachées à une autre Pursuit ou devenues périmées sont refusées.
Le GO de coût demeure nécessaire même si une autorisation corrective existe.

## Recette locale

Deux fichiers de tests dédiés : `test_correction_proposal.py` (20 cas) et
`test_correction_execution.py` (17 cas).

Le scénario d'intégration part d'un HTML invalide : le validateur local réel
retourne le code 11. Un builder factice reconstruit un HTML valide dans le
nouveau workspace ; le même validateur retourne 0, puis la vérification de
livraison passe. L'original et les préfixes des anciens journaux sont comparés
octet par octet. Aucun LLM ni fournisseur facturable n'est appelé par les tests.

Autres cas : propositions inertes, références incohérentes, chemins non
confinés, refus/révocation/obsolescence des accords, modification d'artefact,
ledger corrompu, budget déjà épuisé, retest échoué/timeout, interruption après
consommation et deux soumissions simultanées. La surface Python publique est
exercée pour la livraison réussie et pour le refus sans accord correctif.

Validation du 24 octobre : **1071 passed, 4 skipped en 39,07 s**, soit
37 tests ajoutés depuis la base fusionnée. Commande :
`PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' tests/`.
Registre `--check` : vue à jour, 160 entrées. Analyse syntaxique Python 3.9
des six fichiers Python concernés et `git diff --check` : OK.
Aucune revue indépendante réalisée pour ce lot.

## Limites et suite

Le lot couvre un échec de test initial de site statique, pas une chaîne de
corrections, un patch arbitraire, une correction autonome par LLM ou une
interface utilisateur complète. Il exige une spécification corrigée existante.
Le verrou protège les demandes correctives entre elles ; il ne protège pas
contre un processus extérieur modifiant simultanément les fichiers, ni contre
une livraison ordinaire concurrente. Le confinement de sécurité global et la
résistance aux processus hostiles ne sont pas prouvés. Linux/macOS seulement
pour ce verrou POSIX ; aucune compatibilité Windows annoncée.

Les autorisations lient le sélecteur de fournisseur, pas une attestation de
toute sa configuration externe. Les erreurs d'E/S et interruptions peuvent
laisser une tentative consommée à examiner, jamais une permission de retry.

Prochaine étape : revue du diff et publication de ce lot après GO spécifique
commit/push/PR, puis vérification CI. La continuation locale est autorisée ;
elle ne vaut ni dépense fournisseur ni autorisation de publication ou merge.
Ensuite reprendre le plan P0, en traitant explicitement la reprise et le rappel
avant la recette utilisateur complète. Ne pas annoncer BrainAI terminé.

SECURITY NOT PROVEN = NO PRODUCTION DEPLOYMENT.
NETWORK_ISOLATION=NOT_PROVEN.

SAB aide à développer BrainAI ; SAB ne devient jamais une partie de BrainAI
ni sa mémoire canonique. Aucun chantier SAB n'est relancé par ce lot.
