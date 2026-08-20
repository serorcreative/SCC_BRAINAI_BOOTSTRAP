# Archéologie cognitive de la V1 — Pourquoi elle donnait l'impression de réfléchir avec toi

*Claude S. Avant toute chose : la reprise de Frédérique vaut pour moi aussi. En trois rounds, j'ai écrit des règles — Constitution, articles, observables — avant d'avoir fait ce qui aurait dû être le round zéro : expliquer, preuves à l'appui, ce qui produisait le comportement qu'on cherche à retrouver. Je corrige ici. La bonne nouvelle, démontrée en Phase C : les actifs déjà préparés survivent à l'examen — mais désormais ils sont *fondés*, pas seulement plausibles.*

*Sources : lecture intégrale du Cognitive Engine v0.2, du prompt Blueprint, des 7 Blueprints réels et leurs métadonnées, de la sortie brute J5 (ROADTRIP), du pilier Dialogue de compréhension, et du code v1. Chaque mécanisme est cité avec sa trace.*

---

## Phase A — Les mécanismes qui produisaient le « il réfléchit avec moi »

**M1 — L'identité habitée, pas la consigne suivie.** L'adaptateur de juin ne disait pas « voici tes instructions » mais : *« Ce document n'est pas une consigne d'exécution — c'est ta nature. Tu raisonnes selon ce document. »* Le modèle recevait une identité à habiter, pas une liste à respecter. Un modèle qui suit des consignes produit de la conformité ; un modèle qui habite une identité produit de la cohérence — la même voix du premier au dernier paragraphe.
*Preuve : l'en-tête de `anthropic-adapter.js` ; la constance de ton des 7 Blueprints.*

**M2 — Le Pentagone comme dramaturgie de la réponse.** Cinq capacités *indissociables* (« aucune ne peut être omise sans que BrainAI perde son identité »), dans un ordre vécu : comprendre, structurer, arbitrer, orchestrer, livrer. Chaque réponse *raconte* un raisonnement — elle commence par la compréhension et finit par un livrable. C'est une dramaturgie, pas un plan.
*Preuve : la structure de chaque Blueprint réel (section 1 = restitution, section 3 = arbitrage, section 8 = plan) ; la sortie J5 qui suit spontanément le même arc sans qu'aucun format ne soit imposé.*

**M3 — La génération de plusieurs lectures avant de répondre.** Méthode interne, étapes 3 et 5 : *« cartographier : ce que je sais avec certitude, ce que je suppose, ce qu'il me manque »* puis *« générer plusieurs trajectoires possibles. Pas une seule option. »* C'est le générateur littéral du « je vois trois pistes » : le modèle avait ordre de produire des alternatives intérieurement, avant de choisir. Sans ce mécanisme, un modèle produit *la* réponse ; avec lui, il produit *un choix parmi des réponses* — et ça se voit.
*Preuve : section E du Cognitive Engine ; les Blueprints qui présentent systématiquement des options AVANT la priorisation (section 2 « sans hiérarchie — la hiérarchisation arrive en section 3 »).*

**M4 — L'anti-neutralité : l'arbitrage obligatoire.** *« La neutralité d'analyse est un défaut, pas une qualité. Toute section qui présente trois options sans dire laquelle privilégier doit être réécrite. »* La V1 prenait position — « commencez par X, n'engagez surtout pas Z » — et justifiait. C'est le signal le plus fort du « quelqu'un réfléchit » : un esprit qui ne prend jamais position n'est pas perçu comme un esprit. La V2 actuelle pose des questions ; la V1 prenait des positions. Toute la différence d'expérience est là.
*Preuve : Doctrine 14 dans le prompt ; section C-Arbitrer ; les sections 3 et 6 de chaque Blueprint réel.*

