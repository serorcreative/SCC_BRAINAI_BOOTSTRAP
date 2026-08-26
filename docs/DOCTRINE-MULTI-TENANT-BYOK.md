# Doctrine — Multi-tenant / BYOK / Managed / Mixte (v0.1)

*Doctrine **normative** (JALON 3 T4, Q6). **Écrite, pas implémentée** — l'implémentation est **dette post-v1**
(RS-031). Structure « article + observable ». Le cadre gelé (Plan Directeur v1.0, R0–R12, I1→I9, Constitution)
prévaut en cas de conflit. Sources patrimoniales réelles : `90_HERITAGE/…/BrainAI_Phase0_J4` (orchestration
souveraine BYOK/Managed/Mixte + impacts credentials/multi-tenant/facturation/RGPD), `…/BrainAI_Brief_Positionnement`
(modèle hybride avec souveraineté utilisateur, « BrainAI ne marge pas sur les API »), RS-015/RS-031.*

**Préambule.** Cette doctrine décrit **comment les credentials des fournisseurs tiers sont fournis** et leurs
conséquences (facturation, RGPD, souveraineté, responsabilité). Elle **ne construit rien** ; elle borne ce que toute
implémentation multi-tenant future (post-v1) devra respecter, et distingue ce qui est **bloquant** avant
commercialisation multi-clients de ce qui **ne bloque pas** les tests utilisateurs ni un pilote v1.

---

**Article 1 — Souveraineté utilisateur.** BrainAI **ne décide pas** à la place de l'utilisateur de l'infrastructure
qu'il doit utiliser. L'utilisateur **choisit son mode** de fourniture des credentials, au niveau du **compte**
(préférence par défaut) ou du **projet** (override).
*Observable : tout projet porte un `provisioning_mode` ∈ {byok, managed, mixte} attribué par un acte utilisateur ;
aucun mode n'est imposé silencieusement.*

**Article 2 — Les trois modes.**
- **BYOK** (*Bring Your Own Keys*) — l'utilisateur fournit ses propres clés/compte (Anthropic, OpenAI, plateformes…).
  BrainAI **orchestre uniquement**.
- **Managed** — BrainAI fournit les services et **refacture** les coûts. Expérience « clé en main ».
- **Mixte** — combinaison par ressource (ex. clé Anthropic perso + Supabase fourni par BrainAI).
*Observable : le mode d'un projet détermine, pour chaque fournisseur mobilisé, la source de credentials (utilisateur
vs BrainAI), tracée par ressource.*

**Article 3 — BrainAI ne marge pas sur les API.** BrainAI facture l'**orchestration/intelligence**, jamais une
**revente déguisée** d'API. En Managed, la refacturation reflète le **coût réel** (I6 : coûts `real`/`unavailable`,
jamais fabriqués) ; l'**optimisation des coûts** (conseil d'abonnements, choix du modèle le moins cher suffisant) est
une **valeur ajoutée**, pas une marge cachée.
*Observable : en Managed, le montant refacturé est traçable au coût réel consigné (`BudgetLedger`) ; aucune marge
implicite sur un appel API. Cf. RS-039 (coût honnête).*

**Article 4 — Propriété et cloisonnement des credentials.** Les credentials (clés API, jetons OAuth) sont **par
utilisateur ET par projet**, **chiffrés au repos**, avec **rotation/révocation** gouvernées. Un credential n'est
**jamais** injecté hors de son périmètre ; aucun secret n'entre dans un fait/journal versionné.
*Observable : aucun secret en clair dans un store/dépôt ; une révocation est un **nouveau fait** (append-only), jamais
une suppression ; un credential d'un tenant n'apparaît jamais dans le contexte d'un autre. (Lien étanchéité RS-030/T1,
redaction RV-1.)*

**Article 5 — Isolation multi-tenant.** Les données, projets et credentials de tenants distincts sont **strictement
isolés** (au repos et en contexte). L'observation d'un accès inter-tenant est un **incident de sécurité**.
*Observable : aucune lecture croise la frontière de tenant ; tout accès observé hors périmètre autorisé est tracé
comme signal (cf. « autorisation = règle, observation = fait », SCC-INFRASTRUCTURE-001B).*

**Article 6 — Facturation et responsabilité.** La granularité de facturation (par appel / par projet / par période)
et la **responsabilité contractuelle** en cas de fuite dépendent du mode (BYOK : responsabilité utilisateur ;
Managed : responsabilité éditeur). Toute dépense est **traçable** au coût réel.
*Observable : tout projet Managed expose une comptabilité par tenant traçable au `BudgetLedger` ; en BYOK, BrainAI
n'engage aucun coût fournisseur en propre.*

**Article 7 — RGPD & souveraineté.** Localisation, traçabilité et minimisation des données sont exigées dès la
conception (Vigilance 3 fondatrice). L'utilisateur reste **souverain** sur ses données et ses clés.
*Observable : pour tout projet, on peut nommer où vivent les données et quels traitements les touchent ; aucune donnée
personnelle n'est retenue au-delà du nécessaire.*

**Article 8 — Bloquant vs non-bloquant (clarification gelée).** Sont **bloquants** avant **commercialisation
multi-clients** : isolation des données au repos, comptabilité par tenant, traçabilité RGPD, rotation/révocation des
credentials. **Ne bloquent PAS** : les **tests utilisateurs** ni un **pilote v1** (mono-tenant, propriétaire dans la
boucle).
*Observable : un pilote v1 mono-tenant peut fonctionner sans la machinerie multi-tenant ; aucune fonctionnalité v1 ne
présuppose l'isolation multi-tenant.*

**Article 9 — Primauté du cadre gelé & non-implémentation.** Cette doctrine est **subordonnée** au Plan Directeur et
n'introduit **aucun** enchaînement automatique (I4). Son **implémentation est post-v1** (RS-031) ; rien ici n'est
construit en J3.
*Observable : aucun code multi-tenant/BYOK n'existe au JALON 3 ; toute implémentation future suit la règle d'or
(pattern, revue à trois, GO Frédérique).*

---

## Hors périmètre (rappel)
- **Implémentation = post-v1** (RS-031). Ici : **doctrine seulement**.
- **Dépendances** : RS-015 (doctrine J3, impl. post-v1), RS-031, RS-039 (coût honnête), RS-030/T1 (étanchéité
  credentials), OWNER MODE (frontière propriétaire/tenant, `DOCTRINE-OWNER-MODE.md`).
- **À arbitrer (RS-2)** : granularité exacte de facturation ; distinction fine Managed/Mixte au niveau ressource ;
  gestionnaire de secrets dédié (Vault) — post-v1.
