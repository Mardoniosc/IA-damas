"""Immutable position: pieces on canonical squares plus side to move (ADR-003)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

from damas_ai.rules.geometry import Geometry


class Color(Enum):
    WHITE = "W"
    BLACK = "B"

    @property
    def opponent(self) -> Color:
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class Piece(IntEnum):
    EMPTY = 0
    WHITE_MAN = 1
    WHITE_KING = 2
    BLACK_MAN = 3
    BLACK_KING = 4

    @property
    def color(self) -> Color | None:
        return PIECE_COLOR[self]

    @property
    def is_king(self) -> bool:
        return self in (Piece.WHITE_KING, Piece.BLACK_KING)


PIECE_COLOR: dict[int, Color | None] = {
    Piece.EMPTY: None,
    Piece.WHITE_MAN: Color.WHITE,
    Piece.WHITE_KING: Color.WHITE,
    Piece.BLACK_MAN: Color.BLACK,
    Piece.BLACK_KING: Color.BLACK,
}
MAN_OF = {Color.WHITE: Piece.WHITE_MAN, Color.BLACK: Piece.BLACK_MAN}
KING_OF = {Color.WHITE: Piece.WHITE_KING, Color.BLACK: Piece.BLACK_KING}
PROMOTED = {Piece.WHITE_MAN: Piece.WHITE_KING, Piece.BLACK_MAN: Piece.BLACK_KING}
SWAP_COLOR = {
    Piece.EMPTY: Piece.EMPTY,
    Piece.WHITE_MAN: Piece.BLACK_MAN,
    Piece.WHITE_KING: Piece.BLACK_KING,
    Piece.BLACK_MAN: Piece.WHITE_MAN,
    Piece.BLACK_KING: Piece.WHITE_KING,
}

DSA_CHARS = {Piece.EMPTY: "e", Piece.WHITE_MAN: "w", Piece.WHITE_KING: "W",
             Piece.BLACK_MAN: "b", Piece.BLACK_KING: "B"}
DSA_PIECES = {v: k for k, v in DSA_CHARS.items()}


def promotion_rank(geometry: Geometry, color: Color) -> int:
    return geometry.size - 1 if color is Color.WHITE else 0


@dataclass(frozen=True, eq=False)
class Position:
    geometry: Geometry
    squares: tuple[Piece, ...]
    side_to_move: Color

    def __post_init__(self) -> None:
        if len(self.squares) != self.geometry.num_squares:
            raise ValueError(
                f"{self.geometry.id} needs {self.geometry.num_squares} squares, "
                f"got {len(self.squares)}"
            )
        top = promotion_rank(self.geometry, Color.WHITE)
        for sq, piece in enumerate(self.squares):
            rank = self.geometry.rank_of(sq)
            if (piece == Piece.WHITE_MAN and rank == top) or (piece == Piece.BLACK_MAN and rank == 0):
                raise ValueError(f"unpromoted man on its promotion rank at square {sq}")

    # Equality must not depend on Geometry object identity semantics beyond its id.
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return (self.geometry.id == other.geometry.id and self.squares == other.squares
                and self.side_to_move == other.side_to_move)

    def __hash__(self) -> int:
        return hash((self.geometry.id, self.squares, self.side_to_move))

    # ---------------------------------------------------------------- construction

    @classmethod
    def initial(cls, geometry: Geometry, men_rows: int, first: Color = Color.WHITE) -> Position:
        per_row = geometry.size // 2
        n = men_rows * per_row
        if 2 * men_rows >= geometry.size:
            raise ValueError("men rows overlap")
        squares = ([Piece.WHITE_MAN] * n
                   + [Piece.EMPTY] * (geometry.num_squares - 2 * n)
                   + [Piece.BLACK_MAN] * n)
        return cls(geometry, tuple(squares), first)

    @classmethod
    def from_dsa(cls, geometry: Geometry, text: str) -> Position:
        """Parse the canonical DSA string: side char + one char per canonical square."""
        if not text or text[0] not in "WB":
            raise ValueError("DSA string must start with 'W' or 'B'")
        try:
            squares = tuple(DSA_PIECES[c] for c in text[1:])
        except KeyError as exc:
            raise ValueError(f"invalid DSA piece char {exc.args[0]!r}") from exc
        return cls(geometry, squares, Color(text[0]))

    @classmethod
    def from_pieces(cls, geometry: Geometry, pieces: dict[int, Piece], side: Color) -> Position:
        squares = [Piece.EMPTY] * geometry.num_squares
        for sq, piece in pieces.items():
            squares[sq] = piece
        return cls(geometry, tuple(squares), side)

    # ---------------------------------------------------------------- views

    def to_dsa(self) -> str:
        return self.side_to_move.value + "".join(DSA_CHARS[p] for p in self.squares)

    def flipped(self) -> Position:
        """Rotate 180 degrees and swap colours (including side to move)."""
        n = self.geometry.num_squares
        squares = tuple(SWAP_COLOR[self.squares[n - 1 - i]] for i in range(n))
        return Position(self.geometry, squares, self.side_to_move.opponent)

    def count(self, piece: Piece) -> int:
        return self.squares.count(piece)

    def material(self) -> tuple[int, int, int, int]:
        """(white men, white kings, black men, black kings)."""
        s = self.squares
        return (s.count(Piece.WHITE_MAN), s.count(Piece.WHITE_KING),
                s.count(Piece.BLACK_MAN), s.count(Piece.BLACK_KING))

    def with_side(self, side: Color) -> Position:
        return Position(self.geometry, self.squares, side)
