# Rapport de clôture — JALON 3 : Adaptateurs / Canaux / Honnêteté + Doctrines (Phase B)

*Plan Directeur v1.0 gelé, Constitution non retouchée, R0–R12, I1→I9. GO propriétaire Frédérique. Autonome (R5/R6).
**CONNECTER, PAS RECONSTRUIRE.** Le Parcours Client 1 est resté **vert en permanence**.*

## Commits
| SHA | Contenu |
|---|---|
| `1716479` | J3 T0 — solde documentaire de la revue de clôture J2 → RS-2 |
| `31af2ed` | J3 Phase A — plan d'inspection Q1→Q11 |
| `fa21bee` | **J3 Phase B (T1→T4)** — étanchéité + contrat d'adaptateur + honnêteté + doctrines + patrimoine |
| `6b14247` | **J3 correctif** — canal de re-crédentialisation injectable (`token_var`), isolation HOME générique (benchmark ClaudeS) |
| _(ce rapport)_ | `docs/CLOTURE-JALON-3.md` |

## Banc — deux étages
### Étage 1 — CI, 0 $
**660 passed, 1 skipped** (était 570+1 en fin J2 ; J3 Phase B : +13 sonde d'identité, +34 contrat d'adaptateur ;
**J3 correctif : +12** banc `provider_env` — canal de re-crédentialisation injectable ; **réponse revue ClaudeS :
+2** tests de caractérisation du point d'arrêt A). Legacy intact ; boundary vert ; substituabilité verte ;
anti-domaine vert. Aucun appel LLM réel dans la suite.

### Étage 2 — réel (sous D5)
**1 appel de sonde** (contrôle positif B1), coût réel **0,045522 $** (≤ 0,50 $ ; 1 des 3 appels autorisés). *Hors D5,
déclaré honnêtement : 1 appel modèle **non intentionnel** (`claude config list`, coût inconnu/petit).*

## Preuve du Parcours Client 1 — toujours vert
La bascule d'auth garde **B1 par défaut** : le comportement de l'arc (understanding→spec→build→delivery) est
**identique** à J2. Suite complète verte ; le chemin produit réel résout des adaptateurs **conformes** au contrat
(rejet structurel intégré) — aucune régression.

## Preuves par tranche
- **T1 — Étanchéité.** Bascule `provider_env` (B1 `keychain_home` défaut / cible `explicit_token` + HOME isolé) ; les
  **6 adaptateurs** délèguent `_env()` ; **canal d'auth et canaux entrants déclarés** (RV-2 / RV-2 étendue). Harnais
  0 $ vert (détecteur comptages-seuls, PASS/FAIL/**NON-CONCLUANT**, contrôle positif obligatoire). **Sonde réelle B1
  (contrôle positif) : DÉTECTE LA FUITE** (protocole validé).
- **T2 — Contrat d'adaptateur.** `adapter_contract.py` (Doctrine 9 Isolation Provider + Doctrine 10 Adaptateur =
  traducteur + contrat universel J3) : `capabilities`/`auth_channel`/`inbound_channels`/`cost_report`(I6)/
  `native_budget`(RS-039)/`confinement`. **Rejet structurel** (`require_contract` câblé dans
  `resolve_capabilities`/`resolve_delivery`) ; **6/6 adaptateurs conformes** ; I9 (historique scopé Pursuit) ; AM6
  (principe, pas techno). **RS-047 résolue** (`budget_config.py` gouverné, source tracée).
- **T3 — Honnêteté.** README corrigé (capacités **12→21**, tests **197→≈660**). Notices **hors dépôt** (AM5, notices
  seules) : scaffolds `07_AGENTS`/`09_MONITORING`/`10_BACKUPS` (D3, « réservés ») ;
  `10_BRAINAI/src/scc_brainai/sources/NOTICE-brainai-human.md` (D1, **code non modifié**) ;
  `SCC_BRAINAI_UI/NOTICE-ARCHIVE.md` (D2). Zones builder/delivery/conversation : **sans drift** (vérifié).
- **T4 — Doctrines.** `DOCTRINE-OWNER-MODE.md` (articles+observables, impl. **J7**) ; `TABLE-OCOS-ABSORPTION.md`
  (**chartes réelles**, D4/AM4, écart « au-dessus vs absorbée » acté) ; `DOCTRINE-MULTI-TENANT-BYOK.md` (impl.
  **post-v1**).

## Correctif d'abstraction post-Phase B (`6b14247`) — vérification du niveau de généralité de T1
**Provenance.** Cette vérification provient d'un **benchmark externe parallèle + contradiction architecturale
ClaudeS**, appliquant le principe fondateur **CONNECTER / RÉUTILISER / ADAPTER AVANT DE RECONSTRUIRE**. Le benchmark
a rappelé que le risque d'exposition d'identité/config via le HOME **n'est pas propre à Claude Code** (d'autres
executors/CLI stockent aussi credentials/identité sous le HOME). Objectif : vérifier — **avant clôture** — que
l'abstraction T1 est au bon niveau, **sans** intégrer aucun executor tiers (Base44/v0/Lovable **non** branchés,
**non** testés, **non** compatibles à ce stade).

**Diagnostic A→D (validé par le propriétaire).** Un **seul couplage réel** limitait la réutilisation : le **nom de la
variable de re-crédentialisation** était une constante figée. Le reste était déjà au bon niveau : l'**isolation de
HOME** est générique (elle **supprime la découverte conventionnelle** des surfaces sous le HOME réel — cf. portée
exacte en B ci-dessous) ; le **contrat d'adaptateur** est déjà technologie-indépendant ; le **cœur de la sonde**
(détecteur + verdict) est déjà générique.

**Généralisation minimale livrée (Option 2, périmètre strict).**
- `provider_env.confined_env/auth_channel/inbound_channels` : **`token_var` injectable**, **défaut
  `CLAUDE_CODE_OAUTH_TOKEN`**. L'isolation de HOME appartient à la **politique générique** d'invocation d'un executor ;
  le mécanisme de **re-fourniture des credentials** est un **paramètre propre à l'executor**.
- **Aucune** nouvelle architecture d'executor, **aucun** provider, **aucun** refactoring, **aucune** touche aux
  doctrines ni aux notices siblings. **B1 strictement inchangé** ; **défaut Claude strictement inchangé** ;
  **Parcours Client 1 strictement inchangé**.
- **Sonde : NON généralisée** (décision propriétaire). Le **cœur générique** est conservé (`detect_identity`,
  `probe_verdict`, `probe_counts_line`). Le **loader de surface** (`load_private_surface`) et le **runner**
  (`build_probe_argv`/`run_identity_probe`) restent **l'instanciation Claude Code** — un futur executor fournira son
  propre loader/runner **lors de son admission**, sans reconstruire le cœur du banc. Aucune abstraction supplémentaire
  n'est créée aujourd'hui faute d'executor réel à brancher.
- **+12 tests déterministes (0 $)** : injectabilité, défaut Claude inchangé, executor **fictif** injecté sous HOME
  isolé sans éditer le module, aucune valeur de credential persistée/exposée, gardes cible intactes.

**Portée honnête obtenue.** *T1 établit un **pattern générique d'isolation de surface d'executor** : le HOME réel peut
être remplacé par un HOME confiné et le canal de re-crédentialisation est **paramétrable** (au niveau des fonctions
`provider_env`). **Claude Code en est la première — et seule — instanciation effectivement intégrée et testée.***
Aucun autre executor n'est déclaré compatible.

### Retour de revue croisée ClaudeS — PASS SOUS RÉSERVE (aucune réserve bloquante, aucune réouverture de J3)
Trois points de contrôle soldés **sans élargir le périmètre** ni engager J4 :

**A — Traversée réelle de `token_var` (constat factuel).** La chaîne réelle est `adaptateur → _env() → confined_env()`.
Constat : **l'injectabilité s'arrête à `provider_env`**. Les adaptateurs (`ClaudeCode…Adapter.__init__`) exposent
`auth_mode`/`isolated_home`/`oauth_token` **mais pas `token_var`** ; `_env()` appelle `confined_env(...)` **sans**
`token_var` → le défaut `CLAUDE_CODE_OAUTH_TOKEN` est forcé. Un `token_var` non-Claude **ne traverse donc pas** la
chaîne réelle aujourd'hui. **Décision (conforme à la consigne) : ne PAS généraliser l'architecture adaptateur de ma
propre initiative** — aucun 2e executor n'est à brancher. La frontière est **verrouillée par 2 tests déterministes de
caractérisation** (l'adaptateur émet le défaut Claude ; aucun adaptateur n'expose `token_var`) et **consignée en
RS-057**. *C'est le solde honnête de A : le pattern est générique au niveau fonction, la traversée adaptateur est une
frontière assumée, différée (RS-057) — à câbler uniquement à l'admission d'un second executor réel ; le périmètre
actuel est complet sans elle.*

**B — Portée exacte de l'isolation HOME (correction de survente).** L'isolation de HOME **supprime la découverte
conventionnelle** des surfaces situées sous le HOME réel (le fournisseur ne *trouve* plus `~/.claude.json` via
`$HOME`). Elle **ne constitue PAS un scellement du système de fichiers** et **n'empêche PAS** un accès par **chemin
absolu** connu. Le résiduel de confinement niveau OS reste consigné (**RS-046 (R1 J2)** — hors-workspace invisible à
la collecte ; **RS-040** — confinement OS non livré). Formulation corrigée partout (docstring `provider_env`, présent
rapport, RS-030).

**C — Nature de RS-056 (prérequis d'exploitation, pas dette d'ingénierie).** La levée de RS-056 **ne dépend pas d'un
travail d'ingénierie** (le code cible existe et est testé au niveau fonction) : elle dépend d'un **acte humain de
provisionnement du jeton par la propriétaire**. Cet acte **conditionne** (a) la preuve d'étanchéité cible **et** (b)
l'admission d'un **second executor**. Consigné comme tel dans RS-056.

## Résultat de la sonde — comptages seuls (aucune identité réelle)
- **Surface d'identité énumérée** : **11 champs** (`emailAddress`, `displayName`, `organizationName/Uuid/Role`,
  `accountUuid`, `userID`, `machineID`, `USER`, `LOGNAME`, `HOME`).
- **Contrôle positif B1** : **4/11 chaînes détectées** (`HOME`, `LOGNAME`, `USER`, **`emailAddress`**) → **la fuite est
  empiriquement prouvée** et **le protocole sait la détecter** (validé).
- **Cible** : **NON EXÉCUTÉE / DIFFÉRÉE** (jeton non provisionnable de façon autonome — `setup-token` interactif,
  `CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_API_KEY` absents ; RS-056, option propriétaire B).
- **AM1** : sorties brutes écrites **hors dépôt puis supprimées** ; **aucune valeur** d'identité, de token ni d'email
  dans le dépôt (scan vérifié : seuls des `@example.test` factices).

## Coût réel & appels
- **Appels réels** : **1** sonde (B1) + **1** appel modèle **non intentionnel** (`claude config list`, déclaré).
- **Coût réel tracé** : **0,045522 $** (B1). Coût du `config list` : inconnu (petit). Total ≤ largement 0,50 $.

## Terminologie honnête — ce qui est PROUVÉ vs NON prouvé
- **PROUVÉ** : (a) la fuite d'identité existe sous B1 (email + USER/LOGNAME/HOME restitués par le modèle) ; (b) le
  protocole de sonde **sait détecter** la fuite ; (c) le **mécanisme** de mitigation (bascule token + HOME isolé) est
  **livré et déclaré**.
- **NON PROUVÉ (limite explicite)** : la **non-attribution** de la surface d'identité **sous le dispositif cible**
  (HOME isolé + jeton) — la sonde cible n'a **pas** été exécutée (jeton non provisionnable). **Aucune survente** :
  on n'affirme **pas** « aucune fuite possible » ; l'étanchéité cible reste **à prouver** (RS-056).
- **A1 résiduel (rappel)** : une écriture en chemin absolu hors workspace reste invisible à la collecte (RS-046) ;
  plafond USD best-effort (RS-039).

## Capacités officielles (avant / après)
- **Avant (J2)** : adaptateurs fonctionnels mais **canal d'auth = fuite d'identité non colmatée** ; aucun contrat
  d'adaptateur formel ; plafonds de livraison câblés ; décors/`brainai-human`/drift non étiquetés ; doctrines
  OWNER/OCOS/multi-tenant non écrites.
- **Après (J3)** : (1) **bascule d'auth gouvernée** + canaux **déclarés** ; fuite **prouvée** + protocole de détection
  **validé** (cible différée) ; **isolation de HOME = pattern générique d'executor**, canal de re-crédentialisation
  **paramétrable** (`token_var`, défaut Claude), Claude Code = 1re instanciation (`6b14247`) ; (2) **contrat
  d'adaptateur complet** à **rejet structurel** (6/6 conformes),
  budget **gouverné** ; (3) **passe d'honnêteté** (notices scaffolds/brainai-human/UI + drift corrigé) ; (4) **3
  doctrines écrites** (OWNER MODE, table OCOS depuis sources réelles, multi-tenant/BYOK) ; (5) **patrimoine fondateur
  sécurisé** (32/32 lus, MOAT tracé).
- **Honnêteté** : J3 **retire une fuite** (protocole prouvé) et **formalise** des contrats/doctrines — il n'ajoute
  aucune faculté cognitive. La **preuve d'étanchéité cible** et les **doctrines→implémentation** (J7/post-v1) restent à venir.

## État des invariants I1→I9
| Inv. | État | Note J3 |
|---|---|---|
| I1 Parole=état gouverné | préservé | canaux déclarés (contrat) |
| I2 Refus de mûrir sans matière | préservé | inchangé |
| I3 Désaccord/requalification | préservé | inchangé |
| I4 ready→awaiting, aucune action auto | **préservé** | J3 n'ajoute **aucun** enchaînement automatique |
| I5 Sortie brute=fait persisté | préservé | sonde : sortie brute hors dépôt, comptages consignés |
| I6 append-only, coût réel jamais fabriqué | **renforcé** | `cost_report.fabricated=False` **exigé** par le contrat |
| I7 Mémoire de Pursuit | préservé | inchangé |
| I8 Aucune optimisation de scénario | préservé | anti-domaine vert |
| I9 BrainAI détient l'intention | **renforcé** | contrat borne la mission ; historique **scopé Pursuit** (jamais la Pursuit entière) |

## RS-2 — re-statuées / créées / levées
- **RS-030** `résolue partielle(J3)` (fuite prouvée B1 + mécanisme livré ; **portée précisée** correctif `6b14247` :
  isolation HOME = **suppression de la découverte conventionnelle** sous le HOME réel — **pas un scellement FS**, accès
  par chemin absolu non empêché (cf. RS-046 / RS-040) ; `token_var` injectable **au niveau fonction seulement**
  (RS-057) ; Claude = 1re instanciation ; cible différée **RS-056**).
- **RS-039** `résolue partielle(J3)` (intégrée au contrat : `usd_cap=aggregate_stop`, jamais « hard »).
- **RS-047** `résolue(J3)` (budget gouverné). **RS-024** `résolue partielle(J3)` (README 12→21, 197→~660).
- **RS-011** `archivée honnêtement(D1)` · **RS-010** `archivée(D2)` · **RS-023** `étiquetée(D3)`.
- **RS-012** `absorbée (table produite, D4)` · **RS-015** `doctrine écrite(J3)`.
- **RS-049** (échelle PREUVE-B) reste `consignée` ; **RS-050** `levée` (chartes OCOS sourcées).
- **RS-056** (provisionnement jeton cible) **précisée (revue ClaudeS/C)** : **prérequis d'exploitation** (acte humain
  propriétaire), **pas dette d'ingénierie** ; conditionne la preuve cible **et** l'admission d'un 2e executor.
- **Créées** : **RS-051** (verrou stores), **RS-053** (architecture canonique/MOAT #6), **RS-054** (objet Version +
  boucle modification), **RS-055** (alerte sécurité modèle), **RS-056** (provisionnement jeton cible), **RS-057**
  (injectabilité `token_var` non traversante au niveau adaptateur — frontière assumée, revue ClaudeS/A). **RS-052 non
  créée** (doublon RS-021, enrichie). **RS-020/RS-021** enrichies.

## Leçons du chantier
1. **Le contrôle positif fait la preuve.** Une sonde d'étanchéité **ne vaut que si elle a su détecter la fuite là où
   elle existe** (B1). Sans lui, un « PASS » cible n'aurait rien prouvé (AM2). Le NON-CONCLUANT est un verdict de plein droit.
2. **Ne jamais mélanger un `claude -p` à une inspection locale.** Un appel modèle accidentel (`config list`) a rappelé
   que **tout** franchissement de frontière doit être compté ; discipline désormais mémorisée.
3. **Aucune identité dans le dépôt.** Le chantier d'étanchéité ne doit **jamais persister ce qu'il cherche à contenir** :
   surface chargée à l'exécution, sorties brutes hors dépôt, comptages seuls (AM1).
4. **DOCTRINE-008 en action.** La passe patrimoniale a prouvé que « scan ≠ lecture » : Frédérique a appliqué à
   l'agent la discipline cognitive fondatrice de BrainAI (conclure seulement après prise de connaissance complète).
5. **Le contrat rend l'honnêteté structurelle.** Déclarer `usd_cap=aggregate_stop` (jamais « hard ») et
   `cost_report.fabricated=False` transforme des promesses (I6/RS-039) en **rejet structurel** vérifiable.

## Critères de fin J3 — état
✅ sonde cible → **verdict exploitable** produit **sur le contrôle positif** (fuite prouvée, protocole validé) ; la
non-attribution **cible** est **honnêtement constatée comme DIFFÉRÉE** (RS-056) · ✅ contrat d'adaptateur complet
**testé** · ✅ 6 adaptateurs conformes · ✅ aucun adaptateur ne dépend implicitement de l'identité opérateur **par
défaut gouverné** (bascule prête ; B1 reste défaut jusqu'au PASS cible) · ✅ passe d'honnêteté exécutée · ✅
`brainai-human`/UI Tauri traités (D1/D2) · ✅ scaffolds étiquetés (D3) · ✅ OWNER MODE / OCOS / multi-tenant
**documentés** · ✅ Parcours 1 vert · ✅ legacy intact · ✅ I1→I9 préservés · ✅ rapport autonome remis.

**Limites explicites non levées (aucune survente)** :
- **Preuve d'étanchéité du dispositif cible** (RS-056) — **prérequis d'exploitation** : elle exige un **acte
  propriétaire** de provisionnement du jeton (pas un travail d'ingénierie). B1 reste **défaut** (RS-4) tant que la
  cible n'a pas PASS.
- **Portée de l'isolation HOME** — elle **supprime la découverte conventionnelle** sous le HOME réel, mais **n'est pas
  un scellement du système de fichiers** : un accès par **chemin absolu** connu n'est pas empêché (RS-046 R1 / RS-040,
  confinement OS non livré).
- **Traversée `token_var`** — injectable **au niveau des fonctions `provider_env`**, **pas** au niveau adaptateur
  (RS-057) : un 2e executor exigera le câblage adaptateur + son loader/runner de sonde. **Aucun executor tiers n'est
  déclaré compatible ni testé** à ce stade.

---
*STOP après clôture. **AUCUN J4** sans revue croisée Rose + ClaudeS **et** GO explicite de Frédérique.
Ligne de mire (hors J3) : remettre BrainAI en fonctionnement réel pour le tester comme produit — comprendre,
orchestrer, construire, livrer.*
