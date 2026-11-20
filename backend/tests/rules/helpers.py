"""Test helpers: build positions and describe moves in algebraic notation."""

from __future__ import annotations

from damas_ai.rules import BOARD_8X8, Color, Geometry, Piece, Position, legal_moves
from damas_ai.rules.notation import format_move, from_algebraic, to_algebraic


def pos(white: str = "", black: str = "", side: str = "W", geometry: Geometry = BOARD_8X8) -> Position:
    """``pos("c3 Kd4", "e5")``: K prefix = king. Squares in algebraic notation."""
    pieces: dict[int, Piece] = {}
    for token in white.split():
        king = token.startswith("K")
        pieces[from_algebraic(geometry, token.lstrip("K"))] = Piece.WHITE_KING if king else Piece.WHITE_MAN
    for token in black.split():
        king = token.startswith("K")
        pieces[from_algebraic(geometry, token.lstrip("K"))] = Piece.BLACK_KING if king else Piece.BLACK_MAN
    return Position.from_pieces(geometry, pieces, Color(side))


def moves(position: Position) -> set[str]:
    """Legal moves as algebraic strings (``c3-d4``, ``c3xe5xg7``)."""
    return {format_move(position.geometry, m, "algebraic") for m in legal_moves(position)}


def captured(position: Position, move_text: str) -> set[str]:
    for m in legal_moves(position):
        if format_move(position.geometry, m, "algebraic") == move_text:
            return {to_algebraic(position.geometry, s) for s in m.captured}
    raise AssertionError(f"{move_text} not legal")


def promotes(position: Position, move_text: str) -> bool:
    for m in legal_moves(position):
        if format_move(position.geometry, m, "algebraic") == move_text:
            return m.promotes
    raise AssertionError(f"{move_text} not legal")
