"""G9 evidence: precision of the forcing-shot detector, judged by external engines.

For oracle positions where the detector claims a shot *with a real choice* (sacrifice, or a
capture choice where not every legal move achieves the best gain), each judge engine:
  1. picks its own best move at the given limit;
  2. if it differs from the shot move, evaluates the position after the shot move and after its
     own move (G7 cross-evaluation), giving the judge's regret for the shot move in its units.

    python scripts/engines/tactics_evidence.py --config config/engines.toml \
        --judges scan,kingsrow_intl_hub --max-positions 150 --move-time 0.2 --out reports/poc-runs/g9-shots.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from damas_ai.analysis import EnginePool  # noqa: E402
from damas_ai.config import load_engine_configs  # noqa: E402
from damas_ai.consensus.values import value_after_move  # noqa: E402
from damas_ai.engines import AnalysisRequest, AnalysisStatus, SearchLimit  # noqa: E402
from damas_ai.rules import INTERNATIONAL_PROVISIONAL, apply_move, legal_moves  # noqa: E402
from damas_ai.rules.notation import format_move, from_fen  # noqa: E402
from damas_ai.tactics import find_shots  # noqa: E402


def value_of(pool, engine_id, ruleset, root, move, limit):  # type: ignore[no-untyped-def]
    after = apply_move(root, move)
    if not legal_moves(after):
        return 10_000.0 - 1
    a = pool.get(engine_id)
    a.new_game()
    r = a.analyze(AnalysisRequest(ruleset, root, limit, (move,)))
    if r.status is not AnalysisStatus.OK or r.final_info is None:
        return None
    return value_after_move(r.final_info.score).utility


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--judges", required=True)
    ap.add_argument("--max-positions", type=int, default=150)
    ap.add_argument("--move-time", type=float, default=0.2)
    ap.add_argument("--kind", choices=("sacrifice", "capture_choice", "all"), default="all")
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()

    rs = INTERNATIONAL_PROVISIONAL
    data = json.loads((ROOT / "backend/tests/fixtures/oracle/international_pydraughts.json").read_text())
    selected = []
    kinds = Counter()
    for rec in data["positions"]:
        if not rec["moves"]:
            continue
        p = from_fen(rs.geometry, rec["fen"])
        moves = legal_moves(p)
        if len(moves) < 2:
            continue
        shots = find_shots(p)
        if not shots:
            continue
        best = shots[0]
        if not best.sacrifice and sum(1 for s in shots if s.gain == best.gain) >= len(moves):
            continue
        kind = "sacrifice" if best.sacrifice else "capture_choice"
        kinds[kind] += 1
        selected.append((p, best, kind))
    # Keep every sacrifice; fill the rest with capture choices.
    sac = [x for x in selected if x[2] == "sacrifice"]
    cap = [x for x in selected if x[2] == "capture_choice"]
    pool_kinds = {"sacrifice": sac, "capture_choice": cap, "all": sac + cap}[ns.kind]
    sample = pool_kinds[: ns.max_positions]

    judges = ns.judges.split(",")
    limit = SearchLimit(move_time_s=ns.move_time)
    rows = []
    with EnginePool(load_engine_configs(ns.config).values()) as pool:
        for p, shot, kind in sample:
            row = {"fen": None, "kind": kind, "shot": format_move(rs.geometry, shot.first_move),
                   "gain_men": shot.gain / 100, "judges": {}}
            from damas_ai.rules.notation import to_fen

            row["fen"] = to_fen(p)
            for j in judges:
                a = pool.get(j)
                a.new_game()
                r = a.analyze(AnalysisRequest(rs, p, limit))
                if r.status is not AnalysisStatus.OK or r.best_move is None:
                    row["judges"][j] = {"status": r.status.value}
                    continue
                agree = r.best_move.identity == shot.first_move.identity
                regret = 0.0
                if not agree:
                    v_shot = value_of(pool, j, rs, p, shot.first_move, limit)
                    v_own = value_of(pool, j, rs, p, r.best_move, limit)
                    regret = (v_own - v_shot) if v_shot is not None and v_own is not None else None
                row["judges"][j] = {"best": format_move(rs.geometry, r.best_move), "agree": agree,
                                    "regret": regret}
            rows.append(row)

    summary = {"candidates_found": dict(kinds), "evaluated": len(rows), "move_time_s": ns.move_time}
    for kind in ("sacrifice", "capture_choice"):
        sub = [r for r in rows if r["kind"] == kind]
        stats = {"n": len(sub)}
        for j in judges:
            js = [r["judges"][j] for r in sub if "agree" in r["judges"].get(j, {})]
            regrets = [x["regret"] for x in js if x["regret"] is not None]
            stats[j] = {
                "agree": sum(x["agree"] for x in js),
                "within_0.10": sum(1 for x in regrets if x <= 0.10),
                "regret>=1.0": sum(1 for x in regrets if x >= 1.0),
                "median_regret_when_disagree": (statistics.median([x for x, s in zip(regrets, js) if not s["agree"]])
                                                if any(not s["agree"] for s in js) else None),
            }
        both = sum(1 for r in sub if all(r["judges"].get(j, {}).get("agree") or
                                         (r["judges"].get(j, {}).get("regret") is not None and r["judges"][j]["regret"] <= 0.10)
                                         for j in judges))
        stats["accepted_by_all_judges(agree_or_regret<=0.10)"] = both
        summary[kind] = stats
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
