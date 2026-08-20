# Rapport final de clôture — COGNITIVE-IDENTITY-001

*Clôture arbitrée : ClaudeS (revue contradictoire) → Rose (validation) → Frédérique (GO formel).*
**Verdict : GO CLÔTURE AVEC DETTES CONSIGNÉES.**
Objet du chantier : réimplanter, dans l'architecture gouvernée de la V2, les mécanismes cognitifs qui
faisaient que la V1 « réfléchissait avec » l'utilisateur — via deux vecteurs seulement (identité injectée +
mission du tour), sans réintroduire l'ancienne architecture. Puis, post-campagne, C8 / C9 / C5-minimal.

La Constitution canonique (Art.7 notamment) **reste inchangée** : la dette D3 est enregistrée, pas appliquée.

---

## 1. État final C1 → C9

| Réf | Objet | Statut | Destination |
|---|---|---|---|
| **C1** | Provenance épistémique (partie 1) | **DIFFÉRÉ** | EPISTEMIC-PROVENANCE — interface minimale prête (`ELEMENT` extensible) |
| **C2** | Canaux d'adaptateur | **HORS PÉRIMÈTRE** | ADAPTER-CHANNELS |
| **C3** | Honnêteté de capacité | **HORS PÉRIMÈTRE** | CAPABILITY-HONESTY |
| **C4** | Provenance épistémique (partie 2) | **DIFFÉRÉ** | EPISTEMIC-PROVENANCE |
| **C5** | Persistance mapping session/Pursuit | **C5-minimal ACQUIS** ; C5-complet différé | C5-complet : durabilité des *legacy* encore dans le temp système |
| **C6** | *(non transmis verbatim à ClaudeC)* | **NON SPÉCIFIÉ ICI** | à confirmer sur le diagnostic canonique — non inventé |
| **C7** | *(non transmis verbatim à ClaudeC)* | **NON SPÉCIFIÉ ICI** | à confirmer sur le diagnostic canonique — non inventé |
| **C8** | Calibration de convergence | **ACQUIS** | — (dette D3 rattachée, cf. §8) |
| **C9** | Séparation besoin / solution | **ACQUIS** | extension provenance → EPISTEMIC-PROVENANCE (dette D2) |

*Note d'honnêteté : le texte intégral de C1→C9 n'a pas été fourni dans le fil de travail ; C6/C7 ne sont pas
reconstruits pour ne pas inventer de contenu. Le périmètre réellement implémenté est C8 + C9 + C5-minimal, plus
l'actif identité (v0.4) et ses gardes, tous validés.*

## 2. Invariants canoniques I1 → I8 — statut final

| Inv. | Énoncé | Statut final | Preuve |
|---|---|---|---|
| **I1** | Parole = état gouverné | **PRÉSERVÉ** | tours = faits `turn` persistés (Étage 2 : 4/4) |
| **I2** | Refus de mûrir sans matière | **PRÉSERVÉ / renforcé** | garde C8 `ready ⇒ besoin_fondamental` ; Étage 2 A → `continue` |
| **I3** | Désaccord argumenté / requalification | **PRÉSERVÉ** | Étage 2 C (désaccord), B t2 (révision motivée), A (solution≠besoin) |
| **I4** | `ready → awaiting/confirmation`, jamais de réalisation auto | **PRÉSERVÉ** | Étage 2 B : `awaiting/confirmation`, aucun `realize` |
| **I5** | Sortie brute = fait persisté | **PRÉSERVÉ** | `brut_vs_persiste_identique = true` ×4 |
| **I6** | 1 fait/tentative, append-only, coût réel jamais fabriqué | **PRÉSERVÉ** | coûts réels, aucun retry, T1→T8 sha256 inchangé |
| **I7** | Mémoire de Pursuit | **PRÉSERVÉ / amélioré** | C5-minimal : continuité inter-processus réelle (B t2) |
| **I8** | Aucune optimisation de scénario | **PRÉSERVÉ** | 3 domaines distincts hors T1→T8 ; test anti-domaine vert |

*(Arbitrages du chantier identité — A1 conversation=Pursuit, gardes A4-1/A4-2, isolation cognitive — restent
contraignants, distincts de I1→I8.)*

