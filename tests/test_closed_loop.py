"""Tests de la boucle fermée : apprentissages *validés* → Planning / Decision.

Garde-fou central : seule une recommandation **validée** influence la cognition ;
rien de proposé/rejeté ne doit apparaître dans un plan ou une décision.
"""

from __future__ import annotations

import copy
import json

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap


_EXPERIENCE = [
    "Explique l'architecture", "Explique l'architecture",
    "état du système", "état du système", "Montre le graphe",
]


def _seed_and_learn(boot):
    for q in _EXPERIENCE:
        boot.handle(q)
    boot.learn()
    return boot


def _validate_all_recommendations(boot):
    ids = [it["id"] for it in boot.learnings(kind="recommendation")["items"]]
    for rid in ids:
        boot.validate_learning(rid, "frederique", "go")
    return ids


def test_cognition_learns_when_engine_present(boot):
    _seed_and_learn(boot)
    assert boot.cognition.learns is True


def test_validated_recommendations_become_plan_tasks(boot):
    _seed_and_learn(boot)
    ids = _validate_all_recommendations(boot)
    assert ids, "au moins une recommandation attendue"
    plan = boot.plan("Améliorer la gouvernance documentaire")
    assert plan["ok"] is True
    assert plan["learns"] is True
    assert len(plan["learning_tasks"]) == len(ids)
    # chaque tâche issue d'apprentissage trace sa source
    sources = {s for t in plan["learning_tasks"] for s in t["sources"]}
    for rid in ids:
        assert f"learning:{rid}" in sources


def test_unvalidated_learnings_do_not_influence_plan(boot):
    _seed_and_learn(boot)                # produit mais NE valide PAS
    plan = boot.plan("Améliorer la gouvernance documentaire")
    assert plan["ok"] is True
    assert plan["learning_tasks"] == []          # garde-fou : rien de non validé
    assert plan["applied_learnings"] == []


def test_rejected_recommendation_excluded(boot):
    _seed_and_learn(boot)
    ids = [it["id"] for it in boot.learnings(kind="recommendation")["items"]]
    # valider la première, rejeter le reste
    boot.validate_learning(ids[0], "frederique", "go")
    for rid in ids[1:]:
        boot.validate_learning(rid, "frederique", "non", action="reject")
    plan = boot.plan("Améliorer la gouvernance")
    applied = {s.split(":", 1)[1] for t in plan["learning_tasks"] for s in t["sources"]}
    assert ids[0] in applied
    for rid in ids[1:]:
        assert rid not in applied


def test_decide_cites_validated_learnings(boot):
    _seed_and_learn(boot)
    ids = _validate_all_recommendations(boot)
    decision = boot.decide("Faut-il refactorer ou réécrire ?")
    assert decision["ok"] is True
    assert sorted(decision["applied_learnings"]) == sorted(ids)


def test_decide_without_validated_learnings(boot):
    _seed_and_learn(boot)                # aucune validation
    decision = boot.decide("Faut-il refactorer ou réécrire ?")
    assert decision["applied_learnings"] == []


def test_plan_event_on_bus(boot):
    _seed_and_learn(boot)
    _validate_all_recommendations(boot)
    boot.plan("Améliorer la gouvernance")
    ev = [e for e in boot.bus.events if e["topic"] == "plan.created"]
    assert ev and ev[0]["payload"]["from_learning"] >= 1


def test_plan_is_proposal(boot):
    _seed_and_learn(boot)
    plan = boot.plan("Améliorer la gouvernance")
    assert plan["needs_human_validation"] is True


def test_closed_loop_deterministic(config):
    def run(name):
        cfg = copy.copy(config); cfg.data_dir = config.data_dir.parent / name
        b = BrainAIBootstrap(config=cfg)
        _seed_and_learn(b)
        _validate_all_recommendations(b)
        return b.plan("Améliorer la gouvernance documentaire")
    a, b = run("la"), run("lb")
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False)


def test_closed_loop_persists_cross_process(config):
    shared = config.data_dir.parent / "loop_shared"

    def at_shared():
        cfg = copy.copy(config); cfg.data_dir = shared
        return BrainAIBootstrap(config=cfg)

    b1 = at_shared(); _seed_and_learn(b1); ids = _validate_all_recommendations(b1)
    # process distinct : le plan doit refléter les validations persistées
    b2 = at_shared()
    plan = b2.plan("Améliorer la gouvernance documentaire")
    assert len(plan["learning_tasks"]) == len(ids)
