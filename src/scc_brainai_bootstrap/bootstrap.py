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

from scc_brainai_bootstrap.agents import AgentRegistry
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
from scc_brainai_bootstrap.patrimony import PatrimonyManager
from scc_brainai_bootstrap.subscribers import EventRecorder, LifecycleWatcher

READY_BANNER = "BrainAI READY"


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
        self.agents = AgentRegistry(self.config)
        self.cognition = CognitiveStack(self.config)
        self._booted = False

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
        self.bus.publish("brainai.ready", {"ready": overall, "degraded": degraded})

        banner = READY_BANNER if overall else f"{READY_BANNER} (DÉGRADÉ : {', '.join(degraded)})"
        if on_step:
            on_step({"n": 8, "name": "ready", "ok": overall, "detail": banner, "data": {}})

        self._booted = True
        self._persist_events()
        return {
            "as_of": self.config.as_of,
            "ready": overall,
            "banner": banner,
            "degraded": degraded,
            "steps": steps,
            "patrimony": pat,
            "agents": self.agents.to_list(),
            "events": self.bus.events,
            "event_count": len(self.bus),
            "subscribers": {
                "recorded": len(self.recorder),
                "events_file": str(self.events_path),
                "lifecycle": self.watcher.summary(),
            },
        }

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
        self.config.ensure_directories()
        if not self.cognition.available():
            return {"ok": False, "error": f"pile cognitive indisponible : {self.cognition.error}"}
        delib = self.cognition.reasoning.reason(question)
        rec = self.cognition.decision.decide(
            question, deliberation_id=delib["id"], urgency=urgency)
        self.bus.publish("decision.proposed",
                         {"decision_id": rec["id"], "subject": question})
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
