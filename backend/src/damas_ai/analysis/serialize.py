"""JSON-ready views of analysis results (API responses and JSONL records)."""

from __future__ import annotations

from typing import Any

from damas_ai.analysis.orchestrator import EngineOutcome, MultiAnalysisResult
from damas_ai.engines import AnalysisResult, RawScore, SearchInfo, SearchLimit
from damas_ai.rules import Geometry, Move, Position
from damas_ai.rules.notation import format_move, to_fen, to_numeric

SCHEMA_VERSION = 1


def move_view(geometry: Geometry, move: Move | None) -> dict[str, Any] | None:
    if move is None:
        return None
    return {
        "numeric": format_move(geometry, move, "numeric"),
        "algebraic": format_move(geometry, move, "algebraic"),
        "captured": sorted(to_numeric(geometry, s) for s in move.captured),
        "promotes": move.promotes,
    }


def score_view(score: RawScore | None) -> dict[str, Any] | None:
    if score is None:
        return None
    return {"text": score.text, "value": score.value, "unit": score.unit, "kind": score.kind,
            "distance_plies": score.distance_plies, "perspective": score.perspective}


def limit_view(limit: SearchLimit) -> dict[str, Any]:
    return {"depth": limit.depth, "nodes": limit.nodes, "move_time_s": limit.move_time_s}


def info_view(geometry: Geometry, info: SearchInfo | None) -> dict[str, Any] | None:
    if info is None:
        return None
    return {"depth": info.depth, "nodes": info.nodes, "time_s": info.time_s,
            "score": score_view(info.score),
            "pv": [format_move(geometry, m, "numeric") for m in info.pv],
            "pv_reported": info.pv_text}


def result_view(geometry: Geometry, r: AnalysisResult, transcript: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "engine": {"id": r.engine_id, "name": r.engine_name, "version": r.engine_version},
        "status": r.status.value,
        "best_move": move_view(geometry, r.best_move),
        "best_move_reported": r.best_move_text,
        "ponder_move": move_view(geometry, r.ponder_move),
        "final_info": info_view(geometry, r.final_info),
        "info_count": len(r.infos),
        "interrupted": r.interrupted,
        "elapsed_s": r.elapsed_s,
        "violations": list(r.violations),
    }
    if transcript:
        out["transcript"] = [list(t) for t in r.transcript]
    return out


def outcome_view(geometry: Geometry, o: EngineOutcome, transcript: bool = False) -> dict[str, Any]:
    if o.result is None:
        return {"engine": {"id": o.engine_id}, "status": "not_run", "error": o.error}
    return result_view(geometry, o.result, transcript)


def multi_view(m: MultiAnalysisResult, position: Position, transcript: bool = False) -> dict[str, Any]:
    g = position.geometry
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": m.run_id,
        "started_at": m.started_at,
        "elapsed_s": m.elapsed_s,
        "mode": m.mode,
        "variant": m.variant,
        "ruleset_id": m.ruleset_id,
        "position": {"fen": to_fen(position), "dsa": m.position_dsa},
        "limit": limit_view(m.limit),
        "requested_engines": list(m.requested_engines),
        "config_fingerprint": m.config_fingerprint,
        "note": m.note,
        "proposals": [{"move": move_view(g, p.move), "engines": list(p.engines)} for p in m.proposals],
        "results": [outcome_view(g, o, transcript) for o in m.outcomes],
    }
