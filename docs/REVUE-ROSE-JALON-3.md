# Bundle de revue croisée — JALON 3 (pour Rose)

*Revue **adversariale** demandée avant clôture définitive de J3. **ClaudeS a déjà rendu : PASS avec micro-correction**
(réserves A/B/C soldées) — voir §5 pour ne pas dupliquer. Ton rôle : chercher ce qui serait **survendu, faux, ou
incohérent**, pas confirmer. Base gelée : Plan Directeur v1.0, R0–R12, I1→I9, Constitution.*

## 1. Périmètre de J3 (ce qui est en revue)
Jalon « **Adaptateurs / Canaux / Honnêteté + Doctrines** », 4 tranches :
- **T1 — Étanchéité informationnelle** : bascule d'auth `provider_env` (B1 trousseau/HOME défaut ; cible `explicit_token` + HOME isolé), sonde d'identité (contrôle positif obligatoire), 6 adaptateurs déléguant `_env()`.
- **T2 — Contrat d'adaptateur** : `adapter_contract` complet à **rejet structurel** (`require_contract` câblé dans la résolution) ; 6/6 adaptateurs conformes ; budget de livraison gouverné (RS-047).
- **T3 — Passe d'honnêteté** : README corrigé ; notices hors dépôt (scaffolds / `brainai-human` / UI archivée) ; drift documenté.
- **T4 — Doctrines écrites (pas implémentées)** : OWNER MODE · table OCOS (sources réelles) · multi-tenant/BYOK.

## 2. Documents à lire (source de vérité)
- `docs/CLOTURE-JALON-3.md` — rapport de clôture autonome (R5/R6) **+ Addendum 2026-08-22 (RS-056 levée)**.
- `docs/REGISTRE-EVOLUTION.md` — RS-2 (statuts, créations, levées ; RS-030/039/047/050/053/056/057…).
- `docs/DOCTRINE-OWNER-MODE.md` · `docs/TABLE-OCOS-ABSORPTION.md` · `docs/DOCTRINE-MULTI-TENANT-BYOK.md`.
- `docs/PATRIMOINE-90-HERITAGE-MATRICE.md` — passe patrimoniale (32/32 lus).

## 3. Commits du jalon (fil de référence)
| SHA | Contenu |
|---|---|
| `fa21bee` | J3 Phase B (T1→T4) : étanchéité + contrat + honnêteté + doctrines + patrimoine |
| `6b14247` | Correctif : `token_var` injectable (isolation HOME générique, portée bornée) |
| `80e2e56` | Clôture R5/R6 : rapport autonome |
| `3004484` | Réponse revue ClaudeS (solde A/B/C) |
| `26770fd` | **Clôture officielle** (micro-correction : RS-057 = frontière assumée, pas dette) |
| `ffe9c68` | **Condition de suite RS-056 soldée** : preuve d'étanchéité cible **PASS bornée** |

## 4. Affirmations vérifiables + **limites explicitement déclarées** (à contrôler qu'elles ne sont pas survendues)
1. **Suite déterministe** : **686 passed, 1 skipped** (au dernier état ; J3 propre = 646+1 au `26770fd`). 0 € en Étage 1.
2. **Étanchéité (T1/RS-030)** : la fuite d'identité sous B1 est **prouvée** (contrôle positif : **4/11** champs détectés dont `emailAddress`, coût réel 0,0455 $). La cible (HOME isolé + jeton) a **PASS bornée** (sonde cible : **0/11**, coût 0,042 $, `ffe9c68`).
   - **Limites déclarées (à vérifier qu'on n'affirme rien de plus)** : PASS = **non-attribution de la surface d'identité énumérée** pour **l'instanciation Claude Code testée uniquement** ; **ce n'est PAS** un scellement du système de fichiers (accès par chemin absolu non empêché — RS-046/RS-040) ; **aucune** compatibilité d'un autre executor ; B1 reste le **défaut opérationnel** (activation cible = étape ultérieure).
