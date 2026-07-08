# SCC BrainAI Bootstrap

**Le premier exécutable qui fait démarrer BrainAI.**

Charge la configuration, initialise les sous-systèmes, enregistre les premiers
Agents, puis déclare **« BrainAI READY »**. Il **réutilise** les composants SCC
existants via leurs interfaces publiques, sans en modifier aucun. Stdlib pur,
déterministe, sans réseau.

## Démarrer

```bash
cd 17_BRAINAI_BOOTSTRAP
python -m pip install -e .        # expose la commande `scc-brainai`
scc-brainai start
```

```
[1/8] config          ✓ scc_root=01_CCSC
[2/8] control_plane   ✓ santé=ok
[3/8] patrimony       ✓ 21/21 composants présents
[4/8] memory          ✓ entrées=0
[5/8] knowledge       ✓ entrées=0
[6/8] event_bus       ✓ ouvert (5 événements)
[7/8] agents          ✓ 4 agent(s) enregistré(s)

BrainAI READY
```

## Un seul point d'entrée : `run` (routage automatique)

`run` est **le** point d'entrée de BrainAI. Il démarre la pile si besoin puis
**route automatiquement** la demande :

- demande **décisionnelle** (« faut-il… », « choisir… », « X ou Y »…) →
  boucle `decide` (décision candidate gouvernée, en attente de validation humaine) ;
- **sinon** → **Kernel (10)** puis **mémorisation dans Memory (11)** — la boucle
  vécu → mémoire.

```bash
scc-brainai run "Quelles doctrines gouvernent la gouvernance ?"   # → Kernel
scc-brainai run "Faut-il publier l API maintenant ou différer ?"  # → decide
scc-brainai run "analyse l architecture" --deep     # passe cognitive complète (5 moteurs)
scc-brainai run "..." --route decide                # forcer la route
scc-brainai run "..." --no-record --json            # sans mémorisation ; sortie JSON
```

Une demande informative est routée vers le Kernel :

```
route       : kernel
intention   : governance
agents      : SCC-AGENT-0002, SCC-AGENT-0003, SCC-AGENT-0001, SCC-AGENT-0020
gouvernance : 13 doctrine(s), 5 ADR
runtime     : echo -> succeeded
mémorisé    : trace mem_000000000008 (7 événements)

--- synthèse ---
(cognition déterministe de BrainAI, sans IA externe)
```

Une demande décisionnelle est routée vers la boucle `decide` :

```
route       : decide
décision    : dec_b863911cb793  (statut : proposed)
retenue     : Différer  (classe : routine)
options     :
  ● Différer (score 0.52)
  ○ Statu quo (score 0.52)
  ○ Agir maintenant (score 0.49)
validation humaine requise avant exécution :
  - Validation humaine explicite par un approbateur identifié.

→ valider : scc-brainai validate dec_b863911cb793 --by <acteur>
```

Le routage est **lexical et déterministe** (`router.py`) ; il peut être forcé par
`--route auto|kernel|decide`. La commande `decide` reste disponible comme raccourci
explicite vers la boucle décisionnelle.

## La grande boucle cognitive (décider → valider → exécuter)

Pour les demandes décisionnelles, BrainAI enchaîne **Reasoning (13) → Decision (15)
→ [validation humaine] → Execution (16) → Runtime (07)**, toutes couches câblées et
gouvernées :

```bash
scc-brainai decide "Faut-il publier l API maintenant ou différer ?"
#   → décision candidate (proposée) + conditions de validation humaine

scc-brainai execute <decision_id> --by frederique
#   → REFUSÉ : décision non validée (garde-fou)

scc-brainai validate <decision_id> --by frederique --reason "go"
#   → décision validée (humain)

scc-brainai execute <decision_id> --by frederique
#   → exécution déléguée au Runtime : succeeded
```

Garde-fous : **aucune exécution sans décision validée** ni **acteur autorisé** ; la
décision reste *proposée* jusqu'à validation humaine explicite. État persistant sous
`data/cognition/` (Reasoning / Planning / Decision / Execution). Aucun composant
n'est modifié : tout passe par leurs interfaces publiques.

Après `execute`, les **traces d'exécution** produites par Execution (16) sont
**ingérées dans Memory (11)** — le vécu d'exécution devient mémoire, exploitable plus
tard par Learning. La boucle vécu → mémoire se referme aussi sur l'exécution.

## La chaîne apprenante (Memory → Learning)

BrainAI **apprend de son propre vécu** : Learning (12) lit la **mémoire vivante** du
bootstrap (le `BrainMemoryStore` déjà initialisé) et en dérive des **apprentissages**
— signaux, patterns, leçons, recommandations, hypothèses.

```bash
scc-brainai learn
```

```
vécu analysé  : 40 entrée(s) de Memory
apprentissages: 22 au total (signaux 13, patterns 3, leçons 3, recommandations 2, hypothèses 1)
recommandations (propositions à valider) :
  ○ [recommendation_b735e1245855] Recommandation : agent mobilization  (confiance 1.0, proposed)

→ valider : scc-brainai learn-validate <id> --by <acteur>
```

