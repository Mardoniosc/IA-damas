"""Matches and round-robin tournaments (G12, ADR-014).

Each opening is played twice with colours swapped. Games are sequential (one at a time), which
gives equal conditions (ADR-008).
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from damas_ai.bench.game import GameRecord, play_game
from damas_ai.bench.openings import Opening
from damas_ai.bench.players import Player
from damas_ai.bench.stats import MatchStats, match_stats
from damas_ai.rules import Ruleset

GAMETYPE = {"brazilian-8x8": 26, "international-10x10": 20}


@dataclass(frozen=True)
class MatchResult:
    a: str
    b: str
    games: tuple[GameRecord, ...]
    stats: MatchStats


def run_match(a: Player, b: Player, ruleset: Ruleset, openings: Sequence[Opening],
              max_plies: int = 300, on_game: Callable[[GameRecord], None] | None = None) -> MatchResult:
    games: list[GameRecord] = []
    for op in openings:
        for white, black in ((a, b), (b, a)):
            g = play_game(white, black, ruleset, op.position, max_plies, op.id)
            games.append(g)
            if on_game:
                on_game(g)
    return MatchResult(a.name, b.name, tuple(games), match_stats([g.score_for(a.name) for g in games]))


def round_robin(players: Sequence[Player], ruleset: Ruleset, openings: Sequence[Opening],
                max_plies: int = 300, on_game: Callable[[GameRecord], None] | None = None) -> list[MatchResult]:
    return [run_match(a, b, ruleset, openings, max_plies, on_game) for a, b in itertools.combinations(players, 2)]


def standings(matches: Sequence[MatchResult]) -> list[tuple[str, float, int]]:
    """(player, points, games), best first."""
    pts: dict[str, float] = {}
    n: dict[str, int] = {}
    for m in matches:
        for g in m.games:
            for p in (g.white, g.black):
                pts[p] = pts.get(p, 0.0) + g.score_for(p)
                n[p] = n.get(p, 0) + 1
    return sorted(((p, pts[p], n[p]) for p in pts), key=lambda t: -t[1] / t[2])


def to_pdn(g: GameRecord, event: str, round_no: int) -> str:
    tags = [("Event", event), ("Round", str(round_no)), ("White", g.white), ("Black", g.black),
            ("Result", g.result), ("GameType", str(GAMETYPE.get(g.variant, 0))), ("FEN", g.start_fen),
            ("Termination", g.reason), ("Opening", g.opening_id)]
    head = "\n".join(f'[{k} "{v}"]' for k, v in tags)
    body: list[str] = []
    for i, mv in enumerate(g.moves):
        body.append(f"{i // 2 + 1}. {mv}" if i % 2 == 0 else mv)
    text = " ".join(body + [g.result])
    lines, line = [], ""
    for tok in text.split(" "):
        if len(line) + len(tok) + 1 > 80:
            lines.append(line)
            line = tok
        else:
            line = f"{line} {tok}".strip()
    lines.append(line)
    return head + "\n\n" + "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, event: str, matches: Sequence[MatchResult], meta: dict) -> None:  # type: ignore[type-arg]
    out_dir.mkdir(parents=True, exist_ok=True)
    games = [g for m in matches for g in m.games]
    (out_dir / "games.pdn").write_text("\n".join(to_pdn(g, event, i + 1) for i, g in enumerate(games)),
                                       encoding="utf-8")
    with (out_dir / "games.jsonl").open("w", encoding="utf-8") as fh:
        for g in games:
            fh.write(json.dumps(asdict(g), ensure_ascii=False) + "\n")
    summary = {"event": event, **meta,
               "matches": [{"a": m.a, "b": m.b, **asdict(m.stats)} for m in matches],
               "standings": [{"player": p, "points": s, "games": n} for p, s, n in standings(matches)]}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
