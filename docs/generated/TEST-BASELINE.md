# Baseline de tests — Core BrainAI (L0-E, genere)

> Genere par `scripts/generate_test_baseline.py` (transformateur pur) depuis la sortie
> JUnit-XML reelle du runner + metadonnees explicites. NE PAS EDITER A LA MAIN.
> Machine-readable : `registry/baseline/tests.json`.

- **Core commit teste** : `8e8979d` (branche `reunification/l0-integrity`)
- **Runtime** : Python 3.9.6 · pytest 8.4.2
- **Commande** : `.venv/bin/python -m pytest -p no:cacheprovider (BRAINAI_JALON_LLM unset)`

## Resultats (comptages issus des attributs <testsuite> JUnit)

- **passed** : 686
- **failed** : 0
- **errors** : 0
- **skipped** : 1 (inclut le test facturable exclu)
- **total collectes** : 687
- **duree** : 16.78 s (snapshot, variable)
- **xfailed / xpassed** : non distinguables des attributs `<testsuite>` (non inventes)

## Garanties (bornees a cette execution)
- **0 LLM (observe)** : gate `BRAINAI_JALON_LLM` unset ; `test_real_claude_brief` skippe ; frontieres externes locales/monkeypatchees. NE prouve pas une impossibilite reseau universelle.
- **data/ non modifie** : observe=True.
- **arbre Git non modifie** : observe=True.

> Limites : 'test passe' != 'capacite exercee en runtime reel' : cette baseline prouve la non-regression deterministe, pas l'exercice LLM reel (Etage 2, hors perimetre 0 euro). Snapshot date (duree variable) : non byte-reproductible ; la CI ne le regenere pas.

