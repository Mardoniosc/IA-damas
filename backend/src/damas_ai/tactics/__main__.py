"""Batch criticality assessment: one FEN per line in, one JSON record per line out.

    python -m damas_ai.tactics --variant brazilian-8x8 --fens positions.txt --depth 6 \
        --out tactics.jsonl [--config ../config/engines.toml --consensus-move-time 0.2]

With ``--config`` (and at least two engines for the variant) the G7 consensus classification
is added as a divergence signal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from damas_ai.rules import RULESETS
from damas_ai.rules.notation import NotationError, from_fen
from damas_ai.tactics import Thresholds, assess
from damas_ai.tactics.serialize import criticality_view


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m damas_ai.tactics", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", required=True, choices=sorted({r.variant for r in RULESETS.values()}))
    ap.add_argument("--fens", type=Path, required=True)
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--consensus-move-time", type=float, default=0.2)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args(argv)

    ruleset = next(r for r in RULESETS.values() if r.variant == ns.variant)
    thresholds = Thresholds(depth=ns.depth)
    consensus = pool = None
    if ns.config:
        from damas_ai.analysis import EnginePool
        from damas_ai.config import Settings, load_engine_configs
        from damas_ai.consensus import ConsensusAnalyzer

        pool = EnginePool(load_engine_configs(ns.config).values(), Settings().engine_thread_budget)
        consensus = ConsensusAnalyzer(pool)
    errors = 0
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ns.out.open("w", encoding="utf-8") as out:
            for line_no, line in enumerate(ns.fens.read_text(encoding="utf-8").splitlines(), 1):
                text = line.strip()
                if not text or text.startswith("#"):
                    continue
                try:
                    position = from_fen(ruleset.geometry, text)
                except (NotationError, ValueError) as exc:
                    print(f"line {line_no}: skipped ({exc})", file=sys.stderr)
                    errors += 1
                    continue
                divergence, proof_gap = None, False
                if consensus is not None:
                    from damas_ai.engines import AnalysisRequest, SearchLimit

                    c = consensus.analyze(AnalysisRequest(ruleset, position,
                                                          SearchLimit(move_time_s=ns.consensus_move_time)))
                    divergence, proof_gap = c.classification.value, c.proof_gap
                try:
                    report = assess(position, thresholds, divergence, proof_gap)
                except ValueError as exc:
                    print(f"line {line_no}: skipped ({exc})", file=sys.stderr)
                    errors += 1
                    continue
                out.write(json.dumps(criticality_view(report), ensure_ascii=False) + "\n")
    finally:
        if pool is not None:
            pool.close()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
