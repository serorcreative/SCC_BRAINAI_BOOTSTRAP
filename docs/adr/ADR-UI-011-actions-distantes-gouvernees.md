# ADR-UI-011 — Actions à distance gouvernées

- **Statut :** ✅ **Cadre architectural ACCEPTÉ** · ⏳ **Implémentation DIFFÉRÉE** · 🔒 **Actions à distance DÉSACTIVÉES** tant que le cadre n'est pas implémenté (et ADR-UI-004 réalisé)
- **Phase :** Produit BrainAI — gouvernance des actions demandées à distance
- **Principes cadres :** Doctrine n°5 (l'interface présente, elle n'agit jamais d'elle-même) · Doctrine n°6 (le Contrat est l'unique source de vérité) · Doctrine n°7 (les shells ne portent aucune logique métier).

> **Portée :** cet ADR décide l'**architecture** des actions à distance. Il ne demande **aucune
> implémentation**, ne change **ni Bootstrap, ni Transport, ni Contrat**, n'introduit **aucune
> file d'actions offline** ni **UI optimiste validante**, et ne met **aucune logique métier**
> dans les shells ou le Client.

## 1. Pourquoi BrainAI est en lecture seule côté UI aujourd'hui

- **Sûreté** : aucune surface d'action = aucun risque de mutation non voulue depuis un client (a fortiori distant).
- La **gouvernance** (validation humaine, garde-fou T3, acteur autorisé, préconditions) a été
  conçue **dans le cerveau** ; l'UI n'avait pas encore de moyen **sûr** de *demander* une action
  sans devenir décideuse.
- **Simplicité** : la lecture seule a validé toute la chaîne (transport/client/SPA) sans la
  sécurité et la gouvernance dures des actions (ADR-UI-004 fixe « remote = lecture seule »).

## 2. Pourquoi les actions distantes nécessitent un cadre spécifique

Une action **mute** un état gouverné (proposer une décision, valider un apprentissage, exécuter).
Le faire depuis un client distant soulève : exécution non voulue, double exécution, désync,
sécurité (auth/authz), auditabilité, et la **tentation de laisser l'UI décider**. Le cadre doit
garantir que **l'UI ne fait que *demander*** ; **le cerveau *décide*, *valide*, *exécute* et
*gouverne* toujours**.

## 3. Les six étapes (colonne vertébrale conceptuelle)

| Étape | Définition | **Propriétaire** |
|-------|-----------|------------------|
| **Affichage d'état** | l'UI reflète l'état officiel (lecture seule, ADR-009) | cerveau (source) → UI (reflet) |
| **Intention utilisateur** | le·la humain·e forme une intention dans l'UI (ex. « valider la décision X ») | UI — état **temporaire**, non autoritatif ; **pas encore une action** |
| **Demande d'action** | sur confirmation explicite, l'UI envoie une **requête** via le Contrat | UI **transmet** → cerveau **reçoit** ; ce n'est **pas** une décision |
| **Validation** | le cerveau évalue la requête (T3, validation humaine, acteur autorisé, préconditions) | **cerveau** — l'UI ne valide **jamais** |
| **Exécution** | si acceptée, le moteur d'exécution agit (via le Runtime), sous garde-fous | **moteurs** — l'UI n'exécute **jamais** |
| **Résultat** | le cerveau produit l'issue + le nouvel état officiel | cerveau (produit) → UI (reflète) |

**Flux :** intention (local) → demande (Contrat) → **validation (cerveau)** → **exécution
(moteurs)** → résultat → reflet UI. **L'UI est *demandeuse* et *reflet* — jamais décideuse.**

## 4. La notion d'**action gouvernée**

Une **action gouvernée** est une action que **seul le cerveau** peut accepter, valider et
exécuter, sous ses règles (validation humaine pour l'irréversible/T3, acteur autorisé,
préconditions/critères de succès/échec/abandon, traçabilité). **L'UI ne peut que la *demander*.**
La gouvernance vit **entièrement dans le cerveau** ; *demander ≠ décider*.

## 5. Cycle de vie d'une action (états à distinguer)

