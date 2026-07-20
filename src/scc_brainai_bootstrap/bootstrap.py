"""BrainAIBootstrap — le premier exécutable qui fait **démarrer BrainAI**.

Séquence de démarrage déterministe, dans l'ordre officiel :

1. Charger la configuration
2. Initialiser le Control Plane
3. Initialiser le Patrimony Manager
4. Initialiser Memory
5. Initialiser Knowledge
6. Initialiser l'Event Bus
7. Enregistrer les premiers Agents
8. « BrainAI READY »

Chaque étape publie un événement sur l'Event Bus. Le bootstrap **réutilise** les
composants via leurs interfaces publiques, sans en modifier aucun. En cas de composant
absent, le démarrage se poursuit en **mode dégradé** (l'étape est signalée non prête).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import importlib
import json

from scc_brainai_bootstrap.registry import (
    AdapterRegistry,
    AgentRegistry,
    CapabilityResolver,
    FicheSource,
    ManifestSource,
    load_capability_map,
)
from scc_brainai_bootstrap.components import (
    ControlPlaneComponent,
    KernelComponent,
    KnowledgeComponent,
    MemoryComponent,
)
from scc_brainai_bootstrap.core.config import BrainAIConfig, load_config
from scc_brainai_bootstrap.cognition import CognitiveStack
from scc_brainai_bootstrap.doctor import Doctor
from scc_brainai_bootstrap.event_bus import EventBus
from scc_brainai_bootstrap.learning import LearningLayer
from scc_brainai_bootstrap.patrimony import PatrimonyManager
from scc_brainai_bootstrap.perception import PerceptionService
from scc_brainai_bootstrap import router
from scc_brainai_bootstrap.session import SessionStore
from scc_brainai_bootstrap.subscribers import EventRecorder, LifecycleWatcher

READY_BANNER = "BrainAI READY"


def _project_analysis(delib: Dict[str, Any]) -> Dict[str, Any]:
    """**Projection officielle unique** d'une délibération (INPUT-ANALYSIS-READ-001).

    Toute représentation officielle d'une délibération — ``analyze_input`` (reflet de l'analyse
    en cours) comme ``input_analysis`` (relecture d'une analyse déjà produite) — provient
    **obligatoirement de cette fonction**. Sélection **fidèle** ``{id, statement, sources}`` par
    catégorie + recommandation **candidate** projetée verbatim ; aucune reformulation, aucune
    fuite d'implémentation (ni ``hash``/``data``/``tags``). ``deliberation_id``/``provider``/
    ``as_of`` assurent la traçabilité. La délibération **persistée** reste l'unique source de
    vérité ; ceci n'en est qu'un reflet.
    """
    def _statements(items):
        return [{"id": e.get("id"), "statement": e.get("statement"),
                 "sources": list(e.get("sources", []) or [])}
                for e in (items or [])]

    reco = (delib.get("explanation", {}) or {}).get("recommendation", {}) or {}
    return {
        "deliberation_id": delib.get("id"),
        "provider": delib.get("provider"),
        "as_of": delib.get("as_of"),
        "elements": {
            "facts": _statements(delib.get("facts")),
            "hypotheses": _statements(delib.get("hypotheses")),
            "options": _statements(delib.get("options")),
            "risks": _statements(delib.get("risks")),
            "inferences": _statements(delib.get("inferences")),
        },
        # Recommandation CANDIDATE, projetée verbatim ; aucune décision gouvernée n'est créée.
        "recommendation": {
            "statement": reco.get("statement", ""),
            "requires_human_validation": bool(reco.get("requires_human_validation", True)),
        },
        "recommendation_status": delib.get("decision", {}).get("status"),
    }


class BrainAIBootstrap:
    def __init__(self, config: Optional[BrainAIConfig] = None):
        self.config = config or load_config()
        self.bus = EventBus(self.config.as_of)
        # Abonnés d'observabilité branchés AVANT toute publication (bus vivant).
        self.recorder = EventRecorder()
        self.watcher = LifecycleWatcher()
        self.bus.subscribe(self.recorder.on_event)
        self.bus.subscribe(self.watcher.on_event)
        self.patrimony = PatrimonyManager(self.config)
        self.control_plane = ControlPlaneComponent(self.config)
        self.memory = MemoryComponent(self.config)
        self.knowledge = KnowledgeComponent(self.config)
        self.kernel = KernelComponent(self.config)
        # Registre d'agents déclaratif (catalogue) alimenté par sources pluggables :
        # manifests JSON locaux (agents BrainAI) + adaptation des fiches SCC existantes.
        # Câblage unique (pas par agent) : le mapping capacités des fiches SCC est
        # déclaratif — ajouter/éditer des capacités = éditer le JSON, sans toucher au code.
        self.agents = AgentRegistry(self.config, sources=[
            ManifestSource(self.config.agents_registry_dir, name="brainai"),
            FicheSource(self.config.agents_dir, self.config.first_agents, namespace="scc",
                        capability_map=load_capability_map(self.config.capability_map_path)),
        ])
        self.learning = LearningLayer(self.config)
        # La cognition reçoit un fournisseur du moteur Learning partagé : la boucle
        # apprenante est fermée (apprentissages validés → Planning / Decision).
        self.cognition = CognitiveStack(self.config, learning_provider=self._provide_learning_engine)
        # Adaptateurs : liaison paresseuse capacité → implémentation. Le registre reste
        # découplé ; les imports de moteurs vivent dans ces binders (jamais dans le registre).
        self.adapters = AdapterRegistry()
        self._register_adapters()
        self.capability_resolver = CapabilityResolver(self.agents, self.adapters)
        self.session = SessionStore(self.config)
        # Pilier Perception — socle de lecture des Entrées (fait acquis normalisé, immuable).
        # Le Bootstrap délègue toute la logique d'entrée à ce collaborateur dédié.
        self.perception = PerceptionService(self.config)
        self._session_state = None
        self._booted = False

    def _register_adapters(self) -> None:
        """Déclare les binders des moteurs cognitifs (Bootstrap → Registry → Adapter →
        Agent). Chaque binder charge son moteur **à la demande**, jamais au démarrage."""
        self.adapters.register("brainai-memory", self._bind_memory)
        self.adapters.register("brainai-learning", self._provide_learning_engine)
        self.adapters.register("brainai-planning", lambda: self.cognition.planning)
        self.adapters.register("brainai-decision", lambda: self.cognition.decision)
        self.adapters.register("brainai-execution", lambda: self.cognition.execution)

    def _bind_memory(self):
        self.memory.init()
        return self.memory.store

    @property
    def events_path(self):
        return self.config.data_dir / "events.jsonl"

    def _persist_events(self) -> None:
        try:
            self.recorder.dump(self.events_path)
        except Exception:  # noqa: BLE001 - persistance best-effort
            pass

    def run(self, on_step: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """Exécute la séquence de démarrage et renvoie un rapport structuré."""
        self.config.ensure_directories()
        steps: List[Dict[str, Any]] = []

        def step(n: int, name: str, ok: bool, detail: str, data: Dict[str, Any] = None) -> None:
            s = {"n": n, "name": name, "ok": ok, "detail": detail, "data": data or {}}
            steps.append(s)
            self.bus.publish(f"boot.{name}", {"ok": ok, "detail": detail})
            if on_step:
                on_step(s)

        # 1. Configuration
        step(1, "config", True, f"scc_root={self.config.scc_root.name}",
             {"as_of": self.config.as_of, "first_agents": len(self.config.first_agents)})

        # 2. Control Plane
        cp = self.control_plane.init()
        step(2, "control_plane", cp["ready"], cp["detail"], cp.get("data", {}))

        # 3. Patrimony Manager
        pat = self.patrimony.summary()
        step(3, "patrimony", pat["present"] > 0,
             f"{pat['present']}/{pat['total']} composants présents",
             {"present": pat["present"], "total": pat["total"], "missing": pat["missing"]})

        # 4. Memory
        mem = self.memory.init()
        step(4, "memory", mem["ready"], mem["detail"], mem.get("data", {}))

        # 5. Knowledge
        kno = self.knowledge.init()
        step(5, "knowledge", kno["ready"], kno["detail"], kno.get("data", {}))

        # 6. Event Bus (ouverture aux abonnés)
        self.bus.open()
        step(6, "event_bus", self.bus.is_open, f"ouvert ({len(self.bus)} événements)",
             {"events": len(self.bus)})

        # 7. Premiers Agents
        agents = self.agents.register_first()
        for a in agents:
            self.bus.publish("agent.registered", {"id": a.id, "name": a.name})
        step(7, "agents", len(agents) > 0, f"{len(agents)} agent(s) enregistré(s)",
             {"agents": [a.to_dict() for a in agents]})

        # 8. READY
        mandatory = {"config", "patrimony", "event_bus", "agents"}
        degraded = [s["name"] for s in steps if not s["ok"]]
        ready = all(s["ok"] for s in steps if s["name"] in mandatory)
        overall = ready and not degraded
        banner = READY_BANNER if overall else f"{READY_BANNER} (DÉGRADÉ : {', '.join(degraded)})"

        # Continuité de session : poursuivre (ou ouvrir) la session persistée, avant de
        # déclarer READY — qui reste l'événement **terminal** du démarrage.
        self._session_state = self.session.record_boot({
            "ready": overall, "banner": banner, "steps": steps,
            "agents": self.agents.to_list(), "patrimony": pat})
        self.bus.publish("session.continued",
                         {"session_id": self._session_state["session_id"],
                          "boots": self._session_state["boots"]})
        self.bus.publish("brainai.ready", {"ready": overall, "degraded": degraded})
        if on_step:
            on_step({"n": 8, "name": "ready", "ok": overall, "detail": banner, "data": {}})

        self._booted = True
        report = {
            "as_of": self.config.as_of,
            "ready": overall,
            "banner": banner,
            "degraded": degraded,
            "steps": steps,
            "patrimony": pat,
            "agents": self.agents.to_list(),
            "events": self.bus.events,
            "event_count": len(self.bus),
            "session": {
                "session_id": self._session_state["session_id"],
                "boots": self._session_state["boots"],
                "created_as_of": self._session_state["created_as_of"],
                "totals": dict(self._session_state["totals"]),
            },
            "subscribers": {
                "recorded": len(self.recorder),
                "events_file": str(self.events_path),
                "lifecycle": self.watcher.summary(),
            },
        }
        self._persist_events()
        return report

    # ================================================================== #
    # Cycle de bout en bout : bootstrap -> Kernel -> (Memory)
    # ================================================================== #
    def handle(self, query: str, deep: bool = False, record: bool = True) -> Dict[str, Any]:
        """Traite une demande de bout en bout : démarre BrainAI si besoin, délègue
        au Kernel (10), et **enregistre l'expérience dans Memory** (11) si disponible.

        Aucune couche n'est modifiée : le Kernel et l'enregistreur Memory sont
        utilisés via leurs interfaces publiques.
        """
        if not self._booted:
            self.run()
        kc = self.kernel.init()
        if not kc["ready"] or self.kernel.kernel is None:
            self.bus.publish("kernel.unavailable", {"detail": kc["detail"]})
            return {"ok": False, "query": query, "error": f"Kernel indisponible : {kc['detail']}"}

        self.bus.publish("request.received", {"query": query, "deep": deep})
        response = self.kernel.kernel.handle(query, options={"deep": deep})
        self.bus.publish("request.handled",
                         {"intent": response.get("intent"), "ok": response.get("ok")})

        recorded = None
        if record and self.memory.store is not None:
            try:
                recorder = importlib.import_module("scc_brainai_memory").KernelRecorder(self.memory.store)
                rec = recorder.record_response(response)
                recorded = {"trace_id": rec["trace_id"], "session": rec["session"],
                            "events": len(rec["events"])}
                self.bus.publish("experience.recorded", {"trace_id": rec["trace_id"]})
            except Exception as exc:  # noqa: BLE001 - enregistrement best-effort
                self.bus.publish("experience.record_failed", {"detail": str(exc)})

        self.session.note("runs")
        self._persist_events()
        return {
            "ok": bool(response.get("ok")),
            "query": query,
            "intent": response.get("intent"),
            "agents": [a.get("id") for a in response.get("agents", [])],
            "governance": {"doctrines": len(response.get("governance", {}).get("doctrines", [])),
                           "adrs": len(response.get("governance", {}).get("adrs", []))},
            "runtime": {"kind": response.get("runtime", {}).get("kind"),
                        "status": response.get("runtime", {}).get("status")},
            "synthesis": response.get("synthesis"),
            "provider": response.get("provider", {}).get("selected"),
            "recorded": recorded,
            "alerts": self.watcher.alerts,
            "response": response,
        }

    # ================================================================== #
    # Grande boucle cognitive : Reasoning -> Decision -> [humain] -> Execution
    # ================================================================== #
    def decide(self, question: str, urgency: float = 0.3) -> Dict[str, Any]:
        """Délibère (Reasoning) puis formalise une décision candidate (Decision).

        La décision produite est **proposée** : elle exige une validation humaine
        avant toute exécution. Aucune couche n'est modifiée."""
        if not self._booted:
            self.run()
        self.config.ensure_directories()
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        # Boucle fermée : les apprentissages *validés* informent la décision (traçabilité).
        learning_ids = self._validated_learning_ids()
        delib = self.cognition.reasoning.reason(question)
        rec = self.cognition.decision.decide(
            question, deliberation_id=delib["id"], urgency=urgency, learning_ids=learning_ids)
        self.bus.publish("decision.proposed",
                         {"decision_id": rec["id"], "subject": question,
                          "learnings": len(learning_ids)})
        self.session.note("decisions")
        self._persist_events()
        selected = next((o for o in rec["options"] if o["id"] == rec["selected_id"]), {})
        return {
            "ok": True,
            "question": question,
            "deliberation_id": delib["id"],
            "decision_id": rec["id"],
            "selected": selected.get("name"),
            "class": rec["qualification"].get("class"),
            "status": rec["status"],
            "options": [{"name": o["name"], "score": o["score"], "selected": o["selected"]}
                        for o in rec["options"]],
            "validation_conditions": rec["validation_conditions"],
            "applied_learnings": rec["traceability"].get("learnings", []),
            "needs_human_validation": True,
        }

    def decide_from_input(self, input_id: str, urgency: float = 0.3) -> Dict[str, Any]:
        """Propose une décision gouvernée **à partir de l'analyse existante** d'une Entrée
        (INPUT-DECIDE-001) — pont Entrée → analyse → délibération → décision **proposée**.

        **Ne réexécute jamais** ``reason()`` : réutilise la **délibération déjà produite** (règle
        d'unicité : l'analyse officielle = l'événement ``input.analyzed`` le plus récent, ``seq``
        max). Le moteur Décision **lit** cette délibération (``gateway.deliberation`` →
        ``reasoning.get``) et en dérive la décision ; **aucune seconde délibération** n'est créée.
        L'Entrée n'est **jamais mutée** ; la décision est **proposée** (exige une validation humaine) ;
        la provenance ``decision.traceability.deliberation`` est portée par le moteur. Erreurs
        (convention des lectures/actions) : Entrée introuvable, aucune analyse, délibération
        introuvable, pile cognitive indisponible."""
        if not self._booted:
            self.run()
        self.config.ensure_directories()
        hist = self.input_history(input_id)
        if hist.get("ok") is False:
            return hist                                     # Entrée introuvable (même convention)
        analyzed = [e for e in hist["events"] if e.get("topic") == "input.analyzed"]
        if not analyzed:
            return {"ok": False, "error": f"aucune analyse pour cette Entrée : {input_id}"}
        delib_id = max(analyzed, key=lambda e: e.get("seq", 0))["payload"].get("deliberation_id")
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        try:
            delib = self.cognition.reasoning.get(delib_id)  # sujet autoritatif ; aucun re-raisonnement
        except Exception:  # noqa: BLE001 - id absent / stores désynchronisés
            return {"ok": False, "error": f"délibération introuvable : {delib_id}"}
        subject = (delib.get("problem", {}) or {}).get("question", "")
        learning_ids = self._validated_learning_ids()
        try:
            rec = self.cognition.decision.decide(
                subject, deliberation_id=delib_id, urgency=urgency, learning_ids=learning_ids)
        except Exception as exc:  # noqa: BLE001 - délibération obsolète / options vides
            return {"ok": False, "error": str(exc)}
        self.bus.publish("decision.proposed",
                         {"decision_id": rec["id"], "subject": subject,
                          "learnings": len(learning_ids)})
        self.session.note("decisions")
        self._persist_events()
        selected = next((o for o in rec["options"] if o["id"] == rec["selected_id"]), {})
        return {
            "ok": True,
            "input_id": input_id,
            "deliberation_id": delib_id,
            "decision_id": rec["id"],
            "selected": selected.get("name"),
            "class": rec["qualification"].get("class"),
            "status": rec["status"],
            "options": [{"name": o["name"], "score": o["score"], "selected": o["selected"]}
                        for o in rec["options"]],
            "validation_conditions": rec["validation_conditions"],
            "applied_learnings": rec["traceability"].get("learnings", []),
            "needs_human_validation": True,
        }

    def validate_decision(self, decision_id: str, approver: str, reason: str = "") -> Dict[str, Any]:
        """Validation humaine d'une décision candidate (garde-fou de souveraineté)."""
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        try:
            res = self.cognition.decision.validate(decision_id, approver, reason)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        self.bus.publish("decision.validated", {"decision_id": decision_id, "by": approver})
        self._persist_events()
        return {"ok": True, "decision_id": decision_id, "status": res.get("status")}

    def execute_decision(self, decision_id: str, actor: str) -> Dict[str, Any]:
        """Prépare et exécute une décision **validée** (Execution -> Runtime), sous
        garde-fous. Aucune exécution sans manifeste validé ni acteur autorisé."""
        if not self._booted:
            self.run()
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        run = self.cognition.execution.prepare(decision_id, actor=actor)
        self.bus.publish("execution.prepared",
                         {"run_id": run["id"], "status": run["status"]})
        if run["status"] != "prepared":
            self._persist_events()
            return {"ok": False, "decision_id": decision_id, "run_id": run["id"],
                    "status": run["status"], "refusals": run["guards"]["refusals"]}
        done = self.cognition.execution.execute(run["id"], actor=actor)
        self.bus.publish("execution.done", {"run_id": done["id"], "status": done["status"]})
        # Refermer la boucle vécu -> mémoire : le vécu d'exécution devient mémoire.
        ingested = self._ingest_execution_traces(done)
        if ingested:
            self.bus.publish("execution.memorized", {"run_id": done["id"], "traces": ingested})
        if done["status"] == "succeeded":
            self.session.note("executions")
        self._persist_events()
        return {
            "ok": done["status"] == "succeeded",
            "decision_id": decision_id,
            "run_id": done["id"],
            "status": done["status"],
            "steps": [{"name": s["name"], "status": s["status"], "job_id": s["job_id"]}
                      for s in done["steps"]],
            "memory_ingested": ingested,
        }

    def plan(self, objective: str) -> Dict[str, Any]:
        """Planifie un objectif via Planning (14), **boucle apprenante fermée** : chaque
        **recommandation validée** de Learning devient une tâche d'application du plan.
        Le plan reste une proposition. Aucune couche n'est modifiée."""
        if not self._booted:
            self.run()
        self.config.ensure_directories()
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        self.memory.init()                       # garantit le moteur Learning branché
        ps = self.cognition.planning.plan(objective)
        learning_tasks = [
            {"id": t["id"], "title": t["title"], "sources": t["sources"]}
            for t in ps["tasks"] if "learning" in t.get("tags", [])
        ]
        self.bus.publish("plan.created",
                         {"planset_id": ps["id"], "tasks": len(ps["tasks"]),
                          "from_learning": len(learning_tasks)})
        self.session.note("plans")
        self._persist_events()
        return {
            "ok": True,
            "objective": objective,
            "planset_id": ps["id"],
            "strategy": ps["recommended"]["strategy_name"],
            "task_count": len(ps["tasks"]),
            "tasks": [{"title": t["title"], "phase": t["phase"], "kind": t["kind"],
                       "tags": t["tags"]} for t in ps["tasks"]],
            "learning_tasks": learning_tasks,
            "applied_learnings": ps["traceability"].get("learnings", []),
            "learns": self.cognition.learns,
            "needs_human_validation": True,
        }

    # ================================================================== #
    # Chaîne apprenante : Memory (vécu) -> Learning (apprentissages proposés)
    # ================================================================== #
    def _provide_learning_engine(self):
        """Fournit le moteur Learning partagé à la cognition (boucle fermée). Garantit
        qu'il est branché sur la **mémoire vivante** avant sa mise en cache."""
        self.memory.init()
        return self.learning.engine(self.memory.store)

    def _learning_engine(self):
        """Démarre si besoin, initialise Memory, et retourne le moteur Learning
        branché sur la **mémoire vivante** du bootstrap (ou None si indisponible)."""
        if not self._booted:
            self.run()
        return self._provide_learning_engine()

    def _validated_learning_ids(self, limit: int = 50):
        """Ids des **recommandations validées** — la seule matière réinjectée dans la
        cognition (garde-fou : rien de non validé n'influence une décision/un plan)."""
        engine = self.learning.engine(self.memory.store)
        if engine is None:
            return []
        return [it["id"] for it in engine.search(kind="recommendation",
                                                 status="validated", limit=limit)]

    def learn(self) -> Dict[str, Any]:
        """Analyse le vécu conservé en Memory (11) et en dérive des **apprentissages
        propositionnels** via Learning (12). Aucun apprentissage n'est appliqué : tout
        est une proposition soumise à validation humaine. Aucune couche n'est modifiée.
        """
        engine = self._learning_engine()
        if engine is None:
            return {"ok": False, "error": f"Learning indisponible : {self.learning.error}"}
        result = engine.analyze()
        self.bus.publish("learning.analyzed",
                         {"entries": result["analyzed_entries"],
                          "total": result["total_learnings"]})
        self.session.note("learn_runs")
        self._persist_events()
        recommendations = [
            {"id": it["id"], "title": it["title"],
             "confidence": it["confidence"], "status": it["status"]}
            for it in engine.search(kind="recommendation", limit=10)
        ]
        return {
            "ok": True,
            "analyzed_entries": result["analyzed_entries"],
            "produced": result["produced"],
            "total_learnings": result["total_learnings"],
            "recommendations": recommendations,
            "needs_human_validation": True,
        }

    def learnings(self, kind: Optional[str] = None,
                  status: Optional[str] = None) -> Dict[str, Any]:
        """Liste les apprentissages proposés (lecture seule)."""
        engine = self._learning_engine()
        if engine is None:
            return {"ok": False, "error": f"Learning indisponible : {self.learning.error}"}
        items = engine.search(kind=kind, status=status, limit=1000)
        return {"ok": True, "count": len(items),
                "counts": engine.index.counts(),
                "items": [{"id": it["id"], "kind": it["kind"], "title": it["title"],
                           "confidence": it["confidence"], "status": it["status"]}
                          for it in items]}

    def validate_learning(self, item_id: str, approver: str,
                          reason: str = "", action: str = "validate") -> Dict[str, Any]:
        """Validation humaine d'un apprentissage (garde-fou : jamais appliqué sans
        approbateur identifié). ``action`` ∈ {validate, reject, revoke}."""
        engine = self._learning_engine()
        if engine is None:
            return {"ok": False, "error": f"Learning indisponible : {self.learning.error}"}
        if action not in ("validate", "reject", "revoke"):
            return {"ok": False, "error": f"action inconnue : {action}"}
        try:
            it = getattr(engine, action)(item_id, approver, reason)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        topic = {"validate": "learning.validated", "reject": "learning.rejected",
                 "revoke": "learning.revoked"}[action]
        self.bus.publish(topic, {"item_id": item_id, "by": approver})
        if action == "validate":
            self.session.note("learnings_validated")
        self._persist_events()
        return {"ok": True, "item_id": item_id, "status": it["status"]}

    # ================================================================== #
    # Point d'entrée unique : routage automatique
    # ================================================================== #
    def run_query(self, query: str, route: str = "auto", deep: bool = False,
                  record: bool = True, urgency: float = 0.3) -> Dict[str, Any]:
        """Point d'entrée unique. **Route automatiquement** la demande :

        * demande décisionnelle (« faut-il… », « choisir… », « X ou Y »…) →
          boucle cognitive :meth:`decide` (décision candidate gouvernée) ;
        * sinon → :meth:`handle` (Kernel + mémorisation de l'expérience).

        Le routage peut être forcé (``route="decide"`` / ``"kernel"``). Aucune
        couche n'est modifiée : le routeur est purement lexical et déterministe.
        """
        chosen = router.route(query, forced=route if route in ("decide", "kernel") else None)
        self.bus.publish("run.routed", {"route": chosen, "query": query})
        if chosen == "decide":
            result = self.decide(query, urgency=urgency)
        else:
            result = self.handle(query, deep=deep, record=record)
        result["route"] = chosen
        return result

    # ================================================================== #
    # Overview — agrégateur LECTURE SEULE (point d'entrée du futur UI)
    # ================================================================== #
    def overview(self) -> Dict[str, Any]:
        """Instantané agrégé de BrainAI pour le futur UI, en **lecture seule**.

        Compose uniquement des vues existantes — il **n'écrit rien** (aucun événement
        persisté, aucun incrément de session, aucun enregistrement), **ne démarre pas**
        BrainAI et **ne décide rien** à la place des moteurs. C'est un simple point de
        rassemblement pour l'affichage ; jamais un moteur de workflow."""
        self.agents.load()
        diag = Doctor(self).diagnose()                 # lecture ; ne persiste aucun événement
        session = self.session.summary()
        caps = self.agents.capabilities()
        open_decisions = self._read_open_decisions()
        executable_decisions = self._read_executable_decisions()
        learnings = self._read_learnings_overview()
        recent_events = self._read_recent_events(limit=10)
        recommendation = self._recommend_next_action(diag, session, open_decisions, learnings)
        return {
            "as_of": self.config.as_of,
            "state": {"verdict": diag["verdict"], "banner": diag["banner"],
                      "patrimony": diag["sections"]["patrimony"],
                      "availability": diag["sections"]["availability"]},
            "session": session,
            "agents": {"counts": self.agents.counts(),
                       "namespaces": self.agents.namespaces()},
            "capabilities": {"count": len(caps), "index": caps},
            "open_decisions": open_decisions,
            "executable_decisions": executable_decisions,
            "inputs": self._read_inputs_overview(),
            "learnings": learnings,
            "recent_events": recent_events,
            "diagnostics": {"verdict": diag["verdict"], "issues": diag["issues"]},
            "recommended_next_action": recommendation,
        }

    def _read_open_decisions(self) -> List[Dict[str, Any]]:
        """Décisions **proposées** en attente de validation (lecture seule)."""
        try:
            if not self.cognition.available():
                return []
            records = self.cognition.decision.search(status="proposed")
        except Exception:  # noqa: BLE001
            return []
        return [{"id": r["id"], "subject": r.get("request", {}).get("subject", ""),
                 "class": r.get("qualification", {}).get("class"), "status": r["status"]}
                for r in records]

    def _read_executable_decisions(self) -> List[Dict[str, Any]]:
        """Décisions **validées et non encore exécutées** — actuellement **éligibles à une
        demande d'exécution** selon l'état autoritatif reflété (lecture seule).

        Le cerveau **revalide toujours les préconditions au moment de l'action** ; ceci n'est
        **aucune règle nouvelle**, seulement le reflet de l'état ``validated`` ∧
        ``execution_status == "not_executed"`` (miroir de ``_read_open_decisions``)."""
        try:
            if not self.cognition.available():
                return []
            records = self.cognition.decision.search(status="validated")
        except Exception:  # noqa: BLE001
            return []
        return [{"id": r["id"], "subject": r.get("request", {}).get("subject", ""),
                 "class": r.get("qualification", {}).get("class"), "status": r["status"]}
                for r in records
                if r.get("execution_manifest", {}).get("execution_status") == "not_executed"]

    def _read_learnings_overview(self) -> Dict[str, Any]:
        """Apprentissages **proposés** et **validés** (lecture seule ; pas d'analyse)."""
        try:
            engine = self._provide_learning_engine()
            if engine is None:
                return {"proposed": {"count": 0, "items": []},
                        "validated": {"count": 0, "items": []}}
        except Exception:  # noqa: BLE001
            return {"proposed": {"count": 0, "items": []},
                    "validated": {"count": 0, "items": []}}

        def summarize(status: str) -> Dict[str, Any]:
            items = engine.search(status=status, limit=1000)
            top = [{"id": it["id"], "kind": it["kind"], "title": it["title"]}
                   for it in items[:5]]
            return {"count": len(items), "items": top}
        return {"proposed": summarize("proposed"), "validated": summarize("validated")}

    def _read_inputs_overview(self, limit: int = 5) -> Dict[str, Any]:
        """Entrées perçues — projection minimale pour l'overview (lecture seule).

        Délègue au pilier Perception ; ne fabrique, ne normalise, ni n'analyse rien. Une
        Entrée reste un **fait observé** : jamais une connaissance ni une décision."""
        items = self.perception.project()
        return {"count": len(items), "items": items[:limit]}

    def status_summary(self) -> Dict[str, Any]:
        """Patrimoine et disponibilité des sous-systèmes (lecture seule, sans démarrer)."""
        return {
            "patrimony": self.patrimony.summary(),
            "first_agents": list(self.config.first_agents),
            "components_src": {
                "control_plane": self.config.control_plane_src.exists(),
                "memory": self.config.memory_src.exists(),
                "knowledge": self.config.knowledge_src.exists(),
                "agents_catalog": self.config.agents_dir.exists(),
            },
        }

    def inputs(self) -> Dict[str, Any]:
        """Entrées perçues — **liste projetée** (lecture seule). Délègue au pilier Perception ;
        n'écrit rien, ne démarre pas BrainAI. Une Entrée est un fait observé, jamais un acteur."""
        items = self.perception.project()
        return {"count": len(items), "items": items}

    def input(self, input_id: str) -> Dict[str, Any]:
        """Détail d'une **Entrée** par identifiant (lecture seule). Renvoie l'Entrée telle
        quelle, ou un reflet d'erreur ``{ok: False, error}`` si l'identifiant est inconnu —
        jamais fabriqué, jamais simulé (aucun enrichissement cognitif n'existe à ce stade)."""
        entry = self.perception.read(input_id)
        if entry is None:
            return {"ok": False, "error": f"Entrée introuvable : {input_id}"}
        return entry

    def record_input(self, text: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        """Enregistre une **Entrée texte** — première acquisition officielle (INPUT-WRITE-001).

        Délègue **entièrement** au pilier Perception (normalisation, création canonique
        immuable, ajout append-only, provenance et ``as_of`` conservés). **Aucune** logique
        métier supplémentaire : aucune interprétation, aucun enrichissement, aucune décision,
        aucun apprentissage. Renvoie ``{ok:True, input_id, input}`` ; un texte vide ou une
        provenance invalide sont **reflétés** en ``{ok:False, error}`` (jamais fabriqués)."""
        try:
            entry = self.perception.record_text(text=text, provenance=provenance)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        self.bus.publish("input.recorded",
                         {"input_id": entry["id"], "modality": entry["modality"]})
        self._persist_events()
        return {"ok": True, "input_id": entry["id"], "input": entry}

    def analyze_input(self, input_id: str) -> Dict[str, Any]:
        """Première **analyse cognitive** d'une Entrée (INPUT-ANALYZE-001).

        Récupère l'Entrée officielle, puis fait **circuler son contenu dans le pipeline cognitif
        existant** — Reasoning seul (déterministe, **sans aucune IA/LLM**) via
        ``cognition.reasoning.reason``. Le Bootstrap **orchestre et délègue** ; aucune logique
        cognitive ici. **Aucune** mutation de l'Entrée, aucun enrichissement définitif, aucune
        écriture en Mémoire, aucun apprentissage, **aucune décision** (le moteur Decision n'est
        jamais appelé) et aucune exécution. Le résultat est un **reflet d'analyse transitoire**
        (délibération candidate), jamais gouverné. Id inconnu → ``{ok:False, error}``."""
        entry = self.perception.read(input_id)
        if entry is None:
            return {"ok": False, "error": f"Entrée introuvable : {input_id}"}
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        delib = self.cognition.reasoning.reason(entry["content"])
        # Reflet fidèle de la délibération produite pendant cet appel, via la **projection
        # officielle unique** (:func:`_project_analysis`) — la même que la relecture
        # ``input_analysis`` (INPUT-ANALYSIS-READ-001). La délibération persistée reste l'unique
        # source de vérité ; ceci n'en est qu'un reflet, non persisté ici.
        self.bus.publish("input.analyzed",
                         {"input_id": input_id, "deliberation_id": delib.get("id")})
        self._persist_events()
        return {"ok": True, "input_id": input_id, "analysis": _project_analysis(delib)}

    def input_history(self, input_id: str) -> Dict[str, Any]:
        """Histoire événementielle d'une **Entrée** (INPUT-HISTORY-001) — **lecture seule**.

        Restitue, dans l'**ordre chronologique déterministe** (ordre d'ajout / ``seq``), les
        événements du **journal append-only existant** reliés à cette Entrée
        (``payload.input_id == input_id``), **tels quels** (schéma réel : ``seq/topic/actor/
        timestamp/payload``). **Aucune** mutation du journal ni de l'Entrée, aucun état, aucune
        projection, aucune déduplication, aucun nouveau format. Un ``input_id`` inconnu renvoie
        ``{ok:False, error}`` (convention des lectures, cf. :meth:`input`) ; une Entrée connue
        sans événement renvoie normalement son histoire (``events: []``)."""
        if self.perception.read(input_id) is None:
            return {"ok": False, "error": f"Entrée introuvable : {input_id}"}
        events = [e for e in self.journal()["events"]
                  if isinstance(e.get("payload"), dict)
                  and e["payload"].get("input_id") == input_id]
        return {"input_id": input_id, "events": events}

    def input_analysis(self, input_id: str) -> Dict[str, Any]:
        """Analyse **revisitable** d'une Entrée (INPUT-ANALYSIS-READ-001) — **lecture seule**.

        Relit l'analyse **déjà produite**, **sans jamais recalculer** (aucun ``reason()``), sans
        second stockage ni seconde projection. **Règle d'unicité explicite** : l'analyse officielle
        d'une Entrée est la délibération référencée par son événement ``input.analyzed`` **le plus
        récent** (``seq`` maximal) — plusieurs analyses d'une même Entrée sont possibles (jamais
        dédupliquées), la plus récente fait foi. La délibération **persistée** (moteur Reasoning)
        reste l'**unique source de vérité** ; on la récupère par ``reasoning.get`` et on la met en
        forme via la **projection officielle unique** (:func:`_project_analysis`), identique à
        ``analyze_input``. **Aucun** effet de bord : aucun événement publié, aucune persistance,
        aucune mutation d'Entrée, aucune décision, aucune IA. Cas d'erreur (convention des
        lectures) : Entrée introuvable, aucune analyse, ou délibération introuvable (désync)."""
        hist = self.input_history(input_id)
        if hist.get("ok") is False:
            return hist                                    # Entrée introuvable (même convention)
        analyzed = [e for e in hist["events"] if e.get("topic") == "input.analyzed"]
        if not analyzed:
            return {"ok": False, "error": f"aucune analyse pour cette Entrée : {input_id}"}
        latest = max(analyzed, key=lambda e: e.get("seq", 0))   # règle : seq maximal
        delib_id = latest.get("payload", {}).get("deliberation_id")
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        try:
            delib = self.cognition.reasoning.get(delib_id)      # lecture seule, aucun recalcul
        except Exception:  # noqa: BLE001 - id absent / stores désynchronisés
            return {"ok": False, "error": f"délibération introuvable : {delib_id}"}
        return {"ok": True, "input_id": input_id, "analysis": _project_analysis(delib)}

    def journal(self, topic: str = None) -> Dict[str, Any]:
        """Journal d'événements persistant (lecture seule ; ne démarre pas BrainAI)."""
        path = self.events_path
        if path.exists():
            try:
                events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
                          if l.strip()]
            except Exception:  # noqa: BLE001
                events = []
        else:
            events = list(self.recorder.events)
        if topic:
            events = [e for e in events if e.get("topic") == topic]
        return {"count": len(events), "events": events}

    def _read_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Derniers événements du journal persistant (lecture seule)."""
        path = self.events_path
        if not path.exists():
            return []
        try:
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            return [json.loads(l) for l in lines[-limit:]]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _recommend_next_action(diag, session, open_decisions, learnings) -> Dict[str, Any]:
        """« Prochaine action recommandée » — règles **déterministes** et documentées.
        Suggère une action à l'utilisateur ; ne décide **jamais** à la place des moteurs.

        Priorité (première règle vraie) :
        1. pile dégradée        → diagnostic complet ;
        2. décision(s) ouverte(s) → validation humaine ;
        3. apprentissage(s) proposé(s) → revue humaine ;
        4. session inexistante   → démarrer BrainAI ;
        5. sinon                 → traiter une demande."""
        if diag["verdict"] != "healthy":
            return {"action": "diagnostiquer", "reason": "pile dégradée",
                    "command": "scc-brainai doctor"}
        if open_decisions:
            return {"action": "valider une décision",
                    "reason": f"{len(open_decisions)} décision(s) en attente de validation",
                    "command": f"scc-brainai validate {open_decisions[0]['id']} --by <acteur>"}
        proposed = learnings["proposed"]["count"]
        if proposed:
            return {"action": "revoir les apprentissages",
                    "reason": f"{proposed} apprentissage(s) proposé(s)",
                    "command": "scc-brainai learnings --status proposed"}
        if not session.get("exists"):
            return {"action": "démarrer BrainAI", "reason": "aucune session ouverte",
                    "command": "scc-brainai start"}
        return {"action": "traiter une demande", "reason": "pile saine, rien en attente",
                "command": "scc-brainai run \"…\""}

    # ================================================================== #
    # Diagnostic complet
    # ================================================================== #
    def doctor(self) -> Dict[str, Any]:
        """Diagnostic complet : patrimoine, disponibilité, santé, audits."""
        report = Doctor(self).diagnose()
        self.bus.publish("doctor.run", {"verdict": report["verdict"],
                                        "issues": len(report["issues"])})
        self._persist_events()
        return report

    # ================================================================== #
    # Continuité de session (mode « live »)
    # ================================================================== #
    def session_summary(self) -> Dict[str, Any]:
        """État de la session persistée, **sans démarrer** BrainAI (lecture seule).
        Reflète la continuité entre invocations : identité, démarrages, totaux."""
        return self.session.summary()

    # ================================================================== #
    # Registre d'agents (orchestration : le Bootstrap ne connaît que des descriptions)
    # ================================================================== #
    def agents_catalog(self, namespace: str = None, capability: str = None) -> Dict[str, Any]:
        """Catalogue déclaratif des agents (lecture seule). Filtrable par namespace ou
        capacité. Le Bootstrap n'expose que des descriptions — aucune logique métier."""
        self.agents.load()
        items = self.agents.all()
        if namespace:
            items = [d for d in items if d.namespace == namespace]
        if capability:
            items = [d for d in items if d.provides(capability)]
        return {"count": len(items), "agents": [d.to_dict() for d in items],
                "counts": self.agents.counts(), "malformed": self.agents.malformed}

    def capability_index(self) -> Dict[str, Any]:
        """Index capacité → fournisseurs (many-to-many)."""
        self.agents.load()
        return {"capabilities": self.agents.capabilities(), "counts": self.agents.counts()}

    def resolve_capability(self, capability: str) -> Dict[str, Any]:
        """Résout une capacité vers le fournisseur retenu (liaison paresseuse). Démarre
        BrainAI si besoin pour que les adaptateurs puissent se lier."""
        if not self._booted:
            self.run()
        result = self.capability_resolver.resolve(capability)
        self.bus.publish("capability.resolved",
                         {"capability": capability, "selected": result["selected"]})
        self._persist_events()
        return result

    def _ingest_execution_traces(self, run: Dict[str, Any]) -> int:
        """Ingère les traces d'exécution dans Memory (11) via son interface publique.

        Aucune modification de Memory : simples écritures d'événements (soumises aux
        garde-fous de confidentialité de Memory). Referme la boucle vécu -> mémoire."""
        if self.memory.store is None:
            self.memory.init()
        store = self.memory.store
        if store is None:
            return 0
        session = store.open_session(actor="execution",
                                     meta={"run_id": run.get("id"), "kind": "execution"})
        count = 0
        for tr in run.get("traces_for_memory", []):
            try:
                store.record_event(tr.get("subtype", "execution.event"),
                                   dict(tr.get("data", {})), session_id=session.id,
                                   actor=tr.get("actor", "brainai"),
                                   tags=["execution", "ingested"])
                count += 1
            except Exception:  # noqa: BLE001 - ingestion best-effort
                continue
        return count


__all__ = ["BrainAIBootstrap", "READY_BANNER"]
