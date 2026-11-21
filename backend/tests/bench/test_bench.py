"""G12 benchmarks: arbiter, players, openings, statistics, outputs."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from damas_ai.bench import (
    GreedyPlayer,
    MoveChoice,
    RandomPlayer,
    fit_logistic,
    generate_openings,
    match_stats,
    play_game,
    run_match,
    to_pdn,
    write_outputs,
)
from damas_ai.bench.__main__ import main as bench_cli
from damas_ai.rules import BOARD_8X8, BRAZILIAN_PROVISIONAL, GameState, Move, legal_moves
from damas_ai.rules.notation import from_fen, parse_move

BR = BRAZILIAN_PROVISIONAL
TESTS = Path(__file__).resolve().parents[1]


class Scripted:
    """Plays a fixed list of move texts, then fails (forfeit)."""

    def __init__(self, name: str, moves: list[str], bad: Move | None = None) -> None:
        self.name, self.moves, self.bad, self.i = name, moves, bad, 0

    def new_game(self) -> None:
        self.i = 0

    def choose(self, state, root, history):  # type: ignore[no-untyped-def]
        if self.bad is not None:
            return MoveChoice(self.bad)
        if self.i >= len(self.moves):
            return MoveChoice(None, failure="script exhausted")
        m = parse_move(state.position, self.moves[self.i])
        self.i += 1
        return MoveChoice(m)


# ---------------------------------------------------------------- statistics


def test_match_stats_and_elo() -> None:
    st = match_stats([1, 1, 0.5, 0])
    assert (st.wins, st.draws, st.losses, st.score) == (2, 1, 1, 0.625)
    assert st.elo == pytest.approx(-400 * math.log10(1 / 0.625 - 1), abs=0.1)
    assert st.elo_low is not None and st.elo_low < st.elo < (st.elo_high or math.inf)
    assert 0.5 < (st.los or 0) < 1
    perfect = match_stats([1, 1, 1])
    assert perfect.elo is None and perfect.elo_high is None  # unbounded, not a fake number
    all_draws = match_stats([0.5] * 16)
    assert all_draws.elo == 0.0 and all_draws.elo_low is None and all_draws.elo_high is None  # not "certain"


def test_logistic_fit_recovers_a_relation() -> None:
    xs = [x / 10 for x in range(-30, 31)]
    ys = [1 / (1 + math.exp(-(0.2 + 1.5 * x))) for x in xs]  # fractional targets
    fit = fit_logistic(xs, ys)
    assert fit.converged and fit.slope == pytest.approx(1.5, abs=1e-3)
    assert fit.intercept == pytest.approx(0.2, abs=1e-3)
    assert not fit_logistic([1, 2], [1, 0]).converged


# ---------------------------------------------------------------- arbiter


def test_game_ends_by_rules_core_result() -> None:
    start = from_fen(BOARD_8X8, "W:W22:B18")  # white's only move captures the last black piece
    g = play_game(GreedyPlayer(), GreedyPlayer(), BR, start)
    (only,) = legal_moves(start)
    assert g.result == "1-0" and g.reason == "no legal moves" and len(g.moves) == 1
    assert g.moves[0].startswith("22x") and only.is_capture


def test_forfeit_and_illegal_move_lose() -> None:
    start = BR.initial_position()
    g = play_game(Scripted("w", []), RandomPlayer(), BR, start)
    assert g.result == "0-1" and "forfeit by w" in g.reason
    bogus = Move(0, (31,))  # not a legal move
    g2 = play_game(RandomPlayer(), Scripted("b", [], bad=bogus), BR, start)
    assert g2.result == "1-0" and "illegal move by b" in g2.reason


def test_move_cap_adjudicates_a_draw() -> None:
    g = play_game(RandomPlayer(1), RandomPlayer(2), BR, BR.initial_position(), max_plies=4)
    assert g.result == "1/2-1/2" and "move cap" in g.reason and g.plies == 4


def test_draw_rules_come_from_the_ruleset() -> None:
    # Kings on a1 (29) and h2 (28) shuffle on diagonals that never meet: a repetition draw.
    start = from_fen(BOARD_8X8, "W:WK29:BK28")
    a, b = Scripted("a", ["29-25", "25-29"] * 30), Scripted("b", ["28-32", "32-28"] * 30)
    g = play_game(a, b, BR, start)
    assert g.result == "1/2-1/2" and "repetition" in g.reason


# ---------------------------------------------------------------- openings, matches, outputs


def test_openings_are_deterministic_distinct_and_balanced() -> None:
    a = generate_openings(BR, 4, seed=7)
    b = generate_openings(BR, 4, seed=7)
    assert [o.position for o in a] == [o.position for o in b]
    assert len({o.position.to_dsa() for o in a}) == 4
    assert all(abs(o.internal_score) <= 40 and legal_moves(o.position) for o in a)


def test_match_swaps_colours_and_writes_outputs(tmp_path: Path) -> None:
    openings = generate_openings(BR, 4, seed=11)
    m = run_match(GreedyPlayer(1), RandomPlayer(2), BR, openings)
    assert len(m.games) == 8
    assert [g.white for g in m.games[:2]] == ["greedy", "random"]
    assert m.stats.wins + m.stats.draws + m.stats.losses == 8  # strength is measured in the G12 runs
    pdn = to_pdn(m.games[0], "test", 1)
    assert '[GameType "26"]' in pdn and pdn.rstrip().endswith(m.games[0].result)
    write_outputs(tmp_path, "test", [m], {"variant": BR.variant})
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert {s["player"] for s in summary["standings"]} == {"greedy", "random"}
    assert len((tmp_path / "games.jsonl").read_text(encoding="utf-8").splitlines()) == 8


def test_cli_with_internal_engine_players(tmp_path: Path) -> None:
    cfg = tmp_path / "engines.toml"
    cfg.write_text(
        "[engines.damasai_br]\nprotocol = \"hub\"\n"
        f"executable = {json.dumps(sys.executable)}\nargs = [\"-m\", \"damas_ai.search.hub\"]\n"
        f"working_dir = {json.dumps(str(tmp_path))}\nnative_variant = \"brazilian-8x8\"\n"
        f"[engines.damasai_br.env]\nPYTHONPATH = {json.dumps(str(TESTS.parent / 'src'))}\n"
        "[engines.damasai_br.params]\nvariant = \"brazilian\"\n", encoding="utf-8")
    out = tmp_path / "bench"
    assert bench_cli(["--config", str(cfg), "--variant", "brazilian-8x8", "--players",
                      "engine:damasai_br@depth=3", "random", "--openings", "2", "--out", str(out)]) == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    match = summary["matches"][0]
    assert match["games"] == 4 and match["score"] >= 0.75  # depth-3 search crushes random
    assert summary["players"]["engine:damasai_br@depth=3"]["engine"] == "DamasAI"
    assert "engine:damasai_br@depth=3" in summary["calibration"]
