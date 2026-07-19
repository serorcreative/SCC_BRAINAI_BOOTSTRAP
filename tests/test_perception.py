"""Tests du pilier Perception — socle de lecture des Entrées (INPUT-READ-001).

Prouve : modèle canonique + immuabilité, store append-only + idempotence, lecture
déterministe (liste et par identifiant), erreur sur identifiant inconnu, persistance /
relecture, séparation Bootstrap ↔ service dédié, projection dans l'overview, exposition
Contrat et passthrough Présentation. Aucune acquisition réelle n'est testée (aucune n'existe).
"""

from __future__ import annotations

from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.perception import PerceptionService, build_input
from scc_brainai_bootstrap.presentation import OPERATIONS, Presentation

SAMPLE = dict(
    modality="text",
    content="Bonjour BrainAI",
    provenance={"origin": "test", "medium": "inline"},
    session_id="ses_x",
    actor="fred",
)


# --------------------------------------------------------------------- #
# Modèle canonique + identité adressée-contenu
# --------------------------------------------------------------------- #
def test_build_input_shape_and_fields():
    e = build_input(as_of="2026-07-06T00:00:00+00:00", **SAMPLE)
    for key in ("id", "modality", "content", "provenance", "observed_at", "ingested_at",
                "as_of", "session_id", "actor", "context", "integrity", "fidelity"):
        assert key in e
    assert e["id"].startswith("in_")
    assert e["modality"] == "text"
    assert e["content"] == "Bonjour BrainAI"
    assert e["ingested_at"] == e["as_of"]                     # défaut = as_of (déterministe)
    assert e["integrity"]["content_digest"]                   # intégrité présente


def test_identity_is_deterministic_and_content_addressed():
    a = build_input(as_of="X", **SAMPLE)
    b = build_input(as_of="X", **SAMPLE)
    assert a["id"] == b["id"]                                 # identique → même id
    c = build_input(as_of="X", **{**SAMPLE, "content": "Autre contenu"})
    assert c["id"] != a["id"]                                 # contenu distinct → id distinct
    d = build_input(as_of="X", **{**SAMPLE, "actor": "rose"})
    assert d["id"] != a["id"]                                 # contexte distinct → id distinct


def test_build_input_validates_structure():
    for bad in ({**SAMPLE, "modality": ""}, {**SAMPLE, "content": None},
                {**SAMPLE, "provenance": {}}):
        try:
            build_input(as_of="X", **bad)
            assert False, "une validation structurelle aurait dû échouer"
        except ValueError:
            pass


