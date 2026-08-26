# Rapport de clôture — JALON 2 : Parcours Client 1 / Exécution réelle (Phase B)

*Plan Directeur BrainAI v1.0 gelé. Constitution non retouchée (Art.7 déjà amendé, commit cf76164). GO propriétaire
Frédérique. Autonome (R5/R6). **CONNECTER, PAS RECONSTRUIRE** — les moteurs siblings sont **enveloppés**, jamais recopiés.*

## Objet
Démontrer **EN RÉEL** la chaîne : demande libre → compréhension → proposition → **confirmation humaine** →
**fabrication réelle** → **vérification réelle** → **preview locale réelle** → fait `delivered` → écriture mémoire
minimale. Décision propriétaire **Q4 = A (preview locale réelle)** ; déploiement public **différé** (RS-041).

## Commits
| SHA | Contenu |
|---|---|
| `a1ba312` | Couche `delivery` (T1→T6, A2, A6) + banc Étage 1 + A6 Cas6 |
| _(ce rapport)_ | `docs/CLOTURE-JALON-2.md` + RS-2 mis à jour |

## Architecture — connecter, pas reconstruire
La livraison vit dans **`brainai_app/delivery/`** (hors `builder/`, dont l'isolation d'imports est un invariant
testé ; `brainai_app` a le droit d'importer `builder` **et** de raccorder les siblings). Décisions de raccordement
**vérifiées avant écriture** (exigence propriétaire) :

- **14_PLANNING = ENVELOPPÉ** : `delivery/planning.py` est un shim `BuildStep↔PlanTask` vers le **vrai**
  `scc_brainai_planning.dependencies.topological_order` (Kahn). Import prouvé (`config.planning_src`, même patron
  que `MemoryComponent`) ; ordre `generate→build→verify` et détection de cycle confirmés. **Aucune recopie.**
- **16_EXECUTION = ENVELOPPÉ** : `delivery/vocab.py` importe les vraies énumérations `RunStatus`/`StepStatus`
  (source unique). Le **scheduler** de 16/07 est **remplacé** par le worker de `delivery/runner.py` (jamais patché) ;
  extension J2 explicite `interrupted` (A2), déclarée sans l'attribuer au sibling.
- **11_MEMORY = ENVELOPPÉ** : `delivery/memory.py` construit le **vrai** `BrainMemoryStore` (`config.memory_src`)
  et n'appelle que `record_event` — **écriture seule, aucune récupération** (récupération = J4).
- **15_DECISION = réutilisation vérifiée puis différée (RS-042)** : `HumanValidationPolicy`/gate lu et évalué
  séparément. Conclusion **justifiée** : redondant en J2 avec `convergence_confirmed` + gate déterministe
  `_realize` (une seule autorisation humaine ; deux vocabulaires = deux sources de vérité ; réécrire D3 validé par
  Rose est proscrit). Déclencheur de réutilisation nommé (2ᵉ décision humaine distincte, J3+).

## Banc — deux étages
### Étage 1 — CI, 0 $ (déterministe, fakes ; aucun appel payant)
**Avant : 570 passed, 1 skipped. Après : 599 passed, 1 skipped (+29).** `test_jalon2_delivery_bench.py` (28) +
A6 `test_convergence_cas6…` (1). Couverture : succès · échec (erreur client) · timeout · plafond monétaire
(pré-check) · plafond nombre d'appels · `budget_exhausted` + **arrêt réel** · annulation à **ordre honnête** ·
**run interrompu** au redémarrage (+ idempotence) · reprise = **nouveau run** référençant le précédent · `..` /
absolu refusés (`resolve_within`) · **symlink sortant détecté → build `failed`** (jamais silencieux) · artefact +
sha256 des octets écrits · Verification `passed`/`failed` · **« vérifié » lié au hash** · **un octet change → non
couvert** · pas de propagation implicite · `delivered` (5 champs) · **écriture mémoire en répertoire factice**
(écriture seule) · **substituabilité fake-provider** (preview) + **par binder** (build.site) · `deploy.public`
différé/`unavailable` · **anti-câblage fournisseur** (scan `service.py`) · **anti-domaine** (scan builder/delivery).

### Étage 2 — Parcours Client 1 RÉEL (domaine : club de lecture, hors immobilier)
UN seul parcours, budget annoncé ≤ 3 $, **arrêt anticipé dès la propriété démontrée**. Aucune règle de domaine
dans BrainAI (le domaine ne vit que dans le prompt utilisateur).

- **Demande libre → convergence** : `converse` réel (sonnet), `ready` atteint en **2 tours**.
- **Confirmation humaine** : `realize(actor="Frédérique")` → fait `convergence_confirmed`
  (`{id: Frédérique, attribution: declared, verified: false}`) — déclaré / **non vérifié** (RS-029 conservée).
- **Arc réel** : `understanding`/`specification`/`build` → tous `proposed`.
- **Livraison réelle** : `run` `build→verify` **succeeded** ; le fournisseur a **écrit** `index.html` (12 245 o)
  dans le workspace **confiné** `…/delivery_exec/workspaces/site/` (ToolInvocation `tinv_f1a517f1af98`,
  `status=succeeded`).
- **Vérification réelle** : `verif_8d4e9f33e4ce` `verdict=passed`, **HTTP 200** sur le contenu réellement servi
  (loopback + jeton), `sha256=b37bc70a…` = empreinte du corps servi **et** de l'artefact bâti (lié au hash).
- **Preview locale réelle** : servie sur `127.0.0.1` (port éphémère, jeton, default-deny).
- **`delivered`** : `deliv_c75516e9abf9` (pursuit_ref, artifact_ref, preview_ref, verification_ref, as_of).
- **Mémoire** : `mem_000000000001` (`pursuit_delivered`, écriture seule, provenance par IDs).

**Provenance** : `build_a3e501732589` → `tinv_f1a517f1af98` → `verif_8d4e9f33e4ce` → `deliv_c75516e9abf9` →
`run_456dc3351a60`. Artefact réel : page « Club de Lecture — Umberto Eco » (Les Pages Tournées).

## Budget réel — terminologie honnête
| Poste | Appels | Coût réel (USD) |
|---|---|---|
| converse T1 (sonnet) | 1 | 0,168778 |
| converse T2 (sonnet) | 1 | 0,1009348 |
| arc realize (understanding+specification+build, haiku) | 3 | 0,2070023 |
| build.site (livraison, haiku) | 1 | 0,0660894 |
| **Total** | **6** | **≈ 0,5429 USD** |

- **Réellement DUR** : le **compteur d'appels facturables** (BudgetLedger, `max_calls`) — BrainAI contrôle
  exactement le nombre de franchissements de frontière. Enforceable à 100 %.
- **Best-effort BORNÉ (non strictement dur)** : le **plafond monétaire**. Pré-check `spent+enveloppe<=plafond`
  avant chaque appel, avec l'enveloppe = `--max-budget-usd` natif ; mais ce plafond fournisseur est un **arrêt
  agrégé entre appels**, pas une garantie a priori qu'un appel déjà lancé ne dépasse pas légèrement. **Résidu RS-039.**
- Coûts **réels** quand disponibles, `unavailable` sinon — **jamais inventés**. Aucun `budget_exhausted` sur ce
  parcours (marge large). Arrêt anticipé respecté : **les appels autorisés n'ont pas été consommés « parce que
  disponibles »**.

## Preuves par exigence
- **A1 (confinement)** : `cwd` imposé, argv-only, env minimal ; collecte par `resolve_within` ; symlink sortant
  **détecté → fait `failed`** (banc) ; en réel, ToolInvocation confinée au workspace du site. Hypothèses levées :
  `git` présent dans le PATH confiné (`/usr/bin/git`) ; **worker in-process suffit à J2** → process OS séparé = RS-040.
- **A2 (run interrompu / annulation)** : `run_interrupted` append-only au redémarrage (idempotent, banc) ;
  annulation à **ordre honnête** prouvé (`cancellation_requested` < fait terminal de l'étape en vol < `run cancelled`).
- **A3 (portée de « vérifié »)** : chaque `Verification` porte subject/kind/proof/verdict/**sha256**/as_of ;
  « vérifié » = attribution **SYSTÈME** sur `passed`, **liée au hash** ; un octet change → non couvert ; **aucune
  propagation** (test dédié).
- **A4 (budget borné)** : cf. supra — garde d'appels dure + plafond USD best-effort ; `budget_exhausted` → arrêt
  réel (banc).
- **A5 (substituabilité inconditionnelle)** : test fake-provider preview **vert** ; substitution build.site **par
  binder** ; **aucun slug fournisseur** dans la logique de livraison (`service.py`) ni dans `composition` (scan).
- **A6 (suspension de convergence)** : gate déterministe **déjà en moteur** ; **Cas6** ajouté : une correction
  postérieure à `convergence_confirmed` **périme** la convergence (realize refusé `EVOLVED`), la confirmation
  reste **inerte** (append-only, non re-déclenchée).

## Capacités officielles (avant / après)
- **Avant (J1)** : provenance épistémique émise/persistée ; confirmation humaine = fait gouverné ; capacités
  résolues via le registre ; **aucun build réel exécuté** (`cost=None`, manifeste seulement) ; « vérifié » =
  promesse non tenue.
- **Après (J2)** : (1) **build réel confiné** — le fournisseur écrit une application servable, l'évasion est
  détectée ; (2) **runner asynchrone gouverné** (BuildStep append-only, Kahn enveloppé, annulation/run interrompu
  honnêtes) ; (3) **vérification liée au hash** (« vérifié » système livré) ; (4) **budget réellement borné**
  (compteur dur + USD best-effort) ; (5) **preview locale réelle** substituable ; (6) **`delivered` + mémoire
  minimale**. La chaîne complète est **démontrée en réel** (0,54 $).
- **Honnêteté** : la compréhension reste **double** (converse + arc) — assumé (RS-045) ; le plafond USD **n'est pas**
  strictement dur (RS-039) ; le worker **meurt avec l'app** (RS-040) ; aucun déploiement public (RS-041).

## État des invariants I1→I9 (préservés)
| Inv. | État | Note J2 |
|---|---|---|
| I1 Parole=état gouverné | préservé | faits append-only (build_step, verification, delivered) |
| I2 Refus de mûrir sans matière | préservé | inchangé |
| I3 Désaccord/requalification | préservé | A6 : correction périme la convergence |
| I4 ready→awaiting, jamais d'action auto | préservé | livraison seulement après `realize` humain |
| I5 Sortie brute=fait persisté | **central** | ToolInvocation + sortie brute conservée en `proof`/diagnostic |
| I6 append-only, coût réel | **renforcé** | BudgetLedger réel/unavailable, jamais inventé |
| I7 Mémoire de Pursuit | préservé | delivered dans la Pursuit ; mémoire minimale (écriture seule) |
| I8 Aucune optimisation de scénario | préservé | anti-domaine (scan) ; Étage 2 domaine distinct |
| I9 BrainAI détient l'intention | **renforcé** | capacités build/preview **résolues** ; substituabilité prouvée |

## État I1→I9 du banc **(9/9 vert)** · RS-2 à jour · dettes résiduelles nommées
**Résolues J2** : RS-037 (attribution système « vérifié » liée au hash) ; RS-016 (budget — **partielle** : compteur
dur, USD best-effort). **Nouvelles/consignées** : **RS-039** (plafond USD non strictement dur) · **RS-040**
(process OS séparé) · **RS-041** (déploiement public différé J3+ après RS-030) · **RS-042** (réutilisation
15_DECISION différée, déclencheur nommé) · **RS-043** (retries riches) · **RS-044** (granularité des vérifications)
· **RS-045** (redondance compréhension converse/arc). Aucune dette silencieuse.

## Leçons du chantier
1. **« ENVELOPPER » ≠ recopier.** Le premier réflexe (Kahn local) a été corrigé : raccorder le **vrai** module
   via un shim de types est plus juste et sans coût réel (import prouvé avant écriture). Discipline désormais
   acquise : **prouver l'obstacle avant toute alternative**, sinon envelopper.
2. **La frontière `builder` est un aimant à erreurs utiles.** Le test `kernel_does_not_import_builder` a
   immédiatement rejeté `delivery/` sous le noyau → relocalisation en `brainai_app/` (couche app). La frontière a
   *conçu* l'architecture correcte.
3. **Honnêteté budgétaire.** Le `--max-budget-usd` fournisseur **n'est pas** un plafond dur a priori ; le seul
   plafond mathématiquement dur est le **compteur d'appels**. Le rapport et le fait `budget_exhausted` reflètent la
   propriété **réellement** garantie (pas la propriété désirée).
4. **« Vérifié » doit être esclave du hash.** Lier la vérification au chemin aurait menti dès la première
   modification d'octet ; l'ancrage au sha256 rend l'invariant testable et incassable.
5. **Un seul parcours réel suffit** (0,54 $) : dès la propriété démontrée, arrêt — la discipline « ne pas
   consommer les appels parce qu'ils sont disponibles » économise et prouve à la fois.

## Critères de fin J2 — atteints
✅ Parcours Client 1 démontré EN RÉEL · ✅ rien de simulé dans la livraison · ✅ artefact réellement construit ·
✅ preview réellement servie (HTTP 200) · ✅ vérification liée au contenu (hash) · ✅ confirmation humaine gouverne
l'action · ✅ budget borné selon les garanties **réellement** disponibles · ✅ compteur d'appels respecté ·
✅ substituabilité verte · ✅ confinement disque prouvé · ✅ banc Étage 1 vert (599 passed, 1 skipped) · ✅ legacy
intact · ✅ I1→I9 préservés · ✅ mémoire minimale écrite · ✅ `delivered` persisté · ✅ rapport autonome remis.

---
*STOP après clôture. **AUCUN J3** sans revue croisée Rose + ClaudeS **et** GO explicite de Frédérique.*
