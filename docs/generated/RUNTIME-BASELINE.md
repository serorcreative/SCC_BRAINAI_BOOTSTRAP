# Baseline runtime — stores de faits (L0-F, généré, lecture seule)

> Généré par `scripts/generate_runtime_baseline.py`. NE PAS ÉDITER À LA MAIN.
> Aucune valeur/contenu de fait n'est exposé ; les ids de Pursuit sont hachés.
> Machine-readable : `registry/baseline/runtime.json`. `data/` est gitignoré (non versionné).

- **Stores JSONL** : 9
- **Répertoire data** : `data/` (existe = True)

| Store | Enregistrements | Pursuits distinctes | SHA-256 (court) | Taille (o) | Clés (1er) |
|---|---|---|---|---|---|
| `data/cognition/decision/decisions.jsonl` | 7 | 0 | `7b9ddb9c67e0` | 39932 | as_of, execution_manifest, explanation, failure_criteria, id, options, provider, qualification, rationale, request, revocation_conditions, selected_id, status, success_criteria, traceability, validation, validation_conditions |
| `data/cognition/execution/executions.jsonl` | 1 | 0 | `43741326d86d` | 4340 | as_of, authorization, decision_id, events, guards, id, provider, report, request, status, steps, subject, traces_for_memory |
| `data/cognition/reasoning/deliberations.jsonl` | 9 | 0 | `8004c96dd6c5` | 71479 | arbitration, as_of, constraints, decision, decomposition, explanation, facts, hypotheses, id, inferences, options, problem, provider, risks |
| `data/dossier_links.jsonl` | 4 | 0 | `032524340dce` | 772 | attached_as_of, attached_by, dossier_id, input_id, kind, link_id |
| `data/dossiers.jsonl` | 2 | 0 | `e182d4850a97` | 499 | correlation_key, dossier_id, label, opened_as_of, opened_by, request_id, seed, status |
| `data/events.jsonl` | 2 | 0 | `d2103831ec65` | 349 | actor, payload, seq, timestamp, topic |
| `data/inputs.jsonl` | 6 | 0 | `4b771be5d8e2` | 2412 | actor, as_of, content, context, fidelity, id, ingested_at, integrity, modality, observed_at, provenance, session_id |
| `data/memory/brain_memory.jsonl` | 76 | 0 | `815d5eee777f` | 35333 | actor, data, hash, id, kind, prev_hash, redacted, session_id, subtype, tags, timestamp |
| `data/memory/brain_sessions.jsonl` | 19 | 0 | `5b9c5331ace8` | 6175 | actor, entry_ids, id, meta, started_at, status, summary, updated_at |

## Fichiers non-JSONL sous data/ (chemins seulement)

- `data/session.json`

