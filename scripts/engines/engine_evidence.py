"""Collect behavioural evidence about a configured engine (used for G4/G5 reports).

Runs the engine through ``damas_ai.engines`` on oracle fixture positions and writes a JSON
summary: status counts, violations, PV legality, observed info fields, score kinds, timing,
and the results of specific protocol probes (depth/nodes limits, think vs analyze, move history,
overdue-search stop).

Usage:
    python scripts/engines/engine_evidence.py --config config/engines.toml --engine scan \
        --positions 1500 --move-time 0.1 --out reports/poc-runs/scan-evidence.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from damas_ai.config import load_engine_configs  # noqa: E402
from damas_ai.engines import AnalysisRequest, AnalysisStatus, SearchLimit, create_engine  # noqa: E402
from damas_ai.rules import RULESETS, apply_move, legal_moves  # noqa: E402
from damas_ai.rules.notation import from_fen, parse_move  # noqa: E402

ORACLE = {"international-10x10": "international", "brazilian-8x8": "brazilian"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--positions", type=int, default=1000)
    ap.add_argument("--move-time", type=float, default=0.1)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()

    config = load_engine_configs(ns.config)[ns.engine]
    ruleset = next(r for r in RULESETS.values() if r.variant == config.native_variant)
    fixture = ROOT / "backend" / "tests" / "fixtures" / "oracle" / f"{ORACLE[config.native_variant]}_pydraughts.json"
    records = [r for r in json.loads(fixture.read_text(encoding="utf-8"))["positions"] if r["moves"]]
    # Captures first (the rules that matter most), then the rest, up to the requested count.
    records.sort(key=lambda r: (not r["moves"][0][2], -max(len(m[2]) for m in r["moves"])))
    records = records[: ns.positions]

    status = Counter()
    violations = Counter()
    info_keys = Counter()
    score_kinds = Counter()
    edges = [0, 1, 2, 5, 10, 20, 30, 35, 38, 39, 39.5, 40, 80, 90, 100.01]
    abs_hist = Counter()
    pv_lengths, pv_reported, elapsed = [], [], []
    multi_capture_ok = king_ok = 0
    examples = []
    limit = SearchLimit(move_time_s=ns.move_time)

    engine = create_engine(config)
    info = engine.start()
    t_start = time.monotonic()
    for rec in records:
        position = from_fen(ruleset.geometry, rec["fen"])
        engine.new_game()
        result = engine.analyze(AnalysisRequest(ruleset, position, limit))
        status[result.status.value] += 1
        for v in result.violations:
            violations[v.split(":")[0][:80]] += 1
        elapsed.append(result.elapsed_s)
        for si in result.infos:
            info_keys.update(si.raw.keys())
            if si.score:
                score_kinds[si.score.kind] += 1
                if si.score.value is not None:
                    a = abs(si.score.value)
                    for lo, hi in zip(edges, edges[1:]):
                        if lo <= a < hi:
                            abs_hist[f"[{lo},{hi})"] += 1
                            break
        final = result.final_info
        if final is not None:
            pv_lengths.append(len(final.pv))
            pv_reported.append(len(final.pv_text.split()))
        if result.status is AnalysisStatus.OK and result.best_move is not None:
            if len(result.best_move.captured) >= 2:
                multi_capture_ok += 1
            if "K" in rec["fen"]:
                king_ok += 1
        elif len(examples) < 10:
            examples.append({"fen": rec["fen"], "status": result.status.value,
                             "move": result.best_move_text, "violations": list(result.violations)})
        if not engine.running:
            engine.restart()

    # ---------------------------------------------------------------- protocol probes
    probes = {}
    start = ruleset.initial_position()
    for name, lim in (("depth=6", SearchLimit(depth=6)), ("nodes=20000", SearchLimit(nodes=20000)),
                      ("move_time=0.2", SearchLimit(move_time_s=0.2))):
        try:
            r = engine.analyze(AnalysisRequest(ruleset, start, lim))
            fi = r.final_info
            probes[name] = {"status": r.status.value, "depth": fi.depth if fi else None,
                            "nodes": fi.nodes if fi else None, "elapsed_s": r.elapsed_s}
        except Exception as exc:  # noqa: BLE001
            probes[name] = {"error": f"{type(exc).__name__}: {exc}"}
    r = engine.analyze(AnalysisRequest(ruleset, start, limit, mode="think"))
    probes["go think"] = {"status": r.status.value, "move": r.best_move_text}
    m1 = legal_moves(start)[0]
    m2 = legal_moves(apply_move(start, m1))[0]
    r = engine.analyze(AnalysisRequest(ruleset, start, limit, moves=(m1, m2)))
    probes["move history"] = {"status": r.status.value, "sent": r.transcript[0][2] if r.transcript else ""}
    # Overdue search: a depth limit beyond the time budget forces the stop path. Only possible
    # for engines that honour depth limits (Kingsrow does not, so the probe is skipped).
    from damas_ai.engines import LimitKind

    if LimitKind.DEPTH in engine.capabilities().limits:
        overdue = config.model_copy(update={"search_timeout_s": 0.5})
        probe_engine = create_engine(overdue)
        probe_engine.start()
        r = probe_engine.analyze(AnalysisRequest(ruleset, start, SearchLimit(depth=40)))
        probes["stop on overdue (depth=40, 0.5 s budget)"] = {
            "status": r.status.value, "interrupted": r.interrupted, "elapsed_s": r.elapsed_s,
            "move": r.best_move_text}
        probe_engine.close()
    else:
        probes["stop on overdue"] = {"skipped": "engine profile has no depth limit"}
    shutdown = engine.close()

    summary = {
        "engine": {"id": config.id, "name": info.name, "version": info.version, "profile": info.profile,
                   "declared_params": list(info.declared_params)},
        "variant": ruleset.variant,
        "positions": len(records),
        "move_time_s": ns.move_time,
        "wall_time_s": round(time.monotonic() - t_start, 1),
        "status_counts": dict(status),
        "ok_multi_capture_moves": multi_capture_ok,
        "ok_in_positions_with_kings": king_ok,
        "violations": dict(violations.most_common()),
        "info_fields_seen": dict(info_keys.most_common()),
        "score_kinds": dict(score_kinds),
        "score_abs_histogram": {k: abs_hist[k] for k in sorted(abs_hist, key=lambda s: float(s[1:].split(",")[0]))},
        "pv": {"mean_reported": round(statistics.mean(pv_reported), 2) if pv_reported else 0,
               "mean_legal_prefix": round(statistics.mean(pv_lengths), 2) if pv_lengths else 0,
               "fully_legal_share": round(sum(a == b for a, b in zip(pv_lengths, pv_reported)) / max(1, len(pv_lengths)), 4)},
        "elapsed_s": {"mean": round(statistics.mean(elapsed), 4), "max": round(max(elapsed), 4)},
        "probes": probes,
        "shutdown": shutdown,
        "failure_examples": examples,
    }
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if status.get("ok", 0) == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