**M5 — Les hypothèses nommées, offertes à la correction.** *« Tu peux faire des hypothèses raisonnables, mais tu les nommes explicitement. »* Et dans le Blueprint réel : *« Si l'une de ces hypothèses est fausse, des sections devront être ajustées — je l'indiquerai à chaque fois que c'est structurant. »* Le modèle montrait son modèle de toi et t'invitait à le corriger. C'est le mécanisme de la co-construction : l'humain n'évalue pas une réponse, il corrige une compréhension — il est *dans* le raisonnement.
*Preuve : Blueprint Barrycoaching, « Hypothèses que j'ai dû poser » — cinq hypothèses, toutes discutables, toutes discutées.*

**M6 — La chasse aux conséquences non demandées.** *« Une mission n'est jamais terminée tant que BrainAI n'a pas recherché activement les conséquences que l'utilisateur n'a pas demandées. C'est constitutif du mandat. »* Le produit : la **surprise utile** — le moment où tu apprends quelque chose que tu n'avais pas demandé. Votre questionnaire terrain de juin en avait fait LA métrique (« Q3 — Surprise : si la réponse est "rien", c'est une information précieuse en soi »). Le sentiment d'intelligence naît de la surprise utile, pas de l'exactitude.
*Preuve : section A et D du Cognitive Engine ; les angles morts RGPD/vendor lock-in tissés dans chaque Blueprint ; le « test de surprise utile » imprimé à chaque génération du MVP.*

**M7 — La liberté de forme au moment d'écouter.** Le J5 était explicite : *« aucun rôle système, aucune consigne de format : on observe, on ne cadre pas. »* Résultat : ROADTRIP — 12 755 caractères spontanés, structure émergente, phrase de positionnement, et une section de questions adressées à l'humaine que personne n'avait demandée. La contrainte de format comprime la pensée ; la liberté au bon moment la laisse se déployer. (La V2 doit doser : la gouvernance exige des sorties structurées — mais le champ `reply` de la conversation est du texte libre, et c'est là que ce mécanisme doit vivre.)
*Preuve : `executerMissionEcoute` (aucun système, aucun parsing) ; la sortie J5 intégrale.*

**M8 — La conviction graduée par le vocabulaire.** *« "Je recommande" ≠ "il me semble que" ≠ "cette piste mériterait d'être testée" ≠ "ce choix dépend de votre vision et m'est étranger". Aucun pourcentage. »* La nuance exprimée en langue, pas en chiffres : c'est ce qui fait qu'une position se lit comme un jugement, pas comme un calcul.
*Preuve : section F du Cognitive Engine ; le ton des Blueprints.*

**M9 — Les conditions de révision — et de maintien.** *« Une intelligence est définie par ce qui la fait changer d'avis. »* La V1 savait réviser (information contradictoire, hypothèse invalidée, angle mort signalé) **et maintenir** (objection de confort, pression de rapidité). Un interlocuteur qui cède toujours n'est pas un interlocuteur ; un qui ne cède jamais non plus. La capacité de désaccord motivé est ce qui rend le dialogue réel.
*Preuve : section G, entière — le mécanisme le plus « pensé » du document.*

**M10 — Le test interne avant de livrer.** *« Une personne avec 20 ans d'expérience dirait-elle "tiens, ça je ne l'avais pas vu" ? Si non, ton Blueprint est intelligent mais pas encore utile. Recommence. »* Un plancher de qualité auto-appliqué, formulé comme une exigence de surprise — pas de conformité.
*Preuve : « TEST DE RÉUSSITE INTERNE » du prompt Blueprint ; l'annexe du Cognitive Engine.*

**M11 — La matière première riche, d'un bloc.** Les 9 champs de contexte + les douleurs *dans les mots du dirigeant* (« garder ses mots à lui, ne pas reformuler en langage technique »). Le modèle avait de quoi penser. Mécanisme de l'ère one-shot : en V2, c'est le dialogue lui-même qui accumule cette matière — le mécanisme change de forme, pas de fonction.
*Preuve : `prompt-input.js`, les contextes réels, la consigne du fichier modèle.*

