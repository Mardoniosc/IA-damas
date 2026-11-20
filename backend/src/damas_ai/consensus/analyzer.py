"""Consensus & divergence (G7, ADR-009).

Stage 1: each capable engine proposes a move (G6 MultiEngineAnalyzer).
Stage 2 (cross-evaluation): every engine evaluates every proposed move by searching the position
after it with the same limit. Each engine's judgement is expressed in its own units, so the
*regret* an engine attaches to another engine's move needs no cross-engine score scale.

Classification of a position:
- ``incomplete``: fewer than two engines produced a validated move.
- ``outcome_conflict``: engines *contradict* each other about the root or a candidate: win vs
  loss, or a proven result vs an eval that does not favour the same side.
- ``none``: all engines proposed the same move (and no contradiction).
- ``equivalent_alternatives``: different moves, but every engine's regret for every candidate is
  within that engine's tolerance.
- ``preference``: different moves, and some engine considers another engine's move worse than its
  own by more than its tolerance (or a regret is unknown).

Independently, ``proof_gap`` is set when one engine *proves* a result that another engine only
evaluates in the same direction (e.g. Scan "win in N plies" vs Kingsrow "+10.6"). It is not a
contradiction, but it marks a difference in what each engine can establish.
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from damas_ai.analysis import EnginePool, MultiAnalysisResult, MultiEngineAnalyzer
from damas_ai.analysis.orchestrator import RunMode
from damas_ai.consensus.values import (
    MoveValue,
    OutcomeClass,
    contradicts,
    proof_gap,
    root_value,
    terminal_win,
    value_after_move,
)
from damas_ai.engines import AnalysisRequest, AnalysisStatus, EngineError
from damas_ai.rules import Move, apply_move, legal_moves

log = logging.getLogger("damas_ai.consensus")

CrossCheck = Literal["disagreement", "always", "never"]
DEFAULT_TOLERANCE = 0.10  # in each engine's own eval units; PROVISIONAL (see G7 report)


class Divergence(Enum):
    NONE = "none"
    EQUIVALENT_ALTERNATIVES = "equivalent_alternatives"
    PREFERENCE = "preference"
    OUTCOME_CONFLICT = "outcome_conflict"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class Candidate:
    move: Move
    proposed_by: tuple[str, ...]
    values: dict[str, MoveValue]          # engine id -> value of this move for the mover
    regret: dict[str, float | None]       # engine id -> best utility - this utility (own units)


@dataclass(frozen=True)
class ConsensusResult:
    analysis: MultiAnalysisResult
    classification: Divergence
    unanimous: bool
    agreement_ratio: float | None
    candidates: tuple[Candidate, ...]
    root_values: dict[str, MoveValue]     # engine id -> root value for the side to move
    cross_checked: bool
    tolerance: dict[str, float]
    proof_gap: bool = False
    notes: tuple[str, ...] = field(default=())

    @property
    def root_outcomes(self) -> dict[str, OutcomeClass]:
        return {e: v.outcome for e, v in self.root_values.items()}

    def max_regret(self) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        for engine_id in self.analysis.engines_ok:
            known = [r for c in self.candidates if (r := c.regret.get(engine_id)) is not None]
            out[engine_id] = max(known) if known else None
        return out


def _tolerances(engines: tuple[str, ...], tolerance: float | Mapping[str, float]) -> dict[str, float]:
    if isinstance(tolerance, Mapping):
        return {e: float(tolerance.get(e, DEFAULT_TOLERANCE)) for e in engines}
    return {e: float(tolerance) for e in engines}


def _pairs(values: Mapping[str, MoveValue]) -> list[tuple[MoveValue, MoveValue]]:
    return list(itertools.combinations(values.values(), 2))


class ConsensusAnalyzer:
    def __init__(self, pool: EnginePool) -> None:
        self.pool = pool
        self.multi = MultiEngineAnalyzer(pool)

    def analyze(
        self,
        request: AnalysisRequest,
        engines: list[str] | None = None,
        mode: RunMode = "sequential",
        cross_check: CrossCheck = "disagreement",
        tolerance: float | Mapping[str, float] = DEFAULT_TOLERANCE,
    ) -> ConsensusResult:
        analysis = self.multi.analyze(request, engines, mode)
        ok = analysis.engines_ok
        tol = _tolerances(ok, tolerance)
        notes: list[str] = [analysis.note] if analysis.note else []
        roots = {
            o.engine_id: root_value(o.result.final_info.score
                                    if o.result is not None and o.result.final_info else None)
            for o in analysis.outcomes if o.ok
        }
        if len(ok) < 2:
            notes.append(f"{len(ok)} engine(s) produced a validated move; consensus needs two")
            return ConsensusResult(analysis, Divergence.INCOMPLETE, False, None, (), roots, False,
                                   tol, False, tuple(notes))

        proposals = analysis.proposals
        unanimous = len(proposals) == 1
        agreement = max(len(p.engines) for p in proposals) / len(ok)
        do_cross = cross_check == "always" or (cross_check == "disagreement" and not unanimous)

        values: dict[tuple[int, int, frozenset[int]], dict[str, MoveValue]] = {}
        if do_cross:
            for p in proposals:
                values[p.move.identity] = self.evaluate_move(request, p.move, ok, notes)

        best_utility: dict[str, float | None] = {}
        for engine_id in ok:
            known = [v.utility for p in proposals
                     if (v := values.get(p.move.identity, {}).get(engine_id)) is not None
                     and v.utility is not None]
            best_utility[engine_id] = max(known) if known else None
        candidates = []
        for p in proposals:
            vals = values.get(p.move.identity, {})
            regret: dict[str, float | None] = {}
            for engine_id in ok:
                v, b = vals.get(engine_id), best_utility[engine_id]
                regret[engine_id] = (b - v.utility) if (v is not None and v.utility is not None
                                                        and b is not None) else None
            candidates.append(Candidate(p.move, p.engines, dict(vals), regret))

        classification = self._classify(unanimous, tuple(candidates), roots, tol, do_cross, notes)
        gap = any(proof_gap(a, b) for a, b in _pairs(roots)) or any(
            proof_gap(a, b) for c in candidates for a, b in _pairs(c.values))
        return ConsensusResult(analysis, classification, unanimous, round(agreement, 4),
                               tuple(candidates), roots, do_cross, tol, gap, tuple(notes))

    # ---------------------------------------------------------------- internals

    def evaluate_move(self, request: AnalysisRequest, move: Move, engines: tuple[str, ...],
                       notes: list[str]) -> dict[str, MoveValue]:
        after = apply_move(request.position, move)
        if not legal_moves(after):
            return {e: terminal_win() for e in engines}
        follow_up = AnalysisRequest(request.ruleset, request.root, request.limit,
                                    (*request.moves, move), mode="analyze")
        out: dict[str, MoveValue] = {}
        for engine_id in engines:  # sequential on purpose: equal conditions (ADR-008)
            try:
                adapter = self.pool.get(engine_id)
                adapter.new_game()
                r = adapter.analyze(follow_up)
            except (EngineError, ValueError) as exc:
                notes.append(f"cross-evaluation by {engine_id} failed: {exc}")
                continue
            if r.status is not AnalysisStatus.OK or r.final_info is None:
                notes.append(f"cross-evaluation by {engine_id} returned {r.status.value}")
                out[engine_id] = MoveValue(None, OutcomeClass.UNKNOWN, None)
                continue
            out[engine_id] = value_after_move(r.final_info.score)
        return out

    @staticmethod
    def _classify(unanimous: bool, candidates: tuple[Candidate, ...], roots: dict[str, MoveValue],
                  tol: dict[str, float], cross: bool, notes: list[str]) -> Divergence:
        if any(contradicts(a, b) for a, b in _pairs(roots)) or any(
                contradicts(a, b) for c in candidates for a, b in _pairs(c.values)):
            return Divergence.OUTCOME_CONFLICT
        if unanimous:
            return Divergence.NONE
        if not cross:
            notes.append("engines disagree but cross-evaluation was not run")
            return Divergence.PREFERENCE
        unknown = False
        for c in candidates:
            for engine_id, r in c.regret.items():
                if r is None:
                    unknown = True
                elif r > tol[engine_id]:
                    return Divergence.PREFERENCE
        if unknown:
            notes.append("some regrets are unknown (missing scores or unknown score perspective)")
            return Divergence.PREFERENCE
        return Divergence.EQUIVALENT_ALTERNATIVES
