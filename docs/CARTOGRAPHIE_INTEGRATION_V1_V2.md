# Cartographie d'intégration V1 → V2 — mécanisme par mécanisme, sur les deux arbres réels

*Claude S. Établie après relecture des deux dépôts réels : l'héritage (`90_HERITAGE/.../brainai-mvp` et `brainai-v1`) et l'état V2 du jour (`17_BRAINAI_BOOTSTRAP`, dernier commit `a2aa7dd`, BRAINAI-CONVERSATION-001 T2). **Aucune implémentation dans cette analyse** — c'est la carte, à challenger avant tout prompt à ClaudeC.*

## 0. Le consensus reçu, et deux garanties avant la carte

Le socle des six mécanismes non négociables listés par Frédérique correspond exactement à M1, M3, M4, M5, M6, M9 de l'archéologie — le consensus est donc figé sur cette liste, je n'y reviens pas.

**Garantie 1 — le comportement d'abord, l'administration jamais.** La règle de Frédérique (« le cerveau de BrainAI ne doit pas devenir une administration ») se traduit ici par une frontière stricte, que la carte respecte ligne à ligne : **ce qui atteint le modèle** = l'identité (~1 900 mots, une *nature*) + la mission du tour (~180 mots, une *tâche*). Rien d'autre. La Constitution, les articles, les observables, la traçabilité **ne sont jamais envoyés au modèle** : ce sont nos outils d'évaluation, à nous. Treize articles ou quatre, le modèle n'en verra aucun. Et l'arbitre final reste le comportement : si les 5 tours réels sonnent froid alors que tout est « conforme », c'est la carte qu'on révise, pas le verdict.

**Garantie 2 — la boussole « consigne ou identité ? ».** Chaque intégration ci-dessous est étiquetée **NATURE** (vit dans l'identité, formulée comme un trait d'être), **MISSION** (vit dans la tâche du tour, formulée comme un objectif), ou **NOUS** (vit dans nos documents de gouvernance, jamais dans le prompt). C'est l'application directe de la phrase-boussole.

## 1. Les six mécanismes indispensables

### M1 — L'identité habitée
| | |
|---|---|
| Preuve V1 | `brainai-mvp/src/adapters/anthropic-adapter.js` (« ce n'est pas une consigne — c'est ta nature ») + `cognitive-engine.js` entier |
| Existe déjà en V2 | **Rien.** `conversation.py:56` : « Tu es BrainAI, un partenaire de réflexion (architecte, ingénieur, associé) » — une apposition de trois métiers, pas une nature. `understanding.py:68` et `specification.py:98` : « Tu produis un BRIEF / une SPÉCIFICATION » — pure consigne |
| Ce qui manque | Toute l'identité. C'est le vecteur des cinq autres mécanismes : sans M1, les autres redeviennent des consignes |
| À ne PAS recopier | Le mot « Blueprint » et les références au livrable unique de juin (la V2 a des facultés distinctes) ; le genre flottant (« elle ») de la v0.2 |
| Où il vit | `builder/cognitive_identity.py` (déjà prêt, v0.3) injecté par `compose_prompt()` en tête de `conversation.py::build_prompt` (identité complète) et `understanding.py`/`specification.py::build_prompt` (essence) |
| Couches touchées | **Prompts seulement.** Ni moteur, ni API, ni Pursuit, ni stores, ni schémas |
| Risques | Dilution des consignes de schéma par un prompt long → couvert : le schéma reste en clôture de mission, et un tour non conforme devient `failed` (garde existante de `build_turn`) ; risque mesuré au test réel |
| Étiquette | **NATURE** |

### M3 — Plusieurs lectures avant de répondre
| | |
|---|---|
| Preuve V1 | `cognitive-engine.js` §E, étapes 3 et 5 (« cartographier su/supposé/manquant », « générer plusieurs trajectoires. Pas une seule option ») |
| Existe déjà en V2 | Rien dans les prompts. À noter : le module `13_BRAINAI_REASONING` génère des « options canoniques » codées en dur — c'est un faux ami, pas ce mécanisme |
| Ce qui manque | L'ordre intérieur de produire des lectures alternatives avant de choisir sa contribution |
| À ne PAS recopier | Les 9 étapes comme *procédure affichée* (la V2 ne doit pas réciter sa méthode) ; le catalogue d'options figées du module 13 — c'est l'anti-modèle exact |
| Où il vit | Identité §E (déjà dans la v0.3) + la 2e phrase de mission conversation (« envisage plusieurs lectures… montre-les sur les choix structurants ») |
| Couches touchées | Prompts seulement |
| Risques | Verbosité (le modèle étale toutes ses lectures à chaque tour) → la mission borne : « sur les choix structurants », pas à chaque phrase |
| Étiquette | **NATURE** (le geste) + **MISSION** (quand le montrer) |

