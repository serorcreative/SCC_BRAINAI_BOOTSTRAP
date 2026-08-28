"""L5 — intégration Core de bout en bout : l'expérience de livraison de Pursuit (Memory-11) atteint
réellement Learning-12 (sibling pinné) via ``bootstrap.learn()`` et produit un candidat gouverné.

Chemin prouvé : ``pursuit_delivered`` dans le vrai store Memory-11 → ``boot.learn()`` → ``LearningEngine.analyze()``
(couche Learning-12 réellement raccordée, injectée sur la mémoire vivante) → LearningItem ``pursuit_delivery``
au statut ``proposed``, evidence = IDs Memory-11 réels, aucune auto-application, Memory-11 strictement read-only.
CONNECTER, PAS RECONSTRUIRE : aucun moteur Learning parallèle n'est introduit côté Core.
"""

from __future__ import annotations

from brainai_app.delivery.memory import write_delivery_memory


def test_learn_produces_proposed_pursuit_delivery_candidate_end_to_end(boot):
    boot.run()                                             # boot d'abord (aucun ajout mémoire par learn ensuite)
    boot.memory.init()
    store = boot.memory.store

    # 1. Plusieurs pursuit_delivered réels avec pursuit_ref DISTINCTS dans le vrai store Memory-11 temporaire.
    for r in ("pursuit_a", "pursuit_b"):
        write_delivery_memory(store, pursuit_ref=r, project="site", result="obj",
                              decisions=["ok"], artifact_ref=None, preview_ref=None,
                              provenance_ids={"build_id": "b"}, as_of="t0", need="besoin", status="delivered")
    delivered = store.search(subtype="pursuit_delivered", limit=0)
    assert len({d["data"]["pursuit_ref"] for d in delivered}) == 2   # (2) refs distincts + (3) seuil natif atteint
    mem_ids = {d["id"] for d in delivered}

    before = store.counts()

    # 4. bootstrap.learn() utilise le Learning-12 réellement raccordé (sibling pinné, injecté sur la mémoire vivante).
    res = boot.learn()
    assert res["ok"] is True

    eng = boot.learning.engine(store)                      # moteur réellement construit et raccordé
    assert eng is not None

    # 5+6. Au moins un LearningItem pursuit_delivery produit, tous 'proposed'.
    sigs = eng.search(kind="signal", tag="pursuit_delivery")
    assert sigs
    items = (sigs + eng.search(kind="pattern", tag="pursuit_delivery")
             + eng.search(kind="lesson", tag="pursuit_delivery")
             + eng.search(kind="recommendation", tag="pursuit_delivery"))
    assert all(it["status"] == "proposed" for it in items)

    # 7. evidence = IDs Memory-11 réels.
    assert {ev for s in sigs for ev in s["evidence"]} <= mem_ids

    # 8. Aucune auto-application.
    audit = eng.audit()
    assert audit["safety"]["applied"] == []
    assert audit["safety"]["auto_changed_without_human"] == []

    # 9. Learning-12 n'écrit RIEN de supplémentaire dans Memory-11 (read-only).
    assert store.counts() == before
