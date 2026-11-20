"""64-bit Zobrist keys. The table is a pure function of (geometry id, ZOBRIST_VERSION).

Changing ZOBRIST_VERSION invalidates every stored key (knowledge base, G11).
"""

from __future__ import annotations

import random
from functools import cache

from damas_ai.rules.geometry import Geometry
from damas_ai.rules.moves import Move
from damas_ai.rules.position import PROMOTED, Color, Position

ZOBRIST_VERSION = 1


@cache
def _table(geometry_id: str, num_squares: int) -> tuple[tuple[int, ...], ...]:
    rng = random.Random(f"damas-ai-zobrist-v{ZOBRIST_VERSION}-{geometry_id}")
    # index 0 (EMPTY) is always 0 so empty squares contribute nothing
    return tuple((0, *(rng.getrandbits(64) for _ in range(4))) for _ in range(num_squares + 1))


def _keys(geometry: Geometry) -> tuple[tuple[int, ...], ...]:
    return _table(geometry.id, geometry.num_squares)


def zobrist_key(position: Position) -> int:
    table = _keys(position.geometry)
    key = 0
    for sq, piece in enumerate(position.squares):
        if piece:
            key ^= table[sq][piece]
    if position.side_to_move is Color.BLACK:
        key ^= table[-1][1]
    return key


def key_after(key: int, position: Position, move: Move) -> int:
    """Incremental update of ``key`` (of ``position``) for ``move``."""
    table = _keys(position.geometry)
    piece = position.squares[move.origin]
    new_piece = PROMOTED[piece] if move.promotes else piece
    key ^= table[move.origin][piece] ^ table[move.destination][new_piece]
    for sq in move.captured:
        key ^= table[sq][position.squares[sq]]
    return key ^ table[-1][1]  # side to move always flips
