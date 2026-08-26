# L0 — CLÔTURE PROVISOIRE

Date : 24 août 2026
Autorité : Frédérique, propriétaire de BrainAI

Le lot L0 « intégrité / source de vérité » est déclaré PROVISOIREMENT CLOS.

## Sous-lots réalisés

- L0-A — manifeste de topologie Git
  - commit Core : d5a0ec0

- L0-B — versionnement du corpus normatif 00_SYSTEM
  - commit 00_SYSTEM : da87aee

- L0-D — registre canonique V0 + ratification propriétaire
  - commit Core : 8e8979ddcbae877dc7adb0311d226c42b42ac698
  - registre canonique officiellement append-only à partir de ce commit

- L0-E — baseline déterministe + CI minimale de non-régression
  - commit Core : 9ce0b2977efabd5c8d082a192bf90f91120a9077
  - baseline exercée sur Core 8e8979d :
    686 passed
    1 skipped
    0 failed
    0 errors
  - le test LLM facturable est explicitement exclu par BRAINAI_JALON_LLM

- L0-F + L0-G — baseline runtime + hygiène bornée
  - commit Core : 04281be

## Sous-lot non réalisé

L0-C reste BLOQUÉ.

Cause :
les trois artefacts ClaudeS nécessaires à la conservation/hash/errata ne sont
pas physiquement disponibles sur le drive accessible :

- BRAINAI-AUDIT-PATRIMONIAL-CLAUDES.md
- BRAINAI-AUDIT-REGISTRE-COUVERTURE.md
- BRAINAI-REUNIFICATION-CANONIQUE-CLAUDES.md

Ils ne doivent jamais être reconstruits ou fabriqués depuis mémoire.

## Portée de cette clôture

Cette clôture est PROVISOIRE.

Elle signifie :
- les sous-lots indépendants de L0 sont réalisés et versionnés ;
- la source de vérité canonique existe ;
- la baseline déterministe et la CI minimale existent ;
- les principales baselines Git/runtime/gouvernance sont établies.

Elle NE signifie PAS :
- que L0-C est réalisé ;
- que L0 est définitivement clôturé ;
- que les audits ClaudeS absents sont considérés comme conservés ;
- que L1 est autorisé ;
- que J4 est autorisé ;
- que les arbitrages explicitement ouverts ont été tranchés.

La prochaine action autorisée pour compléter L0 est :
fournir physiquement les trois artefacts ClaudeS puis exécuter L0-C.

L1 et J4 restent interdits jusqu'à nouvelle décision propriétaire explicite.
