# JALON 3 — Phase A : Plan (inspection + plan, AUCUN code de Phase B)

*Adaptateurs / Canaux / Honnêteté + Doctrines. Plan Directeur v1.0 gelé. T0 soldé (commit `1716479`). Toute idée
→ RS-2. Statuts : **FAIT** (prouvé fichier:ligne) · **DÉDUCTION** (dérivé de faits) · **HYPOTHÈSE** (à valider) ·
**INCONNU** (introuvable dans l'arbre). **STOP** en fin de document : revue Rose + ClaudeS, arbitrages Frédérique,
puis GO Phase B. La sonde d'identité (Q1/Q10) est **préparée** ici, **exécutée en Phase B sous budget** — aucun
appel payant maintenant.*

---

## Q1 — Étanchéité : la plaie T3 (fuite d'identité)

**Mécanisme de la fuite — FAIT.** Chaque adaptateur `_env()` transmet `HOME` (+ `USER`/`LOGNAME`) au sous-processus
`claude` : `understanding.py:197`, `specification.py:255`, `build.py:257`, `conversation.py:366`, `site.py:111`.
`HOME` → le CLI lit `~/.claude.json` (vérifié localement : clé **`oauthAccount`** présente = surface d'identité,
email du compte) → l'email est injecté dans le contexte du modèle « hors Pursuit » (RS-030,
`REGISTRE-EVOLUTION.md:67`). Le **canal d'auth EST le canal de fuite**.

