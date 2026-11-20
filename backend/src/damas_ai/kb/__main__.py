"""Knowledge-base CLI.

    python -m damas_ai.kb --db sqlite:///../var/damas_kb.sqlite3 migrate
    python -m damas_ai.kb --db ... ingest --kind consensus results.jsonl [more.jsonl ...]
    python -m damas_ai.kb --db ... ingest --kind tactics --variant brazilian-8x8 tactics.jsonl
    python -m damas_ai.kb --db ... stats
    python -m damas_ai.kb --db ... find --tag stable_divergence
    python -m damas_ai.kb --db ... show 12

``--db`` defaults to DAMAS_DATABASE_URL. Kinds: analysis (G6), consensus (G7), adaptive (G8),
tactics (G9), decision (G10). JSONL files are the outputs of the corresponding CLIs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from damas_ai.config import Settings
from damas_ai.kb import KnowledgeBase
from damas_ai.kb.migrate import upgrade


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m damas_ai.kb", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=Settings().database_url)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    ing = sub.add_parser("ingest")
    ing.add_argument("--kind", required=True, choices=("analysis", "consensus", "adaptive", "tactics", "decision"))
    ing.add_argument("--variant", help="required for tactics and decision records")
    ing.add_argument("files", nargs="+", type=Path)
    sub.add_parser("stats")
    find = sub.add_parser("find")
    find.add_argument("--variant")
    find.add_argument("--tag")
    find.add_argument("--classification")
    find.add_argument("--critical", choices=("yes", "no"))
    find.add_argument("--limit", type=int, default=20)
    show = sub.add_parser("show")
    show.add_argument("id", type=int)
    ns = ap.parse_args(argv)
    if not ns.db:
        print("no database URL (use --db or DAMAS_DATABASE_URL)", file=sys.stderr)
        return 2

    if ns.cmd == "migrate":
        upgrade(ns.db)
        print(f"migrated {ns.db} to head")
        return 0
    kb = KnowledgeBase(ns.db)
    if ns.cmd == "ingest":
        if ns.kind in ("tactics", "decision") and not ns.variant:
            print("--variant is required for tactics/decision", file=sys.stderr)
            return 2
        count = errors = 0
        for path in ns.files:
            with kb.session() as s:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    view = json.loads(line)
                    try:
                        if ns.kind == "analysis":
                            kb.record_analysis(s, view)
                        elif ns.kind == "consensus":
                            kb.record_consensus(s, view)
                        elif ns.kind == "adaptive":
                            kb.record_adaptive(s, view)
                        elif ns.kind == "tactics":
                            kb.record_tactics(s, view, ns.variant)
                        else:
                            kb.record_decision(s, view, ns.variant)
                        count += 1
                    except (KeyError, ValueError) as exc:
                        errors += 1
                        print(f"{path}: skipped a record ({exc})", file=sys.stderr)
        print(json.dumps({"ingested": count, "errors": errors}))
        return 1 if errors else 0
    if ns.cmd == "stats":
        print(json.dumps(kb.stats(), indent=2))
        return 0
    if ns.cmd == "find":
        crit = None if ns.critical is None else ns.critical == "yes"
        rows = kb.find(ns.variant, ns.tag, ns.classification, crit, ns.limit)
        print(json.dumps([asdict(r) for r in rows], indent=1))
        return 0
    detail = kb.get(ns.id)
    print(json.dumps(detail, indent=1, default=str))
    return 0 if detail else 1


if __name__ == "__main__":
    raise SystemExit(main())
