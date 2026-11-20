"""HTTP API (FastAPI), first introduced in G6. Local-first: no authentication, so bind to
127.0.0.1 only.

    uvicorn --factory damas_ai.api.app:create_app --host 127.0.0.1 --port 8000

Endpoints: GET /health, GET /variants, GET /engines, POST /analyses, POST /consensus (G7),
POST /adaptive (G8), POST /tactics (G9), POST /decision and POST /strategy (G10),
GET /kb/stats, GET /kb/positions, GET /kb/positions/{id} (G11).
Analysis endpoints are synchronous (FastAPI runs them in its worker thread pool); engines
serialize concurrent requests per process (ADR-007).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

import damas_ai
from damas_ai.adaptive import AdaptiveAnalyzer, EscalationPolicy
from damas_ai.adaptive.serialize import adaptive_view
from damas_ai.analysis import EnginePool, MultiEngineAnalyzer
from damas_ai.analysis.serialize import multi_view
from damas_ai.config import Settings, load_engine_configs
from damas_ai.consensus import DEFAULT_TOLERANCE, ConsensusAnalyzer
from damas_ai.consensus.serialize import consensus_view
from damas_ai.decision import DecisionMaker
from damas_ai.decision.serialize import decision_view
from damas_ai.strategy import profile
from damas_ai.engines import AnalysisRequest, SearchLimit
from damas_ai.kb import KnowledgeBase
from damas_ai.rules import RULESETS, IllegalMoveError, Ruleset, apply_move
from damas_ai.rules.notation import NotationError, from_fen, parse_move
from damas_ai.tactics import Thresholds, assess
from damas_ai.tactics.serialize import criticality_view


class LimitBody(BaseModel):
    move_time_s: float | None = Field(default=None, gt=0, le=600)
    depth: int | None = Field(default=None, gt=0, le=200)
    nodes: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _exactly_one(self) -> LimitBody:
        if sum(v is not None for v in (self.move_time_s, self.depth, self.nodes)) != 1:
            raise ValueError("give exactly one of move_time_s, depth, nodes")
        return self


class AnalysisBody(BaseModel):
    variant: str
    fen: str = Field(description="PDN FEN of the root position, e.g. W:W31-50:B1-20")
    moves: list[str] = Field(default_factory=list,
                             description="moves played from the root (numeric or algebraic)")
    limit: LimitBody
    engines: list[str] | None = None
    mode: Literal["parallel", "sequential"] = "parallel"
    transcript: bool = False


class ConsensusBody(AnalysisBody):
    mode: Literal["parallel", "sequential"] = "sequential"  # equal conditions (ADR-008)
    cross_check: Literal["disagreement", "always", "never"] = "disagreement"
    tolerance: float = Field(default=DEFAULT_TOLERANCE, ge=0, le=50)


class AdaptiveBody(ConsensusBody):
    factor: float = Field(default=2.0, gt=1, le=10)
    max_steps: int = Field(default=3, ge=1, le=6)
    max_move_time_s: float = Field(default=10.0, gt=0, le=600)


class DecisionBody(ConsensusBody):
    weights: dict[str, float] = Field(default_factory=dict)
    max_candidates: int = Field(default=4, ge=1, le=8)


class StrategyBody(BaseModel):
    variant: str
    fen: str
    moves: list[str] = Field(default_factory=list)


class TacticsBody(BaseModel):
    variant: str
    fen: str
    moves: list[str] = Field(default_factory=list)
    depth: int = Field(default=6, ge=1, le=10, description="internal engine depth")
    consensus: bool = Field(default=False, description="add the G7 divergence signal")
    engines: list[str] | None = None
    consensus_move_time_s: float = Field(default=0.2, gt=0, le=60)


def _ruleset(variant: str) -> Ruleset:
    for r in RULESETS.values():
        if r.variant == variant:
            return r
    raise HTTPException(422, f"unknown variant {variant!r}; known: "
                             f"{sorted(r.variant for r in RULESETS.values())}")


def create_app(settings: Settings | None = None, pool: EnginePool | None = None,
               kb: KnowledgeBase | None = None) -> FastAPI:
    settings = settings or Settings()
    owns_pool = pool is None
    if pool is None:
        path: Path | None = settings.engines_config
        configs = load_engine_configs(path).values() if path else []
        pool = EnginePool(configs, settings.engine_thread_budget)
    the_pool = pool
    if kb is None and settings.database_url:
        kb = KnowledgeBase(settings.database_url)  # schema via `python -m damas_ai.kb migrate`
    the_kb = kb

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_pool:
            the_pool.close()

    app = FastAPI(title="Damas Super AI", version=damas_ai.__version__, lifespan=lifespan)
    analyzer = MultiEngineAnalyzer(the_pool)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": damas_ai.__version__,
                "engines_configured": len(the_pool.engine_ids())}

    @app.get("/variants")
    def variants() -> list[dict[str, Any]]:
        return [{"variant": r.variant, "ruleset_id": r.id, "provisional": r.provisional,
                 "board_size": r.geometry.size, "engines": the_pool.engines_for_variant(r.variant),
                 "notes": list(r.notes)} for r in RULESETS.values()]

    @app.get("/engines")
    def engines() -> list[dict[str, Any]]:
        return [asdict(s) for s in the_pool.status()]

    consensus = ConsensusAnalyzer(the_pool)

    @app.post("/analyses")
    def analyses(body: AnalysisBody) -> dict[str, Any]:
        request = _build_request(body)
        result = analyzer.analyze(request, body.engines, body.mode)
        return multi_view(result, request.position, body.transcript)

    @app.post("/consensus")
    def consensus_endpoint(body: ConsensusBody) -> dict[str, Any]:
        request = _build_request(body)
        result = consensus.analyze(request, body.engines, body.mode, body.cross_check, body.tolerance)
        return consensus_view(result, request.position, body.transcript)

    adaptive = AdaptiveAnalyzer(the_pool)

    @app.post("/adaptive")
    def adaptive_endpoint(body: AdaptiveBody) -> dict[str, Any]:
        request = _build_request(body)
        policy = EscalationPolicy(factor=body.factor, max_steps=body.max_steps,
                                  max_move_time_s=body.max_move_time_s)
        result = adaptive.analyze(request, body.engines, policy, body.mode, body.cross_check,
                                  body.tolerance)
        return adaptive_view(result, request.position, body.transcript)

    @app.post("/tactics")
    def tactics_endpoint(body: TacticsBody) -> dict[str, Any]:
        request = _build_request(AnalysisBody(
            variant=body.variant, fen=body.fen, moves=body.moves,
            limit=LimitBody(move_time_s=body.consensus_move_time_s), engines=body.engines))
        divergence, gap = None, False
        if body.consensus:
            c = consensus.analyze(request, body.engines)
            divergence, gap = c.classification.value, c.proof_gap
        report = assess(request.position, Thresholds(depth=body.depth), divergence, gap)
        return criticality_view(report)

    decider = DecisionMaker(the_pool)

    @app.post("/decision")
    def decision_endpoint(body: DecisionBody) -> dict[str, Any]:
        request = _build_request(body)
        d = decider.decide(request, body.engines, body.mode, body.tolerance, body.weights,
                           body.max_candidates)
        return decision_view(d, request.position)

    @app.post("/strategy")
    def strategy_endpoint(body: StrategyBody) -> dict[str, Any]:
        request = _build_request(AnalysisBody(variant=body.variant, fen=body.fen, moves=body.moves,
                                              limit=LimitBody(move_time_s=1.0)))
        sp = profile(request.position)
        return {"white": asdict(sp.white), "black": asdict(sp.black), "delta": sp.delta(),
                "notes": sp.notes(), "side_to_move": sp.side_to_move.value}

    def _kb() -> KnowledgeBase:
        if the_kb is None:
            raise HTTPException(503, "knowledge base not configured (DAMAS_DATABASE_URL)")
        return the_kb

    @app.get("/kb/stats")
    def kb_stats() -> dict[str, Any]:
        return _kb().stats()

    @app.get("/kb/positions")
    def kb_positions(variant: str | None = None, tag: str | None = None,
                     classification: str | None = None, critical: bool | None = None,
                     limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = _kb().find(variant, tag, classification, critical, min(max(limit, 1), 500), max(offset, 0))
        return [asdict(r) for r in rows]

    @app.get("/kb/positions/{position_id}")
    def kb_position(position_id: int) -> dict[str, Any]:
        detail = _kb().get(position_id)
        if detail is None:
            raise HTTPException(404, "position not found")
        return detail

    return app


def _build_request(body: AnalysisBody) -> AnalysisRequest:
    ruleset = _ruleset(body.variant)
    try:
        root = from_fen(ruleset.geometry, body.fen)
        moves, p = [], root
        for text in body.moves:
            m = parse_move(p, text)
            moves.append(m)
            p = apply_move(p, m)
        limit = SearchLimit(depth=body.limit.depth, nodes=body.limit.nodes,
                            move_time_s=body.limit.move_time_s)
        request = AnalysisRequest(ruleset, root, limit, tuple(moves))
    except (NotationError, IllegalMoveError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if not request.state.legal_moves():
        raise HTTPException(422, "the position is terminal (no legal moves)")
    return request
