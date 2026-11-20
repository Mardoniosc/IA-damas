"""G10 evidence: is the aggregated decision better than single engines at the same budget?

For each position:
  - decision_ext: DecisionMaker with the external engines only;
  - decision_all: DecisionMaker with the external engines plus the internal engine;
  - single-engine moves: each engine's own stage-1 move (taken from the decision runs).
All distinct moves are then judged by longer searches of the judge engines (cross-evaluation,
judge units). Note: the judges are the same programs as two of the deciders, given more time.
That favours their own short-time moves, so this is a conservative test for the aggregate.

    python scripts/engines/decision_evidence.py --config config/engines.toml \
        --fens reports/poc-runs/g8-escalate-fens.txt --external scan,kingsrow_intl_hub \
        --internal damasai_intl --move-time 0.2 --judge-time 1.0 --out reports/poc-runs/g10-decision.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from damas_ai.analysis import EnginePool  # noqa: E402
from damas_ai.config import load_engine_configs  # noqa: E402
from damas_ai.consensus import ConsensusAnalyzer  # noqa: E402
from damas_ai.decision import DecisionMaker  # noqa: E402
from damas_ai.engines import AnalysisRequest, SearchLimit  # noqa: E402
from damas_ai.rules import INTERNATIONAL_PROVISIONAL  # noqa: E402
from damas_ai.rules.notation import format_move, from_fen  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--fens", type=Path, required=True)
    ap.add_argument("--external", required=True)
    ap.add_argument("--internal", required=True)
    ap.add_argument("--move-time", type=float, default=0.2)
    ap.add_argument("--judge-time", type=float, default=1.0)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()
    rs = INTERNATIONAL_PROVISIONAL
    ext = ns.external.split(",")
    judges = ext
    fast, slow = SearchLimit(move_time_s=ns.move_time), SearchLimit(move_time_s=ns.judge_time)
    rows = []
    with EnginePool(load_engine_configs(ns.config).values()) as pool:
        maker = DecisionMaker(pool)
        judge = ConsensusAnalyzer(pool)
        for fen in [x.strip() for x in ns.fens.read_text().splitlines() if x.strip()]:
            p = from_fen(rs.geometry, fen)
            req = AnalysisRequest(rs, p, fast)
            d_ext = maker.decide(req, ext)
            d_all = maker.decide(req, [*ext, ns.internal])
            picks = {"decision_ext": d_ext.move, "decision_all": d_all.move}
            for c in d_all.candidates:
                for src in c.sources:
                    if src != "tactics":
                        picks[src] = c.move
            moves = {m.identity: m for m in picks.values() if m is not None}
            values = {i: judge.evaluate_move(AnalysisRequest(rs, p, slow), m, tuple(judges), [])
                      for i, m in moves.items()}
            regret: dict[str, dict[str, float | None]] = {}
            for j in judges:
                us = [v[j].utility for v in values.values() if j in v and v[j].utility is not None]
                best = max(us) if us else None
                for who, m in picks.items():
                    if m is None:
                        continue
                    v = values[m.identity].get(j)
                    regret.setdefault(who, {})[j] = (best - v.utility) if (best is not None and v and v.utility is not None) else None
            rows.append({"fen": fen, "picks": {k: format_move(rs.geometry, m) for k, m in picks.items() if m},
                         "confidence": {"ext": d_ext.confidence, "all": d_all.confidence}, "regret": regret})

    summary: dict[str, object] = {"positions": len(rows), "move_time_s": ns.move_time, "judge_time_s": ns.judge_time}
    for who in ("decision_ext", "decision_all", *ext, ns.internal):
        stats = {}
        for j in judges:
            vals = [r["regret"].get(who, {}).get(j) for r in rows]
            vals = [v for v in vals if v is not None and v < 1000]
            stats[j] = {"mean": round(statistics.mean(vals), 3) if vals else None,
                        "errors>0.10": sum(v > 0.10 for v in vals),
                        "errors>=1.0": sum(v >= 1.0 for v in vals), "n": len(vals)}
        summary[who] = stats
    conf = {}
    for key in ("ext", "all"):
        for level in ("high", "medium", "low"):
            sel = [r for r in rows if r["confidence"][key] == level]
            vals = [r["regret"][f"decision_{key}"].get(judges[0]) for r in sel]
            vals = [v for v in vals if v is not None and v < 1000]
            conf[f"{key}:{level}"] = {"n": len(sel), "mean_regret_judge0": round(statistics.mean(vals), 3) if vals else None}
    summary["by_confidence"] = conf
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
