"""Doctor — diagnostic complet de BrainAI en une passe.

Agrège, en lecture seule et via interfaces publiques : le **patrimoine**, la
**disponibilité** des composants, la **santé** du Control Plane et les **audits**
des couches (Memory, Reasoning, Planning, Decision, Execution). Rend un verdict
global : « BrainAI HEALTHY » ou « BrainAI DEGRADED ». Aucun composant n'est modifié.
"""

from __future__ import annotations

from typing import Any, Dict, List


class Doctor:
    def __init__(self, boot):
        self._boot = boot

    def diagnose(self) -> Dict[str, Any]:
        b = self._boot
        b.config.ensure_directories()
        issues: List[str] = []

        # -- patrimoine ------------------------------------------------- #
        pat = b.patrimony.summary()
        patrimony_ok = not pat["missing"]
        if not patrimony_ok:
            issues.append(f"patrimoine incomplet ({', '.join(pat['missing'])})")

        # -- disponibilité --------------------------------------------- #
        cp = b.control_plane.init()
        mem = b.memory.init()
        kno = b.knowledge.init()
        ker = b.kernel.init()
        stack_ok = b.cognition.available()
        availability = {
            "control_plane": cp["ready"], "memory": mem["ready"],
            "knowledge": kno["ready"], "kernel": ker["ready"],
            "reasoning": stack_ok, "planning": stack_ok,
            "decision": stack_ok, "execution": stack_ok,
        }
        unavailable = sorted(k for k, v in availability.items() if not v)
        if unavailable:
            issues.append(f"indisponibles : {', '.join(unavailable)}")

        # -- santé Control Plane --------------------------------------- #
        overall, domains = "unavailable", 0
        if b.control_plane.instance is not None:
            try:
                h = b.control_plane.instance.health()
                overall, domains = h.get("overall", "unknown"), len(h.get("domains", []))
            except Exception as exc:  # noqa: BLE001
                overall = f"erreur : {exc}"
        if overall != "ok":
            issues.append(f"santé Control Plane = {overall}")

        # -- audits des couches ---------------------------------------- #
        audits: Dict[str, bool] = {}
        if mem["ready"] and b.memory.store is not None:
            audits["memory"] = bool(b.memory.store.audit().get("ok"))
        if stack_ok:
            for name, eng in (("reasoning", b.cognition.reasoning),
                              ("planning", b.cognition.planning),
                              ("decision", b.cognition.decision),
                              ("execution", b.cognition.execution)):
                try:
                    audits[name] = bool(eng.audit().get("ok"))
                except Exception:  # noqa: BLE001
                    audits[name] = False
        failed_audits = sorted(k for k, v in audits.items() if not v)
        if failed_audits:
            issues.append(f"audits KO : {', '.join(failed_audits)}")

        verdict_ok = patrimony_ok and not unavailable and overall == "ok" and not failed_audits
        banner = "BrainAI HEALTHY" if verdict_ok else "BrainAI DEGRADED"

        return {
            "as_of": b.config.as_of,
            "verdict": "healthy" if verdict_ok else "degraded",
            "banner": banner,
            "issues": issues,
            "sections": {
                "patrimony": {"present": pat["present"], "total": pat["total"],
                              "missing": pat["missing"], "ok": patrimony_ok},
                "availability": availability,
                "health": {"control_plane": overall, "domains": domains},
                "audits": audits,
            },
        }


__all__ = ["Doctor"]
