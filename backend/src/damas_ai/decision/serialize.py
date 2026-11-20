"""JSON view of decisions (schema_version 1)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from damas_ai.analysis.serialize import move_view
from damas_ai.decision.maker import Decision
from damas_ai.rules import Position
from damas_ai.rules.notation import to_fen


def decision_view(d: Decision, position: Position) -> dict[str, Any]:
    g = position.geometry
    return {
        "schema_version": 1,
        "position": {"fen": to_fen(position)},
        "move": move_view(g, d.move),
        "confidence": d.confidence,
        "reasons": list(d.reasons),
        "engines": list(d.engines),
        "candidates": [
            {"move": move_view(g, c.move), "sources": list(c.sources),
             "values": {e: {"utility": v.utility, "outcome": v.outcome.value, "raw": v.raw}
                        for e, v in c.values.items()},
             "normalized_regret": c.normalized_regret, "vetoed_by": list(c.vetoed_by),
             "max_regret": c.max_regret, "mean_regret": c.mean_regret}
            for c in d.candidates
        ],
        "shot": None if d.shot is None else {"move": move_view(g, d.shot.first_move),
                                             "gain_men": d.shot.gain / 100,
                                             "sacrifice": d.shot.sacrifice},
        "strategy": {"white": asdict(d.strategy.white), "black": asdict(d.strategy.black),
                     "notes": d.strategy.notes()},
        "notes": list(d.notes),
    }
