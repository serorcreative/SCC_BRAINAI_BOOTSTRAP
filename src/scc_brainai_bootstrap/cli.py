"""CLI de démarrage de BrainAI (``scc-brainai``).

``start``  exécute la séquence de démarrage et affiche « BrainAI READY ».
``run``    point d'entrée unique : route auto (décision → decide ; sinon Kernel).
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
    else:
        _print_alerts(report.get("subscribers", {}).get("lifecycle", {}).get("alerts", []))
        sess = report.get("session", {})
        print(f"session       : {sess.get('session_id')} · démarrage n°{sess.get('boots')}")
        print(f"(event bus : {report['subscribers']['recorded']} événements journalisés)")
    return 0 if report["ready"] else 1


def _print_alerts(alerts) -> None:
    for a in alerts:
        print(f"  ⚠ [{a['severity']}] {a['topic']} — {a['detail']}")


def cmd_run(args) -> int:
    boot = _boot(args)
    result = boot.run_query(args.query, route=args.route,
                            deep=bool(args.deep), record=not args.no_record,
                            urgency=float(args.urgency))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if not result.get("ok"):
        print(f"✗ {result.get('error', 'échec')}")
        return 1
    print(f"route       : {result['route']}")
    if result["route"] == "decide":
        return _print_decision(result)
    print(f"intention   : {result['intent']}")
    print(f"agents      : {', '.join(result['agents'])}")
    print(f"gouvernance : {result['governance']['doctrines']} doctrine(s), "
          f"{result['governance']['adrs']} ADR")
    print(f"runtime     : {result['runtime']['kind']} → {result['runtime']['status']}")
    if result.get("recorded"):
        print(f"mémorisé    : trace {result['recorded']['trace_id']} "
              f"({result['recorded']['events']} événements)")
    _print_alerts(result.get("alerts", []))
    print("\n--- synthèse ---")
    print(result["synthesis"])
    return 0


def _print_decision(result) -> int:
    print(f"décision    : {result['decision_id']}  (statut : {result['status']})")
    print(f"retenue     : {result['selected']}  (classe : {result['class']})")
    print("options     :")
    for o in result["options"]:
        print(f"  {'●' if o['selected'] else '○'} {o['name']} (score {o['score']})")
    print("validation humaine requise avant exécution :")
    for c in result["validation_conditions"]:
        print(f"  - {c}")
    print(f"\n→ valider : scc-brainai validate {result['decision_id']} --by <acteur>")
    return 0


def cmd_decide(args) -> int:
    result = _boot(args).decide(args.question, urgency=float(args.urgency))
    if args.json or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    return _print_decision(result)


def cmd_plan(args) -> int:
    result = _boot(args).plan(args.objective)
    if args.json or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    print(f"objectif    : {result['objective']}")
    print(f"plan        : {result['planset_id']}  (stratégie : {result['strategy']})")
    print(f"tâches      : {result['task_count']}  "
          f"(dont {len(result['learning_tasks'])} issue(s) d'apprentissages validés)")
    if result["learning_tasks"]:
        print("issues d'apprentissages validés (boucle fermée) :")
        for t in result["learning_tasks"]:
            print(f"  ⟲ {t['title']}  ({', '.join(t['sources'])})")
    else:
        print("(aucune tâche issue d'apprentissage : valider des recommandations via learn-validate)")
    print("plan proposé — validation humaine requise avant exécution.")
    return 0


def cmd_validate(args) -> int:
    result = _boot(args).validate_decision(args.id, args.by, args.reason)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_execute(args) -> int:
    result = _boot(args).execute_decision(args.id, actor=args.by)
    if args.json or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    print(f"exécution   : {result['run_id']}  (statut : {result['status']})")
    for s in result["steps"]:
        print(f"  [{s['status']}] {s['name']}  (job {s['job_id']})")
    if result.get("memory_ingested"):
        print(f"mémorisé    : {result['memory_ingested']} trace(s) d'exécution → Memory")
    return 0


def cmd_learn(args) -> int:
    result = _boot(args).learn()
    if args.json or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    p = result["produced"]
    print(f"vécu analysé  : {result['analyzed_entries']} entrée(s) de Memory")
    print(f"apprentissages: {result['total_learnings']} au total "
          f"(signaux {p['signals']}, patterns {p['patterns']}, leçons {p['lessons']}, "
          f"recommandations {p['recommendations']}, hypothèses {p['hypotheses']})")
    if result["recommendations"]:
        print("recommandations (propositions à valider) :")
        for r in result["recommendations"]:
            print(f"  ○ [{r['id']}] {r['title']}  (confiance {r['confidence']}, {r['status']})")
        print(f"\n→ valider : scc-brainai learn-validate <id> --by <acteur>")
    else:
        print("(aucune recommandation : vécu insuffisant — traiter plus de demandes d'abord)")
    return 0


def cmd_learnings(args) -> int:
    result = _boot(args).learnings(kind=args.kind, status=args.status)
    if args.json or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    print(f"apprentissages: {result['count']}  "
          + "  ".join(f"{k}={v}" for k, v in result["counts"].items()))
    for it in result["items"]:
        print(f"  [{it['status']:<9}] {it['kind']:<14} {it['title']}  "
              f"(conf {it['confidence']})  {it['id']}")
    return 0


def cmd_learn_validate(args) -> int:
    result = _boot(args).validate_learning(args.id, args.by, args.reason, action=args.action)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_doctor(args) -> int:
    report = _boot(args).doctor()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["verdict"] == "healthy" else 1
    s = report["sections"]

    def marks(d):
        return "  ".join(f"{k} {'✓' if v else '✗'}" for k, v in d.items())
    print("BrainAI DOCTOR")
    print("──────────────")
    print(f"patrimoine    : {s['patrimony']['present']}/{s['patrimony']['total']} présents"
          + (f"  (manquants : {', '.join(s['patrimony']['missing'])})" if s['patrimony']['missing'] else ""))
    print(f"disponibilité : {marks(s['availability'])}")
    print(f"santé         : control plane = {s['health']['control_plane']} "
          f"({s['health']['domains']} domaines)")
    print(f"audits        : {marks(s['audits']) if s['audits'] else '(aucune donnée)'}")
    for issue in report["issues"]:
        print(f"  ⚠ {issue}")
    print(f"\nVERDICT : {report['banner']}")
    return 0 if report["verdict"] == "healthy" else 1


def cmd_events(args) -> int:
    boot = _boot(args)
    path = boot.events_path
    if not path.exists():
        boot.run()               # démarre pour peupler le journal du bus
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if path.exists() else boot.recorder.events
    if args.topic:
        events = [e for e in events if e["topic"] == args.topic]
    print(json.dumps({"count": len(events), "events": events}, ensure_ascii=False, indent=2))
    return 0


def cmd_session(args) -> int:
    summary = _boot(args).session_summary()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if not summary.get("exists"):
        print("session : aucune (BrainAI n'a pas encore démarré ici)")
        return 0
    print("BrainAI SESSION")
    print("───────────────")
    print(f"session_id    : {summary['session_id']}")
    print(f"ouverte le    : {summary['created_as_of']}  (as_of figé)")
    print(f"démarrages    : {summary['boots']}")
    print(f"dernier état  : {summary.get('last_banner')}")
    print(f"agents        : {', '.join(summary.get('agents', []))}")
    print("activité cumulée :")
    for k, v in summary.get("totals", {}).items():
        print(f"  {k:<20} {v}")
    return 0


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

    p_run = sub.add_parser("run", help="Point d'entrée unique : route auto (décision → decide ; sinon Kernel).")
    p_run.add_argument("query")
    p_run.add_argument("--route", choices=["auto", "kernel", "decide"], default="auto",
                       help="Forcer la route (défaut : auto).")
    p_run.add_argument("--deep", action="store_true", help="Passe cognitive complète (5 moteurs, route Kernel).")
    p_run.add_argument("--no-record", action="store_true", help="Ne pas mémoriser l'expérience (route Kernel).")
    p_run.add_argument("--urgency", default="0.3", help="Urgence de la décision (route decide).")
    p_run.add_argument("--json", action="store_true", help="Sortie JSON complète.")
    p_run.set_defaults(func=cmd_run)

    p_decide = sub.add_parser("decide", help="Délibérer et formaliser une décision candidate.")
    p_decide.add_argument("question")
    p_decide.add_argument("--urgency", default="0.3")
    p_decide.add_argument("--json", action="store_true")
    p_decide.set_defaults(func=cmd_decide)

    p_plan = sub.add_parser("plan", help="Planifier un objectif (boucle apprenante : recommandations validées → tâches).")
    p_plan.add_argument("objective")
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_val = sub.add_parser("validate", help="Valider humainement une décision.")
    p_val.add_argument("id"); p_val.add_argument("--by", required=True); p_val.add_argument("--reason", default="")
    p_val.set_defaults(func=cmd_validate)

    p_exec = sub.add_parser("execute", help="Exécuter une décision validée (sous garde-fous).")
    p_exec.add_argument("id"); p_exec.add_argument("--by", required=True)
    p_exec.add_argument("--json", action="store_true")
    p_exec.set_defaults(func=cmd_execute)

    p_learn = sub.add_parser("learn", help="Apprendre du vécu (Memory → Learning, propositions).")
    p_learn.add_argument("--json", action="store_true")
    p_learn.set_defaults(func=cmd_learn)

    p_learnings = sub.add_parser("learnings", help="Lister les apprentissages proposés.")
    p_learnings.add_argument("--kind", default=None,
                             choices=["signal", "pattern", "lesson", "recommendation", "hypothesis"])
    p_learnings.add_argument("--status", default=None,
                             choices=["proposed", "validated", "rejected", "revoked"])
    p_learnings.add_argument("--json", action="store_true")
    p_learnings.set_defaults(func=cmd_learnings)

    p_lval = sub.add_parser("learn-validate", help="Valider/rejeter/révoquer un apprentissage (humain).")
    p_lval.add_argument("id")
    p_lval.add_argument("--by", required=True)
    p_lval.add_argument("--reason", default="")
    p_lval.add_argument("--action", default="validate", choices=["validate", "reject", "revoke"])
    p_lval.set_defaults(func=cmd_learn_validate)

    p_doctor = sub.add_parser("doctor", help="Diagnostic complet de BrainAI.")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    p_events = sub.add_parser("events", help="Journal de l'Event Bus (observabilité).")
    p_events.add_argument("--topic", default=None, help="Filtrer par topic.")
    p_events.set_defaults(func=cmd_events)

    p_session = sub.add_parser("session", help="État de la session persistée (continuité, sans démarrer).")
    p_session.add_argument("--json", action="store_true")
    p_session.set_defaults(func=cmd_session)

    sub.add_parser("status", help="Patrimoine et disponibilité des sous-systèmes.").set_defaults(func=cmd_status)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


__all__ = ["main", "build_parser"]
