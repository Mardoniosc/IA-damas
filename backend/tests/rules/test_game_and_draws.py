from __future__ import annotations

import random
from dataclasses import replace

import pytest
from helpers import pos

from damas_ai.rules import (
    BRAZILIAN_PROVISIONAL,
    INTERNATIONAL_PROVISIONAL,
    GameState,
    IllegalMoveError,
    Move,
    Outcome,
    apply_move,
    legal_moves,
    zobrist_key,
)
from damas_ai.rules.notation import parse_move
from damas_ai.rules.zobrist import key_after

BR = BRAZILIAN_PROVISIONAL


def play(state: GameState, *texts: str) -> GameState:
    for t in texts:
        state = state.play(parse_move(state.position, t))
    return state


def test_new_game_is_ongoing_and_rulesets_are_marked_provisional() -> None:
    state = GameState.new(BR)
    assert state.result().outcome is Outcome.ONGOING
    assert BR.provisional and INTERNATIONAL_PROVISIONAL.provisional
    assert GameState.new(INTERNATIONAL_PROVISIONAL).position.material() == (20, 0, 20, 0)


def test_illegal_move_is_refused() -> None:
    state = GameState.new(BR)
    with pytest.raises(IllegalMoveError):
        state.play(Move(9, (14,)))  # c3 -> e5 is not a legal man move


def test_no_legal_moves_loses() -> None:
    state = GameState.new(BR, pos("a1", "b2 c3"))
    assert state.result().outcome is Outcome.BLACK_WINS


def test_capturing_the_last_piece_wins() -> None:
    state = GameState.new(BR, pos("c3", "d4"))
    state = play(state, "c3xe5")
    assert state.result().outcome is Outcome.WHITE_WINS


# Kings shuffle on diagonals that never meet, so no capture ever becomes compulsory.
SHUFFLE = ("a1-b2", "h2-g1", "b2-a1", "g1-h2")
QUIET = ("Ka1 c1", "Kh2 h6")


def test_threefold_repetition_is_a_draw() -> None:
    state = GameState.new(BR, pos(*QUIET))
    shuffle = SHUFFLE
    state = play(state, *shuffle)          # start position seen twice
    assert state.result().outcome is Outcome.ONGOING
    state = play(state, *shuffle)          # third occurrence
    assert state.result().outcome is Outcome.DRAW
    assert "repetition" in state.result().reason


def test_man_move_resets_repetition_window_and_king_counter() -> None:
    state = play(GameState.new(BR, pos(*QUIET)), "a1-b2", "h2-g1")
    assert state.king_only_plies == 2
    state = play(state, "c1-d2")
    assert state.king_only_plies == 0 and len(state.keys_since_irreversible) == 1


def test_king_only_move_limit_is_a_draw() -> None:
    rs = replace(BR, repetition_count=None)
    state = GameState.new(rs, pos(*QUIET))
    for i in range(rs.king_only_limit_plies or 0):
        assert state.result().outcome is Outcome.ONGOING, i
        state = play(state, SHUFFLE[i % 4])
    result = state.result()
    assert result.outcome is Outcome.DRAW and "king-only" in result.reason


def test_three_kings_vs_one_endgame_rule() -> None:
    rs = replace(BR, repetition_count=None, king_only_limit_plies=None)
    state = GameState.new(rs, pos("Ka1 Ka5 Ke1", "Kh2"))
    limit = rs.endgame_rules[0].limit_plies
    for i in range(limit):
        assert state.result().outcome is Outcome.ONGOING
        state = play(state, SHUFFLE[i % 4])
    assert "3 kings vs 1 king" in state.result().reason
    # The same material with a man on the board does not match the rule.
    assert not rs.endgame_rules[0].matches((1, 3, 0, 1))


def test_loss_takes_precedence_over_draw_rules() -> None:
    rs = replace(BR, king_only_limit_plies=0)
    state = GameState.new(rs, pos("a1", "b2 c3"))
    assert state.result().outcome is Outcome.BLACK_WINS


def test_incremental_zobrist_matches_full_recomputation_over_random_games() -> None:
    rng = random.Random(7)
    for _ in range(30):
        p = BR.initial_position()
        key = zobrist_key(p)
        for _ in range(120):
            ms = legal_moves(p)
            if not ms:
                break
            m = rng.choice(ms)
            key = key_after(key, p, m)
            p = apply_move(p, m)
            assert key == zobrist_key(p)


def test_zobrist_distinguishes_side_to_move() -> None:
    p = pos("c3", "f6")
    assert zobrist_key(p) != zobrist_key(p.with_side(p.side_to_move.opponent))
