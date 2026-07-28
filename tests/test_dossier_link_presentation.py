"""Tests contrat + présentation du (dé)rattachement (DOSSIER-LINK-CORE-001/003, Tranche 3).

Prouve l'**exposition additive** de ``attach_input`` / ``detach_input`` (actions gouvernées) et
``dossier_inputs`` (lecture) au Contrat, et le **passthrough verbatim** de la couche Présentation.
Les passthroughs sont testés **isolément** via un stub du Bootstrap renvoyant une **sentinelle** :
on vérifie les arguments transmis à l'identique et l'enveloppe (``operation``/``kind``/
``contract_version``/``generated_as_of``/``data``) — **sans** double appel mutatif. Pour
``detach_input``, on vérifie en plus que les **trois formes autoritatives** (erreur / détaché /
noop) sont **reflétées verbatim**, sans logique ni champ fabriqué. Les comportements métier
(validation, idempotence, audit) sont couverts par les tests Bootstrap de la Tranche 2.
``CONTRACT_VERSION`` reste ``"1.0"`` (ajout additif, aucune rupture).
"""

from __future__ import annotations

from types import SimpleNamespace

from scc_brainai_bootstrap.presentation import (
    CONTRACT_VERSION,
    OPERATIONS,
    Presentation,
    describe,
)

AS_OF = "2026-07-06T00:00:00+00:00"


class _StubBoot:
    """Bootstrap minimal enregistrant les appels et renvoyant une sentinelle par opération.

    N'expose que ce dont ``_wrap`` a besoin (``config.as_of``) et les deux méthodes déléguées."""

    def __init__(self):
        self.config = SimpleNamespace(as_of=AS_OF)
        self.calls: list = []
        self.returns: dict = {}

    def attach_input(self, dossier_id, input_id, actor):
        self.calls.append(("attach_input", (dossier_id, input_id, actor)))
        return self.returns["attach_input"]

    def detach_input(self, dossier_id, input_id, actor):
        self.calls.append(("detach_input", (dossier_id, input_id, actor)))
        return self.returns["detach_input"]

    def dossier_inputs(self, dossier_id):
        self.calls.append(("dossier_inputs", (dossier_id,)))
        return self.returns["dossier_inputs"]


# --------------------------------------------------------------------- #
# Contrat : exposition additive
# --------------------------------------------------------------------- #
def test_contract_exposes_attach_input_as_action():
    assert OPERATIONS["attach_input"]["kind"] == "action"
    assert OPERATIONS["attach_input"]["summary"]


def test_contract_exposes_dossier_inputs_as_read():
    assert OPERATIONS["dossier_inputs"]["kind"] == "read"
    assert OPERATIONS["dossier_inputs"]["summary"]


def test_contract_exposes_detach_input_as_action():
    assert OPERATIONS["detach_input"]["kind"] == "action"
    assert OPERATIONS["detach_input"]["summary"]


def test_contract_version_unchanged_additive():
    assert CONTRACT_VERSION == "1.0"                      # ajout additif : aucune rupture


def test_describe_covers_the_link_operations():
    ops = describe()["operations"]
    assert "attach_input" in ops and "detach_input" in ops and "dossier_inputs" in ops
    # conformité : chaque op du contrat a une méthode homonyme sur Presentation
    assert callable(getattr(Presentation, "attach_input"))
    assert callable(getattr(Presentation, "detach_input"))
    assert callable(getattr(Presentation, "dossier_inputs"))


# --------------------------------------------------------------------- #
# Passthrough verbatim (isolé, sentinelle, sans double appel mutatif)
# --------------------------------------------------------------------- #
def test_attach_input_passthrough_is_verbatim():
    stub = _StubBoot()
    sentinel = object()
    stub.returns["attach_input"] = sentinel
    env = Presentation(bootstrap=stub).attach_input("dos_1", "in_1", "alice")

    # arguments transmis exactement, un seul appel (aucun rejeu provoqué par le test)
    assert stub.calls == [("attach_input", ("dos_1", "in_1", "alice"))]
    # enveloppe conforme + data enveloppée VERBATIM (même objet)
    assert env["operation"] == "attach_input"
    assert env["kind"] == "action"
    assert env["contract_version"] == CONTRACT_VERSION
    assert env["generated_as_of"] == AS_OF
    assert env["data"] is sentinel


def test_dossier_inputs_passthrough_is_verbatim():
    stub = _StubBoot()
    sentinel = object()
    stub.returns["dossier_inputs"] = sentinel
    env = Presentation(bootstrap=stub).dossier_inputs("dos_1")

    assert stub.calls == [("dossier_inputs", ("dos_1",))]
    assert env["operation"] == "dossier_inputs"
    assert env["kind"] == "read"
    assert env["contract_version"] == CONTRACT_VERSION
    assert env["generated_as_of"] == AS_OF
    assert env["data"] is sentinel


def test_detach_input_passthrough_is_verbatim():
    stub = _StubBoot()
    sentinel = object()
    stub.returns["detach_input"] = sentinel
    env = Presentation(bootstrap=stub).detach_input("dos_1", "in_1", "alice")

    # arguments transmis exactement, un seul appel (aucun effet mutatif provoqué par le test)
    assert stub.calls == [("detach_input", ("dos_1", "in_1", "alice"))]
    assert env["operation"] == "detach_input"
    assert env["kind"] == "action"
    assert env["contract_version"] == CONTRACT_VERSION
    assert env["generated_as_of"] == AS_OF
    assert env["data"] is sentinel


def test_detach_input_reflects_authoritative_shapes_verbatim():
    # La présentation **reflète** le résultat autoritatif du Bootstrap, sans logique ni fabrication :
    # les trois formes (erreur / détaché / noop) sont enveloppées **telles quelles** (même objet).
    shapes = {
        "error": {"ok": False, "error": "Dossier introuvable : dos_x"},
        "detached": {"ok": True, "detached": True, "link_id": "doslink_1",
                     "dossier_id": "dos_1", "input_id": "in_1",
                     "detached_by": "alice", "detached_as_of": AS_OF},
        "noop": {"ok": True, "detached": False, "dossier_id": "dos_1", "input_id": "in_1"},
    }
    for data in shapes.values():
        stub = _StubBoot()
        stub.returns["detach_input"] = data
        env = Presentation(bootstrap=stub).detach_input("dos_1", "in_1", "alice")
        assert env["operation"] == "detach_input" and env["kind"] == "action"
        assert env["data"] is data                       # verbatim : aucune copie, aucun champ ajouté/retiré
