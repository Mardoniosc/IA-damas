"""Engine profiles for Hub engines: facts that differ per engine, chosen from the engine's own
``id name=...`` line. Only verified facts are encoded; anything else uses the generic profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from damas_ai.engines.types import LimitKind, RawScore


@dataclass(frozen=True)
class HubProfile:
    name: str
    score_unit: str
    limits: frozenset[LimitKind]
    ponder: bool
    perspective: Literal["side_to_move", "white", "unknown"] = "unknown"
    # (eval_max, db_max, inf): Scan prints internal/100 with Eval_Inf=8000, BB_Inf=9000, Inf=10000.
    bands: tuple[float, float, float] | None = None

    def classify_score(self, text: str) -> RawScore:
        try:
            value = float(text)
        except ValueError:
            return RawScore(text, self.score_unit, None, "unknown", perspective=self.perspective)
        if self.bands is None:
            return RawScore(text, self.score_unit, value, "eval", perspective=self.perspective)
        eval_max, db_max, inf = self.bands
        magnitude = abs(value)
        if magnitude <= eval_max:
            return RawScore(text, self.score_unit, value, "eval", perspective=self.perspective)
        if magnitude <= db_max:  # BB_Inf - ply
            return RawScore(text, self.score_unit, value, "win_band",
                            round((db_max - magnitude) * 100), self.perspective)
        return RawScore(text, self.score_unit, value, "end_band",  # Inf - ply
                        round((inf - magnitude) * 100), self.perspective)


# Scan 3.1, verified in G4:
# - limits depth / nodes / move-time (protocol.txt; observed with the built engine)
# - score = internal / 100 (search.cpp, Output_Hub); constants in score.hpp:
#   Eval_Inf = 8000 (heuristic evals are clamped to +/-80.00), BB_Inf = 9000 (bitbase
#   win = BB_Inf - ply -> 89.xx), Inf = 10000 (search win = Inf - ply -> 99.xx and below)
# - perspective: side to move (observed: same position, W to move +99.93 / B to move -99.92)
SCAN = HubProfile(
    name="scan",
    score_unit="men",
    limits=frozenset({LimitKind.DEPTH, LimitKind.NODES, LimitKind.MOVE_TIME}),
    ponder=True,
    perspective="side_to_move",
    bands=(80.0, 90.0, 100.0),
)

# Anything not verified (e.g. "Kingsrow hub": G1 Q3). Conservative: depth and move-time only,
# since both are in the base Hub v2 spec; unit and perspective unknown until observed.
GENERIC = HubProfile(
    name="generic-hub",
    score_unit="unknown",
    limits=frozenset({LimitKind.DEPTH, LimitKind.MOVE_TIME}),
    ponder=False,
)


def select_profile(engine_name: str) -> HubProfile:
    return SCAN if engine_name.strip().lower() == "scan" else GENERIC
