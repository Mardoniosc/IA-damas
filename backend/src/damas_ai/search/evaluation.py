"""Baseline static evaluation (G8). UNTUNED HEURISTIC, in hundredths of a man, from the side to
move's point of view.

Terms (deliberately few, so the baseline is easy to audit and to beat in G14):
- material: man = 100, king = 300 (a common rule-of-thumb weight for flying-king variants;
  not measured)
- advancement: +4 per row a man has advanced from its own back row (encourages promotion)

Nothing here is claimed to be correct or strong. It is a reference point for the learning
system.
"""

from __future__ import annotations

from damas_ai.rules import Color, Position
from damas_ai.rules.position import Piece

MAN, KING, ADVANCE = 100, 300, 4


def evaluate(position: Position) -> int:
    size = position.geometry.size
    coords = position.geometry.coords
    score = 0  # from White's point of view
    for sq, piece in enumerate(position.squares):
        if piece == Piece.EMPTY:
            continue
        rank = coords[sq][1]
        if piece == Piece.WHITE_MAN:
            score += MAN + ADVANCE * rank
        elif piece == Piece.BLACK_MAN:
            score -= MAN + ADVANCE * (size - 1 - rank)
        elif piece == Piece.WHITE_KING:
            score += KING
        else:
            score -= KING
    return score if position.side_to_move is Color.WHITE else -score