**M12 — La capacité du moteur.** Opus, 8 000 puis 16 000 tokens de sortie, 2-3 minutes par Blueprint, ~0,7-1,2 €. Aucune règle ne remplace la capacité : une partie du « ça pense » de juin était payée en tokens. Mécanisme réel, partiellement interchangeable (l'arbitrage sonnet est le bon compromis — mais il faut le savoir : haiku n'aurait PAS produit ROADTRIP).
*Preuve : les meta.json des 7 Blueprints ; la mise à jour MAX_TOKENS 8000→16000 après le Blueprint tronqué.*

## Phase B — Cartographie : ce que chaque mécanisme apportait face à la V2 actuelle

| Mécanisme | Classement | Ce qu'il apportait que la V2 actuelle n'a pas |
|---|---|---|
| M1 Identité habitée | **Indispensable** | La V2 donne 8 lignes d'instructions → conformité sans voix |
| M3 Plusieurs lectures | **Indispensable** | La V2 produit *la* réponse ; rien n'ordonne de générer des alternatives |
| M4 Anti-neutralité | **Indispensable** | La V2 ne prend jamais position — c'est le cœur du « il ne discute pas » |
| M5 Hypothèses corrigeables | **Indispensable** | Le champ `assumptions` existe mais rien n'ordonne de les *offrir à la correction* |
| M6 Conséquences non demandées | **Indispensable** | Aucune chasse aux angles morts ; le doute légal de Frédérique est passé inaperçu |
| M9 Révision ET maintien | **Indispensable** | Rien ne définit quand la V2 change d'avis ni quand elle tient bon |
| M2 Pentagone-dramaturgie | Utile | Structure du raisonnement visible ; sans lui les réponses restent plates |
| M8 Conviction graduée | Utile | Sans lui, tout se vaut ou tout est certain |
| M10 Test interne | Utile | Plancher de qualité auto-appliqué, quasi gratuit |
| M7 Liberté de forme | Utile (à doser) | Le `reply` libre de la conversation est le bon habitat ; tension résiduelle : le schéma à 7 champs du rung understanding au tour 1 |
| M11 Matière riche | Accessoire (transformé) | Remplacé par l'accumulation dialogique — c'est le rôle de la Pursuit |
| M12 Capacité moteur | Accessoire (arbitré) | Sonnet consenti ; à réévaluer sur preuves si le test d'acceptation déçoit |
| One-shot, 9 questions fixes, JSON du J4, stack TS/Supabase | Obsolètes | Remplacés par le cycle, la Pursuit, les faits, la gouvernance — c'est l'apport propre de la V2, à ne pas toucher |

## Phase C — Traduction : où chaque mécanisme vit dans la V2

