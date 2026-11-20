"""Rules Core (G2): the platform's sole legal-move authority (ADR-001).

Standard library only. No I/O, no engine code.
"""

from damas_ai.rules.game import GameResult, GameState, IllegalMoveError, Outcome
from damas_ai.rules.geometry import BOARD_8X8, BOARD_10X10, Geometry
from damas_ai.rules.movegen import apply_move, legal_moves
from damas_ai.rules.moves import Move
from damas_ai.rules.position import Color, Piece, Position
from damas_ai.rules.resolve import (
    EngineMoveAmbiguous,
    EngineMoveError,
    EngineMoveNotLegal,
    resolve_engine_move,
)
from damas_ai.rules.rulesets import (
    BRAZILIAN_PROVISIONAL,
    INTERNATIONAL_PROVISIONAL,
    RULESETS,
    EndgameDrawRule,
    Ruleset,
)
from damas_ai.rules.zobrist import ZOBRIST_VERSION, zobrist_key

__all__ = [
    "BOARD_8X8", "BOARD_10X10", "BRAZILIAN_PROVISIONAL", "INTERNATIONAL_PROVISIONAL", "RULESETS",
    "ZOBRIST_VERSION", "Color", "EndgameDrawRule", "EngineMoveAmbiguous", "EngineMoveError",
    "EngineMoveNotLegal", "GameResult", "GameState", "Geometry", "IllegalMoveError", "Move",
    "Outcome", "Piece", "Position", "Ruleset", "apply_move", "legal_moves", "resolve_engine_move",
    "zobrist_key",
]
