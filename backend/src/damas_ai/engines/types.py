"""Engine-agnostic platform types (ADR-002). No engine-specific type crosses this boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from damas_ai.rules import GameState, Move, Position, Ruleset

TranscriptLine = tuple[float, str, str]  # (seconds since process start, ">" sent | "<" received | "!" stderr, text)


class LimitKind(Enum):
    DEPTH = "depth"
    NODES = "nodes"
    MOVE_TIME = "move_time"


@dataclass(frozen=True)
class SearchLimit:
    """Exactly one of depth / nodes / move_time_s."""

    depth: int | None = None
    nodes: int | None = None
    move_time_s: float | None = None

    def __post_init__(self) -> None:
        given = [v for v in (self.depth, self.nodes, self.move_time_s) if v is not None]
        if len(given) != 1:
            raise ValueError("SearchLimit needs exactly one of depth, nodes, move_time_s")
        if any(v <= 0 for v in given):
            raise ValueError("search limits must be positive")

    @property
    def kind(self) -> LimitKind:
        if self.depth is not None:
            return LimitKind.DEPTH
        if self.nodes is not None:
            return LimitKind.NODES
        return LimitKind.MOVE_TIME


@dataclass(frozen=True)
class EngineCapabilities:
    native_variants: frozenset[str]
    limits: frozenset[LimitKind]
    multipv: bool
    ponder: bool
    reports_pv: bool
    score_unit: str  # e.g. "men" for Scan; "unknown" when not established


@dataclass(frozen=True)
class EngineInfo:
    """What the engine says about itself (verbatim), plus the profile chosen from it."""

    name: str
    version: str
    author: str = ""
    declared_params: tuple[dict[str, str], ...] = ()
    profile: str = "generic-hub"


@dataclass(frozen=True)
class AnalysisRequest:
    """Analyse the position reached from ``root`` after ``moves`` (moves are needed by engines
    for repetition detection). Moves are validated by the Rules Core at construction."""

    ruleset: Ruleset
    root: Position
    limit: SearchLimit
    moves: tuple[Move, ...] = ()
    mode: Literal["analyze", "think"] = "analyze"
    state: GameState = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        state = GameState.new(self.ruleset, self.root)
        for move in self.moves:
            state = state.play(move)
        object.__setattr__(self, "state", state)

    @property
    def position(self) -> Position:
        return self.state.position


class AnalysisStatus(Enum):
    OK = "ok"                      # validated best move
    ILLEGAL_MOVE = "illegal_move"  # engine answered, but the move is not legal (ADR-001)
    PROTOCOL_ERROR = "protocol_error"
    TIMEOUT = "timeout"            # no answer even after 'stop'; process was killed
    CRASHED = "crashed"            # process exited during the search


@dataclass(frozen=True)
class RawScore:
    """Verbatim score with its unit and an engine-profile classification. Never compared
    across engines without a calibrated normalizer (G7).

    - ``kind``: ``eval`` (heuristic), ``win_band`` (endgame-database win/loss), ``end_band``
      (search-proven win/loss), ``unknown``.
    - ``distance_plies``: for win/loss kinds, the engine-reported distance when the profile
      knows how to decode it.
    - ``perspective``: ``side_to_move`` | ``white`` | ``unknown``.
    """

    text: str
    unit: str
    value: float | None
    kind: Literal["eval", "win_band", "end_band", "unknown"] = "unknown"
    distance_plies: int | None = None
    perspective: Literal["side_to_move", "white", "unknown"] = "unknown"


@dataclass(frozen=True)
class SearchInfo:
    depth: int | None
    score: RawScore | None
    nodes: int | None
    time_s: float | None
    pv_text: str
    pv: tuple[Move, ...]  # longest legal prefix of the reported PV
    raw: dict[str, str]


@dataclass(frozen=True)
class AnalysisResult:
    engine_id: str
    engine_name: str
    engine_version: str
    variant: str
    position_dsa: str
    limit: SearchLimit
    status: AnalysisStatus
    best_move: Move | None
    best_move_text: str | None
    ponder_move: Move | None
    infos: tuple[SearchInfo, ...]
    interrupted: bool
    elapsed_s: float
    violations: tuple[str, ...]
    transcript: tuple[TranscriptLine, ...]

    @property
    def final_info(self) -> SearchInfo | None:
        return self.infos[-1] if self.infos else None
