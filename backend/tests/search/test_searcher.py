from __future__ import annotations

import threading
import time

import pytest
from conftest import oracle_positions

from damas_ai.rules import BOARD_8X8, BRAZILIAN_PROVISIONAL, apply_move, legal_moves
from damas_ai.rules.notation import from_fen
from damas_ai.search import Searcher, evaluate, score_to_men
from damas_ai.search.searcher import CHECK_EVERY, MATE_BOUND, WIN

BR = BRAZILIAN_PROVISIONAL


def test_best_move_is_always_legal_on_oracle_positions() -> None:
    searcher = Searcher()
    for p in oracle_positions("brazilian")[:300]:
        searcher.clear()
        out = searcher.search(p, depth=3)
        assert out.best_move in legal_moves(p)
        # The reported PV is a legal line.
        q = p
        for m in out.pv:
            assert m in legal_moves(q)
            q = apply_move(q, m)


def test_forced_capture_and_majority_come_from_the_rules_core() -> None:
    p = from_fen(BOARD_8X8, "W:W22,30:B18,11,26")  # captures available; majority applies
    out = Searcher().search(p, depth=4)
    assert out.best_move in legal_moves(p) and out.best_move.is_capture
    assert len(out.best_move.captured) == max(len(m.captured) for m in legal_moves(p))


def test_finds_a_short_forced_win() -> None:
    p = from_fen(BOARD_8X8, "W:WK29,K32:B5")
    out = Searcher().search(p, move_time_s=2.0)
    assert out.score is not None and out.score >= MATE_BOUND
    assert WIN - out.score <= 5  # win within a few plies
    assert score_to_men(out.score).startswith("99.9")


def test_terminal_root() -> None:
    out = Searcher().search(from_fen(BOARD_8X8, "W:W:B5"), depth=3)
    assert out.best_move is None and out.score == -WIN


def test_fixed_depth_search_is_deterministic() -> None:
    a = Searcher().search(BR.initial_position(), depth=6)
    b = Searcher().search(BR.initial_position(), depth=6)
    assert (a.best_move, a.score, a.nodes, a.pv) == (b.best_move, b.score, b.nodes, b.pv)


def test_limits_are_honoured() -> None:
    out = Searcher().search(BR.initial_position(), nodes=5000)
    assert out.nodes <= 5000 + CHECK_EVERY and out.stopped
    t0 = time.perf_counter()
    out = Searcher().search(BR.initial_position(), move_time_s=0.3)
    assert time.perf_counter() - t0 < 0.6 and out.depth >= 3
    stop = threading.Event()
    stop.set()
    out = Searcher().search(BR.initial_position(), stop=stop)
    assert out.best_move in legal_moves(BR.initial_position())  # falls back to a legal move


def test_iterative_deepening_reports_each_depth() -> None:
    seen: list[int] = []
    Searcher().search(BR.initial_position(), depth=5, on_depth=lambda i: seen.append(i.depth))
    assert seen == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("name", ["brazilian", "international"])
def test_evaluation_is_colour_symmetric(name: str) -> None:
    for p in oracle_positions(name)[:500]:
        assert evaluate(p) == evaluate(p.flipped())


def test_score_text_encoding() -> None:
    assert score_to_men(0) == "0.00" and score_to_men(-125) == "-1.25"
    assert score_to_men(WIN - 7) == "99.93" and score_to_men(-(WIN - 3)) == "-99.97"
    assert score_to_men(8500) == "80.00"  # evals are clamped below the win band
    assert score_to_men(MATE_BOUND) == "90.00"  # longest representable win: 1000 plies
