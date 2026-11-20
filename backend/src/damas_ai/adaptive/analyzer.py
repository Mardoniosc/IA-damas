"""Adaptive analysis (G8, ADR-010): spend more search effort where the engines diverge.

Run consensus (G7) at a base limit. While the position is in an escalation class (by default
``preference`` or ``outcome_conflict``, or a ``proof_gap``), multiply the limit and run again,
up to ``max_steps`` runs or a ceiling. The whole trajectory is kept, so later analysis can
see whether a divergence resolved with depth, persisted, or flipped.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from damas_ai.analysis import EnginePool
from damas_ai.analysis.orchestrator import RunMode
from damas_ai.consensus import DEFAULT_TOLERANCE, ConsensusAnalyzer, ConsensusResult, Divergence
from damas_ai.consensus.analyzer import CrossCheck
from damas_ai.engines import AnalysisRequest, SearchLimit


@dataclass(frozen=True)
class EscalationPolicy:
    escalate_on: frozenset[Divergence] = frozenset({Divergence.PREFERENCE, Divergence.OUTCOME_CONFLICT})
    escalate_on_proof_gap: bool = True
    factor: float = 2.0
    max_steps: int = 3
    max_move_time_s: float = 10.0
    max_depth: int = 64
    max_nodes: int = 10**9

    def __post_init__(self) -> None:
        if self.factor <= 1.0 or self.max_steps < 1:
            raise ValueError("factor must be > 1 and max_steps >= 1")

    def wants(self, result: ConsensusResult) -> bool:
        return result.classification in self.escalate_on or (
            self.escalate_on_proof_gap and result.proof_gap)

    def next_limit(self, limit: SearchLimit) -> SearchLimit | None:
        """The escalated limit, or None if the ceiling is reached."""
        if limit.move_time_s is not None:
            if limit.move_time_s >= self.max_move_time_s:
                return None
            return SearchLimit(move_time_s=min(self.max_move_time_s, limit.move_time_s * self.factor))
        if limit.depth is not None:
            if limit.depth >= self.max_depth:
                return None
            # Effort grows roughly exponentially with depth: one extra ply per doubling.
            step = max(1, round(math.log2(self.factor)))
            return SearchLimit(depth=min(self.max_depth, limit.depth + step))
        assert limit.nodes is not None
        if limit.nodes >= self.max_nodes:
            return None
        return SearchLimit(nodes=min(self.max_nodes, int(limit.nodes * self.factor)))


@dataclass(frozen=True)
class AdaptiveResult:
    steps: tuple[ConsensusResult, ...]
    limits: tuple[SearchLimit, ...]
    stop_reason: str  # settled | max_steps | ceiling | incomplete
    policy: EscalationPolicy = field(default_factory=EscalationPolicy)

    @property
    def final(self) -> ConsensusResult:
        return self.steps[-1]

    @property
    def escalated(self) -> bool:
        return len(self.steps) > 1

    @property
    def trajectory(self) -> tuple[str, ...]:
        return tuple(s.classification.value for s in self.steps)


class AdaptiveAnalyzer:
    def __init__(self, pool: EnginePool) -> None:
        self.consensus = ConsensusAnalyzer(pool)

    def analyze(
        self,
        request: AnalysisRequest,
        engines: list[str] | None = None,
        policy: EscalationPolicy | None = None,
        mode: RunMode = "sequential",
        cross_check: CrossCheck = "disagreement",
        tolerance: float | Mapping[str, float] = DEFAULT_TOLERANCE,
    ) -> AdaptiveResult:
        policy = policy or EscalationPolicy()
        limit = request.limit
        steps: list[ConsensusResult] = []
        limits: list[SearchLimit] = []
        while True:
            step_request = AnalysisRequest(request.ruleset, request.root, limit, request.moves,
                                           request.mode)
            result = self.consensus.analyze(step_request, engines, mode, cross_check, tolerance)
            steps.append(result)
            limits.append(limit)
            if result.classification is Divergence.INCOMPLETE:
                reason = "incomplete"
                break
            if not policy.wants(result):
                reason = "settled"
                break
            if len(steps) >= policy.max_steps:
                reason = "max_steps"
                break
            next_limit = policy.next_limit(limit)
            if next_limit is None:
                reason = "ceiling"
                break
            limit = next_limit
        return AdaptiveResult(tuple(steps), tuple(limits), reason, policy)
