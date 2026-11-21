"""Game review endpoints (G15 follow-up): parse a PDN upload and analyse one of its games.

    POST /games/parse    {"pdn": "..."}  -> games with tags, ply count and replay status
    POST /games/analyze  {"pdn": "...", "index": 0, "engine": null, "limit": {"depth": 5}}

Every game is replayed through the Rules Core (ADR-001/015). The analysis uses one judge engine
(G13): it is labelled with that engine's name and its known biases.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from damas_ai.analysis import EnginePool
from damas_ai.engines import CapabilityError, EngineError, SearchLimit
from damas_ai.games.analysis import analyze_game
from damas_ai.games.pdn import GAMETYPES, parse_pdn, replay, ruleset_for
from damas_ai.rules import RULESETS, Ruleset
from damas_ai.rules.notation import NotationError, format_move, parse_move, to_fen

MAX_PDN = 5_000_000


class PdnBody(BaseModel):
    pdn: str = Field(max_length=MAX_PDN)
    variant: str | None = Field(default=None, description="override when GameType is missing/unknown")


class ReviewLimit(BaseModel):
    depth: int | None = Field(default=None, ge=1, le=12)
    move_time_s: float | None = Field(default=None, gt=0, le=30)

    @model_validator(mode="after")
    def _one(self) -> ReviewLimit:
        if (self.depth is None) == (self.move_time_s is None):
            raise ValueError("give exactly one of depth, move_time_s")
        return self


class AnalyzeGameBody(PdnBody):
    index: int = Field(ge=0)
    engine: str | None = None
    limit: ReviewLimit = Field(default_factory=lambda: ReviewLimit(depth=5))


def _variant_ruleset(variant: str | None) -> Ruleset | None:
    if variant is None:
        return None
    for r in RULESETS.values():
        if r.variant == variant:
            return r
    raise HTTPException(422, f"unknown variant {variant!r}")


def games_router(pool: EnginePool) -> APIRouter:
    router = APIRouter(prefix="/games", tags=["games"])

    @router.post("/parse")
    def parse(body: PdnBody) -> dict[str, Any]:
        default = _variant_ruleset(body.variant)
        out = []
        for i, g in enumerate(parse_pdn(body.pdn)):
            entry: dict[str, Any] = {
                "index": i, "white": g.tags.get("White", "?"), "black": g.tags.get("Black", "?"),
                "result": g.result, "date": g.tags.get("Date"), "event": g.tags.get("Event"),
                "site": g.tags.get("Site"), "plies": len(g.moves)}
            try:
                rs = ruleset_for(g, default)
                r = replay(g, rs)
                entry.update(variant=rs.variant, ok=r.ok, error=r.error)
            except ValueError as exc:
                entry.update(variant=None, ok=False, error=str(exc))
            out.append(entry)
        return {"games": out, "supported_gametypes": sorted(GAMETYPES)}

    @router.post("/analyze")
    def analyze(body: AnalyzeGameBody) -> dict[str, Any]:
        games = parse_pdn(body.pdn)
        if body.index >= len(games):
            raise HTTPException(422, f"game index {body.index} out of range (0..{len(games) - 1})")
        g = games[body.index]
        try:
            rs = ruleset_for(g, _variant_ruleset(body.variant))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        r = replay(g, rs)
        if not r.ok:
            raise HTTPException(422, f"game does not replay: {r.error}")
        engine_id = body.engine or next(iter(pool.engines_for_variant(rs.variant)), None)
        if engine_id is None:
            raise HTTPException(422, f"no configured engine plays {rs.variant}")
        if engine_id not in pool.engines_for_variant(rs.variant):
            raise HTTPException(422, f"engine {engine_id!r} does not play {rs.variant}")
        limit = SearchLimit(depth=body.limit.depth, move_time_s=body.limit.move_time_s)
        try:
            adapter = pool.get(engine_id)
            if limit.kind not in adapter.capabilities().limits:
                kinds = sorted(k.value for k in adapter.capabilities().limits)
                raise HTTPException(422, f"engine {engine_id} supports only {kinds} limits")
            ga = analyze_game(r, adapter, limit)
        except (EngineError, CapabilityError) as exc:
            raise HTTPException(503, f"engine {engine_id}: {exc}") from exc

        geo = r.start.geometry
        plies = []
        for p in ga.plies:
            pos = r.states[p.ply - 1].position
            best_alg = None
            if p.best:
                try:
                    best_alg = format_move(geo, parse_move(pos, p.best), "algebraic")
                except NotationError:
                    best_alg = None
            proven = p.regret is not None and p.regret >= 5_000
            plies.append({
                "ply": p.ply, "move_number": (p.ply + 1) // 2, "side": p.side, "player": p.player,
                "played": {"numeric": p.played, "algebraic": format_move(geo, r.moves[p.ply - 1], "algebraic")},
                "best": None if p.best is None else {"numeric": p.best, "algebraic": best_alg},
                "regret_men": None if p.regret is None or proven else round(p.regret, 2),
                "throws_away_proven_result": proven, "label": p.label, "forced": p.forced,
                "fen_before": to_fen(pos),
            })
        info = adapter.info
        return {
            "game": {"index": body.index, "white": ga.white, "black": ga.black, "result": ga.result,
                     "variant": rs.variant, "ruleset_id": rs.id, "start_fen": to_fen(r.start),
                     "tags": g.tags},
            "engine": {"id": engine_id, "name": info.name, "version": info.version, "profile": info.profile},
            "limit": {"depth": limit.depth, "move_time_s": limit.move_time_s},
            "summary": ga.summary(),
            "plies": plies,
            "final_fen": to_fen(r.states[-1].position),
            "caveats": [
                f"single judge: {info.name} {info.version} ({info.profile})",
                "labels use provisional thresholds: good <= 0.10, inaccuracy <= 0.50, mistake <= 1.50 men",
                *(["Brazilian draw rules are provisional (G2)"] if rs.variant == "brazilian-8x8" else []),
            ],
        }

    return router
