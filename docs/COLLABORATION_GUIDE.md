# Guide de Collaboration Assisté — COLLABORATION-GUIDE-001

> **Statut : concept produit formalisé (documentation seule).** Aucun code, aucune implémentation.
> Ne modifie ni les moteurs cognitifs, ni le Bootstrap, ni le Transport, ni l'interface.
> Distinct et sans lien de commit avec INPUT-HISTORY-001.

## 1. Le problème utilisateur

Un humain sait *ce qu'il veut*, mais pas toujours *comment le demander* à BrainAI. Sa première
formulation est souvent naturelle, imparfaite ou incomplète : intention réelle implicite,
contraintes non dites, périmètre flou, préférence durable exprimée comme une demande ponctuelle
(ou l'inverse). Résultat : des allers-retours, des livrables à côté, ou pire — une phrase ambiguë
interprétée comme une règle permanente.

Le besoin : **aider l'humain à formuler au mieux sa demande**, sans exiger qu'il apprenne un
« langage de prompt », et **sans que BrainAI décide seul** de ce qui devient une habitude durable.

## 2. Le principe du guide conversationnel

Le Guide de Collaboration Assisté désigne, à ce stade, une **capacité fonctionnelle** de médiation
entre l'humain et BrainAI — décrite par **ce qu'elle fait**, sans préjuger de son **découpage
technique** (fonction interne de BrainAI, mode conversationnel, chatbot spécialisé, couche
d'interface ou composant distinct : indécidé). Elle ne remplace pas BrainAI : elle **prépare** la
demande. Dans la suite, « le guide » désigne cette **capacité**, quelle que soit sa future réalisation.

```
Humain
  → formulation naturelle initiale
  → Guide de Collaboration (comprend · clarifie a minima · optimise)
  → prompt optimisé, directement transmissible
  → transmission à BrainAI
  → (le cas échéant) proposition d'enregistrement dans le Profil de Collaboration
```

Le guide **comprend l'intention**, **ne pose que les questions réellement nécessaires**, puis
**produit un prompt principal clair**. Il laisse **toujours** l'humain valider, modifier ou refuser.

## 3. Réception d'une première formulation libre

L'humain fournit une formulation libre, par exemple :

- « Comment dois-je formuler au mieux cette demande à BrainAI ? »
- « Comment puis-je te demander de toujours réunir plusieurs prompts lorsqu'ils doivent être
  transmis ensemble ? »

Le guide **accueille cette formulation telle quelle**, sans exiger de structure préalable. Il peut
**interpréter et inférer** une intention lorsque c'est utile, mais il **distingue toujours** ce que
l'utilisateur a **explicitement exprimé**, ce que le système a **raisonnablement inféré**, et ce qui
**reste incertain** (et peut nécessiter une clarification). **Toute inférence significative demeure
identifiable et explicable, et n'est jamais présentée comme une déclaration explicite de l'utilisateur.**

## 4. Optimisation et génération du prompt principal

À partir de l'intention comprise, le guide :

1. **structure** la demande (objectif, contexte utile, contraintes, résultat attendu) ;
2. **retire l'ambiguïté** sans ajouter de contenu que l'humain n'a pas exprimé ;
3. **génère un prompt principal** clair, autonome et **directement copiable/transmissible**.

Exemple de prompt généré :

```
BrainAI,

Lorsque plusieurs prompts sont destinés au même interlocuteur et doivent être
transmis ensemble, réunis-les toujours dans un seul bloc directement copiable.

Enregistre cette préférence dans mon profil de collaboration.
```

Le guide **remet le prompt à l'humain**, qui décide de la suite. Il pourra proposer des actions —
par exemple **copier le prompt**, **le modifier**, **le transmettre à BrainAI** ou **abandonner** —
mais **aucune transmission ni exécution n'a lieu sans une action ou une validation explicite de
l'humain**.

## 5. Les clarifications minimales nécessaires

Le guide **ne pose que les questions dont la réponse change réellement le prompt**. Il identifie
les informations **manquantes et utiles** (jamais un questionnaire exhaustif). Principe :
**une clarification n'est légitime que si son absence produirait un prompt inexact.** En l'absence
d'ambiguïté bloquante, il **ne pose aucune question** et génère directement.

## 6. Distinction demande ponctuelle / préférence persistante

Le guide distingue explicitement :

- **Demande ponctuelle** — vaut pour *cette fois* uniquement ;
- **Préférence persistante** — exprime une *habitude durable* de collaboration.

**Invariant fondamental : BrainAI ne transforme jamais silencieusement une phrase ambiguë en
règle permanente.** Lorsqu'il *détecte* une préférence potentielle, il **propose** — il n'impose
pas — quatre issues :

- **Appliquer uniquement cette fois** ;
- **Enregistrer dans le profil** (préférence durable) ;
- **Modifier la formulation** ;
- **Ignorer**.

## 7. Le Profil de Collaboration

La notion centrale est le **Profil de Collaboration** (à employer prioritairement). Il ne décrit
pas seulement *l'utilisateur* : il décrit **la manière dont BrainAI et cet humain travaillent
ensemble**. Il couvre notamment :

- présentation des réponses ;
- longueur et niveau de détail souhaités ;
- organisation des livrables ;
- regroupement ou séparation des prompts ;
- degré d'initiative attendu ;
- modalités de confirmation ;
- traitement des incertitudes ;
- style de communication ;
- préférences **selon le contexte ou le destinataire**.

**Les préférences ne sont jamais universelles** : elles ne s'appliquent **jamais** indistinctement à
tous les utilisateurs. Selon les besoins futurs, une préférence pourra être **associée** à une
**personne**, un **rôle**, une **organisation**, un **projet**, un **contexte** ou un **destinataire
particulier**. Le présent document **ne fige aucun modèle de données**.

## 8. La collecte d'informations cognitives par l'échange

L'échange guidé permet aussi à BrainAI de **recueillir des informations cognitives et
comportementales utiles** : manière de formuler ses intentions, préférences de communication,
niveau de détail souhaité, méthodes de travail, habitudes de validation, attentes récurrentes,
corrections, et distinction ponctuel / durable.

Cette collecte distingue **trois niveaux** : les **informations observées** pendant l'échange
(éléments de contexte ou traces d'échange) ; les **interprétations / préférences potentielles**
(candidats) ; les **règles persistantes** du Profil de Collaboration (promues et gouvernées). Une
observation peut exister comme élément de contexte **sans devenir automatiquement** une préférence
durable ; en revanche, **aucune règle comportementale persistante** applicable à l'utilisateur n'est
créée **silencieusement** à partir d'une observation ambiguë. Cette collecte est un **observé**, pas
une vérité imposée, et doit rester :

- **transparente** (l'humain voit ce qui est retenu) ;
- **gouvernée** (rien de durable sans décision humaine) ;
- **explicable** (BrainAI peut dire *pourquoi* il propose une préférence) ;
- **consultable · modifiable · supprimable** ;
- **soumise à validation humaine avant toute persistance durable**.

*Cohérence avec l'existant :* cette discipline reprend le gradient déjà en vigueur —
**observation ≠ interprétation ≠ règle** — et la souveraineté humaine des portes gouvernées
(proposer → valider). Une préférence *interprétée* est un **candidat**, jamais une règle, tant qu'un
humain ne l'a pas **promue**.

## 9. La validation humaine avant persistance

La validation humaine porte ici sur la **promotion** d'une information observée en **préférence ou
règle durable** — non nécessairement sur l'existence technique d'une trace d'interaction. Aucune
préférence ou règle persistante ne se crée **sans un acte humain explicite** : le flux est
**gouverné** (interprétation → **proposition** → **validation humaine** → enregistrement) ; le refus
et la modification sont des issues de premier rang, au même titre que l'acceptation. **Aucune
promotion silencieuse.** Le présent document reste au niveau **fonctionnel et gouverné** : il ne
fige pas les politiques détaillées de conservation.

## 10. Consultation, modification et suppression des préférences

Le Profil de Collaboration est **entièrement révisable par l'humain** :

- **consulter** l'ensemble des préférences enregistrées et leur origine ;
- **corriger** une préférence (nouvelle formulation, portée, contexte) ;
- **désactiver** une préférence ;
- **supprimer** une préférence.

L'utilisateur doit pouvoir **consulter, corriger, désactiver ou supprimer** une préférence **selon
les politiques de gouvernance et de conservation applicables**. Chaque préférence conserve une
**provenance explicable** (d'où elle vient, quand, sur quelle formulation). Le présent document **ne
décide pas** ici si une suppression conserve ou non une trace historique.

## 11. Exemples concrets

**A — Préférence durable (regroupement de prompts).**
> Humain : « Comment te demander de toujours réunir plusieurs prompts destinés à la même personne ? »
> Guide : génère le prompt (§4) **et** propose : *appliquer cette fois / enregistrer dans le profil /
> modifier / ignorer.* L'humain choisit « enregistrer » → validation → préférence persistée.

**B — Demande ponctuelle mal formulée.**
> Humain : « fais-moi un truc court sur la perception. »
> Guide : détecte 1 ambiguïté utile (« court = résumé de 5 lignes, ou plan ? »), pose **cette seule**
> question, puis génère un prompt clair. **Aucune** préférence proposée (rien n'indique une habitude).

**C — Préférence potentielle détectée mais non imposée.**
> Humain : « répond toujours en français. » (dit une fois, dans un contexte donné)
> Guide : détecte une **préférence potentielle durable**, mais **ne l'applique pas globalement** :
> il propose l'enregistrement (au profil, éventuellement contextualisé) — l'humain tranche.

**D — Révision.**
> Humain : « montre-moi mes préférences enregistrées et supprime celle sur la langue. »
> Guide : liste le profil (avec provenance), l'humain supprime → opération gouvernée et tracée.

## 12. Positionnement dans la roadmap de BrainAI

Le Guide de Collaboration Assisté se situe à la **couche de médiation humain ↔ BrainAI**, **en
amont** de la formulation d'une demande — complémentaire du pilier **Perception** (qui, lui,
acquiert le monde extérieur). Deux liens naturels :

- avec **Perception** : la collecte cognitive par l'échange est un **observé gouverné** (candidat),
  soumis aux mêmes disciplines (transparence, provenance, oubli gouverné) ;
- avec la **gouvernance** : la persistance d'une préférence est une **porte souveraine humaine**,
  du même esprit que les actions gouvernées existantes (proposer → valider).

Séquencement : **après** les incréments Perception en cours, et **indépendant** d'eux. Ce document
**ouvre la direction**, il ne déclenche aucune implémentation.

## 13. Limites de périmètre actuelles

- **Documentation uniquement** : aucun code, aucun moteur, Bootstrap, Transport ou UI modifié.
- **Pas** de format de stockage de profil figé ici, **pas** de machine d'états, **pas** d'architecture
  surdimensionnée, **pas** de nouveau chantier constitutionnel.
- Les préférences du Profil de Collaboration restent **contextualisées** et ne sont **jamais
  universelles** : leur portée pourra être associée, selon les besoins futurs, à une personne, un
  rôle, une organisation, un projet, un contexte ou un destinataire particulier.
- La persistance durable est **hors périmètre tant qu'une porte de validation humaine gouvernée
  n'est pas conçue** — jusque-là, tout reste **ponctuel et proposé**.
- Le **séquencement** et l'**architecture d'implémentation** — y compris tout premier incrément
  technique, modèle de stockage ou surface de consultation — seront **décidés ultérieurement**,
  après **étude de l'existant** et **validation du chantier approprié**. Ce document **formalise la
  capacité et ses principes** ; il ne sélectionne aucun chantier d'implémentation.