### M4 — L'arbitrage obligatoire, la prise de position
| | |
|---|---|
| Preuve V1 | `cognitive-engine.js` §C-Arbitrer (« la neutralité d'analyse est un défaut ») ; Doctrine 14 du prompt Blueprint ; sections 3 et 6 des 7 Blueprints réels |
| Existe déjà en V2 | **Rien — et pire : l'anti-mécanisme existe.** `13_BRAINAI_REASONING/arbitration.py:45-57` fabrique des justifications sur des égalités. La V2 contient un module nommé « arbitrage » qui est l'exact contraire de M4 |
| Ce qui manque | Le droit et le devoir de dire « je privilégierais la deuxième, voici pourquoi » dans le dialogue ; la clause d'honnêteté sur l'égalité réelle |
| À ne PAS recopier | L'obligation d'arbitrer *dans toutes les sections* (format Blueprint) — en dialogue, l'arbitrage vient quand il y a matière, pas à chaque tour ; et ne jamais brancher le module 13 sur la conversation |
| Où il vit | Identité §C-Arbitrer (déjà v0.3, avec la clause d'égalité) ; mission specification (« arbitrages explicites sur les choix structurants ») |
| Couches touchées | Prompts seulement. Le module 13 n'est PAS touché (il est simplement absent de la boucle conversationnelle — il l'est déjà) |
| Risques | Contradiction apparente avec « BrainAI propose, l'humain décide » → aucune : prendre position ≠ décider ; la position est une proposition motivée, la gouvernance reste intacte |
| Étiquette | **NATURE** |

### M5 — Les hypothèses explicites, offertes à la correction
| | |
|---|---|
| Preuve V1 | Prompt Blueprint (« tu les nommes explicitement en section 1 ») ; Blueprint Barrycoaching (« Hypothèses que j'ai dû poser… si l'une est fausse, je l'indiquerai ») |
| Existe déjà en V2 | Le **conteneur** existe : champ `assumptions` dans `BRIEF_SCHEMA` (`understanding.py`) et `SPEC_SCHEMA` (`specification.py`). Le **geste** manque : rien n'ordonne de les formuler comme offertes à la correction, et rien ne les fait vivre dans le dialogue |
| Ce qui manque | En conversation : marquer ses suppositions comme suppositions dans le `reply` et inviter la correction. En understanding/specification : la consigne « nommées comme telles » |
| À ne PAS recopier | La section formatée « Hypothèses » du Blueprint (c'est un format de livrable, pas un geste de dialogue) |
| Où il vit | Identité §F + §H (déjà v0.3) ; consigne `assumptions` ajoutée aux missions understanding/specification (Tâche 3 déjà consentie) |
| Couches touchées | Prompts seulement |
| Risques | Doublon bénin : le geste est dans l'identité ET la consigne de mission — accepté, c'est une redondance de renforcement, pas une contradiction |
| Étiquette | **NATURE** (le geste) + **MISSION** (le champ) |

### M6 — Les conséquences non demandées, les angles morts
| | |
|---|---|
| Preuve V1 | `cognitive-engine.js` §A (« constitutif du mandat ») et §D (double mission) ; les angles morts RGPD/vendor lock-in tissés dans chaque Blueprint réel ; la métrique « Surprise » du questionnaire terrain |
| Existe déjà en V2 | **Rien.** La preuve comportementale est faite : le doute légal de Frédérique (« pas certaine que ce soit légal ») est passé inaperçu dans la conversation du 8 |
| Ce qui manque | La chasse active à ce qui n'a pas été demandé ; le traitement immédiat d'un doute exprimé |
| À ne PAS recopier | La liste figée d'angles morts du prompt Blueprint comme *checklist récitée* — c'est la disposition qui doit vivre, la liste n'est qu'un aide-mémoire dans l'identité |
| Où il vit | Identité §A + §D (déjà v0.3, avec « un doute exprimé devient immédiatement un sujet central ») |
| Couches touchées | Prompts seulement |
| Risques | Anxiogénie (que des risques) → couvert par la double mission elle-même : opportunités ET angles morts, l'équilibre est constitutif |
| Étiquette | **NATURE** |

### M9 — Réviser ou maintenir, de façon motivée
| | |
|---|---|
| Preuve V1 | `cognitive-engine.js` §G, entier — y compris le maintien (« objections de confort ») et la suspension déclarée |
| Existe déjà en V2 | La **matière** existe : l'historique complet est relu depuis le `TurnStore` et restitué au modèle à chaque tour (`conversation.py::build_prompt`) — c'est un acquis V2 que la V1 n'avait pas (elle était one-shot !). Le **comportement** manque : rien ne dit quoi faire de cet historique quand l'humain corrige ou conteste |
| Ce qui manque | Les conditions de révision/maintien/suspension |
| À ne PAS recopier | Rien à recopier côté code : la V1 n'avait AUCUNE mécanique d'historique — c'est le cas d'école de « la V2 l'a mieux résolu » : le support technique de M9 est déjà supérieur à celui de juin |
| Où il vit | Identité §G (déjà v0.3) ; le support (TurnStore + historique) est en place et n'est pas touché |
| Couches touchées | Prompts seulement |
| Risques | Aucun identifié — c'est le mécanisme le mieux servi par l'architecture existante |
| Étiquette | **NATURE** |

## 2. Les mécanismes utiles (portés par les mêmes vecteurs, aucun coût additionnel)

| Mécanisme | Existe en V2 | Où il vit | Étiquette |
|---|---|---|---|
| M2 Pentagone-dramaturgie | Non | Identité §C (déjà v0.3) | NATURE |
| M7 Liberté de forme | **Oui — à préserver** : le `reply` de `CONVERSATION_SCHEMA` est du texte libre. Ne PAS étendre le schéma conversationnel : chaque champ ajouté est un bout de pensée compressé | Aucune action — une interdiction : schéma inchangé (déjà au périmètre) | NOUS (garde-fou de chantier) |
| M8 Conviction graduée | Non | Identité §F (déjà v0.3) | NATURE |
| M10 Test interne | Non | Identité annexe (déjà v0.3) | NATURE |

**Tension M7 résiduelle, confirmée sur l'arbre V2** : `understanding.py` impose ses 7 champs au premier contact du besoin — l'inverse du J5. Non traité dans ce chantier (le dialogue amont, libre, précède désormais le Brief : la tension est adoucie par l'architecture conversationnelle elle-même). À trancher sur preuves au chantier corpus. **Étiquette : NOUS, backlog chantier 2.**

## 3. Ce qui n'entre pas — et pourquoi c'est une décision, pas un oubli

| Élément V1 | Décision | Chantier |
|---|---|---|
| Structure Blueprint 8 sections + prompt mission | La *mission Blueprint* redeviendra une mission de production ; rien à en mettre dans le dialogue | Chantier 2 |
| Corpus 7 Blueprints + 8 contextes | Banc d'essai cognitif (décision Rose déjà actée) | Chantier 2/corpus |
| Mémoire cumulative, leçons, questionnaire terrain | L'accumulation du savoir | Chantier 3 |
| Journal v1 (grammaire auteur+action), versions d'Artifact | La V2 a ses faits `turn`/stores ; la grammaire d'auteur et le chaînage de versions nourriront le chantier 3, pas celui-ci | Chantier 3 |
| Supabase, TypeScript, one-shot, 9 questions fixes | Obsolètes — remplacés par mieux | Jamais |

## 4. Synthèse : la surface totale du chantier 1, mesurée sur l'arbre réel

**Trois fichiers de prompts** (`conversation.py`, `understanding.py`, `specification.py` — quelques lignes chacun), **un fichier déposé** (`cognitive_identity.py`), **un libellé de démo** (`composition.py`, honnêteté déjà consentie), **un paramètre** (sonnet + timeout 180), **une garde de validation** (A4-2, déjà consentie), **une analyse sans code** (A4-1). **Zéro modification** : moteur, API, Pursuit, TurnStore, schémas, UI (hors libellé démo), modules 10-16. Les six mécanismes indispensables sont TOUS portés par deux vecteurs uniquement — l'identité (nature) et trois phrases de mission (tâche). C'est la preuve d'anti-administration que demandait Frédérique : le cerveau reçoit une nature et une tâche ; l'administration reste chez nous.

**Risques transverses, tous trois bornés** : dilution du schéma par le prompt long (mesuré au test réel, garde `failed` existante) ; redondance identité/mission sur M3/M5 (renforcement accepté) ; contradiction identité globale (« fait produire ») vs mission du tour (« ne construis rien ») — résolue par l'ordre nature→tâche de `compose_prompt`, et c'est la distinction acte/produit de Rose.

**Prochaine étape selon l'ordre convenu** : vous challengez cette carte une dernière fois ; je consolide alors le prompt final ClaudeC (les tâches déjà consenties + la traçabilité mécanisme→implémentation) ; ClaudeC traduit sans inventer ; test réel — les 5 tours du scénario, jugés d'abord au comportement, ensuite seulement aux articles.
