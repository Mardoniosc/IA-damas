"""Resolve an engine-reported move against the legal-move list (ADR-001).

Engines report moves in lossy forms. Hub, for example, gives origin, destination and the set of
captured squares, with no pivots and no order. The Rules Core decides which legal move, if any,
the report denotes. Engine-specific *syntax* is parsed by adapters (G3); this module works on
canonical squares.
"""

from __future__ import annotations

from collections.abc import Iterable

from damas_ai.rules.movegen import legal_moves
from damas_ai.rules.moves import Move
from damas_ai.rules.position import Position


class EngineMoveError(ValueError):
    """Base class: the engine's report does not denote exactly one legal move."""


class EngineMoveNotLegal(EngineMoveError):
    pass


class EngineMoveAmbiguous(EngineMoveError):
    def __init__(self, message: str, candidates: tuple[Move, ...]) -> None:
        super().__init__(message)
        self.candidates = candidates


def resolve_engine_move(
    position: Position,
    origin: int,
    destination: int,
    captured: Iterable[int] | None = None,
) -> Move:
    """Return the unique legal move matching the report, or raise an EngineMoveError.

    ``captured=None`` means the engine did not say what it captured. An empty iterable means
    it explicitly reported a non-capture.
    """
    captured_set = None if captured is None else frozenset(captured)
    candidates = tuple(
        m for m in legal_moves(position)
        if m.origin == origin and m.destination == destination
        and (captured_set is None or frozenset(m.captured) == captured_set)
    )
    if not candidates:
        raise EngineMoveNotLegal(
            f"no legal move {origin}->{destination} captured={sorted(captured_set or [])} "
            f"in {position.to_dsa()}"
        )
    if len(candidates) > 1:
        raise EngineMoveAmbiguous(
            f"{len(candidates)} legal moves match {origin}->{destination}; captured set needed",
            candidates,
        )
    return candidates[0]
