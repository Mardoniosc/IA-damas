"""JSON view of adaptive analyses (schema_version 1)."""

from __future__ import annotations

from typing import Any

from damas_ai.adaptive.analyzer import AdaptiveResult
from damas_ai.analysis.serialize import limit_view, move_view
from damas_ai.consensus.serialize import consensus_view
from damas_ai.rules import Position


def adaptive_view(r: AdaptiveResult, position: Position, transcript: bool = False) -> dict[str, Any]:
    g = position.geometry
    p = r.policy
    return {
        "schema_version": 1,
        "stop_reason": r.stop_reason,
        "escalated": r.escalated,
        "trajectory": list(r.trajectory),
        "policy": {"escalate_on": sorted(d.value for d in p.escalate_on),
                   "escalate_on_proof_gap": p.escalate_on_proof_gap, "factor": p.factor,
                   "max_steps": p.max_steps, "max_move_time_s": p.max_move_time_s},
        "steps": [
            {"limit": limit_view(lim), "classification": s.classification.value,
             "proof_gap": s.proof_gap, "unanimous": s.unanimous,
             "proposals": [{"move": move_view(g, pr.move), "engines": list(pr.engines)}
                           for pr in s.analysis.proposals],
             "max_regret": s.max_regret()}
            for s, lim in zip(r.steps, r.limits)
        ],
        "final": consensus_view(r.final, position, transcript),
    }
