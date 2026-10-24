# RESUME-RECALL-MIN — contrat et point de reprise

24 octobre 2026. Branche locale `feat/resume-recall-min`, base
`c13131b5f3a05d595007b57dbe293deeccfb32db` (merge PR #29).
Ce lot n'est pas encore committé, poussé ou ouvert en PR.

## État intégré avant ce lot

- TEST-RUN-SEAM-MIN : PR #28, merge `aa532546…`.
- CORRECT-RETEST-MIN : PR #29, commit `f277e8a…`, merge `c13131b…`.
- CI post-fusion PR #29 : https://github.com/serorcreative/SCC_BRAINAI_BOOTSTRAP/actions/runs/40080346152
  — succès, suite déterministe et registre validés.
- Base locale validée : 1071 passed, 4 skipped. Registre inchangé : 160 entrées.

## Comportement ajouté

`composition.resume(pursuit_ref)` retrouve une session existante depuis son
chemin stable ou les mécanismes de compatibilité existants. Il appelle
`BrainAI.pursue(resume_intent(...))` ; l'intention auparavant non orchestrée
relit maintenant strictement les tours, sans appel de capacité ni écriture.
Les capacités injectées dans ce parcours sont des gardes non exécutables,
pas des fournisseurs résolus ou des réponses de démonstration.

La réponse distingue trois sources :

1. **Dialogue** : historique ordonné, références des tours, dernier statut et
   horodatage persistés, dernière réponse et proposition éventuelle. Un dernier
   tour échoué ne restaure pas une ancienne convergence. Un tour `ready` reste
   une proposition attendant confirmation ; aucun GO n'est créé.
2. **Memory-11** : rappel réel existant (`retrieve_pursuit`) et identifiants de
   mémoire. Une livraison mémorisée reste historique ; elle ne prouve pas que
   son fichier existe encore ou que sa preview fonctionne actuellement.
3. **Exécution** : derniers statuts enregistrés des runs, parent du run,
   interruptions déjà constatées, corrections consommées et charges connues.
   Un coût inconnu reste inconnu ; aucune remise à zéro du budget.

`execution_authorized=False` et `automatic_replay=False`. La reprise ne lance
ni cognition, ni build, ni retest, ni preview. Elle n'écrit aucun tour, aucune
confirmation, aucun événement mémoire et aucun nouveau run. Un prochain
message explicite passe par le `converse` existant, qui relit le même historique
sur la même Pursuit. Une action de réalisation reste gouvernée séparément.

## Intégrité et interruptions

Les références invalides, sessions absentes, journaux mal formés ou tours
incohérents sont refusés. Le nouveau mode strict de `TurnStore.read_all`
n'ignore aucune ligne invalide ; les parcours historiques restent inchangés.
Le rappel strict refuse aussi une mémoire nécessitant une réconciliation,
y compris une queue tronquée que Memory-11 sait normalement récupérer.
Cette reprise ne répare jamais la source pour rendre la lecture possible.

Un run `prepared` ou `running` n'est **pas** déclaré mort sur la seule base
du disque : `requires_reconciliation=True`, `live_worker_status=not_checked`.
Un fait d'interruption existant est reflété sans en créer un nouveau.
Une correction déjà consommée reste consommée, même après redémarrage.

La réponse `status=resumed` signifie que le contexte a été relu, pas qu'un
travail suspendu a été exécuté. L'état `dialogue.state` concerne le dernier
tour conversationnel ; il n'est pas présenté comme l'état global de livraison.

## Recette

`tests/test_resume_recall.py` couvre la reprise sans cache, un processus Python
réellement neuf, le prochain message de conversation, Memory-11 réel, les
références invalides, l'absence de session, les queues corrompues, la dernière
convergence devenue caduque, les symlinks, les doublons, l'état running non
réconcilié, les coûts inconnus et les accords correctifs consommés.

Un scénario traverse le lot précédent : build initial invalide, correction
autorisée, test et livraison réussis, puis rappel du run corrigé, de son parent
et de sa mémoire sans nouvel appel. Les arbres d'état sont comparés avant et
après reprise. Les providers des tests sont factices, le validateur local et
Memory-11 sont réels ; aucun LLM facturable.

Validation finale du 24 octobre : **1095 passed, 4 skipped en 41,29 s**,
dont 24 nouveaux cas dédiés. Commande :
`PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' tests/`.
Registre `--check` : vue à jour, 160 entrées. Syntaxe Python 3.9 des sept
fichiers Python concernés et `git diff --check` : OK.
Les 17 premiers cas dédiés avaient été exécutés rouges avant implémentation.
Aucun audit indépendant réalisé pour ce lot.

Correctif de portabilité du banc après ouverture de la PR #30 : le premier
run CI échouait uniquement dans le test de processus neuf (`ModuleNotFoundError:
brainai_app`). Le `pythonpath` de pytest ne s'hérite pas dans un sous-processus.
L'échec a été reproduit localement sans `PYTHONPATH` ; le test transmet désormais
explicitement le chemin absolu `src` au processus enfant et retire la dépendance
à l'environnement du shell. Aucun changement du code produit dans ce correctif.
Revalidation : `env -u PYTHONPATH .venv/bin/python -m pytest -q -o addopts='' tests/`
— **1095 passed, 4 skipped en 41,82 s**.

## Limites et continuation

- Surface Python explicite. Le raccord du bouton UI et la recette complète
  depuis l'interface restent à traiter dans le lot final du programme.
- Une Pursuit sans tours de dialogue persistés ne peut pas être ré-attachée
  par cette surface. Aucune continuité n'est inventée depuis un dossier vide.
- Pas de reprise automatique d'étape interrompue, de nouveau GO, de réparation
  de mémoire ou d'inférence de fin d'un worker. La réconciliation opérationnelle
  reste explicite et hors de ce lot de rappel.
- Pas de snapshot transactionnel multi-journaux : lecture pendant une mutation
  externe non garantie. Ce résultat informatif n'autorise aucune exécution.
- Le rappel n'atteste ni l'intégrité actuelle de l'artefact ni la disponibilité
  de la preview, ni la sécurité globale de l'environnement local.
- Les décisions historiques demeurent des faits, jamais des permissions
  nouvelles. Le budget de la reprise de lecture n'est pas une enveloppe
  permettant de relancer un outil.

Après revue et publication autorisée : LEARNING-PROPOSAL-MIN, puis raccords
et démonstration BUILD-RUNTIME-E2E-MIN depuis l'interface, avec succès et échec.
La génération automatique de corrections reste distincte du parcours de
reconstruction depuis une spécification corrigée déjà produite et approuvée.
Le programme complet n'est donc pas déclaré terminé.

SECURITY NOT PROVEN = NO PRODUCTION DEPLOYMENT.
NETWORK_ISOLATION=NOT_PROVEN.

SAB aide à développer BrainAI ; SAB ne devient jamais une partie de BrainAI
ni sa mémoire canonique. Les SAB restent hors de ce chantier.
