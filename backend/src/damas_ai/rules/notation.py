"""Human/interchange notations. They are converters only; the canonical index stays internal.

Numeric (PDN) numbering, provisional for Brazilian (G1 Q2/R14): square 1 is the leftmost
playable square of the top row as seen by White, numbering runs left to right and top to
bottom, so a1 = 29 on 8x8 and a1 = 46 on 10x10. Sources: en.wikipedia "Brazilian draughts"
[S] and the py-draughts board layout, which agree. The 10x10 form is the standard
International numbering used by Hub/Scan.
"""

from __future__ import annotations

import re

from damas_ai.rules.geometry import FILES, Geometry
from damas_ai.rules.movegen import legal_moves
from damas_ai.rules.moves import Move
from damas_ai.rules.position import Color, Piece, Position


class NotationError(ValueError):
    pass


class AmbiguousMoveError(NotationError):
    pass


# --------------------------------------------------------------------------- squares


def to_numeric(geometry: Geometry, sq: int) -> int:
    file, rank = geometry.coords[sq]
    return (geometry.size - 1 - rank) * (geometry.size // 2) + file // 2 + 1


def from_numeric(geometry: Geometry, number: int) -> int:
    half = geometry.size // 2
    if not 1 <= number <= geometry.num_squares:
        raise NotationError(f"square {number} out of range 1..{geometry.num_squares}")
    row_from_top, col = divmod(number - 1, half)
    rank = geometry.size - 1 - row_from_top
    file = 2 * col + (rank % 2)
    return geometry.index(file, rank)


def to_algebraic(geometry: Geometry, sq: int) -> str:
    file, rank = geometry.coords[sq]
    return f"{FILES[file]}{rank + 1}"


def from_algebraic(geometry: Geometry, name: str) -> int:
    m = re.fullmatch(r"([a-z])(\d{1,2})", name.strip().lower())
    if not m:
        raise NotationError(f"bad algebraic square {name!r}")
    try:
        return geometry.index(FILES.index(m.group(1)), int(m.group(2)) - 1)
    except ValueError as exc:
        raise NotationError(str(exc)) from exc


# --------------------------------------------------------------------------- moves


def format_move(geometry: Geometry, move: Move, style: str = "numeric") -> str:
    """Quiet: ``origin-destination``. Capture: origin then every landing square, joined by x."""
    conv = (lambda s: str(to_numeric(geometry, s))) if style == "numeric" else \
        (lambda s: to_algebraic(geometry, s))
    if not move.is_capture:
        return f"{conv(move.origin)}-{conv(move.destination)}"
    return "x".join(conv(s) for s in (move.origin, *move.path))


def parse_move(position: Position, text: str) -> Move:
    """Parse numeric or algebraic notation and resolve it against the legal moves.

    ``a-b`` or ``axb`` give origin and destination. A longer ``axbxc...`` gives the full
    landing path. A short form that matches several legal moves raises AmbiguousMoveError.
    """
    geometry = position.geometry
    text = text.strip()
    tokens = re.split(r"[-x:]", text.lower())
    if len(tokens) < 2 or not all(tokens):
        raise NotationError(f"bad move {text!r}")
    conv = (lambda t: from_numeric(geometry, int(t))) if tokens[0].isdigit() else \
        (lambda t: from_algebraic(geometry, t))
    squares = [conv(t) for t in tokens]
    origin, rest = squares[0], tuple(squares[1:])
    is_capture_text = "x" in text.lower()
    legal = legal_moves(position)
    candidates = [
        m for m in legal
        if m.origin == origin and (m.path == rest or (len(rest) == 1 and m.destination == rest[0]))
        and (m.is_capture or not is_capture_text)
    ]
    if not candidates and len(rest) > 1:
        # A full path naming a different (equally legal) route: kings may land on any empty
        # square beyond a captured piece, so writers (e.g. PlayOK) can name another route with the
        # same origin, destination and captured pieces. That is the same move (Move.identity):
        # derive the captured pieces from the written path and match by identity.
        captured = _captured_along(position, (origin, *rest))
        if captured is not None:
            candidates = [m for m in legal if m.identity == (origin, rest[-1], captured)]
    if not candidates:
        raise NotationError(f"{text!r} is not legal in {position.to_dsa()}")
    if len(candidates) > 1:
        raise AmbiguousMoveError(f"{text!r} matches {len(candidates)} legal moves; give the full path")
    return candidates[0]


def _captured_along(position: Position, path: tuple[int, ...]) -> frozenset[int] | None:
    """Pieces jumped along a written capture path: exactly one occupied square per segment.
    Returns None if a segment is not a diagonal or does not jump exactly one piece."""
    rays = position.geometry.rays
    captured: set[int] = set()
    for a, b in zip(path, path[1:]):
        between = None
        for ray in rays[a]:
            if b in ray:
                between = ray[: ray.index(b)]
                break
        if between is None:
            return None
        occupied = [sq for sq in between if position.squares[sq] != Piece.EMPTY and sq != path[0]]
        if len(occupied) != 1:
            return None
        captured.add(occupied[0])
    return frozenset(captured)


# --------------------------------------------------------------------------- PDN FEN


def to_fen(position: Position) -> str:
    g = position.geometry
    groups = {Color.WHITE: [], Color.BLACK: []}
    for sq, piece in enumerate(position.squares):
        if piece == Piece.EMPTY:
            continue
        color = piece.color
        assert color is not None
        groups[color].append((to_numeric(g, sq), piece.is_king))
    parts = []
    for color in (Color.WHITE, Color.BLACK):
        items = sorted(groups[color])
        parts.append(color.value + ",".join(("K" if k else "") + str(n) for n, k in items))
    return f"{position.side_to_move.value}:{parts[0]}:{parts[1]}"


def from_fen(geometry: Geometry, text: str) -> Position:
    """Parse ``W:W21,22,K5:B1-12``-style PDN FEN (ranges and K prefixes allowed)."""
    m = re.search(r'\[FEN\s+"([^"]*)"\]', text)
    fen = (m.group(1) if m else text).strip().rstrip(".")
    fields = fen.split(":")
    if len(fields) != 3 or fields[0].upper() not in ("W", "B"):
        raise NotationError(f"bad FEN {text!r}")
    pieces: dict[int, Piece] = {}
    for field in fields[1:]:
        field = field.strip()
        if not field:
            continue
        color = Color(field[0].upper())
        for item in filter(None, (s.strip() for s in field[1:].split(","))):
            king = item.upper().startswith("K")
            item = item.lstrip("Kk")
            lo, _, hi = item.partition("-")
            for number in range(int(lo), int(hi or lo) + 1):
                sq = from_numeric(geometry, number)
                if sq in pieces:
                    raise NotationError(f"square {number} listed twice")
                if color is Color.WHITE:
                    pieces[sq] = Piece.WHITE_KING if king else Piece.WHITE_MAN
                else:
                    pieces[sq] = Piece.BLACK_KING if king else Piece.BLACK_MAN
    return Position.from_pieces(geometry, pieces, Color(fields[0].upper()))
