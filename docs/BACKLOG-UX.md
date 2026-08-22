# Backlog UX — BrainAI (produit)

*Items UX identifiés pendant le **test produit réel** (2026-08-22). Non implémentés. Chaque item respecte les
principes produit : **jamais** inventer une progression, **jamais** exposer la chaîne de pensée du modèle ;
n'afficher que des **états réels** du workflow.*

## UX-001 — « BrainAI travaille » (retour immédiat après Envoyer) — *priorité haute*
**Problème observé** : après **Envoyer**, l'utilisateur ne voit **rien** pendant que la cognition réelle tourne
(plusieurs minutes possibles). L'interface donne l'impression que BrainAI est **figé** — c'est ce qui a rendu le
tour lent illisible avant même le watchdog.

**Attendu** :
- après **Envoyer**, indiquer **immédiatement** que BrainAI **travaille** (état actif visible) ;
- afficher un **temps écoulé** (compteur) ;
- prévoir un bouton **Annuler**.

**Contraintes (non négociables)** :
- **aucune** progression inventée, **aucune** simulation, **aucune** chaîne de pensée du modèle exposée ;
- les **étapes réelles du workflow** (préparation → appel en cours → consolidation → vérification → livraison…)
  ne s'affichent **que lorsque le moteur en dispose réellement**.

**Dépendances techniques** :
- les **états réels de workflow** dépendent du **streaming** (RS-059 : `Popen` + `--output-format stream-json`,
  signal d'activité réel ; le contenu intermédiaire n'est **ni exposé ni persisté**, il sert à constater la
  vivacité et à produire des états sûrs) ;
- le bouton **Annuler** dépend de la **capacité d'annulation** (RS-059 : handle de process + op `cancel`).
- Tant que ces mécanismes n'existent pas, un **retour minimal honnête** est possible dès aujourd'hui (état
  « BrainAI travaille… » + temps écoulé, **sans** fausses étapes), mais l'annulation et les étapes réelles
  attendent RS-059.

## Notes de cohérence
- Lié **RS-059** (streaming / idle watchdog / annulation) et **RS-058** (croissance du contexte : réduire
  latence/coût **sans** dégrader la mémoire utile).
- Le **watchdog de sécurité** (palier immédiat, livré) empêche déjà un process éternel, mais **ne remplace pas**
  ce retour UX : un temps long ne doit plus **paraître** un blocage.