```bash
scc-brainai learnings --kind recommendation      # lister les propositions
scc-brainai learn-validate <id> --by frederique  # validation humaine
scc-brainai learn-validate <id> --by frederique --action reject
```

Garde-fous hérités de Learning : **aucun apprentissage appliqué**, **aucune
auto-modification** (doctrine, workflow, agent, mémoire, graphe, code). Tout est une
**proposition traçable, révocable, soumise à validation humaine**. L'état des
apprentissages est persistant sous `data/learning/` (une décision humaine survit aux
redémarrages). La boucle **vécu → mémoire → apprentissage** se referme ici, sans qu'aucun
composant ne soit modifié : Learning n'écrit que dans son propre registre de propositions.

## La boucle fermée (apprentissages validés → cognition)

Un apprentissage **validé** ne reste pas inerte : il **nourrit la cognition**. Le moteur
Learning partagé est injecté dans Planning (14) et Decision (15) ; **seules les
recommandations validées** sont exploitées (garde-fou porté par Learning).

```bash
scc-brainai plan "Améliorer la gouvernance documentaire"
```

Avant validation, le plan ignore les apprentissages ; après `learn-validate`, chaque
**recommandation validée devient une tâche d'application** du plan :

```
tâches      : 12  (dont 2 issue(s) d'apprentissages validés)
issues d'apprentissages validés (boucle fermée) :
  ⟲ Appliquer la recommandation : Recommandation : agent mobilization  (learning:recommendation_b735e1245855)
plan proposé — validation humaine requise avant exécution.
```

De même, `decide` **cite les apprentissages validés** dans la traçabilité de la décision
(`applied_learnings`). La boucle complète se referme : **vécu → mémoire → apprentissage →
validation humaine → cognition** — sans auto-modification ni auto-application, et de façon
déterministe. Le plan produit reste une **proposition** soumise à validation.

## Séquence de démarrage (les 8 étapes)

1. **Configuration** — charge `config/brainai.json` (scc_root, `as_of`, premiers agents).
2. **Control Plane** — réutilise `09_CONTROL_PLANE` (`ControlPlane().health()`).
3. **Patrimony Manager** — inventaire du patrimoine de BrainAI (21 composants/actifs).
4. **Memory** — réutilise `11_BRAINAI_MEMORY` (`BrainMemoryStore`).
5. **Knowledge** — réutilise `04_KNOWLEDGE` (`KnowledgeEngine`).
6. **Event Bus** — bus d'événements en process (publish/subscribe, append-only).
7. **Premiers Agents** — enregistre les rôles pivots depuis `00_SYSTEM/agents`.
8. **« BrainAI READY »**.

Chaque étape publie un événement sur l'Event Bus. Un composant absent n'arrête pas
le démarrage : l'étape est signalée et BrainAI démarre en **mode dégradé**.

## Diagnostic (`doctor`)

Un diagnostic complet de toute la pile en une commande :

```bash
scc-brainai doctor
```

```
BrainAI DOCTOR
──────────────
patrimoine    : 21/21 présents
disponibilité : control_plane ✓  memory ✓  knowledge ✓  kernel ✓  reasoning ✓  planning ✓  decision ✓  execution ✓  learning ✓
santé         : control plane = ok (15 domaines)
audits        : memory ✓  reasoning ✓  planning ✓  decision ✓  execution ✓  learning ✓

VERDICT : BrainAI HEALTHY
```

Il agrège, en lecture seule : le **patrimoine**, la **disponibilité** des composants,
la **santé** du Control Plane et les **audits** des couches (Memory + Reasoning /
Planning / Decision / Execution / Learning). Verdict `healthy` / `degraded` (code de sortie 0/1).

## Event Bus vivant (observabilité)

Deux abonnés sont branchés **avant toute publication** :

- **EventRecorder** — persiste tous les événements dans `data/events.jsonl`
  (journal d'observabilité append-only) ;
- **LifecycleWatcher** — surveille le flux et lève des **alertes** sur les topics
  d'échec (étape KO, Kernel indisponible, démarrage dégradé…).

```bash
scc-brainai events                       # journal complet du bus
scc-brainai events --topic agent.registered
```

Le bus est un vrai **point d'abonnement** : `bus.subscribe(callback)` permet aux
couches supérieures d'écouter le cycle de vie de BrainAI. En mode dégradé, les
alertes sont affichées directement par `start` / `run`.

## Nouveaux sous-systèmes de cette couche

- **Patrimony Manager** (`patrimony.py`) — inventaire en lecture seule de ce dont
  BrainAI est fait (moteurs, Runtime, API, Control Plane, couches BrainAI, catalogues).
- **Event Bus** (`event_bus.py`) — bus léger du cycle de vie de BrainAI, point
  d'abonnement pour les couches supérieures (distinct du journal de jobs du Runtime).

## Utilisation (Python)

```python
from scc_brainai_bootstrap import BrainAIBootstrap

report = BrainAIBootstrap().run()
print(report["banner"])            # "BrainAI READY"
```

## Tests

```bash
python -m pytest -q      # 103 tests (déterministes ; démarrage réel des composants)
```

Détails : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
