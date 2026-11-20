"""One or more named tests per Brazilian rule clause (rules-compatibility.md, BR column).

Positions are hand-built from the rule text. Expected move sets were reasoned out by hand;
the reasoning is in each docstring.
"""

from __future__ import annotations

from helpers import captured, moves, pos, promotes

from damas_ai.rules import BRAZILIAN_PROVISIONAL, Color, Piece, apply_move, legal_moves


# ---------------------------------------------------------------- setup


def test_br_start_position_12_men_each_white_on_ranks_1_to_3_white_first() -> None:
    p = BRAZILIAN_PROVISIONAL.initial_position()
    assert p.material() == (12, 0, 12, 0)
    assert p.side_to_move is Color.WHITE
    assert p.to_dsa() == "W" + "w" * 12 + "e" * 8 + "b" * 12
    assert moves(p) == {"a3-b4", "c3-b4", "c3-d4", "e3-d4", "e3-f4", "g3-f4", "g3-h4"}


# ---------------------------------------------------------------- men


def test_br_man_moves_one_square_diagonally_forward_only() -> None:
    assert moves(pos("d4")) == {"d4-c5", "d4-e5"}
    assert moves(pos("", "d4", side="B")) == {"d4-c3", "d4-e3"}


def test_br_man_captures_backward() -> None:
    """A white man on d4 captures the black man on c3 behind it, landing on b2."""
    assert moves(pos("d4", "c3")) == {"d4xb2"}


def test_br_man_capture_is_short_range() -> None:
    """A man only jumps an adjacent piece: e5 is two squares away from c3, so no capture."""
    assert moves(pos("c3", "e5")) == {"c3-b4", "c3-d4"}


def test_br_two_adjacent_pieces_cannot_be_jumped_and_no_moves_means_loss() -> None:
    p = pos("a1", "b2 c3")
    assert legal_moves(p) == ()


# ---------------------------------------------------------------- mandatory capture & majority


def test_br_capture_is_mandatory() -> None:
    """d4 could move quietly to c5, but capturing e5 is compulsory."""
    assert moves(pos("d4 a1", "e5")) == {"d4xf6"}


def test_br_majority_rule_must_take_the_most_pieces() -> None:
    """h2xf4 takes 1 (g3), c3xe5xg7 takes 2: only the 2-piece capture is legal."""
    assert moves(pos("c3 h2", "d4 f6 g3")) == {"c3xe5xg7"}
    # Without the 2-piece route, the 1-piece capture is legal (sanity check of the setup).
    assert moves(pos("c3 h2", "g3")) == {"h2xf4"}


def test_br_majority_backward_continuation_counts() -> None:
    """a3xc5 continues backward c5xe3 (taking d4): 2 pieces, so it ties with c3xe5xg7."""
    assert moves(pos("c3 a3", "d4 f6 b4")) == {"a3xc5xe3", "c3xe5xg7"}


def test_br_majority_counts_kings_and_men_equally_king_does_not_outweigh() -> None:
    """e1xg3 takes a king (1 piece) and c3xe5xg7 takes two men: the two men must be taken."""
    assert moves(pos("c3 e1", "d4 f6 Kf2")) == {"c3xe5xg7"}


def test_br_majority_ties_between_king_and_men_routes_are_all_legal() -> None:
    """Route 1 takes d4 + king f6, route 2 takes b4 + b6: both take 2, both legal."""
    p = pos("c3", "d4 Kf6 b4 b6")
    assert moves(p) == {"c3xe5xg7", "c3xa5xc7"}
    assert captured(p, "c3xe5xg7") == {"d4", "f6"}


def test_br_multi_capture_must_be_completed() -> None:
    """Stopping after the first jump (c3xe5) is not a legal move."""
    p = pos("c3", "d4 f6")
    assert moves(p) == {"c3xe5xg7"}


# ---------------------------------------------------------------- capture mechanics


def test_br_turkish_rule_captured_pieces_block_until_the_move_ends() -> None:
    """King f4; black d6, e5, g5, d2.

    f4xh6 (taking g5) could continue h6-g5-f4-e3 to take d2 *only if* g5 had already been
    removed. Under the Turkish rule it is still on the board and blocks, so the maximum
    capture is 1 piece and both single captures are legal. e5/d6 stand together and cannot
    be jumped.
    """
    assert moves(pos("Kf4", "d6 e5 g5 d2")) == {"f4xh6", "f4xc1"}


def test_br_piece_cannot_be_jumped_twice_but_empty_squares_may_be_revisited() -> None:
    """A king loop around four men returns to its own origin square (10x10 example)."""
    from damas_ai.rules import BOARD_10X10
    from damas_ai.rules.notation import format_move, from_fen

    p = from_fen(BOARD_10X10, "W:WK2:B7,8,17,18")
    result = [format_move(p.geometry, m) for m in legal_moves(p)]
    # Two visiting orders exist (2x13x22x11x2 and 2x11x22x13x2); they are one move.
    assert len(result) == 1 and result[0].startswith("2x") and result[0].endswith("x2")
    assert len(legal_moves(p)[0].captured) == 4


# ---------------------------------------------------------------- kings


def test_br_king_is_flying_and_blocked_by_pieces() -> None:
    p = pos("Kd4 f6")
    assert moves(p) >= {"d4-e5", "d4-a1", "d4-a7", "d4-g1", "d4-c5"}
    assert "d4-g7" not in moves(p)  # own man on f6 blocks the diagonal


def test_br_king_captures_at_distance_and_may_land_on_any_empty_square_beyond() -> None:
    assert moves(pos("Ka1", "c3")) == {"a1xd4", "a1xe5", "a1xf6", "a1xg7", "a1xh8"}


def test_br_king_landing_is_restricted_when_one_landing_allows_more_captures() -> None:
    """Ka1 x d4 must land on e5, the only square from which d6 can be taken (majority)."""
    p = pos("Ka1", "d4 d6")
    assert moves(p) == {"a1xe5xc7", "a1xe5xb8"}


# ---------------------------------------------------------------- promotion


def test_br_man_promotes_when_it_ends_the_move_on_the_last_rank() -> None:
    """b6xd8 ends on rank 8. Another capture (f6) would be possible for a king but not for a
    man, so the move ends and the man promotes."""
    p = pos("b6", "c7 f6")
    assert moves(p) == {"b6xd8"}
    assert promotes(p, "b6xd8")
    after = apply_move(p, legal_moves(p)[0])
    assert after.squares[after.geometry.index(3, 7)] == Piece.WHITE_KING
    assert after.side_to_move is Color.BLACK  # the new king moves only on a later turn


def test_br_man_passing_through_the_last_rank_mid_capture_does_not_promote() -> None:
    """b6xd8 reaches rank 8, but the man must continue (d8xf6, a backward capture) and
    finishes as a man."""
    p = pos("b6", "c7 e7")
    assert moves(p) == {"b6xd8xf6"}
    assert not promotes(p, "b6xd8xf6")


def test_br_quiet_move_to_last_rank_promotes() -> None:
    p = pos("c7")
    assert moves(p) == {"c7-b8", "c7-d8"}
    assert promotes(p, "c7-d8")
    assert not promotes(pos("c5"), "c5-d6")
