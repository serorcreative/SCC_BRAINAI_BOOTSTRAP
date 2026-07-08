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
from scc_brainai_bootstrap.event_bus import EventBus
from scc_brainai_bootstrap.patrimony import PatrimonyManager

READY_BANNER = "BrainAI READY"


class BrainAIBootstrap:
    def __init__(self, config: Optional[BrainAIConfig] = None):
        self.config = config or load_config()
        self.bus = EventBus(self.config.as_of)
        self.patrimony = PatrimonyManager(self.config)
        self.control_plane = ControlPlaneComponent(self.config)
        self.memory = MemoryComponent(self.config)
        self.knowledge = KnowledgeComponent(self.config)
        self.kernel = KernelComponent(self.config)
        self.agents = AgentRegistry(self.config)
        self._booted = False

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
            "response": response,
        }


__all__ = ["BrainAIBootstrap", "READY_BANNER"]
