"""Board geometry: playable squares, canonical indexing and diagonal rays.

Canonical index (ADR-003): for an ``N x N`` board seen from White, with file ``f`` and rank ``r``
both 0-based and square a1 dark, a square is playable iff ``(f + r) % 2 == 0`` and its index is
``i = r * (N // 2) + f // 2``. White starts on the low indices.
"""

from __future__ import annotations

from dataclasses import dataclass

# Direction order is part of the contract (rays[sq][d]).
NE, NW, SE, SW = 0, 1, 2, 3
DIRECTIONS: tuple[tuple[int, int], ...] = ((1, 1), (-1, 1), (1, -1), (-1, -1))
FILES = "abcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True, eq=False)
class Geometry:
    """Immutable, precomputed board geometry. Compare geometries by ``id``."""

    id: str
    size: int
    num_squares: int
    coords: tuple[tuple[int, int], ...]  # index -> (file, rank)
    rays: tuple[tuple[tuple[int, ...], ...], ...]  # rays[sq][direction] -> squares outward

    def index(self, file: int, rank: int) -> int:
        if not (0 <= file < self.size and 0 <= rank < self.size) or (file + rank) % 2:
            raise ValueError(f"({file}, {rank}) is not a playable square on {self.id}")
        return rank * (self.size // 2) + file // 2

    def rank_of(self, sq: int) -> int:
        return self.coords[sq][1]

    def rotate180(self, sq: int) -> int:
        """180-degree rotation; combined with a colour swap it is the board symmetry."""
        return self.num_squares - 1 - sq

    def __repr__(self) -> str:
        return f"Geometry({self.id!r})"


def make_geometry(geometry_id: str, size: int) -> Geometry:
    if size < 4 or size % 2:
        raise ValueError("board size must be an even number >= 4")
    half = size // 2
    coords: list[tuple[int, int]] = []
    for rank in range(size):
        for file in range(rank % 2, size, 2):
            coords.append((file, rank))
    index = {(f, r): r * half + f // 2 for f, r in coords}
    rays: list[tuple[tuple[int, ...], ...]] = []
    for file, rank in coords:
        per_dir: list[tuple[int, ...]] = []
        for df, dr in DIRECTIONS:
            ray: list[int] = []
            f, r = file + df, rank + dr
            while 0 <= f < size and 0 <= r < size:
                ray.append(index[(f, r)])
                f, r = f + df, r + dr
            per_dir.append(tuple(ray))
        rays.append(tuple(per_dir))
    return Geometry(geometry_id, size, len(coords), tuple(coords), tuple(rays))


BOARD_8X8 = make_geometry("8x8", 8)
BOARD_10X10 = make_geometry("10x10", 10)
