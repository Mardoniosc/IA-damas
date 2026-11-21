"""Benchmark tournaments.

    python -m damas_ai.bench --config ../config/engines.toml --variant brazilian-8x8 \
        --players "engine:damasai_br@depth=6" "engine:damasai_br@depth=3" greedy random \
        --openings 10 --out ../reports/bench/br-depth

Player specs:
  engine:<id>[@depth=N|@move_time=S|@nodes=N]   (default move_time from --move-time)
  random[@seed=N]   greedy[@seed=N]
Every engine player gets its own engine process (no shared tables between players).
Each opening is played twice with colours swapped; games run sequentially (ADR-014).
Outputs: games.pdn, games.jsonl, summary.json (match stats, standings, score calibration).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from damas_ai import __version__
from damas_ai.bench import (
    EnginePlayer,
    GreedyPlayer,
    Player,
    RandomPlayer,
    fit_logistic,
    generate_openings,
    round_robin,
    write_outputs,
)
from damas_ai.bench.game import GameRecord
from damas_ai.config import load_engine_configs
from damas_ai.engines import SearchLimit, create_engine
from damas_ai.engines.base import EngineAdapter
from damas_ai.rules import RULESETS


def build_player(spec: str, configs: dict, default_move_time: float, adapters: list[EngineAdapter]) -> Player:  # type: ignore[type-arg]
    kind, _, opts = spec.partition("@")
    kv = dict(o.split("=", 1) for o in opts.split(",") if o)
    if kind == "random":
        return RandomPlayer(int(kv.get("seed", 0)), name=spec)
    if kind == "greedy":
        return GreedyPlayer(int(kv.get("seed", 0)), name=spec)
    if kind.startswith("engine:"):
        engine_id = kind.split(":", 1)[1]
        if engine_id not in configs:
            raise SystemExit(f"unknown engine {engine_id!r}")
        if "depth" in kv:
            limit = SearchLimit(depth=int(kv["depth"]))
        elif "nodes" in kv:
            limit = SearchLimit(nodes=int(kv["nodes"]))
        else:
            limit = SearchLimit(move_time_s=float(kv.get("move_time", default_move_time)))
        adapter = create_engine(configs[engine_id])
        adapter.start()
        adapters.append(adapter)
        return EnginePlayer(spec, adapter, limit)
    raise SystemExit(f"bad player spec {spec!r}")


def calibration(games: list[GameRecord]) -> dict[str, dict]:  # type: ignore[type-arg]
    """Per player: logistic fit of game outcome on the player's own eval (its side's view)."""
    data: dict[str, tuple[list[float], list[float]]] = {}
    for g in games:
        for info in g.move_infos:
            if info.get("score_kind") != "eval" or info.get("score_value") is None:
                continue
            p = info["player"]
            xs, ys = data.setdefault(p, ([], []))
            xs.append(float(info["score_value"]))
            ys.append(g.score_for(p))
    return {p: fit_logistic(xs, ys).__dict__ for p, (xs, ys) in data.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m damas_ai.bench", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--variant", required=True, choices=sorted({r.variant for r in RULESETS.values()}))
    ap.add_argument("--players", nargs="+", required=True)
    ap.add_argument("--openings", type=int, default=10)
    ap.add_argument("--opening-plies", type=int, default=6)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--move-time", type=float, default=0.1)
    ap.add_argument("--max-plies", type=int, default=300)
    ap.add_argument("--event", default="Damas Super AI benchmark")
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args(argv)

    ruleset = next(r for r in RULESETS.values() if r.variant == ns.variant)
    configs = load_engine_configs(ns.config) if ns.config else {}
    adapters: list[EngineAdapter] = []
    try:
        players = [build_player(s, configs, ns.move_time, adapters) for s in ns.players]
        openings = generate_openings(ruleset, ns.openings, ns.opening_plies, ns.seed)

        def progress(g: GameRecord) -> None:
            print(f"{g.white} vs {g.black}: {g.result} ({g.reason}, {g.plies} plies, {g.duration_s}s)",
                  file=sys.stderr, flush=True)

        matches = round_robin(players, ruleset, openings, ns.max_plies, progress)
        meta = {"variant": ns.variant, "ruleset_id": ruleset.id, "version": __version__,
                "openings": [{"id": o.id, "moves": list(o.moves), "internal_score": o.internal_score}
                             for o in openings],
                "opening_seed": ns.seed, "max_plies": ns.max_plies,
                "players": {p.name: ({"engine": a.info.name, "version": a.info.version}
                                     if isinstance(p, EnginePlayer) and (a := p.adapter).running else {})
                            for p in players},
                "calibration": calibration([g for m in matches for g in m.games])}
        write_outputs(ns.out, ns.event, matches, meta)
        print((ns.out / "summary.json").read_text(encoding="utf-8"))
    finally:
        for a in adapters:
            a.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
