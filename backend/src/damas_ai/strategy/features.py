"""Strategic profile (G10, ADR-012): descriptive positional features, per side.

These are *descriptions*, not evaluations: each is a well-defined count from the Rules Core
geometry. Whether a feature matters is measured (G10 report: correlation with Scan's eval),
not assumed.

Features per side:
- men, kings                 piece counts
- tempo                      sum over men of rows advanced from own back row (classic draughts
                             "tempo count"; higher = more advanced)
- center                     pieces on the central squares (the middle half of files and ranks)
- back_rank                  men still on own first row (guard against promotion)
- mobility                   legal moves if it were that side's turn
- runaways                   men with no opposing man in the forward cone of squares they could
                             still reach, and no opposing king at all (a simple "unstoppable"
                             proxy; it ignores tempo races)
"""

from __future__ import annotations

from dataclasses import dataclass

from damas_ai.rules import Color, Position, legal_moves
from damas_ai.rules.position import Piece


@dataclass(frozen=True)
class SideFeatures:
    men: int
    kings: int
    tempo: int
    center: int
    back_rank: int
    mobility: int
    runaways: int


@dataclass(frozen=True)
class StrategicProfile:
    white: SideFeatures
    black: SideFeatures
    side_to_move: Color

    def delta(self) -> dict[str, int]:
        """White minus Black, per feature."""
        return {k: getattr(self.white, k) - getattr(self.black, k) for k in SideFeatures.__dataclass_fields__}

    def notes(self) -> list[str]:
        """Plain-language description of the most notable differences (no value judgements)."""
        d = self.delta()
        out = []
        for key, label in (("men", "men"), ("kings", "kings"), ("runaways", "unstoppable-looking men"),
                           ("tempo", "tempo"), ("mobility", "mobility"), ("center", "central pieces"),
                           ("back_rank", "back-rank guards")):
            if d[key]:
                leader = "White" if d[key] > 0 else "Black"
                out.append(f"{leader} has {abs(d[key])} more {label}")
        return out


def _side(position: Position, color: Color) -> SideFeatures:
    g = position.geometry
    size = g.size
    man = Piece.WHITE_MAN if color is Color.WHITE else Piece.BLACK_MAN
    king = Piece.WHITE_KING if color is Color.WHITE else Piece.BLACK_KING
    enemy = {Piece.BLACK_MAN, Piece.BLACK_KING} if color is Color.WHITE else {Piece.WHITE_MAN, Piece.WHITE_KING}
    lo, hi = size // 4, size - 1 - size // 4
    men = kings = tempo = center = back = runaways = 0
    for sq, piece in enumerate(position.squares):
        if piece not in (man, king):
            continue
        f, r = g.coords[sq]
        if lo <= f <= hi and lo <= r <= hi:
            center += 1
        if piece == king:
            kings += 1
            continue
        men += 1
        adv = r if color is Color.WHITE else size - 1 - r
        tempo += adv
        if adv == 0:
            back += 1
        # forward cone: squares (f', r') ahead with |f' - f| <= distance in ranks
        blocked = False
        for sq2, p2 in enumerate(position.squares):
            if p2 not in enemy:
                continue
            if p2 in (Piece.WHITE_KING, Piece.BLACK_KING):
                blocked = True  # a flying king can intercept from anywhere
                break
            f2, r2 = g.coords[sq2]
            dist = (r2 - r) if color is Color.WHITE else (r - r2)
            if dist > 0 and abs(f2 - f) <= dist + 1:
                blocked = True
                break
        runaways += not blocked
    mobility = len(legal_moves(position.with_side(color)))
    return SideFeatures(men, kings, tempo, center, back, mobility, runaways)


def profile(position: Position) -> StrategicProfile:
    return StrategicProfile(_side(position, Color.WHITE), _side(position, Color.BLACK),
                            position.side_to_move)
