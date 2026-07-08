"""CLI de démarrage de BrainAI (``scc-brainai``).

``start`` exécute la séquence de démarrage et affiche « BrainAI READY ».
``status`` affiche le patrimoine et l'état des sous-systèmes (sans démarrer).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Optional

from scc_brainai_bootstrap import __version__
from scc_brainai_bootstrap.bootstrap import BrainAIBootstrap
from scc_brainai_bootstrap.core.config import load_config


def _boot(args) -> BrainAIBootstrap:
    return BrainAIBootstrap(config=load_config(args.config))


def cmd_start(args) -> int:
    boot = _boot(args)

    def printer(step):
        if step["name"] == "ready":
            print("\n" + step["detail"])
        else:
            mark = "✓" if step["ok"] else "✗"
            print(f"[{step['n']}/8] {step['name']:<15} {mark} {step['detail']}")

    report = boot.run(on_step=None if args.json else printer)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


def cmd_status(args) -> int:
    boot = _boot(args)
    print(json.dumps({
        "patrimony": boot.patrimony.summary(),
        "first_agents": boot.config.first_agents,
        "components_src": {
            "control_plane": boot.config.control_plane_src.exists(),
            "memory": boot.config.memory_src.exists(),
            "knowledge": boot.config.knowledge_src.exists(),
            "agents_catalog": boot.config.agents_dir.exists(),
        },
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scc-brainai", description="Démarrage officiel de BrainAI.")
    parser.add_argument("--version", action="version", version=f"scc-brainai {__version__}")
    parser.add_argument("--config", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Démarrer BrainAI (séquence complète).")
    p_start.add_argument("--json", action="store_true", help="Sortie JSON du rapport de démarrage.")
    p_start.set_defaults(func=cmd_start)

    sub.add_parser("status", help="Patrimoine et disponibilité des sous-systèmes.").set_defaults(func=cmd_status)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


__all__ = ["main", "build_parser"]
