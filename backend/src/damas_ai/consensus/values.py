"""Engine values as an *intra-engine* total order (ADR-009).

A ``RawScore`` becomes a utility for the side that just moved, in that engine's own units:

- heuristic eval ``v``            -> ``v``
- proven win at distance ``d``    -> ``+(WIN - d)``
- proven loss at distance ``d``   -> ``-(WIN - d)``

Utilities from different engines are never compared numerically. Only their *outcome
classes* (win / loss / eval) are compared across engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from damas_ai.engines import RawScore

WIN = 10_000.0  # far above any heuristic eval of either engine (Scan clamps at 80)


class OutcomeClass(Enum):
    WIN = "win"
    LOSS = "loss"
    EVAL = "eval"       # not proven either way
    UNKNOWN = "unknown"  # no usable score (missing, unparseable, unknown perspective)


@dataclass(frozen=True)
class MoveValue:
    """Value of a move for the side that plays it, as judged by one engine."""

    utility: float | None
    outcome: OutcomeClass
    raw: str | None          # score text as reported (from the side to move after the move)
    distance_plies: int | None = None
    source: str = "search"   # "search" | "terminal" (the move ends the game)


def value_after_move(score: RawScore | None) -> MoveValue:
    """Convert the engine's score of the position *after* a move (reported from the opponent's
    side, i.e. the side to move then) into the mover's value."""
    if score is None or score.value is None or score.perspective != "side_to_move":
        return MoveValue(None, OutcomeClass.UNKNOWN, score.text if score else None)
    opp = score.value
    if score.kind in ("end_band", "win_band"):
        d = score.distance_plies or 0
        if opp > 0:   # opponent wins -> mover loses
            return MoveValue(-(WIN - d), OutcomeClass.LOSS, score.text, d)
        return MoveValue(WIN - d, OutcomeClass.WIN, score.text, d)
    return MoveValue(-opp, OutcomeClass.EVAL, score.text)


def terminal_win() -> MoveValue:
    """The move leaves the opponent without legal moves: an immediate win."""
    return MoveValue(WIN - 1, OutcomeClass.WIN, None, 1, "terminal")


def root_value(score: RawScore | None) -> MoveValue:
    """Value of the root position for the side to move (no negation)."""
    if score is None or score.value is None or score.perspective != "side_to_move":
        return MoveValue(None, OutcomeClass.UNKNOWN, score.text if score else None)
    if score.kind in ("end_band", "win_band"):
        d = score.distance_plies or 0
        if score.value > 0:
            return MoveValue(WIN - d, OutcomeClass.WIN, score.text, d)
        return MoveValue(-(WIN - d), OutcomeClass.LOSS, score.text, d)
    return MoveValue(score.value, OutcomeClass.EVAL, score.text)


def root_outcome(score: RawScore | None) -> OutcomeClass:
    """Outcome class of an engine's root score (side to move's perspective)."""
    return root_value(score).outcome


def contradicts(a: MoveValue, b: MoveValue) -> bool:
    """True if two engines' judgements of the same thing point in opposite directions:
    win vs loss, or a proven result vs an eval that does not favour the same side."""
    pair = {a.outcome, b.outcome}
    if OutcomeClass.UNKNOWN in pair:
        return False
    if pair == {OutcomeClass.WIN, OutcomeClass.LOSS}:
        return True
    for x, y in ((a, b), (b, a)):
        if x.outcome is OutcomeClass.WIN and y.outcome is OutcomeClass.EVAL:
            return y.utility is None or y.utility <= 0
        if x.outcome is OutcomeClass.LOSS and y.outcome is OutcomeClass.EVAL:
            return y.utility is None or y.utility >= 0
    return False


def proof_gap(a: MoveValue, b: MoveValue) -> bool:
    """True if one engine proves a result and the other only evaluates it, in the same direction."""
    decisive = {OutcomeClass.WIN, OutcomeClass.LOSS}
    return ({a.outcome, b.outcome} & decisive != set()
            and OutcomeClass.EVAL in {a.outcome, b.outcome}
            and not contradicts(a, b))
