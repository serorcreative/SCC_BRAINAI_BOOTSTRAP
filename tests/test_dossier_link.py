"""Tests du service métier de rattachement (DOSSIER-LINK-CORE-001, Tranche 1).

Prouve, sur le service **pur** (aucune orchestration, aucun contrat, aucun événement) : le
**fait de rattachement** Entrée↔Dossier, son identité **déterministe adressée par la paire**,
le store **append-only durable** (``data/dossier_links.jsonl``), l'**idempotence par paire**
(rejeu → aucune seconde ligne, fait **figé**), la **cardinalité plurielle** (plusieurs Entrées
par Dossier ; une même Entrée dans plusieurs Dossiers), l'**isolation de lecture** par Dossier,
la **persistance** au travers d'une réinstanciation, l'**ordre déterministe** et l'**absence de
mutation** du store par l'appelant. Aucun détachement (hors périmètre).
"""

from __future__ import annotations

from scc_brainai_bootstrap.dossier_link import DossierLinkService, DossierLinkError

D1, D2 = "dos_aaa111", "dos_bbb222"
I1, I2 = "in_xxx111", "in_yyy222"


def _lines(svc: DossierLinkService):
    return [l for l in svc.path.read_text(encoding="utf-8").splitlines() if l.strip()]


# --------------------------------------------------------------------- #
# Création + modèle du fait
# --------------------------------------------------------------------- #
def test_attach_creates_link_with_exact_fields(config):
    svc = DossierLinkService(config)
    res = svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    assert res["outcome"] == "attached"
    link = res["link"]
    assert set(link) == {"link_id", "dossier_id", "input_id", "attached_by", "attached_as_of"}
    assert link["link_id"].startswith("doslink_")
    assert link["dossier_id"] == D1 and link["input_id"] == I1
    assert link["attached_by"] == "alice"
    assert link["attached_as_of"] == config.as_of              # datation figée = as_of déterministe


def test_actor_key_seed_required(config):
    svc = DossierLinkService(config)
    for bad in (dict(dossier_id="", input_id=I1, actor="a"),
                dict(dossier_id=D1, input_id="  ", actor="a"),
                dict(dossier_id=D1, input_id=I1, actor="")):
        try:
            svc.attach(**bad)
            assert False, "un champ manquant aurait dû être refusé"
        except DossierLinkError:
            pass
    assert not svc.path.exists()                               # aucun refus n'a écrit le store


# --------------------------------------------------------------------- #
# Identité déterministe adressée par la paire
# --------------------------------------------------------------------- #
def test_link_id_is_deterministic_and_pair_addressed(config):
    svc = DossierLinkService(config)
    assert svc.link_id(D1, I1) == svc.link_id(D1, I1)          # stable
    assert svc.link_id(D1, I1) != svc.link_id(D1, I2)          # autre Entrée → autre id
    assert svc.link_id(D1, I1) != svc.link_id(D2, I1)          # autre Dossier → autre id
    # l'identité ne dépend que de la paire (ni acteur ni as_of)
    a = svc.attach(dossier_id=D1, input_id=I1, actor="alice")["link"]["link_id"]
    assert a == svc.link_id(D1, I1)


# --------------------------------------------------------------------- #
# Idempotence par paire : rejeu, aucune seconde ligne, fait figé
# --------------------------------------------------------------------- #
def test_replay_same_pair_is_idempotent(config):
    svc = DossierLinkService(config)
    a = svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    b = svc.attach(dossier_id=D1, input_id=I1, actor="alice")  # rejeu strict
    assert a["outcome"] == "attached" and b["outcome"] == "replayed"
    assert b["link"] == a["link"]


def test_replay_writes_no_second_line(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")      # rejeu séquentiel
    assert len(_lines(svc)) == 1                               # append-only, aucun doublon logique


def test_replay_freezes_the_fact(config):
    svc = DossierLinkService(config)
    first = svc.attach(dossier_id=D1, input_id=I1, actor="alice")["link"]
    replay = svc.attach(dossier_id=D1, input_id=I1, actor="bob")  # autre acteur, même paire
    assert replay["outcome"] == "replayed"
    assert replay["link"]["attached_by"] == "alice"           # un fait ne se corrige pas
    assert len(_lines(svc)) == 1


# --------------------------------------------------------------------- #
# Cardinalité plurielle
# --------------------------------------------------------------------- #
def test_many_inputs_in_one_dossier(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.attach(dossier_id=D1, input_id=I2, actor="alice")
    got = svc.list_for_dossier(D1)
    assert {l["input_id"] for l in got} == {I1, I2}
    assert len(got) == 2


def test_one_input_in_many_dossiers(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.attach(dossier_id=D2, input_id=I1, actor="alice")     # même Entrée, autre Dossier
    assert [l["input_id"] for l in svc.list_for_dossier(D1)] == [I1]
    assert [l["input_id"] for l in svc.list_for_dossier(D2)] == [I1]
    # aucune exclusivité globale : deux faits distincts, deux link_id distincts
    assert svc.link_id(D1, I1) != svc.link_id(D2, I1)
    assert len(_lines(svc)) == 2


# --------------------------------------------------------------------- #
# Isolation de lecture, persistance, ordre déterministe
# --------------------------------------------------------------------- #
def test_read_is_isolated_per_dossier(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.attach(dossier_id=D2, input_id=I2, actor="alice")
    got = svc.list_for_dossier(D1)
    assert all(l["dossier_id"] == D1 for l in got)
    assert I2 not in [l["input_id"] for l in got]
    assert svc.list_for_dossier("dos_inexistant") == []       # Dossier sans rattachement


def test_persist_and_reload_across_instances(config):
    DossierLinkService(config).attach(dossier_id=D1, input_id=I1, actor="alice")
    reloaded = DossierLinkService(config)                     # nouvelle instance, même config
    got = reloaded.list_for_dossier(D1)
    assert len(got) == 1 and got[0]["input_id"] == I1         # durable au-delà de l'instance


def test_read_order_is_deterministic(config):
    svc = DossierLinkService(config)
    # ordre d'insertion volontairement non trié par link_id
    for iid in ("in_c", "in_a", "in_b", "in_d"):
        svc.attach(dossier_id=D1, input_id=iid, actor="alice")
    got = svc.list_for_dossier(D1)
    ids = [l["link_id"] for l in got]
    assert ids == sorted(ids)                                 # tri stable par link_id
    assert got == svc.list_for_dossier(D1)                    # reproductible


# --------------------------------------------------------------------- #
# Absence de mutation par l'appelant (le store fait foi)
# --------------------------------------------------------------------- #
def test_store_is_immutable_against_caller_mutation(config):
    svc = DossierLinkService(config)
    link = svc.attach(dossier_id=D1, input_id=I1, actor="alice")["link"]
    link["attached_by"] = "HACKED"                            # mutation côté appelant
    got = svc.list_for_dossier(D1)[0]
    assert got["attached_by"] == "alice"                      # le store reste intact
    reread = svc.list_for_dossier(D1)[0]
    reread["dossier_id"] = "dos_HACKED"                       # mutation d'une lecture
    assert svc.list_for_dossier(D1)[0]["dossier_id"] == D1    # relecture disque non affectée
