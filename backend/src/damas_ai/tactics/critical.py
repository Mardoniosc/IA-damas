"""Critical-position assessment (G9, ADR-011).

A position is *critical* when a wrong choice is likely to be costly or when the platform's
evidence is unstable. Each flag is computed independently and reported with its evidence:

- ``shot``: the side to move has a forcing line winning material (forcing.find_shots)
- ``threat``: the opponent threatens to capture at least N pieces (null-move view)
- ``only_move``: by the internal engine, the best move beats the second by a large margin
- ``volatile``: the internal engine's best move changed late in iterative deepening, or its
  score swung strongly
- ``divergence``: optional input from G7/G8 (stable preference, outcome conflict, proof gap)

All thresholds are parameters (``Thresholds``); the defaults are provisional (G9 report).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from damas_ai.rules import Move, Position, apply_move, legal_moves
from damas_ai.rules.zobrist import zobrist_key
from damas_ai.search import Searcher
from damas_ai.search.searcher import MATE_BOUND
from damas_ai.tactics.forcing import Shot, Threat, find_shots, threats_against


@dataclass(frozen=True)
class Thresholds:
    shot_min_gain: int = 100           # hundredths of a man
    threat_pieces: int = 2
    only_move_gap: int = 100           # best - second best, internal engine, hundredths
    volatile_last_depths: int = 2      # best move changed within the last N completed depths
    volatile_swing: int = 100          # score swing over the last N depths
    depth: int = 6                     # internal engine depth for move values / volatility


@dataclass(frozen=True)
class MoveValue:
    move: Move
    score: int  # internal engine, hundredths of a man, for the side to move


@dataclass(frozen=True)
class CriticalityReport:
    position: Position
    critical: bool
    reasons: tuple[str, ...]
    shots: tuple[Shot, ...]
    threat: Threat
    move_values: tuple[MoveValue, ...]
    gap: int | None
    best_move_changes: int
    score_swing: int
    divergence: str | None = None
    proof_gap: bool = False
    thresholds: Thresholds = field(default_factory=Thresholds)


def evaluate_moves(position: Position, depth: int) -> tuple[MoveValue, ...]:
    """Internal-engine value of every legal move (a full-width 'multi-PV'), best first."""
    searcher = Searcher()
    history = (zobrist_key(position),)
    values = []
    for m in legal_moves(position):
        child = apply_move(position, m)
        if not legal_moves(child):
            values.append(MoveValue(m, 10_000 - 1))  # the move wins at once
            continue
        out = searcher.search(child, history, depth=max(1, depth - 1))
        values.append(MoveValue(m, -(out.score or 0)))
    return tuple(sorted(values, key=lambda v: -v.score))


def assess(position: Position, thresholds: Thresholds | None = None,
           divergence: str | None = None, proof_gap: bool = False) -> CriticalityReport:
    t = thresholds or Thresholds()
    reasons: list[str] = []
    moves = legal_moves(position)
    if not moves:
        raise ValueError("terminal position")
    decision = len(moves) > 1  # a single legal move is not a decision

    shots = find_shots(position, min_gain=t.shot_min_gain)
    if shots and decision:
        # It matters only if some legal move does not achieve the best gain (a real choice).
        best_gain = shots[0].gain
        if shots[0].sacrifice or sum(1 for s in shots if s.gain == best_gain) < len(moves):
            kind = "sacrifice" if shots[0].sacrifice else "capture choice"
            reasons.append(f"shot: {kind} gaining {best_gain / 100:.2f} men")

    threat = threats_against(position)
    if threat.max_pieces >= t.threat_pieces:
        reasons.append(f"threat: opponent could capture {threat.max_pieces} pieces")

    values = evaluate_moves(position, t.depth) if decision else ()
    gap = None
    if len(values) >= 2:
        gap = values[0].score - values[1].score
        # Not an "only move" if even the best move loses by force (nothing to choose).
        if values[0].score > -MATE_BOUND and gap >= t.only_move_gap:
            shown = "a forced loss" if values[1].score <= -MATE_BOUND else f"{gap / 100:.2f} men"
            reasons.append(f"only move: best beats second by {shown} (internal, depth {t.depth})")

    changes, swing = 0, 0
    if decision:
        infos = Searcher().search(position, depth=t.depth).infos
        recent = infos[-(t.volatile_last_depths + 1):]
        changes = sum(1 for a, b in zip(recent, recent[1:]) if a.pv[:1] != b.pv[:1])
        swing = (max(i.score for i in recent) - min(i.score for i in recent)) if recent else 0
        # Odd/even depth alternation is normal in alpha-beta; flag only a final choice that none
        # of the previous N depths preferred, or a large score swing.
        final_new = len(recent) > 1 and all(i.pv[:1] != recent[-1].pv[:1] for i in recent[:-1])
        if final_new:
            reasons.append(f"volatile: final best move is new in the last {t.volatile_last_depths} depths")
        elif swing >= t.volatile_swing:
            reasons.append(f"volatile: score swung {swing / 100:.2f} men in the last depths")

    if divergence in ("preference", "outcome_conflict"):
        reasons.append(f"divergence: engines disagree ({divergence})")
    if proof_gap:
        reasons.append("divergence: proof gap between engines")

    return CriticalityReport(position, bool(reasons), tuple(reasons), shots, threat, values, gap,
                             changes, swing, divergence, proof_gap, t)