| État | Signification | Produit par |
|------|---------------|-------------|
| **Demandée** | l'UI a envoyé la requête ; le cerveau l'a reçue | UI → cerveau |
| **Acceptée** | la gouvernance autorise à poursuivre (proposée/validée selon l'opération) | **cerveau** |
| **Refusée** | garde-fou : non validée, acteur non autorisé, précondition non remplie | **cerveau** |
| **Exécutée** | le moteur a terminé avec succès ; état officiel mis à jour | **moteurs** |
| **Échouée** | exécution tentée mais échouée (critères d'échec) ; échec enregistré | **cerveau/moteurs** |

Ces états sont **détenus par le cerveau** et **reflétés** par l'UI. L'UI n'en **fabrique jamais**
(pas d'« exécutée » optimiste).

## 6. Rôles

- **Contrat (axe unique)** : les opérations d'action **existent déjà** dans le Contrat
  (`decide`, `plan`, `validate_decision`, `execute_decision`, `validate_learning`…) ; elles ne
  sont simplement **pas exposées à distance** (ADR-004 : remote = lecture seule). Les exposer
  *plus tard* est une décision d'**exposition transport**, pas une nouvelle logique. Le Contrat
  reste la source de vérité ; requêtes **et** résultats passent par lui. **Aucun changement maintenant.**
- **Transport** : achemine les requêtes d'action sur un **canal sécurisé** (ADR-004). C'est un
  **tuyau** (n°6) : il **ne décide pas** ; il authentifie/autorise l'appelant et **transmet** à la
  Presentation ; le cerveau gouverne. Remote reste lecture seule **jusqu'à** l'implémentation de ce cadre.
- **Client TypeScript** : **transmet** la requête (opération d'action du Contrat) et **reflète**
  le résultat. **Aucune logique métier** : il ne décide pas l'acceptation, ne valide pas, ne
  fabrique aucun état de résultat. Réutilise le `fetch` injectable. **Aucune UI optimiste validante.**
- **Shells (Web / Desktop / Mobile)** : présentent l'UI d'intention (confirmation explicite),
  envoient la requête via le client, **reflètent** le résultat. **Aucune logique métier** (n°7) ;
  ils ne valident/exécutent/décident **jamais**. Mobile : idem, sur le canal sécurisé (ADR-004).

## 7. Liens avec les autres ADR

- **ADR-UI-004 (accès réseau sécurisé)** : **prérequis**. Les actions à distance exigent le cadre
  réseau sécurisé (auth par appareil, chiffrement, autorisation). Activer les actions à distance
  est un **opt-in explicite et gouverné**, **au-delà** du « remote = lecture seule ».
- **ADR-UI-009 (état, cache, offline)** : **temporaire ≠ validé** ; **aucune file d'actions
  offline** ; **aucune UI optimiste** ; cache non autoritatif. Une demande d'action est une
  **intention temporaire** tant que le cerveau n'a pas produit un **résultat validé**. **Hors
  ligne : aucune action** (impossible de gouverner sans le cerveau).

## 8. Risques & garde-fous

| Risque | Garde-fou |
|--------|-----------|
| **Exécution non voulue** | confirmation explicite dans l'UI (intention → confirmer → demande) ; gouvernance cerveau (validation humaine, acteur autorisé) ; remote = lecture seule sauf opt-in gouverné |
| **Double exécution** | **clé d'idempotence** sur la requête (rejouer = même résultat, pas de ré-exécution) **+** garde-fous d'exécution **existants** du cerveau (une décision validée s'exécute **une fois** ; ré-exécution refusée) |
| **Désynchronisation** | le cerveau est l'unique vérité ; résultat reflété via Contrat/refetch ; l'UI ne fabrique aucune issue ; cache non autoritatif (ADR-009) |
| **Actions hors ligne** | **interdites** — aucune file offline ; hors ligne = lecture seule ; l'action exige un aller-retour gouverné en direct |
| **Confiance excessive dans l'UI** | l'UI n'est **jamais** de confiance pour décider/valider/exécuter ; le cerveau **re-vérifie tout** (autorisation, préconditions, garde-fous) quoi qu'ait envoyé l'UI (entrée non fiable) |
| **Sécurité** | auth par appareil (ADR-004), chiffrement, **autorisation des opérations d'action** (plus stricte que la lecture), audit |
| **Auditabilité** | chaque requête/résultat tracé dans le cerveau (traçabilité existante : décisions, exécutions, Event Bus, Memory) ; requêtes **attribuables** (qui/quel appareil/quand) |

## 9. Exigences de traçabilité

- Chaque requête d'action porte : **identité de l'acteur** (credential par appareil → acteur),
  **clé d'idempotence**, horodatage (audit).
- Le cerveau **enregistre** : requête reçue → décision de gouvernance (acceptée/refusée + raison)
  → exécution (faite/échouée + résultat), via sa traçabilité existante (enregistrements de
  décision, runs d'exécution, Event Bus, ingestion Memory).
- **Attribution obligatoire** : l'acteur doit être identifiable et autorisé ; la gouvernance (T3)
  peut exiger une validation humaine **indépendamment** du demandeur.

## 10. Architecture vs implémentation

**Relève de l'ARCHITECTURE (décidé ici) :**
- Les **6 étapes** (affichage / intention / demande / validation / exécution / résultat) et leurs propriétaires.
- Les **5 états** (demandée / acceptée / refusée / exécutée / échouée), détenus par le cerveau, reflétés par l'UI.
- Les actions à distance = **requêtes** vers des opérations **gouvernées** ; le cerveau gouverne toujours ; **l'UI ne décide/valide/exécute jamais**.
- Invariants : **aucune action hors ligne**, **aucune UI optimiste validante**, **aucune logique**
  dans l'UI/Client, cache non autoritatif, **Contrat inchangé** (les actions réutilisent les
  opérations existantes une fois exposées), transport = tuyau sécurisé.
- Exigences : **idempotence**, **auditabilité/attribution**, **re-vérification côté cerveau (UI
  non fiable)**, opt-in **explicite et gouverné** pour activer les actions à distance.
- Dépendances : **ADR-004 prérequis** ; **ADR-009** régit le côté UI.

**Relève de l'IMPLÉMENTATION future (différé) :**
- **Exposer** les opérations d'action sur le transport (aujourd'hui lecture seule) — opt-in futur, explicite, gouverné.
- Mécanisme de **clé d'idempotence** (pourra **étendre** les requêtes d'action du Contrat *plus tard* — changement **versionné et gouverné**, **pas maintenant**).
- **Modèle d'autorisation** des opérations d'action (mapping appareil → acteur ; permissions par opération).
- **Flux de validation humaine** dans les shells (UX).
- Restitution de l'**audit**.

## 11. Décisions & décisions différées

- **Décidé** : le cadre (étapes, états, invariants, exigences) ci-dessus.
- **Différé** : toute l'implémentation (§10), l'activation des actions à distance, l'idempotence,
  l'autorisation, l'UX de validation, l'extension éventuelle du Contrat.
- **Interdit (non différé — banni)** : file d'actions offline, UI optimiste validante, logique
  métier dans l'UI/Client.

## 12. Prérequis

1. **ADR-UI-004** réalisé (réseau sécurisé + auth par appareil).
2. **Modèle d'autorisation** des opérations d'action + attribution.
3. **Idempotence** + audit (peut étendre le Contrat, versionné/gouverné).

## 13. Scénarios d'évolution

1. Remote **lecture seule** (actuel, ADR-004) → **inchangé** tant que ce cadre n'est pas implémenté.
2. Activation **locale** des actions gouvernées via l'UI (même machine, avant le distant), pour éprouver l'UX intention→confirmation→reflet.
3. Actions **à distance** gouvernées (après ADR-004) : opt-in explicite, par opération, avec idempotence + audit + autorisation.
4. Validation humaine **dans l'UI** comme reflet d'une étape de gouvernance du cerveau (jamais une décision locale).

## 14. Conclusion

- **Décision finale : cadre ACCEPTÉ (architecture) · implémentation DIFFÉRÉE · actions à distance
  DÉSACTIVÉES** jusqu'à réalisation du cadre et d'ADR-004. Ce n'est **ni** un rejet **ni** une
  implémentation : le cadre est posé, rien n'est construit.
- **Conséquences sur l'architecture BrainAI** : le cerveau reste **l'unique gouverneur** ; le
  **Contrat est inchangé** (source de vérité, n°6) ; l'UI, le Client et le Transport **ne gagnent
  aucune logique** (n°7) ; remote reste **lecture seule** jusqu'à un opt-in **explicite et
  gouverné** qui activera les actions **dans ce cadre**.
- **Feuille de route** : (1) réaliser ADR-004 (réseau sécurisé) ; (2) modèle d'autorisation des
  actions + attribution ; (3) idempotence + audit (peut étendre le Contrat, gouverné/versionné) ;
  (4) UX de validation humaine dans les shells ; (5) opt-in explicite pour activer les actions,
  par opération, lecture seule par défaut.

ADR-UI-011 **ne lance aucun chantier**. Il garantit qu'à terme, une interface pourra *demander*
une action au cerveau — **sans jamais** que l'UI, le Client, le cache ou le Transport ne
deviennent porteurs de décision : *demander, jamais décider ; refléter, jamais fabriquer*.
