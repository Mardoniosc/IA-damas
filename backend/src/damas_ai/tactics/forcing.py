"""Forcing analysis: threats and shots (combinations) (G9, ADR-011).

A *shot* is a line in which the side to move (S) wins material while every opponent move is a
**forced capture** (capture is mandatory in draughts, so a sacrifice can force the opponent's
reply). The line ends as soon as the opponent is not obliged to capture, and material is then
counted. S may also stop at any node where S itself is not obliged to capture ("stand pat").

This is a deliberately narrow, explainable detector, *not* a full search. It finds forced
material gains up to a bounded number of S's quiet (non-capturing) moves. Its claims are
checked against Scan/Kingsrow in the G9 report.
"""

from __future__ import annotations

from dataclasses import dataclass

from damas_ai.rules import Color, Move, Position, apply_move, legal_moves
from damas_ai.rules.position import Piece

MAN, KING = 100, 300
LOSS = -100_000


def material(position: Position, side: Color) -> int:
    """Material balance for ``side`` in hundredths of a man (man 100, king 300)."""
    s = 0
    for piece in position.squares:
        if piece == Piece.EMPTY:
            continue
        value = KING if piece in (Piece.WHITE_KING, Piece.BLACK_KING) else MAN
        s += value if piece.color is side else -value
    return s


@dataclass(frozen=True)
class Threat:
    """Captures the opponent could make if it were their move."""

    max_pieces: int
    squares: frozenset[int]  # S's pieces that some opponent capture takes
    moves: tuple[Move, ...]


def threats_against(position: Position) -> Threat:
    """Threats against the side to move (a 'null move' view: the opponent moves instead)."""
    flipped = position.with_side(position.side_to_move.opponent)
    moves = legal_moves(flipped)
    caps = tuple(m for m in moves if m.is_capture)
    squares = frozenset(sq for m in caps for sq in m.captured)
    return Threat(max((len(m.captured) for m in caps), default=0), squares, caps)


@dataclass(frozen=True)
class Shot:
    first_move: Move
    line: tuple[Move, ...]       # forcing line as found (S, forced reply, S, ...)
    gain: int                    # material gained by S along the line, hundredths of a man
    sacrifice: bool              # first move is quiet and the opponent must capture next
    s_quiet_moves: int


class _Forcing:
    def __init__(self, side: Color, max_quiet: int, max_plies: int) -> None:
        self.side = side
        self.max_quiet = max_quiet
        self.max_plies = max_plies
        self.nodes = 0

    def value(self, pos: Position, quiet_left: int, plies_left: int,
              alpha: int, beta: int) -> tuple[int, tuple[Move, ...]]:
        self.nodes += 1
        moves = legal_moves(pos)
        if not moves:
            return (LOSS if pos.side_to_move is self.side else -LOSS), ()
        static = material(pos, self.side)
        if plies_left == 0:
            return static, ()
        forced_capture = moves[0].is_capture
        if pos.side_to_move is self.side:
            best, best_line = (static, ()) if not forced_capture else (LOSS - 1, ())
            for m in moves:
                if not m.is_capture:
                    if quiet_left == 0:
                        continue
                    after = apply_move(pos, m)
                    # A quiet move only belongs in a forcing line if the opponent must capture.
                    reply = legal_moves(after)
                    if not reply or not reply[0].is_capture:
                        continue
                    v, line = self.value(after, quiet_left - 1, plies_left - 1, max(alpha, best), beta)
                else:
                    v, line = self.value(apply_move(pos, m), quiet_left, plies_left - 1,
                                         max(alpha, best), beta)
                if v > best:
                    best, best_line = v, (m, *line)
                if best >= beta:
                    break
            if best == LOSS - 1:  # forced to capture but no line evaluated (cannot happen)
                best = static
            return best, best_line
        # Opponent: forcing only while it must capture.
        if not forced_capture:
            return static, ()
        worst, worst_line = -LOSS + 1, ()
        for m in moves:
            v, line = self.value(apply_move(pos, m), quiet_left, plies_left - 1, alpha, min(beta, worst))
            if v < worst:
                worst, worst_line = v, (m, *line)
            if worst <= alpha:
                break
        return worst, worst_line


def find_shots(position: Position, max_quiet: int = 2, max_plies: int = 14,
               min_gain: int = MAN) -> tuple[Shot, ...]:
    """All first moves of S that start a forcing line gaining at least ``min_gain``."""
    side = position.side_to_move
    base = material(position, side)
    engine = _Forcing(side, max_quiet, max_plies)
    shots: list[Shot] = []
    for m in legal_moves(position):
        after = apply_move(position, m)
        reply = legal_moves(after)
        if not m.is_capture and (not reply or not reply[0].is_capture):
            continue  # a quiet first move that forces nothing is not a shot
        quiet_left = max_quiet - (0 if m.is_capture else 1)
        v, line = engine.value(after, quiet_left, max_plies - 1, LOSS, -LOSS)
        gain = v - base
        if gain >= min_gain:
            sacrifice = not m.is_capture and bool(reply) and reply[0].is_capture
            quiet = sum(1 for i, x in enumerate((m, *line)) if i % 2 == 0 and not x.is_capture)
            shots.append(Shot(m, (m, *line), gain, sacrifice, quiet))
    shots.sort(key=lambda s: (-s.gain, s.s_quiet_moves))
    return tuple(shots)
