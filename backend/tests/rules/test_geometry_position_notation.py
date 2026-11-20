from __future__ import annotations

import pytest
from helpers import pos

from damas_ai.rules import BOARD_8X8, BOARD_10X10, BRAZILIAN_PROVISIONAL, Color, Piece, Position
from damas_ai.rules.geometry import NE, SW
from damas_ai.rules.notation import (
    AmbiguousMoveError,
    NotationError,
    format_move,
    from_algebraic,
    from_fen,
    from_numeric,
    parse_move,
    to_algebraic,
    to_fen,
    to_numeric,
)

# ---------------------------------------------------------------- geometry (ADR-003)


def test_canonical_index_formula_and_corners() -> None:
    g = BOARD_8X8
    assert g.num_squares == 32
    assert from_algebraic(g, "a1") == 0 and from_algebraic(g, "g1") == 3
    assert from_algebraic(g, "b2") == 4 and from_algebraic(g, "h8") == 31
    for sq, (f, r) in enumerate(g.coords):
        assert (f + r) % 2 == 0 and sq == 4 * r + f // 2


def test_light_squares_are_rejected() -> None:
    with pytest.raises(NotationError):
        from_algebraic(BOARD_8X8, "b1")


def test_rays_follow_diagonals() -> None:
    g = BOARD_8X8
    assert [to_algebraic(g, s) for s in g.rays[0][NE]] == ["b2", "c3", "d4", "e5", "f6", "g7", "h8"]
    assert g.rays[0][SW] == ()


@pytest.mark.parametrize("geometry", [BOARD_8X8, BOARD_10X10])
def test_rotate180_maps_i_to_n_minus_1_minus_i(geometry) -> None:  # type: ignore[no-untyped-def]
    n, size = geometry.num_squares, geometry.size
    for sq, (f, r) in enumerate(geometry.coords):
        assert geometry.index(size - 1 - f, size - 1 - r) == geometry.rotate180(sq) == n - 1 - sq


# ---------------------------------------------------------------- position


def test_dsa_round_trip_and_validation() -> None:
    p = BRAZILIAN_PROVISIONAL.initial_position()
    assert Position.from_dsa(BOARD_8X8, p.to_dsa()) == p
    with pytest.raises(ValueError):
        Position.from_dsa(BOARD_8X8, "W" + "e" * 31)
    with pytest.raises(ValueError):
        Position.from_dsa(BOARD_8X8, "X" + "e" * 32)


def test_unpromoted_man_on_promotion_rank_is_rejected() -> None:
    with pytest.raises(ValueError):
        pos("b8")
    with pytest.raises(ValueError):
        pos("", "a1")


def test_flip_is_an_involution_and_swaps_side() -> None:
    p = pos("c3 Kd4", "e7", side="B")
    f = p.flipped()
    assert f.side_to_move is Color.WHITE
    assert f.squares[BOARD_8X8.rotate180(from_algebraic(BOARD_8X8, "c3"))] == Piece.BLACK_MAN
    assert f.flipped() == p


# ---------------------------------------------------------------- numeric / PDN (provisional numbering)


def test_numeric_numbering_8x8_provisional_convention() -> None:
    """Square 1 = b8, 4 = h8, 29 = a1, 32 = g1 (en.wikipedia + py-draughts agree; UNVERIFIED vs CBJD)."""
    g = BOARD_8X8
    assert to_numeric(g, from_algebraic(g, "b8")) == 1
    assert to_numeric(g, from_algebraic(g, "h8")) == 4
    assert to_numeric(g, from_algebraic(g, "a1")) == 29
    assert to_numeric(g, from_algebraic(g, "g1")) == 32
    assert all(from_numeric(g, to_numeric(g, s)) == s for s in range(32))


def test_numeric_numbering_10x10_is_standard_international() -> None:
    g = BOARD_10X10
    assert to_numeric(g, from_algebraic(g, "a1")) == 46
    assert to_numeric(g, from_algebraic(g, "j10")) == 5
    assert all(from_numeric(g, to_numeric(g, s)) == s for s in range(50))


def test_fen_round_trip_with_kings_and_ranges() -> None:
    start = BRAZILIAN_PROVISIONAL.initial_position()
    assert to_fen(start) == "W:W21,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,11,12"
    assert from_fen(BOARD_8X8, "W:W21-32:B1-12") == start
    p = from_fen(BOARD_8X8, '[FEN "B:WK29,22:BK1,10"]')
    assert p.side_to_move is Color.BLACK and p.material() == (1, 1, 1, 1)
    assert from_fen(BOARD_8X8, to_fen(p)) == p
    with pytest.raises(NotationError):
        from_fen(BOARD_8X8, "W:W1,1:B")


def test_parse_and_format_moves() -> None:
    p = BRAZILIAN_PROVISIONAL.initial_position()
    m = parse_move(p, "22-18")
    assert format_move(p.geometry, m, "algebraic") == "c3-d4"
    assert parse_move(p, "c3-d4") == m
    with pytest.raises(NotationError):
        parse_move(p, "22-15")


def test_parse_short_capture_ambiguity_is_reported() -> None:
    """Ka1 x c3 can land on d4..h8; 'a1xh8' is unique. Kc5 has two 3-piece routes ending on
    d8 that capture different pieces (f4 vs g3), so the short form needs the full path."""
    p = pos("Ka1", "c3")
    assert format_move(p.geometry, parse_move(p, "a1xh8"), "algebraic") == "a1xh8"
    q = pos("Kc5", "a3 d4 e7 f4 g3")
    with pytest.raises(AmbiguousMoveError):
        parse_move(q, "c5xd8")
    assert parse_move(q, "c5xe3xg5xd8").captured != parse_move(q, "c5xf2xh4xd8").captured
