"""Tests d'orchestration du rattachement (DOSSIER-LINK-CORE-001, Tranche 2).

Prouve le câblage Bootstrap au-dessus du service pur (Tranche 1) : action gouvernée
``attach_input`` (validation d'existence Dossier **puis** Entrée, idempotence par paire, audit
initial/rejeu, reflet strict) et lecture-projection ``dossier_inputs`` (projection **officielle**
des Entrées réutilisée, isolation par Dossier, **fail-closed** sur incohérence de stockage).
Aucune mutation de l'Entrée ni du record Dossier ; aucun détachement. Contrat/présentation
restent hors périmètre de cette tranche.
"""

from __future__ import annotations

from scc_brainai_bootstrap.dossier_link import DossierLinkService

PROV = {"origin": "test", "medium": "inline"}
INPUT_PROJECTION_KEYS = {"id", "modality", "preview", "provenance",
                         "observed_at", "ingested_at", "session_id"}


def _dossier(boot, seed="Sujet", key="k1", actor="alice"):
    return boot.open_dossier(seed, key, actor)["dossier_id"]


def _input(boot, text="Une Entrée"):
    return boot.record_input(text, PROV)["input_id"]


def _link_lines(boot):
    p = boot.dossier_link_service.path
    return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


# --------------------------------------------------------------------- #
# attach_input — action gouvernée
# --------------------------------------------------------------------- #
def test_attach_input_end_to_end(boot):
    did, iid = _dossier(boot), _input(boot)
    res = boot.attach_input(did, iid, "alice")
    assert res["ok"] is True and res["replayed"] is False
    assert res["link_id"].startswith("doslink_")
    assert res["dossier_id"] == did and res["input_id"] == iid
    assert res["attached_by"] == "alice"
    assert res["attached_as_of"] == boot.config.as_of


def test_attach_input_unknown_dossier_reflects_error(boot):
    iid = _input(boot)
    res = boot.attach_input("dos_inexistant", iid, "alice")
    assert res["ok"] is False and "Dossier introuvable" in res["error"]
    assert _link_lines(boot) == []                            # aucun refus n'écrit le store


def test_attach_input_unknown_input_reflects_error(boot):
    did = _dossier(boot)
    res = boot.attach_input(did, "in_inexistante", "alice")
    assert res["ok"] is False and "Entrée introuvable" in res["error"]
    assert _link_lines(boot) == []


def test_attach_input_requires_actor(boot):
    did, iid = _dossier(boot), _input(boot)
    res = boot.attach_input(did, iid, "")                     # acteur requis (service raise → reflet)
    assert res["ok"] is False and "actor" in res["error"]
    assert _link_lines(boot) == []


def test_attach_input_is_idempotent_by_pair(boot):
    did, iid = _dossier(boot), _input(boot)
    a = boot.attach_input(did, iid, "alice")
    b = boot.attach_input(did, iid, "bob")                    # rejeu (même paire, autre acteur)
    assert a["replayed"] is False and b["replayed"] is True
    assert b["link_id"] == a["link_id"]
    assert b["attached_by"] == "alice"                        # fait figé : un fait ne se corrige pas
    assert len(_link_lines(boot)) == 1                        # aucune seconde ligne


def test_attach_input_audit_initial_and_replay(boot):
    did, iid = _dossier(boot), _input(boot)
    boot.attach_input(did, iid, "alice")
    boot.attach_input(did, iid, "alice")
    topics = [e["topic"] for e in boot.recorder.events]
    assert "dossier.input_attached" in topics
    assert "dossier.input_attach_replayed" in topics
    assert topics.count("dossier.input_attached") == 1        # un seul vrai rattachement


def test_attach_input_does_not_mutate_entry(boot):
    did = _dossier(boot)
    iid = boot.record_input("Contenu à préserver", PROV)["input_id"]
    boot.attach_input(did, iid, "alice")
    assert boot.input(iid)["content"] == "Contenu à préserver"   # Entrée intacte


def test_attach_input_does_not_mutate_dossier(boot):
    did, iid = _dossier(boot), _input(boot)
    before = boot.get_dossier(did)
    boot.attach_input(did, iid, "alice")
    assert boot.get_dossier(did) == before                    # record Dossier inchangé


# --------------------------------------------------------------------- #
# dossier_inputs — lecture-projection
# --------------------------------------------------------------------- #
def test_dossier_inputs_projects_attached_entries(boot):
    did = _dossier(boot)
    i1 = boot.record_input("Entrée 1", PROV)["input_id"]
    i2 = boot.record_input("Entrée 2", PROV)["input_id"]
    boot.attach_input(did, i1, "alice")
    boot.attach_input(did, i2, "alice")
    res = boot.dossier_inputs(did)
    assert res["ok"] is True and res["dossier_id"] == did and res["count"] == 2
    for item in res["items"]:
        assert set(item.keys()) == INPUT_PROJECTION_KEYS      # projection officielle réutilisée
    assert {item["id"] for item in res["items"]} == {i1, i2}


def test_dossier_inputs_is_isolated_per_dossier(boot):
    d1 = _dossier(boot, key="k1")
    d2 = _dossier(boot, key="k2")
    i1, i2 = _input(boot, "A"), _input(boot, "B")
    boot.attach_input(d1, i1, "alice")
    boot.attach_input(d2, i2, "alice")
    assert [it["id"] for it in boot.dossier_inputs(d1)["items"]] == [i1]
    assert [it["id"] for it in boot.dossier_inputs(d2)["items"]] == [i2]


def test_dossier_inputs_empty_when_no_link(boot):
    did = _dossier(boot)
    res = boot.dossier_inputs(did)
    assert res == {"ok": True, "dossier_id": did, "count": 0, "items": []}


def test_dossier_inputs_unknown_dossier_reflects_error(boot):
    res = boot.dossier_inputs("dos_inexistant")
    assert res["ok"] is False and "Dossier introuvable" in res["error"]


def test_dossier_inputs_fail_closed_on_storage_incoherence(boot):
    # Simule une incohérence durable : un fait de liaison référençant une Entrée absente du store.
    # On passe par le service pur (qui ne valide pas l'existence) pour poser ce fait incohérent.
    did = _dossier(boot)
    DossierLinkService(boot.config).attach(dossier_id=did, input_id="in_ghost", actor="alice")
    res = boot.dossier_inputs(did)
    assert res["ok"] is False
    assert res["error"] == "Incohérence de rattachement : Entrée introuvable : in_ghost"
    assert "items" not in res                                 # aucune liste partielle présentée


def test_dossier_inputs_is_read_only(boot):
    did, iid = _dossier(boot), _input(boot)
    boot.attach_input(did, iid, "alice")
    events_before = boot.journal()["count"]
    lines_before = len(_link_lines(boot))
    boot.dossier_inputs(did)
    boot.dossier_inputs(did)
    assert boot.journal()["count"] == events_before           # aucun événement produit par la lecture
    assert len(_link_lines(boot)) == lines_before             # aucun fait ajouté