3. **Contrat (T2)** : rejet **structurel** d'un adaptateur au contrat incomplet (`require_contract` dans `resolve_capabilities`/`resolve_delivery`) ; `usd_cap=aggregate_stop` **jamais** « hard » (RS-039) ; `cost_report.fabricated=False` exigé (I6). Contrôle : techno-indépendance (`test_contract_is_technology_independent`).
4. **`token_var` (RS-057)** : injectable **au niveau des fonctions** `provider_env`, **PAS câblé au niveau adaptateur** (frontière assumée, différée ; 2 tests la verrouillent). À vérifier : aucune sur-affirmation « multi-executor prêt ».
5. **Honnêteté (T3)** : aucune capacité **cognitive** ajoutée en J3 ; les notices siblings sont **documentaires seules** (AM5 : aucun déplacement/suppression/modif fonctionnelle).
6. **Doctrines (T4)** : **écrites, PAS implémentées** (OWNER MODE → J7 ; multi-tenant → post-v1) — à vérifier qu'aucune n'est présentée comme livrée.
7. **AM1** : aucune valeur d'identité/jeton dans le dépôt (sorties de sonde hors dépôt, comptages seuls).

## 5. Verdict ClaudeS déjà rendu (ne pas dupliquer — cross-checker)
**PASS avec micro-correction.** Réserves soldées :
- **A** — traversée `token_var` : constat que l'injectabilité **s'arrête à `provider_env`** (non câblée adaptateur) → consignée RS-057, 2 tests de caractérisation. **Non généralisé** (aucun 2e executor).
- **B** — portée isolation HOME : corrigée (« supprime la découverte conventionnelle », **pas** un scellement FS ; renvoi RS-046/RS-040).
- **C** — nature de RS-056 : **prérequis d'exploitation** (acte humain), pas dette d'ingénierie.
- Micro-correction finale : RS-057 requalifiée « frontière assumée, différée » (jamais « dette »).

## 6. Points de contrôle proposés pour Rose (adversariaux)
- L'étanchéité est-elle **survendue** quelque part (docstrings, rapport, RS-030) — trouve toute formulation impliquant un scellement FS ou une compatibilité multi-executor.
- Le **rejet structurel** du contrat est-il réel sur le **chemin produit** (pas seulement en test) ? Un adaptateur sans `contract()` fait-il **échouer** la résolution ?
- Les doctrines T4 s'appuient-elles sur des **sources réelles** (OCOS-001/002/003) sans invention ? La table OCOS distingue-t-elle « absorbé » de « au-dessus » honnêtement ?
- La preuve RS-056 est-elle correctement **bornée** (PASS pour l'instanciation testée) et **honnête** sur la nuance (contrôle positif hérité J3, aucune identité au dépôt) ?
- Les **statuts RS-2** reflètent-ils la réalité du code (résolue/partielle/consignée) sans optimisme ?
- Invariants **I1→I9** : un quelconque enchaînement automatique (I4) a-t-il été introduit ? Un coût fabriqué (I6) ?

## 7. Hors périmètre J3 (pour information — NE PAS reviewer comme du J3)
Après la clôture officielle, une **passe produit** (mise en fonctionnement réel + durcissement) a produit des commits **séparés**, déjà consignés en RS-2, **hors jalon J3** :
- raccord UI mode réel (`513321e`) · correctif A4-2 continue+matured (`7380cc9`) · raccord reprise de Pursuit (`f4b6aab`) · **watchdog de sécurité gouverné** remplaçant le cutoff 180 s (`b05e536`, clôturé `9301491`) · **cadrage J4** anti-dilution (RS-060, `cf85d9f`).
- Ces éléments **ne rouvrent pas** J3 ; ils sont mentionnés pour transparence. Rose peut les noter mais ils relèvent de la phase produit, pas du jalon en revue.

## 8. Sortie attendue de Rose
Un verdict : **PASS** / **PASS avec réserves** (lesquelles, bornées) / **NON-PASS** (blocages précis), avec, pour chaque réserve : le fichier/la ligne/l'affirmation en cause et la correction minimale suggérée. Après quoi : **GO propriétaire final** pour clôturer J3 et autoriser J4.