## 3. Résultats Étage 1 (déterministe, 0 $)
- Banc `tests/test_convergence_bench.py` (13 tests) + tests C8/C9 dans `test_builder_conversation.py`.
- Prouve : schéma C9, normalisation legacy (D3), gardes A4-2 & C8, `ready` accepté avec inconnues non bloquantes,
  séparation besoin/solutions, invariance du besoin sous changement de solution, continuité C5-minimal après
  redémarrage simulé, index legacy, absence de terme métier interdit, fait legacy relisible **sans réécriture**.
- **Suite complète : 558 passed, 1 skipped** (avant ajout de ce rapport ; re-vérifiée à la clôture, cf. §10).

## 4. Résultats Étage 2 (cognitif réel — 4 appels, domaines distincts hors T1→T8)
| Appel | Scénario / domaine | Pursuit | `readiness` | Observation clé |
|---|---|---|---|---|
| 1 | A — assentiment ambigu / restauration | `pursuit_43e382ed2ee9` | continue | « solution, pas encore un besoin » ; ne mûrit pas |
| 2 | C — hypothèse séduisante fausse / e-commerce | `pursuit_dd7b85959b2f` | continue | désaccord argumenté + requalification (« symptôme, pas cause ») |
| 3 | B t1 — besoin défini + inconnues / bénévoles | `pursuit_43c0ce36dc1a` | **ready** | `matured_need` structuré ; 5 inconnues conservées (C8) |
| 4 | B t2 — changement de solution / bénévoles | `pursuit_43c0ce36dc1a` | **ready** | besoin fondamental **invariant**, solution révisée (C9, Art.12) |

Tous `status=proposed` ; `brut_vs_persiste_identique=true` ×4 ; aucun `realize` déclenché.

## 5. Coûts réels
**Mini-campagne Étage 2** : A 0.165142 · C 0.0975778 · B t1 0.1144258 · B t2 0.1167708 → **≈ 0.4939 USD** (4 appels).
*Transparence, dépense réelle totale du chantier* : campagne T1→T8 (8 appels, cumul 0.939801) + sonde forensique
isolée (0.12231) + Étage 2 (0.493916) ≈ **1.556 USD** sur ~13 appels réels.

## 6. Compatibilité historique T1 → T8 — preuve
- 8 faits intacts : T1–T7 `matured_need=None`, T8 `matured_need` **legacy (chaîne)**.
- T8 legacy traverse la chaîne actuelle : `matured_need_present`=True ; `normalize` → `besoin_fondamental` == la
  chaîne ; `matured_need_to_need_text` contient `BESOIN FONDAMENTAL` + le besoin.
- **Aucune réécriture** : `turns.jsonl` sha256 **identique** avant/après (`f2590dbd2019ae86…`). Append-only préservé.

## 7. Preuve C5-minimal & racine d'état déterministe (A1)
- Racine stable configurable `BRAINAI_STATE_ROOT` (défaut `~/.brainai/state`), distincte du temp système et du
  `data/` du noyau.
- Chemin **déterministe** `<state_root>/pursuits/<pursuit_id>/` (transit du 1ᵉʳ tour créé **sous** cette racine,
  jamais dans le temp) → recalculable après redémarrage, **sans index nominal**. `_SESSIONS` = cache mémoire.
- **Preuve réelle** : Étage 2 B t2 (processus séparé) a retrouvé la Pursuit **sans remapping manuel** — exactement
  le geste manuel que la campagne T1→T8 exigeait, désormais supprimé.
- Index de compat `legacy_sessions.json` réservé aux **anciens** répertoires hors racine ; réserve résiduelle
  limitée aux Pursuits *legacy* encore physiquement dans le temp système (C5-complet).

## 8. Décisions d'architecture actées (post-campagne)
- **A1 — racine d'état déterministe** : le plan « index `pursuit_id → path` sur des `mkdtemp` » est **refusé**
  (fausse persistance) ; retenu : chemin déterministe sous racine stable. (C5-minimal.)