| Mécanisme | Article de la Constitution v0.2 | Implémentation |
|---|---|---|
| M1 | Préambule + Art. 10 | `compose_prompt` (la phrase « c'est ta nature » y est déjà — reprise mot pour mot de juin) |
| M2 | Art. 1, 10 | Identité v0.3 §C (Pentagone intégral) |
| M3 | **Art. 3 (raisonnement explicite)** | Identité §E + 2e phrase ajoutée à la mission conversation |
| M4 | Art. 6, 8 | Identité §C-Arbitrer (avec la clause d'égalité honnête) ; mission specification |
| M5 | Art. 5, 6 | Identité §F ; consigne `assumptions` des missions understanding/specification |
| M6 | Art. 6 | Identité §A + §D (double mission) ; critère T2 du test (le doute légal) |
| M7 | Art. 2 | Le `reply` libre du schéma conversation — le schéma n'est PAS étendu, précisément pour ça |
| M8 | Art. 6, 9 | Identité §F |
| M9 | Art. 12 | Identité §G |
| M10 | Art. 13 (boucle de validation) | Identité annexe + évaluation des 5 tours contre les articles au rapport de clôture |
| M11 | Art. 11 (la Pursuit comme accumulation) | TurnStore + historique relu — déjà en place |
| M12 | — (choix d'implémentation) | A6 : sonnet, réévaluable sur preuves |

**Constat de la traduction : rien à jeter, une seule tension résiduelle.** Les six mécanismes indispensables sont tous portés par l'identité v0.3 et la Constitution v0.2 — non par hasard : l'identité *est* le Cognitive Engine de juin, et la Constitution en formalise les invariants. La tension résiduelle est M7 : le rung understanding impose ses 7 champs dès le premier contact avec le besoin — l'exact contraire du J5. Elle ne bloque pas ce chantier (la conversation, elle, est libre dans son `reply`) ; elle est à trancher au chantier corpus, avec des preuves (comparer Brief structuré d'emblée vs écoute libre puis structuration).

**Ce que cela ajoute au prompt final de ClaudeC — un seul paragraphe :**

> TRAÇABILITÉ COGNITIVE : ce chantier traduit des mécanismes identifiés par archéologie de la V1
> (document ARCHEOLOGIE_COGNITIVE_V1.md fourni). Ton rapport de clôture inclut la table de
> traçabilité : mécanisme (M1-M10) → article de la Constitution → lieu d'implémentation → et,
> pour chacun, une ligne : « ce que ce mécanisme apporte que la V2 n'avait pas ». Tu n'implémentes
> aucun mécanisme sans savoir dire ce qu'il apportait.

---

## Les trois chantiers fondateurs — et mon engagement de rigueur

La hiérarchie de Frédérique est la bonne, et les objectifs profonds proposés sont justes. Je les relie à ce qui existe déjà pour qu'on ne reparte de rien :

1. **Cognition dialogique** — *« Permettre à BrainAI de raisonner avec l'humain avant toute production. »* C'est ce chantier. Test ultime : la phrase de Frédérique (« je veux qu'il réfléchisse avec moi »), opérationnalisée par les 6 mécanismes indispensables et les 5 tours du test.
2. **Production intelligente** — *« Transformer un besoin mûri en livrables par une orchestration gouvernée de facultés, d'outils et d'IA. »* Les briques existent (rungs 1-3, garde-fous) ; les pièces à venir sont connues et déjà nommées : le chef d'orchestre (la composition comme faculté), la vérification de ce qui est construit, l'Atlas des outils.
3. **Mémoire cognitive** — *« Permettre à BrainAI d'accumuler et réutiliser durablement son savoir en restant capable de le remettre en question. »* Les préalables sont déjà identifiés et attendent leur tour sans polluer le chantier 1 : le journal append-only à réparer, la boucle Learning à reconnecter, la réinjection des leçons validées, le Budget de réflexion, le corpus de juin comme banc d'essai.

Mon engagement, dans les termes de Frédérique — une rigueur exemplaire, et vérifiable : **(a)** chaque proposition que je ferai nommera le chantier qu'elle sert ; si c'est un autre que le chantier en cours, elle va au backlog en une ligne, pas dans le débat ; **(b)** plus jamais de règle sans archéologie — toute proposition de comportement cite le mécanisme et sa preuve, ou se déclare comme pari ; **(c)** un livrable par round, jamais deux débats sans artefact entre eux ; **(d)** je garde la mesure du coût de correction — ce recentrage-ci a coûté un round ; découvert dans six mois, il aurait coûté l'écosystème entier bâti sur une conversation creuse.

Une dernière chose, parce qu'elle boucle la boucle : la question « pourquoi la V1 donnait-elle l'impression de réfléchir ? » a une réponse courte, maintenant démontrée pièce par pièce — **parce qu'on lui avait écrit une nature au lieu de lui écrire des consignes, et qu'on lui ordonnait de prendre position au lieu de lui permettre de poser des questions.** Tout le chantier tient dans le rétablissement de ces deux gestes, sous la gouvernance que la V2 a su construire et que la V1 n'avait pas.
