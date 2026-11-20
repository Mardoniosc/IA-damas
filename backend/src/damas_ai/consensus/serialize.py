"""JSON views of consensus results (schema_version 1)."""

from __future__ import annotations

from typing import Any

from damas_ai.analysis.serialize import move_view, multi_view
from damas_ai.consensus.analyzer import ConsensusResult
from damas_ai.consensus.values import MoveValue
from damas_ai.rules import Position


def _value(v: MoveValue) -> dict[str, Any]:
    return {"utility": v.utility, "outcome": v.outcome.value, "raw": v.raw,
            "distance_plies": v.distance_plies, "source": v.source}


def consensus_view(c: ConsensusResult, position: Position, transcript: bool = False) -> dict[str, Any]:
    g = position.geometry
    return {
        "schema_version": 1,
        "classification": c.classification.value,
        "unanimous": c.unanimous,
        "agreement_ratio": c.agreement_ratio,
        "cross_checked": c.cross_checked,
        "tolerance": c.tolerance,
        "proof_gap": c.proof_gap,
        "root_values": {k: _value(v) for k, v in c.root_values.items()},
        "max_regret": c.max_regret(),
        "candidates": [
            {"move": move_view(g, cand.move), "proposed_by": list(cand.proposed_by),
             "values": {e: _value(v) for e, v in cand.values.items()},
             "regret": cand.regret}
            for cand in c.candidates
        ],
        "notes": list(c.notes),
        "analysis": multi_view(c.analysis, position, transcript),
    }
