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

# Kingsrow hub 1.63 (Ed Gilbert), verified in G5:
# - kr_hub.pdf: "level" implements moves/time/inc/move-time/infinite and NOT depth or nodes.
#   Observed: 'level depth=6' is silently ignored (searched to depth 14), so depth/nodes must be
#   refused here rather than sent.
# - Ponder moves are only returned for 'go think' / 'go ponder' (kr_hub.pdf).
# - Score: side-to-move perspective (W to move +1.18 / B to move -1.20, same position); about
#   1.2 per extra man (empirical, NOT calibrated against Scan). Wins print as 40 - plies/100
#   (39.93 = win in 7 plies, matching Scan's 99.93 on the same position).
# - Band boundary is EMPIRICAL: over 11,455 info lines no |score| fell in [35, 39.5); evals
#   stayed below 35. Without an endgame db no db-win band was observed (none encoded).
KINGSROW = HubProfile(
    name="kingsrow",
    score_unit="men (empirical)",
    limits=frozenset({LimitKind.MOVE_TIME}),
    ponder=True,
    perspective="side_to_move",
    bands=(35.0, 35.0, 40.0),
)

# Anything not verified. Conservative: depth and move-time, both in the base Hub v2 spec.
# NOTE (G5): an engine may silently ignore a limit it does not implement (Kingsrow does), so
# every real engine should get a verified profile before its results are relied upon.
GENERIC = HubProfile(
    name="generic-hub",
    score_unit="unknown",
    limits=frozenset({LimitKind.DEPTH, LimitKind.MOVE_TIME}),
    ponder=False,
)

# The platform's own engine (damas_ai.search.hub, G8). Facts are by construction (our code):
# eval in hundredths of a man clamped to +/-80.00; wins print as 100 - plies/100; side to move;
# depth, nodes and move-time limits all honoured; no endgame database.
DAMASAI = HubProfile(
    name="damasai",
    score_unit="men (internal baseline eval)",
    limits=frozenset({LimitKind.DEPTH, LimitKind.NODES, LimitKind.MOVE_TIME}),
    ponder=False,
    perspective="side_to_move",
    bands=(80.0, 80.0, 100.0),
)

_BY_NAME = {"scan": SCAN, "kingsrow": KINGSROW, "damasai": DAMASAI}


def select_profile(engine_name: str) -> HubProfile:
    return _BY_NAME.get(engine_name.strip().lower(), GENERIC)
