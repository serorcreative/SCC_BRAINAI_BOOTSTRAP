"""Tests du service métier de liaison (DOSSIER-LINK-CORE-001/003, Tranche 1).

Prouve, sur le service **pur** (aucune orchestration, aucun contrat, aucun événement) : les
**faits de liaison** Entrée↔Dossier (``attached`` / ``detached``), leur identité **déterministe
adressée par la paire**, le store **append-only durable** (``data/dossier_links.jsonl``),
l'**idempotence fondée sur l'appartenance courante** (rejeu d'attache → aucune seconde ligne,
fait **figé**), la **cardinalité plurielle**, l'**isolation de lecture** par Dossier, la
**persistance**, l'**ordre déterministe** et l'**absence de mutation** du store par l'appelant.

DOSSIER-LINK-CORE-003 (Tranche 1) : le **détachement** comme **nouveau fait immuable** (jamais
une suppression) ; la **projection « dernier fait gagnant »** ; le **ré-attachement** après
détachement ; l'idempotence du détachement (``noop`` si rien à annuler) ; la conservation
**intégrale** des faits (append-only strict).
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
    assert set(link) == {"link_id", "dossier_id", "input_id", "kind", "attached_by", "attached_as_of"}
    assert link["link_id"].startswith("doslink_")
    assert link["kind"] == "attached"                          # fait typé (attaché / détaché)
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


# --------------------------------------------------------------------- #
# Détachement — nouveau fait immuable (DOSSIER-LINK-CORE-003)
# --------------------------------------------------------------------- #
def test_detach_appends_fact_and_never_deletes(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    res = svc.detach(dossier_id=D1, input_id=I1, actor="bob")
    assert res["outcome"] == "detached"
    fact = res["link"]
    assert set(fact) == {"link_id", "dossier_id", "input_id", "kind", "detached_by", "detached_as_of"}
    assert fact["kind"] == "detached"
    assert fact["detached_by"] == "bob" and fact["detached_as_of"] == config.as_of
    assert fact["link_id"] == svc.link_id(D1, I1)             # même paire → même link_id que l'attache
    # append-only strict : le fait d'attache n'est PAS supprimé (les deux lignes coexistent)
    assert len(_lines(svc)) == 2


def test_detach_excludes_pair_from_projection(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.attach(dossier_id=D1, input_id=I2, actor="alice")
    svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    got = [l["input_id"] for l in svc.list_for_dossier(D1)]
    assert got == [I2]                                        # I1 détachée → hors appartenance ; I2 conservée
    assert I1 not in got


def test_detach_requires_actor(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    for bad in (dict(dossier_id="", input_id=I1, actor="a"),
                dict(dossier_id=D1, input_id="  ", actor="a"),
                dict(dossier_id=D1, input_id=I1, actor="")):
        try:
            svc.detach(**bad)
            assert False, "un champ manquant aurait dû être refusé"
        except DossierLinkError:
            pass
    assert len(_lines(svc)) == 1                              # aucun refus n'a écrit de fait


def test_detach_is_idempotent_noop_when_not_attached(config):
    svc = DossierLinkService(config)
    # jamais rattachée → rien à détacher
    r0 = svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    assert r0["outcome"] == "noop"
    assert not svc.path.exists() or len(_lines(svc)) == 0
    # attachée puis détachée → re-détacher est un noop (aucune 3e ligne)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    r1 = svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    assert r1["outcome"] == "noop"
    assert len(_lines(svc)) == 2                              # 1 attach + 1 detach, rien de plus


# --------------------------------------------------------------------- #
# Projection « dernier fait gagnant » + ré-attachement
# --------------------------------------------------------------------- #
def test_last_fact_wins_determines_membership(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    assert [l["input_id"] for l in svc.list_for_dossier(D1)] == [I1]   # dernier = attached → membre
    svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    assert svc.list_for_dossier(D1) == []                             # dernier = detached → non membre


def test_reattach_after_detach_appends_new_attached_fact(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    res = svc.attach(dossier_id=D1, input_id=I1, actor="carol")       # ré-attachement après détachement
    assert res["outcome"] == "attached"                              # nouvel acte, pas un rejeu
    assert res["link"]["attached_by"] == "carol"
    got = svc.list_for_dossier(D1)
    assert [l["input_id"] for l in got] == [I1] and got[0]["attached_by"] == "carol"
    # trois faits conservés (attach, detach, attach) : append-only strict, aucun fait supprimé
    assert len(_lines(svc)) == 3


def test_reattach_is_idempotent_once_attached(config):
    svc = DossierLinkService(config)
    svc.attach(dossier_id=D1, input_id=I1, actor="alice")
    svc.detach(dossier_id=D1, input_id=I1, actor="alice")
    svc.attach(dossier_id=D1, input_id=I1, actor="carol")            # ré-attachement (3e fait)
    r = svc.attach(dossier_id=D1, input_id=I1, actor="dan")         # déjà rattaché → rejeu figé
    assert r["outcome"] == "replayed" and r["link"]["attached_by"] == "carol"
    assert len(_lines(svc)) == 3                                    # aucune 4e ligne


def test_facts_persist_across_instances(config):
    DossierLinkService(config).attach(dossier_id=D1, input_id=I1, actor="alice")
    DossierLinkService(config).detach(dossier_id=D1, input_id=I1, actor="alice")
    reloaded = DossierLinkService(config)                            # nouvelle instance, même config
    assert reloaded.list_for_dossier(D1) == []                       # projection durable (détaché)
    assert len(_lines(reloaded)) == 2                                # faits durables au-delà de l'instance
