"""One benchmark game with the Rules Core as arbiter (G12, ADR-014)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from damas_ai.bench.players import Player
from damas_ai.rules import Color, GameState, IllegalMoveError, Move, Outcome, Position, Ruleset
from damas_ai.rules.notation import format_move, to_fen


@dataclass
class GameRecord:
    white: str
    black: str
    variant: str
    ruleset_id: str
    start_fen: str
    moves: list[str] = field(default_factory=list)          # numeric notation
    move_infos: list[dict[str, Any]] = field(default_factory=list)
    result: str = "*"                                         # "1-0" | "0-1" | "1/2-1/2"
    reason: str = ""
    plies: int = 0
    duration_s: float = 0.0
    opening_id: str = ""

    def score_for(self, name: str) -> float:
        """1 / 0.5 / 0 for the named player (by name, either colour)."""
        if self.result == "1/2-1/2":
            return 0.5
        white_won = self.result == "1-0"
        if name == self.white:
            return 1.0 if white_won else 0.0
        return 0.0 if white_won else 1.0


def play_game(white: Player, black: Player, ruleset: Ruleset, start: Position,
              max_plies: int = 300, opening_id: str = "") -> GameRecord:
    """Play until the Rules Core declares a result, a player fails, or ``max_plies`` (draw by
    adjudication). A failure (illegal move, timeout, crash) loses the game for that player."""
    root = GameState.new(ruleset, start)
    state = root
    history: tuple[Move, ...] = ()
    rec = GameRecord(white.name, black.name, ruleset.variant, ruleset.id, to_fen(start), opening_id=opening_id)
    white.new_game()
    black.new_game()
    t0 = time.perf_counter()
    while True:
        result = state.result()
        if result.outcome is not Outcome.ONGOING:
            rec.result, rec.reason = result.outcome.value, result.reason
            break
        if state.ply >= max_plies:
            rec.result, rec.reason = "1/2-1/2", f"adjudicated: move cap of {max_plies} plies"
            break
        mover = white if state.position.side_to_move is Color.WHITE else black
        choice = mover.choose(state, root, history)
        if choice.move is None:
            rec.result = "0-1" if mover is white else "1-0"
            rec.reason = f"forfeit by {mover.name}: {choice.failure}"
            rec.move_infos.append({"player": mover.name, **choice.info})
            break
        try:
            next_state = state.play(choice.move)
        except IllegalMoveError as exc:  # defence in depth: adapters already validate
            rec.result = "0-1" if mover is white else "1-0"
            rec.reason = f"illegal move by {mover.name}: {exc}"
            break
        rec.moves.append(format_move(start.geometry, choice.move))
        rec.move_infos.append({"player": mover.name, **choice.info})
        history = (*history, choice.move)
        state = next_state
    rec.plies = state.ply
    rec.duration_s = round(time.perf_counter() - t0, 3)
    return rec
