"""Provider local déterministe de la capacité ``test.run``.

L'adaptateur construit lui-même un argv fermé vers le vérificateur statique BrainAI et l'exécute
une seule fois via ``run_confined``. Aucun shell, réseau, LLM, credential ou contenu libre fourni
par un modèle n'entre dans la commande.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract
from scc_brainai_bootstrap.builder.tool_runner import run_confined

PROVIDER_NAME = "deterministic_local_test"
CAPABILITY = "test.run"
DEFAULT_TEST_TIMEOUT_S = 30.0


class LocalDeterministicTestAdapter:
    """Test statique local, déterministe et confiné au workspace de livraison."""

    capability = CAPABILITY
    name = PROVIDER_NAME
    model = "deterministic"
    max_budget_usd = 0.0

    def __init__(self, *, timeout: float = DEFAULT_TEST_TIMEOUT_S) -> None:
        if timeout <= 0:
            raise ValueError("timeout de test strictement positif requis")
        self.timeout = float(timeout)

    def contract(self) -> AdapterContract:
        return AdapterContract(
            capabilities_served=(CAPABILITY,),
            auth_channel={"kind": "none", "explicit": True, "leaks_identity": False,
                          "detail": "test statique local — aucune credential"},
            inbound_channels=(),
            cost_report={"mode": "unavailable", "fabricated": False},
            native_budget={"usd_cap": "none", "call_cap": "enforced_by_brainai"},
            confinement={
                "workspace": True,
                "tools_allowed": ["python:static-site-check"],
                "tools_disallowed": ["shell", "network", "llm"],
                "permission_mode": "argv-only+shell-false",
                "env_mode": "minimal",
                "network": {"required": False, "isolation": "not_proven"},
            },
        )

    def run(self, *, cwd: Path, artifact_ref: Dict[str, Any]) -> Dict[str, Any]:
        relative_path = artifact_ref.get("relative_path") if isinstance(artifact_ref, dict) else None
        expected_sha256 = artifact_ref.get("sha256") if isinstance(artifact_ref, dict) else None
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise ValueError("artifact_ref incomplet pour test.run")
        tool = Path(__file__).with_name("static_site_test_tool.py").resolve()
        argv = [sys.executable, "-I", str(tool), relative_path, expected_sha256]
        result = run_confined(argv, cwd=Path(cwd), timeout=self.timeout)
        return {"called": True, "argv": argv, **result}


__all__ = ["PROVIDER_NAME", "CAPABILITY", "DEFAULT_TEST_TIMEOUT_S",
           "LocalDeterministicTestAdapter"]
