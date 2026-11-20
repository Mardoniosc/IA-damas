"""Move value type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    """A complete move (one player's turn).

    - ``path``: landing squares in order; the last one is the destination. A quiet move has a
      single entry. A capture has one landing square per captured piece.
    - ``captured``: captured squares **in capture order** (``len(captured) == len(path)`` for
      captures, empty for quiet moves).
    - ``promotes``: the moving man ends on its promotion rank.
    """

    origin: int
    path: tuple[int, ...]
    captured: tuple[int, ...] = ()
    promotes: bool = False

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("a move needs at least one landing square")
        if self.captured and len(self.captured) != len(self.path):
            raise ValueError("a capture needs one landing square per captured piece")

    @property
    def destination(self) -> int:
        return self.path[-1]

    @property
    def is_capture(self) -> bool:
        return bool(self.captured)

    @property
    def identity(self) -> tuple[int, int, frozenset[int]]:
        """Outcome identity: moves with equal identity leave identical positions.

        Capture routes that differ only in visiting order (same origin, destination and set of
        captured pieces) are the same move. This convention is the one used by Hub notation
        and by the py-draughts oracle.
        """
        return (self.origin, self.destination, frozenset(self.captured))
