# Rapport de clôture — JALON 1 : Fondations épistémiques + Capability Registry minimal

*Plan Directeur BrainAI v1.0 gelé. Phase B autorisée (convergence Rose + ClaudeS, GO Frédérique). Autonome (R5).*

## Objet
(i) statuts épistémiques minimaux **persistés sur le chemin produit** ; (ii) la Surface 3 **résout ses capacités
via le registre** (découplage du fournisseur). D3 traité en premier. **Connecter, pas reconstruire.**

## Preuves
- **Suite complète 0 $ : 570 passed, 1 skipped** (+11 tests J1). Étage 1 déterministe couvre : schéma ELEMENT
  additif ; provenance persistée & relue ; « vérifié » structurellement inémettable + dropé par normalize ;
  legacy/absence → `inconnu` sans fabrication ; hypothèses gouvernées ; `convergence_confirmed` append-only &
  inerte ; acteur `declared`/`verified:false` ; realize n'ajoute une confirmation **sans muter** les tours
  (sha256 inchangé) ; `resolve(capability)` sur le chemin produit ; **absence de câblage fournisseur** dans
  `composition.py` et `builder/brainai.py` (scan de source) ; **substituabilité** par changement de descriptor ;
  champ `cost` présent (ancrage J2) mais `None` (aucun budget exécuté).
- **Étage 2 réel (plafonné)** : **1 appel** (sur 2-3 autorisés), sonnet, **coût réel 0,182375 $** (≤ 0,50).
  Domaine distinct (école de musique). Résultat : `ready`, `matured_need` à **9 éléments portant chacun une
  `source`** (`deduit`/`suppose`/`fourni_par_utilisateur`/`inconnu`), **toutes dans l'enum**, **jamais
  « vérifié »**, et cognitivement cohérentes (détails ouverts déclarés par l'utilisateur → `fourni_par_utilisateur`).
  Propriété démontrée → arrêt anticipé (discipline : ne pas fabriquer une campagne).

## Fichiers
| Fichier | Changement |
|---|---|
| `builder/conversation.py` | `ELEMENT.source` (5 valeurs, `vérifié` exclu) ; `normalize` conserve source valide, sinon → `inconnu` ; helper `element_source` ; rendu A2 typé ; mission ajustée (émission exigée) |
| `builder/confirmations.py` (**nouveau**) | fait `convergence_confirmed` append-only + `ConfirmationStore` + `declared_actor` (toujours `verified:false`) |
| `builder/brainai.py` | `Stores.confirmations` ; `realize_intent(actor=)` ; `_realize` enregistre la confirmation (séparée, inerte, avant l'arc) |
| `brainai_app/providers.py` (**nouveau**) | descriptors 4 capacités → `claude_code` (+ `cost` ancrage J2) ; binder `(fournisseur, capacité)→adaptateur` ; `resolve_capability` via le registre existant |
| `brainai_app/composition.py` | `real_capabilities()` délègue à `providers` (plus aucun `ClaudeCode`/slug) ; journal `confirmations` ; `realize(actor=)` |
| `tests/*`, `docs/REGISTRE-EVOLUTION.md` | banc Étage 1 étendu ; RS-2 mis à jour |

## Les 3 conditions de Rose
1. **D3 / confirmation humaine** ✅ — fait `convergence_confirmed` **séparé append-only** ; `ready` reste une
   appréciation ; **aucun `matured_need` muté** (I5, prouvé sha256) ; acteur **DÉCLARÉ / NON VÉRIFIÉ** (RS-029
   conservée) ; **ne déclenche rien** (record ≠ décision).
2. **Provenance opérationnelle dès J1** ✅ — émission **exigée** (mission), prouvée en réel ; extension **additive**
   de `ELEMENT` ; **`vérifié` inémettable structurellement** (enum) ; legacy relu, absence → `inconnu`, **aucune
   réécriture** (sha256 campagne inchangé).
3. **Capability Registry / découplage fournisseur** ✅ — registre existant **réutilisé** ; binder dans la couche
   infrastructure (`providers.py`) ; **interdits respectés** (aucun binder/slug/`ClaudeCode*` dans
   `composition.py` ni `builder/*`) ; **substituabilité prouvée** ; `cost` = ancrage J2 **non exécuté**.

## Capacités officielles (avant / après)
- **Avant** : conversation gouvernée (identité v0.4, C8/C9, C5-minimal) ; `matured_need` structuré **sans
  provenance** ; fournisseur **câblé en dur** dans la composition ; confirmation humaine = acte `realize` **non
  tracé comme fait**.
- **Après (J1)** : (1) **provenance épistémique émise et persistée** par élément sur le chemin produit ; (2)
  **confirmation humaine = fait gouverné distinct** (`convergence_confirmed`, acteur déclaré/non vérifié) ; (3)
  **capacités résolues via le registre** (logique métier indépendante du fournisseur).
- **Honnêteté** : J1 n'ajoute **aucune faculté cognitive nouvelle** — c'est de la **provenance + gouvernance +
  plomberie de résolution**. `vérifié` reste une promesse **non tenue** (réservée J2+), signalée comme telle.

## État des invariants I1→I9
| Inv. | État | Note |
|---|---|---|
| I1 Parole=état gouverné | préservé | provenance dans les faits existants |
| I2 Refus de mûrir sans matière | préservé | inchangé |
| I3 Désaccord/requalification | préservé/aidé | la provenance rend la requalification traçable |
| I4 ready→awaiting, jamais d'action auto | préservé | le fait de confirmation ne déclenche rien |
| I5 Sortie brute=fait persisté | **central, préservé** | provenance **émise par le modèle** ; confirmation = fait séparé, **jamais** mutation |
| I6 append-only, coût réel | préservé | extension additive ; normalisation en lecture ; sha256 inchangé |
| I7 Mémoire de Pursuit | préservé | même TurnStore + confirmations dans la Pursuit |
| I8 Aucune optimisation de scénario | préservé | vocabulaire générique ; test anti-domaine ; Étage 2 domaine distinct |
| I9 BrainAI détient l'intention | **renforcé** | fournisseur découplé ; missions bornées ; sortie = proposition |

## Dettes restantes explicites
- **RS-005** — réconciliation du **texte de la Constitution** (Art.7 `ready` vs `realize`) : **arbitrage de
  gouvernance, NON appliqué** (mécanisme livré).
- **RS-038** — provenance au niveau `besoin_fondamental` (chaîne) : à jalonner (D2 résiduel).
- **RS-029** — identité acteur non authentifiée : représentée honnêtement, non résolue.
- **RS-037** — attribution système `vérifié` sur vérification réelle : J2+.
- (Registre RS-2 complet à jour ; aucune dette silencieuse.)

## J2 n'a PAS commencé
**FAIT** — aucun runner, **aucun budget exécuté** (`descriptor.cost = None`), aucune récupération contextuelle
mémoire, aucun Atlas riche, aucun nouveau fournisseur, aucune modification du Plan Directeur, aucune architecture
parallèle. Toute idée nouvelle → RS-2.

## Critères de fin — atteints
✅ assertions typées émises/persistées/relues · ✅ hypothèses gouvernées + confirmation append-only · ✅ faits
historiques relisibles (sha256 inchangé) · ✅ Surface 3 via `resolve(capability)` · ✅ anti-câblage vert · ✅ banc
vert (570 passed) · ✅ Étage 2 réel concluant (1 appel, 0,182 $) · ✅ RS-2 à jour · ✅ rapport remis.

---
*STOP après clôture. Aucun démarrage de J2 sans revue croisée Rose + ClaudeS et nouveau GO explicite de Frédérique.*
