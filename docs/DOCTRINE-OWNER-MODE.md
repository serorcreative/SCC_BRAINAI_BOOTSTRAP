# Doctrine — OWNER MODE (v0.1)

*Doctrine **normative** (JALON 3 T4, décision propriétaire Q4/D-OWNER). **Écrite, pas implémentée** — l'implémentation
est **J7**. Structure « **article + observable** » comme la Constitution : *une convention qui ne peut être vérifiée
n'est qu'un vœu*. En cas de conflit avec le Plan Directeur v1.0 gelé / R0–R12 / I1→I9 / la Constitution, ces derniers
prévalent. Sources patrimoniales réelles : `90_HERITAGE/…/SCC-INFRASTRUCTURE-001B` (Logical Owner/Steward/Consumers),
`SCC-INFRASTRUCTURE-001D` (Service Registry), `…/BrainAI_Phase0_J7` (BrainAI Core/Lab), `Débriefe`/STATE-DEBRIEF-001
(les 4 interfaces), Constitution Art. 7/11/13, `src/scc_brainai_bootstrap/patrimony.py`.*

**Préambule.** L'OWNER MODE définit ce que le **propriétaire** de BrainAI peut voir et faire que le **client** ne
voit jamais, et la gouvernance de l'évolution de BrainAI par lui-même. Il ne décrit pas une implémentation : il définit
ce que toute implémentation (J7) devra respecter. L'OWNER est **une personne physique authentifiée** (≠ acteur
« déclaré / non vérifié » du client, RS-029).

---

**Article 1 — Finalité.** L'OWNER MODE est la surface par laquelle le propriétaire **gouverne BrainAI de l'intérieur**
(patrimoine, délibérations, coûts, registre, évolution). Il n'est **jamais** une surface produit vendue au client ;
il n'exécute rien à la place du client.
*Observable : aucune capacité OWNER n'apparaît dans un ViewModel/contrat servi au client (chemin `brainai_app.server`).*

**Article 2 — Asymétrie de visibilité (le client ne voit jamais les moteurs).** L'OWNER voit ce que le client **ne
voit jamais** : le **patrimoine** (inventaire `patrimony.py`), les **délibérations** cognitives, les **coûts réels**,
le **registre** des capacités/décisions/apprentissages, le **journal** d'événements. Le client ne voit que sa
demande, la proposition, le livrable et son avancement **projeté depuis des faits**.
*Observable : pour toute réponse client, on peut nommer la source-fait de chaque élément affiché ; aucun objet de
délibération/moteur/coût-interne n'y figure. (Fondation : les 4 interfaces — Workspace **client** / Administration
**owner** / Développement / Observabilité — STATE-DEBRIEF-001.)*

