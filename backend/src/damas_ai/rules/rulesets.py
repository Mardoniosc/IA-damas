"""Rule sets: geometry, start position and draw-rule parameters as versioned data.

Draw rules are data, not code, because the Brazilian sources disagree
(rules-compatibility.md §2 and INC-5). Every ruleset says whether it is provisional and where
each value comes from. All limits are expressed in **plies** (half-moves) to avoid the
"moves per side vs total" ambiguity of the rule texts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from damas_ai.rules.geometry import BOARD_8X8, BOARD_10X10, Geometry
from damas_ai.rules.position import Color, Position


@dataclass(frozen=True)
class EndgameDrawRule:
    """Draw if the stronger side fails to win within ``limit_plies`` of this material appearing.

    Material is matched exactly: one side has (strong_kings, strong_men), the other
    (weak_kings, weak_men). The counter starts when the material first matches and resets
    whenever the material changes.
    """

    name: str
    strong_kings: int
    strong_men: int
    weak_kings: int
    weak_men: int
    limit_plies: int
    source: str

    def matches(self, material: tuple[int, int, int, int]) -> bool:
        wm, wk, bm, bk = material
        strong, weak = (self.strong_kings, self.strong_men), (self.weak_kings, self.weak_men)
        return ((wk, wm) == strong and (bk, bm) == weak) or ((bk, bm) == strong and (wk, wm) == weak)


@dataclass(frozen=True)
class Ruleset:
    id: str
    variant: str
    geometry: Geometry
    men_rows: int
    first_to_move: Color
    repetition_count: int | None
    king_only_limit_plies: int | None
    endgame_rules: tuple[EndgameDrawRule, ...] = ()
    provisional: bool = True
    sources: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def initial_position(self) -> Position:
        return Position.initial(self.geometry, self.men_rows, self.first_to_move)


BRAZILIAN_PROVISIONAL = Ruleset(
    id="br-provisional-2026-11",
    variant="brazilian-8x8",
    geometry=BOARD_8X8,
    men_rows=3,
    first_to_move=Color.WHITE,
    repetition_count=3,
    # "20 lances sucessivos de damas, sem tomada ou deslocamento de pedra" (pt.wikipedia "Damas").
    # Interpreted as 20 moves by EACH side = 40 plies. UNVERIFIED interpretation.
    king_only_limit_plies=40,
    endgame_rules=(
        EndgameDrawRule(
            name="3 kings vs 1 king",
            strong_kings=3, strong_men=0, weak_kings=1, weak_men=0,
            limit_plies=40,  # "não conseguir obter vitória em vinte lances" -> 20 moves each
            source="pt.wikipedia 'Damas' (accessed 2026-11-20)",
        ),
    ),
    provisional=True,
    sources=(
        "pt.wikipedia.org/wiki/Damas (raw wikitext, accessed 2026-11-20)",
        "en.wikipedia.org/wiki/Brazilian_draughts (accessed 2026-11-20)",
    ),
    notes=(
        "PROVISIONAL: the official CBJD text has not been obtained (G1 Q2).",
        "A competition regulation seen only via search mentions faster '5-move' draws in some "
        "king endings; NOT encoded because the text could not be read (HTTP 403).",
        "Repetition is treated as an automatic draw in analysis; over the board it must be "
        "claimed (pt.wikipedia).",
    ),
)

INTERNATIONAL_PROVISIONAL = Ruleset(
    id="intl-provisional-2026-11",
    variant="international-10x10",
    geometry=BOARD_10X10,
    men_rows=4,
    first_to_move=Color.WHITE,
    repetition_count=3,
    # FMJD 25-move king rule, read as 25 moves each = 50 plies. Domain knowledge [K], UNVERIFIED.
    king_only_limit_plies=50,
    endgame_rules=(),  # FMJD special endgame counts not encoded: not verified in G1/G2.
    provisional=True,
    sources=("general domain knowledge [K]; FMJD rules text not yet obtained",),
    notes=(
        "Exists only to validate SCAN / Kingsrow International moves (ADR-005 option A).",
        "Move generation is the same International-family code as Brazilian.",
    ),
)

RULESETS: dict[str, Ruleset] = {r.id: r for r in (BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL)}