# --------------------------------------------------------------------- #
# Store append-only, immuabilité, idempotence
# --------------------------------------------------------------------- #
def test_record_is_append_only_and_idempotent(config):
    svc = PerceptionService(config)
    a = svc.record(**SAMPLE)
    b = svc.record(**{**SAMPLE, "content": "Deuxième fait"})
    assert svc.record(**SAMPLE) == a                          # ré-enregistrer à l'identique = idempotent
    lines = [l for l in svc.path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2                                    # aucun doublon d'id
    assert [e["id"] for e in svc.list()] == [a["id"], b["id"]]  # ordre d'ajout (déterministe)


def test_read_by_id_and_unknown(config):
    svc = PerceptionService(config)
    e = svc.record(**SAMPLE)
    assert svc.read(e["id"]) == e
    assert svc.read("in_inexistante") is None


def test_store_is_immutable_against_caller_mutation(config):
    svc = PerceptionService(config)
    e = svc.record(**SAMPLE)
    got = svc.read(e["id"])
    got["content"] = "HACKED"                                 # mutation côté appelant
    assert svc.read(e["id"])["content"] == "Bonjour BrainAI"  # le store reste intact


def test_persist_and_reload_across_instances(config):
    e = PerceptionService(config).record(**SAMPLE)
    reloaded = PerceptionService(config)                      # nouvelle instance, même config
    assert reloaded.read(e["id"]) == e


def test_projection_is_light_and_deterministic(config):
    svc = PerceptionService(config)
    svc.record(**SAMPLE)
    proj = svc.project()
    assert len(proj) == 1
    p = proj[0]
    assert set(p.keys()) == {"id", "modality", "preview", "provenance",
                             "observed_at", "ingested_at", "session_id"}
    assert p["preview"] == "Bonjour BrainAI"
    assert p["provenance"] == "test"                          # provenance synthétique (origin)


# --------------------------------------------------------------------- #
# Séparation Bootstrap ↔ service dédié ; lecture seule
# --------------------------------------------------------------------- #
def test_bootstrap_delegates_to_perception_service(boot):
    assert isinstance(boot.perception, PerceptionService)
    e = boot.perception.record(**SAMPLE)
    got = boot.inputs()
    assert got["count"] == 1 and got["items"][0]["id"] == e["id"]
    assert boot.input(e["id"]) == e


def test_bootstrap_input_unknown_reflects_error(boot):
    res = boot.input("in_inexistante")
    assert res["ok"] is False
    assert "error" in res


def test_reads_do_not_start_or_write(config):
    b = BrainAIBootstrap(config=config)
    b.inputs(); b.input("in_x"); b.overview()
    assert b._booted is False
    assert not b.perception.path.exists()                     # aucune lecture n'écrit le store
    assert not b.events_path.exists()
    assert not b.session.path.exists()


def test_overview_includes_inputs_projection(boot):
    assert boot.overview()["inputs"] == {"count": 0, "items": []}
    boot.perception.record(**SAMPLE)
    ov = boot.overview()
    assert ov["inputs"]["count"] == 1
    assert ov["inputs"]["items"][0]["preview"] == "Bonjour BrainAI"


# --------------------------------------------------------------------- #
# Exposition Contrat + passthrough Présentation
# --------------------------------------------------------------------- #
def test_contract_exposes_inputs_reads():
    assert OPERATIONS["inputs"]["kind"] == "read"
    assert OPERATIONS["input"]["kind"] == "read"


def test_presentation_passthrough(boot):
    e = boot.perception.record(**SAMPLE)
    present = Presentation(bootstrap=boot)
    env = present.inputs()
    assert env["operation"] == "inputs" and env["kind"] == "read"
    assert env["data"] == boot.inputs()                       # délégation verbatim
    detail = present.input(e["id"])
    assert detail["kind"] == "read" and detail["data"] == e
    unknown = present.input("in_inexistante")
    assert unknown["data"]["ok"] is False and "error" in unknown["data"]


# --------------------------------------------------------------------- #
# Écriture — première acquisition d'une Entrée texte (INPUT-WRITE-001)
# --------------------------------------------------------------------- #
PROV = {"origin": "test", "medium": "inline"}


def test_record_text_normalizes_and_creates(config):
    svc = PerceptionService(config)
    e = svc.record_text(text="  Bonjour BrainAI  ", provenance=PROV)
    assert e["modality"] == "text"
    assert e["content"] == "Bonjour BrainAI"                  # trim des bords, sans perte de sens
    assert e["id"].startswith("in_")
    assert svc.read(e["id"]) == e                             # lecture immédiate


def test_record_text_rejects_invalid(config):
    svc = PerceptionService(config)
    for bad in ("", "   ", "\n\t "):
        try:
            svc.record_text(text=bad, provenance=PROV)
            assert False, "un texte vide aurait dû être refusé"
        except ValueError:
            pass
    try:
        svc.record_text(text="ok", provenance={})            # provenance vide → refus
        assert False, "une provenance vide aurait dû être refusée"
    except ValueError:
        pass


def test_record_text_append_only_and_deterministic(config):
    svc = PerceptionService(config)
    a = svc.record_text(text="Fait A", provenance=PROV)
    svc.record_text(text="Fait B", provenance=PROV)
    again = svc.record_text(text="Fait A", provenance=PROV)   # identique → idempotent
    assert again["id"] == a["id"]                             # id déterministe
    lines = [l for l in svc.path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2                                    # append-only, aucun doublon


def test_bootstrap_record_input_end_to_end(boot):
    res = boot.record_input("Première Entrée officielle", PROV)
    assert res["ok"] is True and res["input_id"].startswith("in_")
    iid = res["input_id"]
    assert boot.input(iid)["id"] == iid                       # lecture immédiate via `input`
    assert iid in [i["id"] for i in boot.inputs()["items"]]   # apparition dans `inputs`
    ov = boot.overview()["inputs"]
    assert ov["count"] >= 1 and iid in [i["id"] for i in ov["items"]]   # apparition dans overview


def test_bootstrap_record_input_rejects_invalid(boot):
    assert boot.record_input("   ", PROV)["ok"] is False      # texte vide
    assert boot.record_input("ok", {})["ok"] is False         # provenance invalide


def test_bootstrap_record_input_is_immutable(boot):
    iid = boot.record_input("Immuable ?", PROV)["input_id"]
    got = boot.input(iid)
    got["content"] = "ALTÉRÉ"                                 # mutation côté appelant
    assert boot.input(iid)["content"] == "Immuable ?"         # le store reste intact


def test_presentation_record_input_passthrough(boot):
    present = Presentation(bootstrap=boot)
    env = present.record_input(text="Via présentation", provenance=PROV)
    assert env["operation"] == "record_input" and env["kind"] == "action"
    assert env["data"]["ok"] is True and env["data"]["input_id"].startswith("in_")


# --------------------------------------------------------------------- #
# Analyse — première circulation d'une Entrée dans le cerveau (INPUT-ANALYZE-001)
# --------------------------------------------------------------------- #
def test_analyze_input_runs_reasoning(boot):
    iid = boot.record_input("Faut-il préparer la première interface ?", PROV)["input_id"]
    res = boot.analyze_input(iid)
    assert res["ok"] is True
    assert res["input_id"] == iid
    analysis = res["analysis"]
    assert analysis["deliberation_id"]                        # une délibération a été produite
    assert analysis["provider"] and analysis["as_of"]         # traçabilité présente
    elements = analysis["elements"]
    assert set(elements) == {"facts", "hypotheses", "options", "risks", "inferences"}
    # OUTPUT-001 : chaque catégorie est une LISTE d'énoncés {id, statement, sources}
    # (substance projetée, plus des compteurs).
    for cat in elements.values():
        assert isinstance(cat, list)
        for item in cat:
            assert set(item) == {"id", "statement", "sources"}
            assert isinstance(item["statement"], str)
            assert isinstance(item["sources"], list)


def test_analyze_input_reflects_candidate_recommendation(boot):
    iid = boot.record_input("Faut-il préparer la première interface ?", PROV)["input_id"]
    reco = boot.analyze_input(iid)["analysis"]["recommendation"]
    assert "statement" in reco
    assert reco["requires_human_validation"] is True          # proposition, jamais appliquée seule
    # la recommandation reste candidate (aucune décision gouvernée)
    assert boot.analyze_input(iid)["analysis"]["recommendation_status"] == "candidate"


def test_analyze_input_event_carries_only_pointer(boot):
    # Source de vérité UNIQUE : l'événement ne porte QUE {input_id, deliberation_id} — aucune
    # substance dupliquée dans le journal (aucune seconde source de vérité).
    iid = boot.record_input("Analyse sans duplication", PROV)["input_id"]
    boot.analyze_input(iid)
    ev = [e for e in boot.recorder.events if e["topic"] == "input.analyzed"][-1]
    assert set(ev["payload"]) == {"input_id", "deliberation_id"}


def test_analyze_input_is_deterministic_no_divergence(boot):
    # Re-analyser la même Entrée redonne le MÊME deliberation_id (adressé-contenu) et la MÊME
    # substance : le reflet ne peut pas diverger de la source persistée.
    iid = boot.record_input("Même contenu, même délibération", PROV)["input_id"]
    a = boot.analyze_input(iid)["analysis"]
    b = boot.analyze_input(iid)["analysis"]
    assert a["deliberation_id"] == b["deliberation_id"]
    assert a["elements"] == b["elements"]
    assert a["recommendation"] == b["recommendation"]


def test_analyze_input_unknown_reflects_error(boot):
    res = boot.analyze_input("in_inexistante")
    assert res["ok"] is False and "error" in res


def test_analyze_input_does_not_mutate_entry(boot):
    iid = boot.record_input("Contenu à préserver", PROV)["input_id"]
    boot.analyze_input(iid)
    assert boot.input(iid)["content"] == "Contenu à préserver"   # Entrée intacte après analyse


def test_analyze_input_writes_no_memory(boot):
    iid = boot.record_input("Analyse sans mémoire", PROV)["input_id"]
    boot.analyze_input(iid)
    store = boot.memory.store
    # l'analyse ne persiste RIEN en Mémoire (le store reste vide, ou n'est pas alimenté).
    assert store is None or sum(store.counts().values()) == 0


def test_analyze_input_creates_no_decision_no_execution(boot):
    iid = boot.record_input("Analyse sans décision", PROV)["input_id"]
    boot.analyze_input(iid)
    # aucune Décision gouvernée créée (le moteur Decision n'a jamais été appelé)
    assert boot.cognition.decision.search() == []
    assert boot.overview()["open_decisions"] == []
    assert boot.overview()["executable_decisions"] == []
    # aucune Exécution, aucun apprentissage, aucune Décision côté événements
    topics = {e["topic"] for e in boot.recorder.events}
    assert "input.analyzed" in topics
    assert not any(t.startswith("decision.") or t.startswith("execution.")
                   or t.startswith("learn") for t in topics)


def test_presentation_analyze_input_passthrough(boot):
    iid = boot.record_input("Via présentation", PROV)["input_id"]
    present = Presentation(bootstrap=boot)
    env = present.analyze_input(iid)
    assert env["operation"] == "analyze_input" and env["kind"] == "action"
    assert env["data"]["ok"] is True and env["data"]["analysis"]["deliberation_id"]


# --------------------------------------------------------------------- #
# Analyse revisitable d'une Entrée (INPUT-ANALYSIS-READ-001)
# --------------------------------------------------------------------- #
def test_input_analysis_reopens_exact_persisted_analysis(boot):
    iid = boot.record_input("Faut-il préparer la première interface ?", PROV)["input_id"]
    analyzed = boot.analyze_input(iid)                       # produit + persiste
    reread = boot.input_analysis(iid)                        # relit, sans recalcul
    assert reread["ok"] is True and reread["input_id"] == iid
    # Projection OFFICIELLE UNIQUE : la relecture == le reflet d'analyse, à l'identique.
    assert reread["analysis"] == analyzed["analysis"]
    assert reread["analysis"]["deliberation_id"] == analyzed["analysis"]["deliberation_id"]


def test_input_analysis_is_read_only_no_event_no_recompute(boot):
    iid = boot.record_input("Lecture sans effet de bord", PROV)["input_id"]
    boot.analyze_input(iid)
    before = [e for e in boot.recorder.events if e["topic"] == "input.analyzed"]
    boot.input_analysis(iid)
    after = [e for e in boot.recorder.events if e["topic"] == "input.analyzed"]
    assert len(after) == len(before)                         # aucune nouvelle analyse, aucun événement


def test_input_analysis_unknown_entry_reflects_error(boot):
    res = boot.input_analysis("in_inexistante")
    assert res["ok"] is False and "error" in res             # convention des lectures


def test_input_analysis_entry_never_analyzed_reflects_error(boot):
    iid = boot.record_input("Jamais analysée", PROV)["input_id"]
    res = boot.input_analysis(iid)
    assert res["ok"] is False and "aucune analyse" in res["error"]


def test_input_analysis_resolves_latest_analyzed_event(boot):
    # Règle explicite : l'analyse officielle = l'événement input.analyzed le plus récent (seq max).
    iid = boot.record_input("Analyses répétées", PROV)["input_id"]
    boot.analyze_input(iid)
    boot.analyze_input(iid)
    analyzed = [e for e in boot.input_history(iid)["events"] if e["topic"] == "input.analyzed"]
    latest = max(analyzed, key=lambda e: e["seq"])
    res = boot.input_analysis(iid)
    assert res["analysis"]["deliberation_id"] == latest["payload"]["deliberation_id"]


def test_presentation_input_analysis_passthrough(boot):
    iid = boot.record_input("Via présentation", PROV)["input_id"]
    boot.analyze_input(iid)
    env = Presentation(bootstrap=boot).input_analysis(iid)
    assert env["operation"] == "input_analysis" and env["kind"] == "read"
    assert env["data"]["ok"] is True and env["data"]["analysis"]["deliberation_id"]


# --------------------------------------------------------------------- #
# Histoire événementielle d'une Entrée (INPUT-HISTORY-001)
# --------------------------------------------------------------------- #
def test_input_history_returns_events_in_order(boot):
    iid = boot.record_input("À historiser ?", PROV)["input_id"]
    boot.analyze_input(iid)
    hist = boot.input_history(iid)
    assert hist["input_id"] == iid
    topics = [e["topic"] for e in hist["events"]]
    assert "input.recorded" in topics and "input.analyzed" in topics
    assert topics.index("input.recorded") < topics.index("input.analyzed")   # chronologique
    for e in hist["events"]:                                # schéma réel réutilisé (pas de nouveau format)
        assert {"seq", "topic", "timestamp", "payload"} <= set(e.keys())
        assert e["payload"]["input_id"] == iid


def test_input_history_unknown_reflects_error(boot):
    res = boot.input_history("in_inexistante")
    assert res["ok"] is False and "error" in res            # convention des lectures (cf. input)


def test_input_history_filters_strictly_by_input_id(boot):
    a = boot.record_input("Entrée A", PROV)["input_id"]
    b = boot.record_input("Entrée B", PROV)["input_id"]
    boot.analyze_input(a)
    hist_b = boot.input_history(b)
    assert all(e["payload"]["input_id"] == b for e in hist_b["events"])
    assert a not in [e["payload"].get("input_id") for e in hist_b["events"]]


def test_input_history_repeated_analyses_not_deduped(boot):
    iid = boot.record_input("Analyses répétées", PROV)["input_id"]
    boot.analyze_input(iid)
    boot.analyze_input(iid)
    analyzed = [e for e in boot.input_history(iid)["events"] if e["topic"] == "input.analyzed"]
    assert len(analyzed) == 2                                # distinct, jamais dédupliqué ni mué en état


def test_input_history_known_entry_without_events(config):
    b = BrainAIBootstrap(config=config)
    e = b.perception.record(**SAMPLE)                        # créée via le service : aucun événement publié
    assert b.input_history(e["id"]) == {"input_id": e["id"], "events": []}   # histoire vide, normale


def test_input_history_is_read_only(boot):
    iid = boot.record_input("Journal intact", PROV)["input_id"]
    before = boot.journal()["count"]
    boot.input_history(iid)
    boot.input_history(iid)
    assert boot.journal()["count"] == before                # aucune écriture au journal
    assert boot.input(iid)["content"] == "Journal intact"   # Entrée intacte


def test_presentation_input_history_passthrough(boot):
    iid = boot.record_input("Via présentation", PROV)["input_id"]
    present = Presentation(bootstrap=boot)
    env = present.input_history(iid)
    assert env["operation"] == "input_history" and env["kind"] == "read"
    assert env["data"] == boot.input_history(iid)           # délégation verbatim
    unknown = present.input_history("in_inexistante")
    assert unknown["data"]["ok"] is False and "error" in unknown["data"]
