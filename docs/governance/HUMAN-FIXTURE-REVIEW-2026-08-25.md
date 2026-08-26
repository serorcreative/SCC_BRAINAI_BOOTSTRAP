# REVUE HUMAINE CIBLÉE DES FIXTURES DE TEST — 25 août 2026

Date : 25 août 2026
Autorité : Frédérique, propriétaire de BrainAI
Régime : ZERO-DISCLOSURE (aucune valeur, aucun préfixe, aucun suffixe, aucun
extrait source d'un littéral n'est reproduit ; seuls des sha256[:10] servent
d'identifiants).

## 1. Contexte

Un pré-flight de sécurité a été exécuté avant toute décision de publication.
Un traceur forensique local (temporaire, non versionné, ZERO-DISCLOSURE) a
analysé les occurrences ressemblant à des credentials dans les suites de tests.
Il a laissé 6 occurrences résiduelles non tranchées automatiquement, réductibles
à DEUX valeurs uniques. Le présent document consigne la revue humaine ciblée de
ces deux valeurs. Il ne consigne aucune décision de publication.

## 2. Méthode

- Les deux littéraux ont été inspectés localement, dans leur intégralité, par
  lecture humaine du source et de son historique Git.
- Aucune valeur n'a été affichée ni recopiée : seules des métadonnées et des
  booléens dérivés ont été produits, plus les sha256[:10].
- Aucun appel externe de validation de credential n'a été effectué (aucun appel
  provider, aucune requête réseau, aucune tentative d'usage des valeurs).
- Le traceur automatique reste FIGÉ ; aucune correction ne lui a été appliquée
  dans le cadre de cette revue.

## 3. Distinction — traceur automatique FAIL vs revue humaine PASS

### 3.1 Traceur automatique (figé) — FAIL conservateur

- statut : `FAIL` conservateur ;
- CONFIRMED = 0 sur les 6 occurrences résiduelles ;
- INCONCLUSIVE = 6 ;
- POSSIBLE_REAL_SECRET = 0 ;
- aucune frontière réelle détectée :
  network = false, subprocess = false, provider = false,
  real process environment = false, persistence = false ;
- provenance_ok = true.

Sens exact de ce FAIL : « l'outil automatique n'a pas réussi à démontrer
intégralement les flux ». Il ne signifie PAS « un secret réel a été trouvé ».
Ce FAIL automatique n'est pas réécrit en PASS.

### 3.2 Revue humaine ciblée — PASS borné

Après lecture réelle des valeurs et de leur contexte de création, les deux
fingerprints résiduels sont classés comme fixtures synthétiques de test.

## 4. Fingerprints examinés (sha256[:10] uniquement)

| sha256[:10] | dépôt | occurrences | classification |
|---|---|---|---|
| `edc8901d30` | 11_BRAINAI_MEMORY | 1 | MANUALLY_CONFIRMED_TEST_FIXTURE |
| `4afc0279aa` | 17_BRAINAI_BOOTSTRAP | 5 | MANUALLY_CONFIRMED_TEST_FIXTURE |

Constats associés (sans valeur) :

- hardcoded_in_tests = oui ;
- test_only_history = oui ;
- same_fingerprint_outside_tests = NON ;
- family_signature_outside_tests = NON ;
- credential_rotation_history = non ;
- introduced_with_test = oui ;
- format constaté incompatible avec un credential opérationnel réel (longueurs
  très inférieures aux formats réels des familles concernées) ;
- aucune validation externe de credential effectuée.

Deux fixtures avaient déjà été confirmées lors du pré-flight et restent
acquises : `2691eb83df` et `8af10a0181`.

## 5. Conclusions

`FIXTURE REVIEW : PASS`

Ce PASS signifie uniquement : « les alertes résiduelles ressemblant à des
credentials ont été examinées et confirmées comme fixtures synthétiques de
test ».

## 6. Limitation connue du traceur (conservée)

`OFFSET_BUG_CONFIRMED / LATENT / NOT_EXERCISED_BY_CURRENT_TARGETS`

- défaut self/cls démontré dans `param_for_site` du traceur forensique
  temporaire ;
- défaut latent ;
- non exercé par les 6 occurrences ciblées ;
- aucun effet sur leur verdict constaté ;
- aucune correction appliquée ; traceur désormais FIGÉ.

Cette limitation concerne un outil forensique temporaire, PAS un composant
produit BrainAI ; elle n'est pas classée comme issue produit.

## 7. Portée exacte du PASS

Décision gouvernée consignée : `HUMAN_FIXTURE_REVIEW_PASS`.

Portée :

- lève UNIQUEMENT le blocage relatif aux deux fingerprints résiduels de
  fixtures de test (`edc8901d30`, `4afc0279aa`) ;
- ne lève PAS les autres préconditions de publication ;
- la publication des dépôts reste soumise à un pré-flight final séparé.

## 8. Interdiction explicite

Cette consignation ne constitue PAS, et ne doit jamais être interprétée comme :

- un PASS global de sécurité ;
- une autorisation de publication ;
- une autorisation de rendre les dépôts publics ;
- une autorisation de modifier la visibilité GitHub ;
- une autorisation de merger la Pull Request ;
- une autorisation de modifier la CI.

`FIXTURE REVIEW = PASS`
`AUTOMATED FORENSIC = FAIL CONSERVATEUR`
`PUBLICATION AUTHORIZATION = NO`

Toute étape suivante requiert une décision propriétaire explicite.
