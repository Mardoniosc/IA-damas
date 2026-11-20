"""JSON view of criticality reports (schema_version 1)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from damas_ai.analysis.serialize import move_view
from damas_ai.rules.notation import format_move, to_fen, to_numeric
from damas_ai.tactics.critical import CriticalityReport


def criticality_view(r: CriticalityReport) -> dict[str, Any]:
    g = r.position.geometry
    return {
        "schema_version": 1,
        "position": {"fen": to_fen(r.position), "dsa": r.position.to_dsa()},
        "critical": r.critical,
        "reasons": list(r.reasons),
        "shots": [{"first_move": move_view(g, s.first_move), "gain_men": s.gain / 100,
                   "sacrifice": s.sacrifice, "s_quiet_moves": s.s_quiet_moves,
                   "line": [format_move(g, m) for m in s.line]} for s in r.shots[:5]],
        "threat": {"max_pieces": r.threat.max_pieces,
                   "squares": sorted(to_numeric(g, s) for s in r.threat.squares)},
        "move_values": [{"move": format_move(g, v.move), "score_men": v.score / 100}
                        for v in r.move_values],
        "gap_men": None if r.gap is None else r.gap / 100,
        "best_move_changes": r.best_move_changes,
        "score_swing_men": r.score_swing / 100,
        "divergence": r.divergence,
        "proof_gap": r.proof_gap,
        "thresholds": asdict(r.thresholds),
        "source": "internal engine (untuned baseline) + forcing detector; see ADR-011",
    }