- **A2 — rendu ARC typé** : `matured_need_to_need_text()` conserve en toutes lettres la fonction de chaque
  élément (besoin / solutions / hypothèses / inconnues), sans les refusionner. **Pont temporaire** : EXPLORATION
  consommera le `matured_need` **structuré depuis le fait persisté** (l'objet est la vérité).
- **A3** — *(pas de décision distincte sous ce label dans la consolidation post-campagne ; l'« A3 » du chantier
  identité désignait l'honnêteté du mode démo, déjà actée : la démo ne simule plus jamais une compréhension).*
- **A4 — gouvernance des phrases D5** : phrases de calibration C8/structuration C9 **génériques**, restituées
  **verbatim** et **validées** (R1 intégrée) avant tout appel réel ; aucune formulation de domaine.
- **D1a** : `matured_need` structuré ; `ELEMENT = {statement}` **gelé** (extension provenance additive future).
- **D4** : gardes A4-2 (`matured ⇒ ready`) + C8 (`ready ⇒ besoin_fondamental` non vide) ; inconnues non
  bloquantes **autorisées** à `ready`.

## 9. Dettes consignées (avec destination)
- **D1 — présomption « phase suivante »** : observation **mineure de surface** conversationnelle (la structure ne
  la porte pas ; non répétée à B t2). **Aucun correctif.** À surveiller **sur plusieurs cas** avant toute
  modification générique. → *backlog interne.*
- **D2 — porosité ponctuelle besoin / contrainte de solution** : le cœur du besoin reste invariant ; une
  contrainte dérivée d'une solution a affleuré dans l'énoncé. **Ne pas modifier C9, ne pas créer d'heuristique.**
  → *matière d'entrée pour EPISTEMIC-PROVENANCE* (porter statut/provenance d'un élément via l'extension réservée).
- **D3 — Article 7 / `ready`** : **non-conformité à l'observable LITTÉRAL** de l'Art.7 (à B t1, `ready` au tour de
  la première restitution, sans confirmation préalable) — **mais substance de l'Art.7 et I1→I8 préservés**
  (souveraineté humaine, anti-usurpation via restitution offerte à validation, aucune réalisation auto, correction
  toujours possible ; `realize` = confirmation humaine). **Réconciliation de gouvernance requise**, formulée par
  ClaudeS : *distinguer `readiness=ready` (appréciation de maturité, précédée d'une restitution) de la maturité
  confirmée (ouverte par l'acte humain `realize`)* — **sans nouvel état ni modification de code**. **La Constitution
  canonique reste inchangée** tant que cette évolution n'a pas fait l'objet d'un **arbitrage explicite**. →
  *à arbitrer en tête d'EPISTEMIC-PROVENANCE (même périmètre : `matured_need`, frontière appréciation/confirmation).*

## 10. PROUVÉ / OBSERVÉ / NON PROUVÉ / DIFFÉRÉ
- **PROUVÉ (traces / structurel)** : schéma C9 émis+persisté fidèlement ; gardes A4-2/C8 ; `ready` réellement
  atteignable ; besoin fondamental cœur invariant sous changement de solution ; aucune retouche brut→persisté ;
  C5-minimal continuité inter-processus réelle ; compatibilité T1→T8 sans réécriture.
- **OBSERVÉ (cognitif, non généralisable)** : refus de maturité ambiguë (A), désaccord argumenté (C), maturation
  calibrée avec inconnues conservées (B) — **1 cas par propriété**, 3 domaines, limites reconnues.
- **NON PROUVÉ** : la **généralité statistique** des propriétés cognitives (échantillon volontairement minimal) ;
  la **conformité littérale** de l'Art.7 (D3, non-conformité assumée subordonnée au critère suprême).
- **DIFFÉRÉ** : provenance/statut épistémique (C1/C4) ; canaux & honnêteté d'adaptateur (C2/C3) ; C5-complet ;
  EXPLORATION ; MEMORY-GOVERNED ; réconciliation Art.7 (D3).

## 11. Note de campagne
Le **5ᵉ appel réel autorisé N'A PAS été consommé** : les trois propriétés étant observées en 4 appels, aucun appel
n'a été fabriqué pour « réussir » un scénario. Aucun retry, aucune retouche, aucun correctif pendant la campagne.

## 12. Rappel de trajectoire (inchangée)
Chantier suivant : **EPISTEMIC-PROVENANCE → ADAPTER-CHANNELS / CAPABILITY-HONESTY → EXPLORATION →
MEMORY-GOVERNED** (TELEMETRY en fond). EPISTEMIC-PROVENANCE **n'est pas commencé**.

---
*Comportement réel > conformité documentaire. Le chantier sort proprement, avec dettes consignées — pas parfait.*
