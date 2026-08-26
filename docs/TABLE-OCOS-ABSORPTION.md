# Table d'absorption OCOS → BrainAI V2

*JALON 3 T4, décision propriétaire **D4**. Construite à partir du **contenu réel** des chartes, lues intégralement
(AM4 satisfaite) : `90_HERITAGE/PROJETS IA/BRAIN AI/CHARTER-OCOS-001.docx` · `…/CHARTER-OCOS-002.docx` ·
`…/CHARTER-OCOS-003.docx`. **Aucun contenu inventé.** Provenance par ligne. Arbitrage propriétaire du 20 août :
OCOS **ABSORBÉE** dans la gouvernance de BrainAI V2 (RS-012) — « absorbée, pas perdue » (RS-3) : cette table **est** la
preuve de non-perte.*

## Ce que disent réellement les 3 chartes (résumé fidèle des sources)
- **OCOS-001** — *exercice à blanc* : tester s'il existe **naturellement** une séparation entre le **système cognitif**
  et **l'infrastructure qui le fait fonctionner**. Méthode imposée : DOCTRINE-008 (explorer avant de conclure,
  déclarer l'incertitude).
- **OCOS-002** — *découverte* : convergence spontanée vers **3 couches** (Cognitif / Orchestration / Infrastructure).
  Insight : l'orchestration n'est pas qu'une couche — c'est un **« système d'exploitation cognitif »** = doctrines +
  gouvernance + registre + contrats + capacités + politiques + règles d'exécution + transitions de session +
  gouvernance des IA + discipline cognitive. **L'orchestrateur est un composant d'OCOS, pas l'inverse.**
- **OCOS-003** — *gel* : la plateforme est **neutre, n'appartient à aucun agent** ; **couche supérieure de
  gouvernance** = le cognitive OS. **BrainAI est UNE entité cognitive sous sa gouvernance** ; la discipline s'impose à
  **toute** entité participant à un processus gouverné, **y compris BrainAI**. Hiérarchie : **plateforme gouverne →
  BrainAI orchestre/raisonne → moteurs exécutent → agents tiers collaborent sous les mêmes règles**.

## Table de correspondance OCOS ↔ incarnation BrainAI V2

| Concept OCOS (source réelle) | Incarnation BrainAI V2 aujourd'hui | Provenance | État |
|---|---|---|---|
| **Séparation cognitif / infrastructure** (OCOS-001) | Frontière **`builder` (cognition/appliance) ↔ noyau** (invariant d'imports testé) + les **3 plans** Cognition louée / Gouvernance / Exécution (revue d'architecture) | source retrouvée (OCOS-001) + mapping prouvé (`test_builder_boundary.py`, `delivery/`) | **ABSORBÉ** |
| **Méthode DOCTRINE-008** (explorer avant conclure, déclarer l'incertitude) | Honnêteté épistémique : provenance `ELEMENT.source`, statuts FAIT/DÉDUCTION/HYPOTHÈSE/INCONNU, « vérifié » système lié au hash | source retrouvée (OCOS-001 + doctrine et1/et3) | **ABSORBÉ partiel** — escalier de confiance complet = RS-021 |
| **« Système d'exploitation cognitif »** = doctrines + gouvernance + registre + contrats + capacités + politiques (OCOS-002) | **Plan de gouvernance BrainAI V2** : Constitution + RS-2 + `convergence_confirmed` + **Capability Registry** (descriptors/binder) + **contrat d'adaptateur** (J3 T2) | mapping existant (registre, Constitution, contrat T2) | **ABSORBÉ** (BrainAI V2 = l'incarnation du cognitive OS) |
| **Orchestrateur = composant, pas le tout** (OCOS-002) | Le **runner de livraison** + l'arc sont des **composants** sous gouvernance (faits append-only, gate humain) — jamais « le cerveau » | mapping existant (`delivery/runner.py`, gate `_realize`) | **ABSORBÉ** |
| **Registre / contrats / capacités** (OCOS-002) | `registry/` (AgentRegistry/CapabilityResolver) + **contrat d'adaptateur** (Doctrine 9/10, J3 T2) | mapping existant | **ABSORBÉ** |
| **Politiques / règles d'exécution** (OCOS-002) | R0–R12 + gardes (default-deny, append-only, budget, confinement A1) | mapping existant | **ABSORBÉ** |
| **Transitions de session** (OCOS-002) | Continuité de Pursuit (C5) ; **Session Transition** comme objet gouverné officiel = **NON absorbé** | source (OCOS-002 + doctrine et1) | **PARTIEL** → RS-018 |
| **Gouvernance des IA / discipline cognitive** (OCOS-002) | Constitution (discipline conversationnelle) + Doctrine 8 (discipline cognitive) + gouvernance humaine | mapping existant + source | **ABSORBÉ partiel** |
| **Plateforme neutre, n'appartient à aucun agent** (OCOS-003) | **Découplage capacité↔fournisseur** (I9, substituabilité) + gouvernance propriétaire (arbitrage Frédérique) | mapping existant (`providers.py`) + arbitrage 20 août | **ABSORBÉ (arbitrage)** |
| **Couche supérieure de gouvernance** (OCOS-003) | **Gouvernance propriétaire** (GO Frédérique, RS-2, règle d'or) + doctrine **OWNER MODE** (J3 T4, impl. J7) | arbitrage 20 août + `DOCTRINE-OWNER-MODE.md` | **ABSORBÉ (doctrine) ; impl. J7** |
| **Discipline s'imposant à TOUTE entité, y compris BrainAI** (OCOS-003) | DOCTRINE-008 imposée à **BrainAI ET aux agents orchestrés**, jamais à l'humain | source retrouvée (OCOS-003 + doctrine et3) | **PARTIEL** → RS-021 (politique d'orchestration non formalisée) |
| **Hiérarchie plateforme > BrainAI > moteurs > agents** (OCOS-003) | Absorbée à plat : BrainAI V2 **est** la plateforme gouvernée (pas de couche OCOS séparée) — **écart signalé ci-dessous** | arbitrage 20 août | **ABSORBÉ avec écart doctrinal** |
| **Archivage des chartes** | Chartes conservées dans `90_HERITAGE` (patrimoine) ; référencées ici | 90_HERITAGE (lecture seule) | **fait** |

## Écart doctrinal signalé (le cadre gelé prévaut)
Les chartes posent OCOS comme une **couche AU-DESSUS** de BrainAI (BrainAI = une entité parmi d'autres). L'arbitrage
propriétaire du 20 août a **absorbé OCOS DANS** la gouvernance de BrainAI V2 (il n'existe pas de produit « OCOS »
séparé ; BrainAI V2 **est** l'incarnation du cognitive OS). **Le gel prévaut (absorbée).** Conséquence à garder en
vue : si un jour plusieurs entités cognitives tierces doivent être gouvernées **au-dessus** de BrainAI, la couche
OCOS-neutre pourra ré-émerger le long de cette frontière — sans rien casser (cf. RS-013 multi-fournisseurs J5/J6,
RS-015 multi-tenant, OWNER MODE J7). Consigné, non ré-ouvert.

## Ce qui reste INCONNU / à arbitrer
- Aucun **texte de charte** au-delà des 3 fichiers lus (OCOS-001/002/003) — la table est **complète** vis-à-vis des
  sources disponibles ; RS-050 est **levée** (chartes sourcées).
- Formalisation d'une éventuelle **couche OCOS ré-émergente** (multi-entités) = **à arbitrer** post-v1 (non J3).
