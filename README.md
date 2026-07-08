# SCC BrainAI Bootstrap

**Le premier exécutable qui fait démarrer BrainAI.**

Charge la configuration, initialise les sous-systèmes, enregistre les premiers
Agents, puis déclare **« BrainAI READY »**. Il **réutilise** les composants SCC
existants via leurs interfaces publiques, sans en modifier aucun. Stdlib pur,
déterministe, sans réseau.

## Démarrer

```bash
cd 17_BRAINAI_BOOTSTRAP
python -m pip install -e .        # expose la commande `scc-brainai`
scc-brainai start
```

```
[1/8] config          ✓ scc_root=01_CCSC
[2/8] control_plane   ✓ santé=ok
[3/8] patrimony       ✓ 21/21 composants présents
[4/8] memory          ✓ entrées=0
[5/8] knowledge       ✓ entrées=0
[6/8] event_bus       ✓ ouvert (5 événements)
[7/8] agents          ✓ 4 agent(s) enregistré(s)

BrainAI READY
```

## Séquence de démarrage (les 8 étapes)

1. **Configuration** — charge `config/brainai.json` (scc_root, `as_of`, premiers agents).
2. **Control Plane** — réutilise `09_CONTROL_PLANE` (`ControlPlane().health()`).
3. **Patrimony Manager** — inventaire du patrimoine de BrainAI (21 composants/actifs).
4. **Memory** — réutilise `11_BRAINAI_MEMORY` (`BrainMemoryStore`).
5. **Knowledge** — réutilise `04_KNOWLEDGE` (`KnowledgeEngine`).
6. **Event Bus** — bus d'événements en process (publish/subscribe, append-only).
7. **Premiers Agents** — enregistre les rôles pivots depuis `00_SYSTEM/agents`.
8. **« BrainAI READY »**.

Chaque étape publie un événement sur l'Event Bus. Un composant absent n'arrête pas
le démarrage : l'étape est signalée et BrainAI démarre en **mode dégradé**.

## Nouveaux sous-systèmes de cette couche

- **Patrimony Manager** (`patrimony.py`) — inventaire en lecture seule de ce dont
  BrainAI est fait (moteurs, Runtime, API, Control Plane, couches BrainAI, catalogues).
- **Event Bus** (`event_bus.py`) — bus léger du cycle de vie de BrainAI, point
  d'abonnement pour les couches supérieures (distinct du journal de jobs du Runtime).

## Utilisation (Python)

```python
from scc_brainai_bootstrap import BrainAIBootstrap

report = BrainAIBootstrap().run()
print(report["banner"])            # "BrainAI READY"
```

## Tests

```bash
python -m pytest -q      # 17 tests (déterministes ; démarrage réel des composants)
```

Détails : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
