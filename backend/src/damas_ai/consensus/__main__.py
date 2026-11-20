"""Batch consensus analysis: one FEN per line in, one JSON record per line out.

    python -m damas_ai.consensus --config ../config/engines.toml --variant international-10x10 \
        --fens positions.txt --move-time 0.2 --cross-check disagreement --tolerance 0.1 \
        --out consensus.jsonl

Engines run sequentially by default (equal conditions, ADR-008).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from damas_ai.analysis import EnginePool
from damas_ai.config import Settings, load_engine_configs
from damas_ai.consensus import DEFAULT_TOLERANCE, ConsensusAnalyzer
from damas_ai.consensus.serialize import consensus_view
from damas_ai.engines import AnalysisRequest, SearchLimit
from damas_ai.logging_config import configure_logging
from damas_ai.rules import RULESETS
from damas_ai.rules.notation import NotationError, from_fen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m damas_ai.consensus", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--variant", required=True, choices=sorted({r.variant for r in RULESETS.values()}))
    ap.add_argument("--fens", type=Path, required=True)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--move-time", type=float)
    group.add_argument("--depth", type=int)
    group.add_argument("--nodes", type=int)
    ap.add_argument("--engines")
    ap.add_argument("--mode", choices=("parallel", "sequential"), default="sequential")
    ap.add_argument("--cross-check", choices=("disagreement", "always", "never"), default="disagreement")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args(argv)

    settings = Settings()
    configure_logging(settings)
    ruleset = next(r for r in RULESETS.values() if r.variant == ns.variant)
    limit = SearchLimit(depth=ns.depth, nodes=ns.nodes, move_time_s=ns.move_time)
    engines = ns.engines.split(",") if ns.engines else None
    errors = 0
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    with EnginePool(load_engine_configs(ns.config).values(), settings.engine_thread_budget) as pool, \
            ns.out.open("w", encoding="utf-8") as out:
        analyzer = ConsensusAnalyzer(pool)
        for line_no, line in enumerate(ns.fens.read_text(encoding="utf-8").splitlines(), 1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                position = from_fen(ruleset.geometry, text)
                request = AnalysisRequest(ruleset, position, limit)
            except (NotationError, ValueError) as exc:
                print(f"line {line_no}: skipped ({exc})", file=sys.stderr)
                errors += 1
                continue
            if not request.state.legal_moves():
                print(f"line {line_no}: skipped (terminal position)", file=sys.stderr)
                errors += 1
                continue
            result = analyzer.analyze(request, engines, ns.mode, ns.cross_check, ns.tolerance)
            out.write(json.dumps(consensus_view(result, request.position), ensure_ascii=False) + "\n")
            out.flush()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
