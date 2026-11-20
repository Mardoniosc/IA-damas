"""Game state, checked move application, termination and draw detection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from damas_ai.rules.movegen import apply_move, legal_moves
from damas_ai.rules.moves import Move
from damas_ai.rules.position import Color, Piece, Position
from damas_ai.rules.rulesets import Ruleset
from damas_ai.rules.zobrist import key_after, zobrist_key


class Outcome(Enum):
    ONGOING = "ongoing"
    WHITE_WINS = "1-0"
    BLACK_WINS = "0-1"
    DRAW = "1/2-1/2"


@dataclass(frozen=True)
class GameResult:
    outcome: Outcome
    reason: str = ""


class IllegalMoveError(ValueError):
    pass


@dataclass(frozen=True)
class GameState:
    """Immutable game state.

    - ``keys_since_irreversible``: Zobrist keys of every position since the last capture or man
      move, current position included (repetition can only occur inside this window).
    - ``king_only_plies``: consecutive plies of non-capturing king moves.
    - ``endgame_plies``: plies since the current material signature appeared (meaningful only
      when an ``EndgameDrawRule`` matches).
    """

    ruleset: Ruleset
    position: Position
    key: int
    keys_since_irreversible: tuple[int, ...]
    king_only_plies: int = 0
    endgame_plies: int = 0
    ply: int = 0

    @classmethod
    def new(cls, ruleset: Ruleset, position: Position | None = None) -> GameState:
        pos = position if position is not None else ruleset.initial_position()
        if pos.geometry.id != ruleset.geometry.id:
            raise ValueError("position geometry does not match the ruleset")
        key = zobrist_key(pos)
        return cls(ruleset, pos, key, (key,))

    def legal_moves(self) -> tuple[Move, ...]:
        return legal_moves(self.position)

    def play(self, move: Move) -> GameState:
        """Apply a move after checking it is legal (compared by ``Move.identity``)."""
        legal = {m.identity: m for m in self.legal_moves()}
        canonical = legal.get(move.identity)
        if canonical is None:
            raise IllegalMoveError(f"illegal move {move} in {self.position.to_dsa()}")
        return self._advance(canonical)

    def _advance(self, move: Move) -> GameState:
        pos = self.position
        moved = pos.squares[move.origin]
        irreversible = move.is_capture or moved in (Piece.WHITE_MAN, Piece.BLACK_MAN)
        new_pos = apply_move(pos, move)
        new_key = key_after(self.key, pos, move)
        keys = (new_key,) if irreversible else (*self.keys_since_irreversible, new_key)
        endgame_plies = (self.endgame_plies + 1
                         if new_pos.material() == pos.material() else 0)
        return replace(
            self,
            position=new_pos,
            key=new_key,
            keys_since_irreversible=keys,
            king_only_plies=0 if irreversible else self.king_only_plies + 1,
            endgame_plies=endgame_plies,
            ply=self.ply + 1,
        )

    def result(self) -> GameResult:
        """Loss by no legal moves takes precedence over every draw rule."""
        if not self.legal_moves():
            winner = self.position.side_to_move.opponent
            outcome = Outcome.WHITE_WINS if winner is Color.WHITE else Outcome.BLACK_WINS
            return GameResult(outcome, "no legal moves")
        rs = self.ruleset
        if rs.repetition_count and self.keys_since_irreversible.count(self.key) >= rs.repetition_count:
            return GameResult(Outcome.DRAW, f"{rs.repetition_count}-fold repetition")
        if rs.king_only_limit_plies is not None and self.king_only_plies >= rs.king_only_limit_plies:
            return GameResult(Outcome.DRAW, f"{rs.king_only_limit_plies} plies of king-only moves")
        material = self.position.material()
        for rule in rs.endgame_rules:
            if rule.matches(material) and self.endgame_plies >= rule.limit_plies:
                return GameResult(Outcome.DRAW, f"endgame rule: {rule.name}")
        return GameResult(Outcome.ONGOING)
