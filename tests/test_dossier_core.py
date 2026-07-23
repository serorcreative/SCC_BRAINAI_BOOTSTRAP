"""Tests du noyau Dossier (DOSSIER-CORE-001).

Prouve : l'ouverture **gouvernée** d'un Dossier (unité durable de travail) via une **demande
d'ouverture idempotente**. Identité de la demande dérivée **uniquement** de ``{actor,
correlation_key}`` ; contenu canonique (``seed``) **figé à la première réception** ; **rejeu**
idempotent ; **conflit** sur même clé + contenu différent ; **deux intentions distinctes** →
deux Dossiers ; **acteur explicite requis** ; **audit** distinguant ouverture/rejeu/conflit ;
**comparaison canonique** du sujet ; lectures liste/détail.
"""

from __future__ import annotations

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.core.config import load_config
from scc_brainai_bootstrap.presentation import Presentation


def test_open_creates_dossier(boot):
    r = boot.open_dossier("Préparer la V1", "key-abc", "alice")
    assert r["ok"] is True and r["replayed"] is False
    assert r["dossier_id"].startswith("dos_") and r["request_id"].startswith("dosreq_")
    assert r["status"] == "open" and r["label"] == "Préparer la V1" and r["opened_by"] == "alice"


def test_replay_same_intention_returns_same_dossier(boot):
    a = boot.open_dossier("Sujet", "key-1", "alice")
    b = boot.open_dossier("Sujet", "key-1", "alice")          # rejeu strict
    assert b["replayed"] is True and b["dossier_id"] == a["dossier_id"]
    assert boot.list_dossiers()["count"] == 1                 # aucun doublon


def test_identity_ignores_as_of_and_freezes_content(boot):
    r1 = boot.open_dossier("Sujet A", "key-2", "alice")
    did, first_as_of = r1["dossier_id"], r1["opened_as_of"]
    # nouvelle instance, MÊME data_dir, ``as_of`` DIFFÉRENT (process rejoué)
    cfg2 = load_config()
    cfg2.data_dir = boot.config.data_dir
    cfg2.as_of = "2099-12-31T00:00:00+00:00"
    boot2 = BrainAIBootstrap(config=cfg2)
    r2 = boot2.open_dossier("Sujet A", "key-2", "alice")
    assert r2["replayed"] is True                             # rejeu reconnu malgré as_of différent
    assert r2["dossier_id"] == did                            # identité = {actor, correlation_key} seule
    assert r2["opened_as_of"] == first_as_of != cfg2.as_of    # contenu figé à la 1ère réception


def test_replay_uses_canonical_seed(boot):
    boot.open_dossier("Sujet", "key-c", "alice")
    r = boot.open_dossier("   Sujet   ", "key-c", "alice")    # écarts de bord non significatifs
    assert r["ok"] is True and r["replayed"] is True          # forme canonique → rejeu, pas conflit


def test_conflict_same_key_different_content(boot):
    boot.open_dossier("Sujet X", "key-x", "alice")
    r = boot.open_dossier("Sujet Y", "key-x", "alice")        # même clé, contenu différent
    assert r["ok"] is False and r.get("conflict") is True
    assert "dossier.open_rejected" in [e["topic"] for e in boot.recorder.events]
    assert boot.list_dossiers()["count"] == 1                 # refus : aucune création


def test_two_distinct_intentions_two_dossiers(boot):
    a = boot.open_dossier("Même sujet", "key-1", "alice")
    b = boot.open_dossier("Même sujet", "key-2", "alice")     # nouvelle correlation_key
    assert a["dossier_id"] != b["dossier_id"]
    assert boot.list_dossiers()["count"] == 2


def test_actor_scopes_identity(boot):
    a = boot.open_dossier("Sujet", "key-1", "alice")
    b = boot.open_dossier("Sujet", "key-1", "bob")            # même clé, acteur différent
    assert a["dossier_id"] != b["dossier_id"]                 # {actor, key} → distincts


def test_open_requires_actor_key_seed(boot):
    assert boot.open_dossier("Sujet", "key", "")["ok"] is False    # aucun acteur générique
    assert boot.open_dossier("Sujet", "   ", "alice")["ok"] is False  # clé requise (client)
    assert boot.open_dossier("", "key", "alice")["ok"] is False       # sujet requis


def test_audit_distinguishes_open_replay_conflict(boot):
    boot.open_dossier("Sujet", "k1", "alice")                 # → opened
    boot.open_dossier("Sujet", "k1", "alice")                 # → replayed
    boot.open_dossier("Autre", "k1", "alice")                 # → rejected
    topics = [e["topic"] for e in boot.recorder.events]
    assert "dossier.opened" in topics
    assert "dossier.open_replayed" in topics
    assert "dossier.open_rejected" in topics
    assert topics.count("dossier.opened") == 1                # une seule vraie ouverture


def test_reads_list_and_detail(boot):
    r = boot.open_dossier("Sujet lisible", "k", "alice")
    lst = boot.list_dossiers()
    assert lst["count"] == 1 and lst["items"][0]["dossier_id"] == r["dossier_id"]
    d = boot.get_dossier(r["dossier_id"])
    assert d["dossier_id"] == r["dossier_id"] and d["status"] == "open" and d["label"] == "Sujet lisible"
    assert boot.get_dossier("dos_inexistant")["ok"] is False


def test_presentation_dossier_passthrough(boot):
    r = boot.open_dossier("Via présentation", "k", "alice")
    present = Presentation(bootstrap=boot)
    env = present.open_dossier("Via présentation", "k", "alice")   # rejeu (même clé + contenu)
    assert env["operation"] == "open_dossier" and env["kind"] == "action"
    assert env["data"]["ok"] is True and env["data"]["replayed"] is True
    envl = present.dossiers()
    assert envl["operation"] == "dossiers" and envl["kind"] == "read"
    envd = present.dossier(r["dossier_id"])
    assert envd["operation"] == "dossier" and envd["kind"] == "read"
    assert envd["data"]["dossier_id"] == r["dossier_id"]
