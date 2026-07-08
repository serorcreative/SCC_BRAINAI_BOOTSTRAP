# ADR-UI-009 — État, cache et fonctionnement offline

- **Statut :** ✅ **Architecture acceptée** · ⏳ **Implémentation différée** · 🚫 **Aucune technologie de persistance choisie à ce stade**
- **Phase :** Produit BrainAI — gestion de l'état côté interfaces
- **Principes cadres :** Doctrine n°6 (le Contrat est l'unique source de vérité) · Doctrine n°7 (les shells ne portent aucune logique métier).

> **Portée :** cet ADR décide l'**architecture** de l'état/cache/offline des interfaces. Il ne
> demande **aucune implémentation**, ne change **ni Bootstrap, ni Transport, ni Contrat, ni les
> shells existants**, et ne choisit **aucune base de données locale**.

## 1. Pourquoi l'état UI doit rester séparé du cerveau

Le cerveau (Bootstrap) est **déterministe et autoritatif** ; son état officiel est exposé
**uniquement** par le Contrat. Si l'interface devenait une seconde source de vérité, on
violerait la Doctrine n°6 et on créerait de la **désynchronisation**. Donc :

> **L'interface *reflète* l'état officiel ; elle ne le *possède* ni ne le *modifie* jamais localement.**

Deux natures d'état, strictement séparées.

## 2. Ce qui relève de l'état **local d'interface** (non autoritatif)

Éphémère, propre à l'appareil, purement présentationnel :
- préférences de vue (thème, disposition, panneaux repliés/dépliés, tris, filtres) ;
- navigation, position de défilement ;
- **brouillons** de saisie (avant soumission) ;
- indicateurs (connexion, « actualisation… », horodatage du dernier rafraîchissement).

Jamais une source de vérité, jamais envoyé au cerveau *comme vérité*.

## 3. Ce qui relève de l'état **officiel exposé par BrainAI** (autoritatif)

Tout ce que le Contrat expose (`overview` et ses sections, `session`, `agents`, `capabilities`,
`learnings`, décisions ouvertes, journal, diagnostics, prochaine action…). **Autoritatif**,
produit par le cerveau, **reflété en lecture seule** par l'UI.

## 4. Rôle du Client TypeScript

- Le client est l'**unique porte** vers l'état officiel : il appelle les opérations `read` du
  Contrat et renvoie des enveloppes typées.
- Il reste **mince et sans état** (il *reflète* le Contrat) ; **le cache est une couche
  *au-dessus* du client**, pas dans le client. Le test de conformité protège toujours le Contrat.

## 5. Rôle éventuel d'un cache (Web / Desktop / Mobile)

Le cache est une **copie côté UI** de l'état officiel, pour : rendu instantané au chargement,
survie à une coupure brève, réduction des rafraîchissements. **Invariant : le cache est
toujours un reflet *périmable*, jamais autoritatif ; un fetch réussi le remplace.**

| Shell | Cache mémoire | Cache persistant (survie au redémarrage) |
|-------|---------------|-------------------------------------------|
| **Web** | oui (actuel) | optionnel, **minimal** (péremption + confidentialité) |
| **Desktop** | oui | optionnel (démarrage instantané), stockage local Tauri |
| **Mobile** | oui | **plus utile** (réseau instable, app suspendue) — mais **stockage sécurisé** (données officielles éventuellement sensibles) |

*(Aucune techno de persistance n'est choisie ici — localStorage / IndexedDB / SQLite / store
Tauri / stockage sécurisé mobile restent à décider en implémentation.)*

## 6. Fonctionnement en cas de perte de connexion

- Transport injoignable → l'UI affiche le **dernier instantané connu** (depuis le cache) avec un
  **indicateur explicite** « hors ligne · données du &lt;horodatage&gt; ». **Lecture seule.**
- **Aucun nouvel état officiel** ne peut être produit hors ligne (le cerveau est injoignable).
- **Aucune mutation hors ligne** (pas de décision/validation sans le cerveau).
- Au retour du réseau → refetch → **réconciliation** : l'état frais du Contrat remplace le cache ;
  l'indicateur disparaît.

## 7. Lecture seule vs état temporaire vs état validé

| Type | Qui le produit | Autorité | Exemple |
|------|----------------|----------|---------|
| **Lecture seule (officiel)** | le cerveau, via le Contrat | **autoritatif**, immuable dans l'UI | `overview`, décisions ouvertes |
| **Temporaire (local UI)** | l'utilisateur dans l'UI | **non autoritatif**, jetable | brouillon de formulaire, sélection, placeholder optimiste |
| **Validé (officiel)** | **le cerveau seul** (accepté/persisté) | autoritatif | décision validée, apprentissage enregistré |

**Règle** : l'UI ne « valide » jamais localement. Un état temporaire ne devient **validé**
qu'après passage par le cerveau (gouverné), puis reflété via refetch. L'UI **ne court-circuite
jamais** cette chaîne (Doctrines n°5/n°7).

## 8. Limites du mode offline

- **Pas de calcul du cerveau hors ligne** (déterministe, sur l'hôte, pas sur le client).
- **Pas de mutation hors ligne** ; **pas d'état validé** créé hors ligne.
- Offline = **instantané périmé en lecture seule**, dont la **péremption est visible**.
- Un cache persistant de données officielles = **enjeu de confidentialité** → stockage sécurisé
  (mobile), minimal (web) ; chiffrement au repos = décision d'implémentation.

## 9. Risques de désynchronisation

| Risque | Garde-fou |
|--------|-----------|
| Cache périmé affiché comme courant | indicateur de péremption + horodatage (`generated_as_of`) |
| UI optimiste divergeant du cerveau (futur) | **pas d'optimisme** pour les actions gouvernées ; réconciliation au refetch |
| Multi-appareils voyant des instantanés différents | chacun reflète le cerveau ; le cerveau est l'unique vérité ; refetch réconcilie |
| Dérive / cache « empoisonné » | garde de version du client + cache non autoritatif (toujours écrasé par un fetch frais) |

## 10. Règles de rafraîchissement

- **Rafraîchissement périodique** à intervalle raisonnable (actuel : 5 s, D5).
- **Refetch au retour de connexion** ; refetch au focus (optionnel).
- **Un fetch réussi remplace toujours le cache.**
- Indicateur « actualisation… » en arrière-plan (D5) ; « hors ligne + instantané » en échec.
- **Rafraîchissement manuel** = une **lecture** (autorisé, ce n'est pas une action).

## 11. Architecture vs implémentation

**Relève de l'ARCHITECTURE (décidé ici) :**
- État officiel = Contrat, **unique source de vérité** (n°6) ; l'UI reflète, ne possède/mute jamais.
- Séparation stricte **officiel** (lecture seule) vs **local UI** (éphémère).
- Cache = reflet **non autoritatif**, toujours remplacé par un fetch frais ; péremption **visible**.
- Offline = instantané périmé **lecture seule** + indicateur ; **aucune mutation / aucun état validé hors ligne**.
- Distinction **lecture seule / temporaire / validé**.
- Client **mince** ; cache **au-dessus** du client ; shells = état **présentationnel** uniquement (n°7).

**Relève de l'IMPLÉMENTATION future (différé) :**
- **Technologie de persistance** (localStorage / IndexedDB / SQLite / store Tauri / stockage
  sécurisé mobile) — **non choisie**, à justifier ; chiffrement au repos.
- Où/quoi persister par shell ; intervalles/backoff/focus précis ; UX offline détaillée.
- **UI optimiste** (pertinente seulement avec les actions gouvernées) — différée et **contrainte**.

## 12. Impacts

- **Web** : cache mémoire (actuel) ; persistance optionnelle minimale ; offline = instantané + indicateur.
- **Desktop** : cache mémoire + persistance optionnelle (démarrage instantané) ; offline = instantané.
- **Mobile** : cache persistant plus utile (réseau instable, suspension) ; **stockage sécurisé** ;
  offline = instantané + indicateur fort. (Le cache/offline prend tout son sens avec ADR-UI-004.)
- **Contrat / Transport / Bootstrap** : **aucun** impact (Doctrine n°6 ; l'état/cache est une
  préoccupation *de l'interface*, au-dessus du client).
- **Futures actions distantes gouvernées** : le modèle impose **temporaire ≠ validé** ; les
  actions passent par le cerveau (validation humaine) ; **jamais** de file d'actions hors ligne
  faisant croire à un succès. Toute file offline pour des actions = **décision explicite et
  gouvernée ultérieure** (probablement rejetée pour les actions gouvernées).

## 13. Risques & garde-fous (synthèse)

- **Risque** : confondre reflet et vérité → **garde-fou** : cache non autoritatif, péremption visible.
- **Risque** : faux succès offline → **garde-fou** : aucune mutation/validation hors ligne.
- **Risque** : fuite de données en cache → **garde-fou** : stockage sécurisé (mobile), minimal (web), chiffrement (impl.).
- **Risque** : shell qui « décide » → **garde-fou** : n°7, l'UI présente/reflète, le cerveau valide.

## 14. Prérequis

- **ADR-UI-004** (accès réseau) : le cache/offline prend son intérêt réel pour le distant/mobile.
- **Futur ADR « actions à distance gouvernées »** avant toute écriture / UI optimiste.

## 15. Scénarios d'évolution

1. Cache mémoire (fait, D5) → cache persistant par shell (optionnel) → indicateur d'instantané offline.
2. Mobile : cache persistant **sécurisé** + mode hors ligne.
3. Actions gouvernées : séparation stricte temporaire/validé ; réconciliation par refetch ; **aucun faux succès offline**.

## 16. Conclusion

- **Décision finale : ACCEPTÉE** pour l'*architecture* de l'état/cache/offline ; **DIFFÉRÉE**
  pour l'implémentation ; **aucune techno de persistance choisie**.
- **Conséquences sur l'architecture BrainAI** : le cerveau **reste l'unique source de vérité**
  (n°6) ; le Contrat, le Transport et le Bootstrap sont **inchangés** ; l'UI **reflète, met en
  cache (non autoritatif) et se dégrade en lecture seule périmée hors ligne** ; les shells
  restent **sans logique métier** (n°7).
- **Feuille de route** : (1) formaliser l'indicateur d'instantané/offline ; (2) cache persistant
  par shell (techno à choisir) ; (3) stockage sécurisé mobile ; (4) alignement avec ADR-004 et le
  futur ADR d'actions gouvernées.

ADR-UI-009 **ne lance aucun chantier**. Il fixe la discipline d'état des interfaces : *refléter,
jamais posséder ; mettre en cache sans autorité ; se dégrader proprement hors ligne*.