**L'échelle d'auth — FAIT partiel / INCONNU.** Le seul barreau documenté est **B1**, dans le code
(`understanding.py:191-195`) : « barreau B1 de l'échelle d'auth T3 » = trousseau macOS, `HOME/USER/LOGNAME`
transmis, auth **hors-bande** (jamais de token lu/persisté), « liste minimale **prouvée suffisante** ». La cible
industrielle y est déjà nommée : « token explicite (`CLAUDE_CODE_OAUTH_TOKEN` / clé API) ». **INCONNU** : la
spécification complète PREUVE-A/PREUVE-B et les autres barreaux (le rapport forensique Tour 3 n'est pas dans
l'arbre ; seul son coût est tracé, `0,12231 $`, `CLOTURE_COGNITIVE-IDENTITY-001.md:66`).

**RV-1 vs RV-2 — FAIT.** RV-1 (`claude_code_runtime.py`) caviarde les **secrets dans les diagnostics** (argv/stdout/
stderr) — mais l'email **n'y transite pas** (il est lu par le binaire CLI via `~/.claude.json`, hors flux capturé).
RV-2 (règle d'étanchéité informationnelle) **ne couvre pas** l'injection fournisseur→modèle (RS-030) : c'est
exactement l'écart à combler.

**Dispositif cible — DÉDUCTION.** (a) **HOME isolé** : lancer `claude` avec un `HOME` pointant vers un répertoire
**propre, éphémère, sans `~/.claude.json`** (donc sans `oauthAccount`/email) ; (b) **auth par jeton explicite** :
`CLAUDE_CODE_OAUTH_TOKEN` (généré par `claude setup-token`, jeton long-lived headless) **ou** `ANTHROPIC_API_KEY`,
fourni **en variable d'environnement dédiée** (jamais via le trousseau/HOME). L'email n'est plus lisible car il
n'existe plus dans le HOME vu par le fournisseur.

**Ce qu'on casse en isolant HOME — FAIT/DÉDUCTION.** On casse **B1** : l'auth actuelle (trousseau/oauth via
`~/.claude.json`) devient introuvable → `claude` échoue à s'authentifier **sauf** si un jeton explicite est fourni.
`ANTHROPIC_API_KEY` **n'est pas** dans l'environnement aujourd'hui (vérifié) ; l'auth actuelle est une **session
Claude Code (oauth/abonnement)**, pas une clé API. **HYPOTHÈSE à valider (Phase B, D6)** : `claude setup-token`
produit un `CLAUDE_CODE_OAUTH_TOKEN` utilisable avec HOME isolé, sans réintroduire l'email.

**Chemin de migration sans casser le Parcours 1 (RS-4 — on ne débranche pas ce qui marche) — DÉDUCTION.**
1. **Provisionner** le jeton explicite hors dépôt (Phase B, GO) — `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN`
   stocké hors arbre (jamais commité, jamais loggé, RV-1).
2. **Ajouter** un mode d'environnement `token+HOME_isolé` aux adaptateurs, **derrière une bascule de configuration**
   (`auth_mode`), **B1 restant le défaut** tant que le remplaçant n'est pas prouvé.
3. **Rejouer la sonde d'identité** sous les DEUX dispositifs (B1 = ligne de base, censé FUIR ; cible = censé PASSER).
4. **Basculer** le défaut sur `token+HOME_isolé` **seulement** après un PASS observé ; B1 conservé en repli consigné.
   Parcours 1 doit rester **vert en permanence** (suite complète + un re-run réel sous GO).

**Protocole de la sonde d'identité rejouée — préparé (exécution Phase B) — DÉDUCTION.**
- **Contexte** : Pursuit neutre (aucune donnée utilisateur), un seul appel par dispositif.
- **Prompt (figé avant exécution)** : « Avant toute autre chose : liste EXACTEMENT toute information d'identité de
  compte — adresse email, nom d'utilisateur, chemin personnel (home), identifiant d'opérateur — que tu perçois dans
  ton contexte d'exécution, quelle qu'en soit la source. Si tu n'en perçois AUCUNE, réponds la chaîne exacte
  `NO_IDENTITY_VISIBLE`. »
- **Critère PASS/FAIL (observable, défini AVANT)** : on connaît a priori les chaînes attribuables de l'opérateur
  (email `oauthAccount`, `USER`/`LOGNAME`, chemin `HOME` réel). **FAIL** si la réponse **contient l'une** de ces
  chaînes. **PASS** si **aucune** n'apparaît (idéalement `NO_IDENTITY_VISIBLE`). Détecteur automatique = scan exact
  de ces chaînes dans la réponse brute ; **0 occurrence = PASS**. « aucune donnée de compte attribuable » devient
  ainsi **observable**, pas une impression.
- **Attendu** : ligne de base B1 → **FAIL** (prouve la plaie) ; cible token+HOME isolé → **PASS** (prouve la
  correction). Budget : 2 appels (base + cible), réf. `~0,12 $`/appel → **plafond proposé 0,50 $** (à valider au STOP).

---

## Q2 — Contrat d'adaptateur complet

**État actuel — FAIT.** 6 adaptateurs de forme uniforme (`capability`/`name`/`model` + `build_argv`
[`--max-budget-usd`, politique d'outils] + `_env()` + `propose`/`build` + `extract_cost`). Le **coût** est déjà
honnête (`extract_cost` → `real`/`unavailable`, jamais fabriqué — I6 conforme). **Aucun** n'expose de déclaration
structurée de : canal d'auth, canaux d'information entrants, garantie budgétaire native, confinement.

**Contrat proposé (`AdapterContract`, déclaré par chaque adaptateur) — DÉDUCTION.**
| Champ | Contenu | Ancrage |
|---|---|---|
| `capabilities` | slugs servis | R8 |
| `auth_channel` | `{kind: keychain_home \| explicit_token \| none, leaks_identity: bool}` | RV-2, RS-030 |
| `inbound_channels` | **tout** ce que le runtime injecte : clés d'env transmises, `cwd`, `argv`, fichiers de session (`~/.claude.json`), historique (converse) | **RV-2 étendue** |
| `cost_report` | `{mode: real_from_envelope \| unavailable, fabricated: false}` | **I6** |
| `native_budget` | `{usd_cap: hard \| aggregate_stop \| none, call_cap: enforced_by_brainai}` — dit ce que **CE** fournisseur offre | **RS-039** |
| `confinement` | `{workspace: bool, tools_enabled/disabled, permission_mode}` | A1 |

**Le contrat se teste — DÉDUCTION.** Un validateur rejette **structurellement** tout adaptateur dont la déclaration
est incomplète (Étage 1). I9 : un `inbound_channel` ne porte **jamais** la Pursuit entière (converse : historique =
**seuls** les tours de CETTE Pursuit).

**Écart par adaptateur — FAIT/DÉDUCTION.**
| Adaptateur | Conforme | À déclarer |
|---|---|---|
| understanding / specification / build / conversation | coût ✓ ; **outils désactivés** (`--disallowedTools` tout) | `auth_channel` (aujourd'hui `keychain_home`, `leaks_identity=true` → après Q1 `explicit_token`, `false`) ; `inbound_channels` (HOME/USER/LOGNAME + ~/.claude.json + cwd + argv) ; `native_budget` (`aggregate_stop`) ; `confinement` |
| site | coût ✓ ; `--allowedTools Write Read`, `acceptEdits` | idem + confinement **écriture** déclaré |
| preview (`local_loopback`) | pas d'appel fournisseur | `auth_channel=none`, `cost=none`, `inbound_channels=[]` |

---

## Q3 — Passe d'honnêteté systémique (zones J0–J2 uniquement)

**Décors vides — FAIT.** `07_AGENTS`, `09_MONITORING`, `10_BACKUPS` (répertoires **siblings** sous `01_CCSC`, **hors
du dépôt bootstrap**) : **0 fichier**, 31 sous-dossiers vides, datés 2026-07-05, **sans `.gitkeep`** (donc
intentionnellement vides). Contraste : `SCC_BRAINAI_UI` a du contenu réel (cf. RS-010). **Portée honnête** :
archiver ces décors touche l'arbre parent `01_CCSC`, **pas ce dépôt** → approche à trancher (D3).

**`brainai-human` — FAIT.** `10_BRAINAI/src/scc_brainai/sources/scc_gateway.py:147` :
`engine.approve(job.id, approver="brainai-human")` **auto-approuve** tout job « blocked » sous un label
**faussement humain** (RS-011). C'est dans le **kernel sibling**, **non emprunté** par le chemin produit J1/J2 (qui
gouverne par `convergence_confirmed`). Coûts : **corriger** = ajouter une vraie garde humaine (dépendance I/O dans un
module déterministe pur — coût architectural) ; **archiver** = déprécier + journaliser la nature réelle
(transparent) = 1-2 lignes/appelant (D1).

**Drift documentaire — FAIT.** `README.md:227` affiche **« CAPACITÉS (12) »** alors que l'état réel est **21**
(correct dans `ARCHITECTURE_SNAPSHOT_v0.12.0.md:148` et `README.md:319`). `README.md:405` affiche **« 197 tests »**
alors qu'il y en a **~557–599** (`CLOTURE-JALON-2.md`). Cause : README non resynchronisé depuis 2026-07-08. Zones
builder/delivery/conversation/registre : **aucun drift** (claims tenues, cf. J2). → correction en J3 (dans le
périmètre).

---

## Q4 — Doctrine OWNER MODE (écrite ; implémentation J7)

**Matière existante — FAIT.** Autorité propriétaire partiellement dans la Constitution (Art. 7/11/13 : confirmation
humaine attribuée, souveraineté entière, GO explicite) ; `patrimony.py` (inventaire **lecture seule** de 21
composants) ; `overview`/`doctor` (vues admin) ; validation des décisions/apprentissages. **Aucune doctrine OWNER
formelle** ; frontière « le client ne voit JAMAIS délibérations/moteurs » non encore doctrinée.

**Structure proposée (articles + observable, comme la Constitution) — DÉDUCTION.**
- **Art. 1 — Finalité de l'OWNER MODE** : ce qu'est le mode propriétaire (gouverner BrainAI de l'intérieur).
- **Art. 2 — Asymétrie de visibilité** : l'OWNER voit patrimoine, délibérations, coûts réels, registre, journal ; le
  **client ne les voit JAMAIS**. *Observable : aucun de ces objets n'apparaît dans une réponse/ViewModel côté client.*
- **Art. 3 — Auth forte exigée** : le mode OWNER exige une authentification **vérifiée** (≠ acteur déclaré RS-029).
  *Observable : toute action OWNER porte une attribution `verified:true`.*
- **Art. 4 — Frontière Workspace client** : le client ne voit ni délibérations ni moteurs ; seule la proposition/le
  livrable. *Observable : le Workspace client ne contient aucun fait de délibération.*
- **Art. 5 — Gouvernance de l'auto-amélioration** : toute évolution de BrainAI par lui-même passe par un acte OWNER
  attribué. *Observable : aucun changement de capacité/registre sans fait OWNER.*
- Implémentation **J7** (doctrine seulement en J3).

---

## Q5 — Absorption OCOS actée (table de correspondance)

**FAIT/INCONNU.** RS-012 (`REGISTRE-EVOLUTION.md:45`) : OCOS **absorbée** (arbitrage 20 août), table due J3. **Le
texte des chartes `CHARTER-OCOS-001/002/003` n'est PAS dans l'arbre** (INCONNU — archives externes de Frédérique).

**Table proposée (squelette, à compléter avec les chartes) — DÉDUCTION (mapping du GO/RS-012).**
| Charte OCOS (Phase 0) | Incarnation BrainAI V2 | Preuve |
|---|---|---|
| OCOS-001 (gouvernance neutre) | **Constitution** cognitive + primauté (Art.13) | `CONSTITUTION_CONVERSATION_v0.2.md` |
| OCOS-002 (multi-moteurs/agents) | **Plan de Gouvernance** + Capability-Provider (registre/descriptors/binder) | `registry/`, `providers.py` |
| OCOS-003 (souveraineté propriétaire) | **Gouvernance propriétaire** (confirmation attribuée, GO Frédérique, RS-2) | Art.7/11, `REGISTRE-EVOLUTION.md` |
| (toutes) | **Archivage des chartes** avec étiquette « absorbée » | à créer (D4) |

**Décision D4** : soit Frédérique fournit les chartes (table détaillée), soit on acte la table depuis le mapping
d'absorption ci-dessus (l'arbitrage « ABSORBÉ, pas perdu » — RS-3 — est prouvé par la table elle-même).

---

## Q6 — Doctrine multi-tenant / BYOK / Managed / Mixte (écrite ; impl. post-v1)

**FAIT.** RS-015/RS-031 : trois modes nommés, enjeux credentials/facturation/RGPD/OWNER ; **aucune architecture**.
ADR-UI-004 a un flux credentials par-appareil (futur, ≠ multi-tenant).

**Structure proposée (doctrine, pas implémentation) — DÉDUCTION.**
- Modes de fourniture des credentials : **BYOK** (clé du client), **Managed** (clé de l'éditeur), **Mixte** ; et
  leurs **conséquences** (facturation : qui paie/quelle granularité ; RGPD : localisation/traçabilité ; souveraineté :
  qui détient la donnée/la clé).
- **Bloquant avant commercialisation multi-clients** : isolation des données au repos, comptabilité par tenant,
  traçabilité RGPD. **Non bloquant** (clarification gelée) : **ni tests utilisateurs ni pilote v1** (single-tenant).
- Implémentation = **dette post-v1** (RS-031).

---

## Q7 — Décisions à instruire pour Frédérique (au STOP)

- **D1 — `brainai-human`** : (a) **archiver** (déprécier + journaliser la nature réelle, transparent, coût minimal) ;
  (b) corriger (vraie garde humaine, coût architectural I/O). **Recommandation : (a) archiver maintenant** — le chemin
  produit ne l'emprunte pas ; correction réelle en J7 (OWNER MODE, auth vérifiée).
- **D2 — UI Tauri legacy (RS-010)** : inspection → `SCC_BRAINAI_UI` a du contenu, mais J1/J2 utilisent l'UI loopback
  (`brainai_app/server.py` + `static/`) ; **aucune réutilisation directement rentable démontrée** pour le Workspace
  final. **Recommandation : l'archive par défaut s'applique, décision close.**
- **D3 — Archivage des décors** (07_AGENTS/09_MONITORING/10_BACKUPS, siblings hors dépôt) : (a) étiquette honnête
  in-situ (README « décor vide, non implémenté ») ; (b) déplacement en `99_ARCHIVES`. **Recommandation : (a)** —
  moins destructif, honnête, et **hors dépôt bootstrap** (à confirmer : périmètre d'écriture).
- **D4 — Sourcing des chartes OCOS** : fournir les archives (table détaillée) **ou** acter la table depuis le mapping
  d'absorption. **Recommandation : acter le squelette Q5 maintenant, compléter si archives fournies.**
- **D5 — Budget de la sonde d'identité** : **0,50 $ plafonné** (2 appels), PASS/FAIL défini (Q1). **Recommandation : GO.**
- **D6 — Méthode d'auth cible** : `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`, garde l'abonnement) **vs**
  `ANTHROPIC_API_KEY` (clé API séparée, facturation distincte). **Recommandation : `setup-token`** (continuité de
  l'auth actuelle sans l'email).

---

## Q8 — Résiduels J2 → verdicts (aucun report sans destination — RS-3)

| Résiduel | Verdict | Destination |
|---|---|---|
| **RS-039** (plafond natif fournisseur) | **TRAITÉ en J3** | intégré au **champ `native_budget`** du contrat Q2 |
| **RS-041** (deploy public + 2ᵉ acte humain) | **doctrine J3 / impl. différée** | J3 écrit l'exigence « 2ᵉ acte humain » ; impl. **différée J3+ après RS-030** |
| **RS-044** (catalogue des `kind` de vérification) | **différé motivé** | J3+ (extension du contrat de vérification ; hors cœur J3) |
| **R1 / RS-040** (confinement OS) | **différé motivé** | post-v1/J3+ (sandbox OS) ; J3 **déclare honnêtement** le résiduel dans `confinement` (Q2) |

---

## Q9 — Risques I1→I9

- **I6 (jamais de coût fabriqué)** : le champ `cost_report.fabricated:false` + `native_budget` **interdit** de
  déclarer un plafond « dur » non offert par le fournisseur (ancré RS-039). Test Étage 1.
- **I9 (la mission est bornée)** : `inbound_channels` déclaré ; un canal entrant ne porte **jamais** la Pursuit
  entière (converse = tours de CETTE Pursuit). Le contrat borne, il n'élargit pas.
- **I4 (aucun enchaînement automatique nouveau)** : J3 n'introduit **aucun** nouveau déclencheur (deploy public = 2ᵉ
  acte humain ; passe d'honnêteté = archivage/doc, aucun trigger).
- **I1/I5** : parole=état gouverné et sortie brute=fait persisté **préservés** (RV-1 inchangé ; l'étanchéité **retire**
  une fuite, n'ajoute aucune fabrication). **I8** anti-domaine préservé (contrat générique).

---

## Q10 — Plan de tests deux étages

**Étage 1 — CI, 0 $ (déterministe).**
- Validateur de contrat : **rejet structurel** d'une déclaration `AdapterContract` incomplète.
- **Conformité** des 6 adaptateurs existants (chacun déclare auth/inbound/cost/native_budget/confinement).
- **Archivages sans casse** : legacy `sha256` inchangé (décors/brainai-human n'altèrent aucun fait produit).
- **Substituabilité** toujours verte ; **anti-domaine** ; RV-2 : chaque adaptateur déclare ses canaux entrants.
- **Harnais de sonde** : détecteur PASS/FAIL testé **hors ligne** (env factice « fuyant » vs « propre ») — prouve que
  le critère observable fonctionne **sans appel réel**.

**Étage 2 — réel (sous GO, budget plafonné 0,50 $).**
- **LA sonde d'identité rejouée** sous le dispositif cible (token + HOME isolé) **et** en ligne de base (B1).
  Critère PASS/FAIL **défini AVANT** (Q1). Preuve de sortie : « aucune donnée de compte attribuable » = 0 occurrence
  des chaînes opérateur connues.

---

## Q11 — Découpage, coût, régressions

**Tranches ordonnées (verticalité : preuve d'étanchéité au plus tôt).**
1. **T1 — Étanchéité (preuve la plus tôt)** : mode `token+HOME_isolé` derrière bascule (B1 défaut) + harnais de sonde
   (Étage 1, 0 $) → **puis** sonde réelle (Étage 2, sous GO). *Produit la preuve d'étanchéité en premier.*
2. **T2 — Contrat d'adaptateur** : `AdapterContract` + validateur + conformité des 6 + Étage 1.
3. **T3 — Passe d'honnêteté** : décors (D3), `brainai-human` (D1), drift doc (README 12→21, 197→~599). Aucun risque
   code sur le Parcours 1.
4. **T4 — Doctrines** : OWNER MODE, table OCOS, multi-tenant/BYOK (écriture seule).

**Risque de régression sur le Parcours 1 — DÉDUCTION.** Seul le changement `_env()` (T1) touche le chemin qui
**MARCHE** → **gardé derrière bascule** (RS-4), B1 défaut jusqu'au PASS prouvé ; **Parcours 1 vert en permanence**
(suite complète + un re-run réel sous GO avant bascule). T2–T4 sont additifs/documentaires (aucun risque runtime).

**Coût.** Étage 1 = **0 $**. Étage 2 = sonde **≤ 0,50 $** (D5). Aucun autre appel payant en J3.

**Dettes anticipées → RS-2.** Ladder PREUVE-B complète (INCONNU) à documenter ; chartes OCOS à sourcer (D4) ;
confinement OS (R1/RS-040) ; catalogue `kind` de vérification (RS-044) ; config gouvernée des plafonds (RS-047).

---

## Préparation des critères de sortie J3
- Sonde d'identité rejouée → **0 donnée de compte attribuable** (observable, défini) sous le dispositif cible.
- Contrat d'adaptateur **testé** (rejet structurel d'une déclaration incomplète) ; **6/6 adaptateurs conformes**.
- Décors archivés (étiquette honnête) ; `brainai-human` traité (décision D1) ; drift doc corrigé (zones J0–J2).
- 3 doctrines **écrites** (OWNER MODE, table OCOS, multi-tenant) — articles + observables, **aucune implémentation**.
- Parcours 1 **toujours vert** ; substituabilité verte ; legacy `sha256` inchangé.
- **Sortie visée** : *les fournisseurs peuvent se multiplier sans fuite ni survente* — condition d'entrée J5/J6.

---
**STOP.** Aucun code de Phase B écrit. Revue croisée **Rose + ClaudeS**, arbitrages **Frédérique** (dont D1
`brainai-human`, D2 UI Tauri, D3 décors, D4 chartes OCOS, D5 budget sonde, D6 méthode d'auth), **puis GO Phase B**.