**Article 3 — Le client voit un rôle, jamais un fournisseur.** Au client, BrainAI présente des **rôles métier**
(« un spécialiste de l'analyse métier »), **jamais** le nom d'un modèle/fournisseur (Claude, Anthropic, …). Le
fournisseur reste une information OWNER/Développement.
*Observable : aucun slug/nom de fournisseur (`claude_code`, `anthropic`, `claude-*`) dans une réponse client ; le
détail technique (provider/modèle) n'est accessible qu'en surface OWNER dépliable. (Source : J5, règle « rôle métier
vs provider ».)*

**Article 4 — Authentification forte de l'OWNER.** Toute action OWNER exige une **identité authentifiée et vérifiée**
(≠ l'attribution « déclarée / non vérifiée » RS-029 du client). Une action OWNER porte une attribution `verified:true`.
*Observable : tout fait produit par une action OWNER porte `actor.attribution="verified"` et `verified:true` ; une
action OWNER sans identité vérifiée est refusée. (Note : l'auth forte est J7 ; aujourd'hui `verified:true` est une
promesse non tenue — signalée RS-029/RS-011.)*

**Article 5 — Frontière OWNER / Workspace client.** Le client ne voit **jamais** les délibérations, les moteurs, les
coûts internes, ni le patrimoine. Le Workspace client est une **projection de faits** ; l'Administration OWNER est la
surface « à nu ». Aucune fuite d'une surface vers l'autre.
*Observable : le Workspace client ne contient aucun fait de délibération/coût-interne/patrimoine ; toute donnée OWNER
qui apparaîtrait côté client est un défaut. (Cohérent Doctrine 2 ; lien étanchéité RS-030/T1 : aucune identité
opérateur dans le contexte client.)*

**Article 6 — Propriété logique et intendance (Logical Owner / Steward / Consumers).** Chaque actif gouverné porte un
**propriétaire logique unique**, un **steward** (responsable de gouvernance, = propriétaire par défaut) et des
**consommateurs** (autorisés **et** observés — « l'autorisation est une règle, l'observation est un fait »). Seule
l'autorité de gouvernance (type Patrimony/Service Manager) modifie ces attributs.
*Observable : tout actif OWNER expose `logical_owner` (unique), `steward`, `authorized_consumers`, `observed_consumers` ;
un consommateur **observé mais non autorisé** est un signal de sécurité tracé. (Source : SCC-INFRASTRUCTURE-001B/001D.)*

**Article 7 — Gouvernance de l'auto-amélioration (Core / Lab).** BrainAI **capitalise** l'expérience mais **ne modifie
jamais son propre fonctionnement de manière autonome** (Doctrine 13). Toute évolution de méthode/prompt/logique passe
par un **acte OWNER attribué**. L'exploration d'auto-amélioration **libre** vit dans un **Lab isolé** (sandbox dédié,
aucune donnée client réelle, pas de clés de production, **kill-switch**, logs auditables, **validation humaine avant
toute réintégration** dans le Core).
*Observable : aucun changement de capacité/registre/prompt-système du Core sans fait OWNER `verified:true` ; toute
idée issue du Lab porte une trace de validation OWNER avant réintégration. (Source : J7, BrainAI Core/Lab.)*

**Article 8 — Workflow d'évolution gouvernée.** Toute évolution de BrainAI par l'OWNER suit une chaîne **tracée** :
**proposition → analyse d'impact → tests → validation propriétaire → déploiement → rollback possible → audit**.
Chaque étape est un fait append-only ; aucune étape n'est implicite ; le rollback est un **nouveau fait**, jamais une
suppression.
*Observable : pour toute évolution OWNER, la chaîne des 7 faits est reconstituable dans l'ordre ; un déploiement sans
validation propriétaire antérieure est un défaut. (Cohérent append-only I6 ; retraçabilité d'impact = RS-021.)*

**Article 9 — Primauté du cadre gelé.** L'OWNER MODE est **subordonné** au Plan Directeur v1.0 gelé, à R0–R12, aux
invariants I1→I9 et à la Constitution. En cas de conflit, le cadre gelé prévaut ; l'OWNER MODE n'introduit **aucun**
enchaînement automatique nouveau (I4).
*Observable : aucune capacité OWNER ne déclenche une action structurante sans acte humain distinct ; toute évolution
de l'OWNER MODE suit la règle d'or (pattern sur plusieurs cas, revue à trois, GO Frédérique).*

---

## Hors périmètre (rappel)
- **Implémentation OWNER = J7** (auth forte, surface d'administration réelle, Lab sandbox). Ici : **doctrine seulement**.
- **Non couvert / à arbitrer (RS-2)** : granularité de la visibilité par-tenant (lien multi-tenant, cf.
  `DOCTRINE-MULTI-TENANT-BYOK.md`) ; journal de changement du patrimoine ; qui peut éditer le registre (OWNER vs délégué).
- **Dépendances patrimoniales tracées** : Logical Owner (RS-020), Core/Lab (RS-019/RS-032), retraçabilité d'impact
  (RS-021), auth vérifiée (RS-011/RS-029), étanchéité (RS-030).
