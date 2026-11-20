"""Multi-engine analysis: one position, several engines, results side by side (ADR-008).

G6 is descriptive: it reports what each engine proposes, grouped by move. Agreement metrics,
divergence detection and score calibration are G7.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from damas_ai.analysis.pool import EnginePool
from damas_ai.engines import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    EngineError,
    SearchLimit,
)
from damas_ai.rules import Move

log = logging.getLogger("damas_ai.analysis")

RunMode = Literal["parallel", "sequential"]


@dataclass(frozen=True)
class EngineOutcome:
    """Either a result (the engine ran) or an error (it could not be asked)."""

    engine_id: str
    result: AnalysisResult | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.status is AnalysisStatus.OK


@dataclass(frozen=True)
class MoveProposal:
    move: Move
    engines: tuple[str, ...]


@dataclass(frozen=True)
class MultiAnalysisResult:
    run_id: str
    started_at: str
    elapsed_s: float
    mode: RunMode
    variant: str
    ruleset_id: str
    position_dsa: str
    limit: SearchLimit
    requested_engines: tuple[str, ...]
    outcomes: tuple[EngineOutcome, ...]
    note: str = ""
    config_fingerprint: str = ""
    proposals: tuple[MoveProposal, ...] = field(default=())

    @property
    def engines_ok(self) -> tuple[str, ...]:
        return tuple(o.engine_id for o in self.outcomes if o.ok)


def _proposals(outcomes: tuple[EngineOutcome, ...]) -> tuple[MoveProposal, ...]:
    groups: dict[tuple[int, int, frozenset[int]], tuple[Move, list[str]]] = {}
    for o in outcomes:
        if o.ok and o.result is not None and o.result.best_move is not None:
            m = o.result.best_move
            groups.setdefault(m.identity, (m, []))[1].append(o.engine_id)
    ordered = sorted(groups.values(), key=lambda g: (-len(g[1]), sorted(g[1])))
    return tuple(MoveProposal(m, tuple(sorted(ids))) for m, ids in ordered)


def config_fingerprint(pool: EnginePool, engine_ids: tuple[str, ...]) -> str:
    """Stable hash of the engine configs used (for reproducibility records)."""
    data = {i: pool.configs[i].model_dump(mode="json") for i in engine_ids if i in pool.configs}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


class MultiEngineAnalyzer:
    def __init__(self, pool: EnginePool) -> None:
        self.pool = pool

    def analyze(
        self,
        request: AnalysisRequest,
        engines: list[str] | None = None,
        mode: RunMode = "parallel",
    ) -> MultiAnalysisResult:
        variant = request.ruleset.variant
        capable = self.pool.engines_for_variant(variant)
        if engines is None:
            selected = tuple(capable)
        else:
            selected = tuple(dict.fromkeys(engines))  # keep order, drop duplicates
        started = datetime.now(UTC).isoformat(timespec="seconds")
        t0 = time.perf_counter()

        def run(engine_id: str) -> EngineOutcome:
            if engine_id not in self.pool.configs:
                return EngineOutcome(engine_id, None, "unknown or disabled engine")
            if engine_id not in capable:
                native = self.pool.configs[engine_id].native_variant
                return EngineOutcome(engine_id, None, f"engine plays {native}, not {variant}")
            try:
                adapter = self.pool.get(engine_id)
                adapter.new_game()
                return EngineOutcome(engine_id, adapter.analyze(request))
            except (EngineError, ValueError) as exc:
                log.warning("engine could not analyse", extra={"ctx": {"engine": engine_id,
                                                                         "error": str(exc)}})
                return EngineOutcome(engine_id, None, f"{type(exc).__name__}: {exc}")

        if mode == "parallel" and len(selected) > 1:
            with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="analysis") as ex:
                outcomes = tuple(ex.map(run, selected))
        else:
            outcomes = tuple(run(e) for e in selected)

        note = ""
        if not capable:
            note = (f"no configured engine plays {variant}; external analysis is unavailable "
                    f"for this variant (see ADR-005)")
        result = MultiAnalysisResult(
            run_id=uuid.uuid4().hex,
            started_at=started,
            elapsed_s=round(time.perf_counter() - t0, 4),
            mode=mode,
            variant=variant,
            ruleset_id=request.ruleset.id,
            position_dsa=request.position.to_dsa(),
            limit=request.limit,
            requested_engines=selected,
            outcomes=outcomes,
            note=note,
            config_fingerprint=config_fingerprint(self.pool, selected),
            proposals=_proposals(outcomes),
        )
        log.info("multi-engine analysis", extra={"ctx": {
            "run_id": result.run_id, "variant": variant, "engines": list(selected),
            "ok": list(result.engines_ok), "elapsed_s": result.elapsed_s, "mode": mode}})
        return result
