"""Perft (move-path enumeration) for validating move generation."""

from __future__ import annotations

from damas_ai.rules.movegen import apply_move, legal_moves
from damas_ai.rules.position import Position


def perft(position: Position, depth: int) -> int:
    """Number of leaf nodes at ``depth`` plies (moves counted by ``Move.identity``)."""
    if depth <= 0:
        return 1
    moves = legal_moves(position)
    if depth == 1:
        return len(moves)
    return sum(perft(apply_move(position, m), depth - 1) for m in moves)


def divide(position: Position, depth: int) -> dict[int, int]:
    """Perft split by root move index (debugging aid)."""
    return {i: perft(apply_move(position, m), depth - 1)
            for i, m in enumerate(legal_moves(position))}
