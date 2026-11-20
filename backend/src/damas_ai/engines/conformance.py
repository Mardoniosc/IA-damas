"""Rules-conformance suite: does an engine's chosen move belong to the Rules Core's legal set?

This is the empirical gate of ADR-002 §6. An engine must pass it on its declared variant
before its output is used. Positions should cover forced and majority captures, kings and
promotions (the G2 oracle fixtures do).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from damas_ai.engines.base import EngineAdapter
from damas_ai.engines.types import AnalysisRequest, AnalysisResult, AnalysisStatus, SearchLimit
from damas_ai.rules import Position, Ruleset, legal_moves


@dataclass(frozen=True)
class ConformanceReport:
    engine_id: str
    variant: str
    total: int
    by_status: dict[str, int]
    failures: tuple[AnalysisResult, ...]
    skipped_terminal: int

    @property
    def passed(self) -> bool:
        return self.total > 0 and self.by_status.get(AnalysisStatus.OK.value, 0) == self.total

    @property
    def legal_rate(self) -> float:
        return self.by_status.get(AnalysisStatus.OK.value, 0) / self.total if self.total else 0.0


def run_conformance(
    engine: EngineAdapter,
    ruleset: Ruleset,
    positions: Iterable[Position],
    limit: SearchLimit,
    max_failures_kept: int = 20,
) -> ConformanceReport:
    counts: Counter[str] = Counter()
    failures: list[AnalysisResult] = []
    total = skipped = 0
    for position in positions:
        if not legal_moves(position):
            skipped += 1
            continue
        engine.new_game()
        result = engine.analyze(AnalysisRequest(ruleset, position, limit))
        total += 1
        counts[result.status.value] += 1
        if result.status is not AnalysisStatus.OK and len(failures) < max_failures_kept:
            failures.append(result)
        if not engine.running:
            break  # crashed or killed: stop, the report shows where
    return ConformanceReport(engine.engine_id, ruleset.variant, total, dict(counts),
                             tuple(failures), skipped)
