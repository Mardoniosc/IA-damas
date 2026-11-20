"""Hub protocol v2 codec, written to the text of Scan 3.1 ``protocol.txt``.

Syntax: ``<command> <arg>=<val> <arg>=<val> ...``. Values may be double-quoted, which is
required for values containing spaces or ``=``, and for empty values. Flags have no ``=val``.
The spec defines **no escape mechanism**, so backslashes are literal and a value cannot
contain a double quote. Unknown commands/arguments must be ignored, not rejected.

Positions: side char ``W``/``B`` followed by one char per square in standard numeric order
(1..N), with ``w b W B e``. Moves: ``from-to`` for quiet moves; captures are
``from x to x captured x captured ...`` (captured squares in any order, no pivots).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from damas_ai.rules import Geometry, Move, Position
from damas_ai.rules.notation import from_numeric, to_numeric
from damas_ai.rules.position import DSA_CHARS, DSA_PIECES, Color


class HubSyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class HubMessage:
    command: str
    args: dict[str, str]
    raw: str

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.args.get(key, default)


def parse_line(line: str) -> HubMessage | None:
    """Parse one line; None for blank lines. Raises HubSyntaxError on an unterminated quote."""
    text = line.strip()
    if not text:
        return None
    i, n = 0, len(text)

    def skip_spaces(j: int) -> int:
        while j < n and text[j] == " ":
            j += 1
        return j

    start = i
    while i < n and text[i] != " ":
        i += 1
    command = text[start:i]
    args: dict[str, str] = {}
    i = skip_spaces(i)
    while i < n:
        start = i
        while i < n and text[i] not in " =":
            i += 1
        key = text[start:i]
        if i < n and text[i] == "=":
            i += 1
            if i < n and text[i] == '"':
                end = text.find('"', i + 1)
                if end < 0:
                    raise HubSyntaxError(f"unterminated quote in {line!r}")
                value = text[i + 1:end]
                i = end + 1
            else:
                start = i
                while i < n and text[i] != " ":
                    i += 1
                value = text[start:i]
        else:
            value = ""
        if key:
            args[key] = value
        i = skip_spaces(i)
    return HubMessage(command, args, line)


def format_line(command: str, *flags: str, **args: str | int | float) -> str:
    """Build a Hub line; keyword args become ``key=value`` (quoted when needed)."""
    parts = [command, *flags]
    for key, value in args.items():
        text = str(value)
        if '"' in text:
            raise HubSyntaxError("Hub values cannot contain double quotes")
        if text == "" or " " in text or "=" in text:
            text = f'"{text}"'
        parts.append(f"{key.replace('_', '-')}={text}")
    return " ".join(parts)


# --------------------------------------------------------------------------- positions


def encode_position(position: Position) -> str:
    g = position.geometry
    chars = ["e"] * g.num_squares
    for sq, piece in enumerate(position.squares):
        chars[to_numeric(g, sq) - 1] = DSA_CHARS[piece]
    return position.side_to_move.value + "".join(chars)


def decode_position(geometry: Geometry, text: str) -> Position:
    if len(text) != geometry.num_squares + 1 or text[0] not in "WB":
        raise HubSyntaxError(f"Hub position must be W/B + {geometry.num_squares} squares")
    pieces = {}
    for i, ch in enumerate(text[1:], start=1):
        if ch not in DSA_PIECES:
            raise HubSyntaxError(f"bad Hub square char {ch!r}")
        pieces[from_numeric(geometry, i)] = DSA_PIECES[ch]
    return Position.from_pieces(geometry, pieces, Color(text[0]))


# --------------------------------------------------------------------------- moves

_MOVE_RE = re.compile(r"^\d{1,3}(?:-\d{1,3}|(?:x\d{1,3})+)$")


@dataclass(frozen=True)
class HubMoveReport:
    """What a Hub move text says, in canonical squares (not yet validated).

    ``captured`` is the empty set for a quiet move, and None for the non-standard short
    capture form ``from x to`` (no captured squares given)."""

    origin: int
    destination: int
    captured: frozenset[int] | None


def parse_move(geometry: Geometry, text: str) -> HubMoveReport:
    if not _MOVE_RE.match(text):
        raise HubSyntaxError(f"not a Hub move: {text!r}")
    numbers = [int(t) for t in re.split(r"[-x]", text)]
    squares = [from_numeric(geometry, n) for n in numbers]  # raises on out-of-range
    if "x" in text and len(squares) == 2:
        return HubMoveReport(squares[0], squares[1], None)
    return HubMoveReport(squares[0], squares[1], frozenset(squares[2:]))


def format_move(geometry: Geometry, move: Move) -> str:
    def num(sq: int) -> str:
        return str(to_numeric(geometry, sq))

    if not move.is_capture:
        return f"{num(move.origin)}-{num(move.destination)}"
    return "x".join([num(move.origin), num(move.destination), *(num(c) for c in move.captured)])
