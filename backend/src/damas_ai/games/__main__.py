"""Games: validate, analyse, generate and turn into datasets (G13, ADR-015).

    python -m damas_ai.games replay  games.pdn [more.pdn]
    python -m damas_ai.games analyze games.pdn --config ../config/engines.toml --engine scan \
        --move-time 0.2 --max-games 6 --out analysis.jsonl
    python -m damas_ai.games selfplay --variant brazilian-8x8 --games 200 --depth 4 --out selfplay/
    python -m damas_ai.games dataset games.pdn [more.pdn] --jsonl games.jsonl --out dataset/

``dataset`` takes PDN files. Optional ``--jsonl`` files (benchmark/self-play game records with the
same games) supply the mover's own eval per ply.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from damas_ai.games.pdn import parse_pdn, replay


def _load(paths: list[Path]):  # type: ignore[no-untyped-def]
    for path in paths:
        for i, g in enumerate(parse_pdn(path.read_text(encoding="utf-8"))):
            yield f"{path.stem}#{i + 1}", g


def cmd_replay(ns: argparse.Namespace) -> int:
    counts: Counter[str] = Counter()
    for gid, g in _load(ns.files):
        r = replay(g)
        counts["ok" if r.ok else "error"] += 1
        if not r.ok:
            print(f"{gid}: {r.error}", file=sys.stderr)
    print(json.dumps(dict(counts)))
    return 0 if counts["error"] == 0 else 1


def cmd_analyze(ns: argparse.Namespace) -> int:
    from damas_ai.config import load_engine_configs
    from damas_ai.engines import SearchLimit, create_engine
    from damas_ai.games.analysis import analyze_game

    engine = create_engine(load_engine_configs(ns.config)[ns.engine])
    engine.start()
    limit = SearchLimit(move_time_s=ns.move_time) if ns.depth is None else SearchLimit(depth=ns.depth)
    totals: dict[str, Counter[str]] = {}
    try:
        with ns.out.open("w", encoding="utf-8") as out:
            for n, (gid, g) in enumerate(_load(ns.files)):
                if ns.max_games and n >= ns.max_games:
                    break
                r = replay(g)
                if not r.ok:
                    continue
                ga = analyze_game(r, engine, limit)
                summary = ga.summary()
                for player, s in summary.items():
                    t = totals.setdefault(player, Counter())
                    for k, v in s.items():
                        if k not in ("accuracy", "mean_regret"):
                            t[k] += v
                out.write(json.dumps({"game_id": gid, "white": ga.white, "black": ga.black,
                                      "result": ga.result, "engine": ga.engine, "summary": summary,
                                      "plies": [asdict(p) for p in ga.plies]}) + "\n")
    finally:
        engine.close()
    report = {p: {**t, "accuracy": round((t["best"] + t["good"]) / t["moves"], 4) if t["moves"] else 0.0}
              for p, t in totals.items()}
    print(json.dumps(report, indent=1))
    return 0


def cmd_selfplay(ns: argparse.Namespace) -> int:
    from damas_ai.bench import SearchPlayer, generate_openings, play_game, write_outputs
    from damas_ai.bench.match import MatchResult
    from damas_ai.bench.stats import match_stats
    from damas_ai.rules import RULESETS

    rs = next(r for r in RULESETS.values() if r.variant == ns.variant)
    openings = generate_openings(rs, ns.games, ns.opening_plies, ns.seed, max_abs_score=ns.max_abs_score)
    a, b = SearchPlayer(ns.depth, f"selfplay-a@{ns.depth}"), SearchPlayer(ns.depth, f"selfplay-b@{ns.depth}")
    games = [play_game(a, b, rs, op.position, ns.max_plies, op.id) for op in openings]
    m = MatchResult(a.name, b.name, tuple(games), match_stats([g.score_for(a.name) for g in games]))
    write_outputs(ns.out, f"self-play depth {ns.depth}", [m], {"variant": rs.variant, "seed": ns.seed,
                                                                "depth": ns.depth, "openings": len(openings)})
    print(json.dumps({"games": len(games), "results": dict(Counter(g.result for g in games)),
                      "mean_plies": round(sum(g.plies for g in games) / max(1, len(games)), 1)}))
    return 0


def cmd_dataset(ns: argparse.Namespace) -> int:
    from damas_ai.games.dataset import SourceGame, build_dataset

    evals: dict[tuple[str, str, str], list[dict]] = {}  # type: ignore[type-arg]
    for path in ns.jsonl or []:
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            evals[(rec["start_fen"], " ".join(rec["moves"]), rec["white"])] = rec["move_infos"]

    def sources():  # type: ignore[no-untyped-def]
        for gid, g in _load(ns.files):
            r = replay(g)
            infos = evals.get((g.tags.get("FEN", ""), " ".join(g.moves), g.tags.get("White", "")))
            ev = None
            if infos:
                ev = {i: float(x["score_value"]) for i, x in enumerate(infos)
                      if x.get("score_kind") == "eval" and x.get("score_value") is not None}
            yield SourceGame(gid, r, ev, "mover's own engine eval" if ev else None)

    manifest = build_dataset(sources(), ns.out, seed=ns.seed, skip_plies=ns.skip_plies,
                             sources=[str(p) for p in ns.files])
    print(json.dumps({k: manifest[k] for k in ("games_per_split", "leakage_removed", "skipped_games", "files")}, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m damas_ai.games", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay")
    r.add_argument("files", nargs="+", type=Path)
    a = sub.add_parser("analyze")
    a.add_argument("files", nargs="+", type=Path)
    a.add_argument("--config", type=Path, required=True)
    a.add_argument("--engine", required=True)
    a.add_argument("--move-time", type=float, default=0.2)
    a.add_argument("--depth", type=int)
    a.add_argument("--max-games", type=int, default=0)
    a.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("selfplay")
    s.add_argument("--variant", required=True)
    s.add_argument("--games", type=int, default=100)
    s.add_argument("--depth", type=int, default=4)
    s.add_argument("--opening-plies", type=int, default=8)
    s.add_argument("--max-abs-score", type=int, default=60)
    s.add_argument("--seed", type=int, default=13)
    s.add_argument("--max-plies", type=int, default=300)
    s.add_argument("--out", type=Path, required=True)
    d = sub.add_parser("dataset")
    d.add_argument("files", nargs="+", type=Path)
    d.add_argument("--jsonl", nargs="*", type=Path)
    d.add_argument("--seed", type=int, default=13)
    d.add_argument("--skip-plies", type=int, default=0)
    d.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args(argv)
    return {"replay": cmd_replay, "analyze": cmd_analyze, "selfplay": cmd_selfplay, "dataset": cmd_dataset}[ns.cmd](ns)


if __name__ == "__main__":
    raise SystemExit(main())
