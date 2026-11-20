from __future__ import annotations

import pytest

from damas_ai.engines.hub.profiles import GENERIC, SCAN, select_profile


@pytest.mark.parametrize(
    ("text", "kind", "distance"),
    [
        ("0.15", "eval", None),
        ("-1.50", "eval", None),
        ("80.00", "eval", None),        # Eval_Inf: heuristic evals are clamped here
        ("89.43", "win_band", 57),      # BB_Inf - 57 plies
        ("-89.10", "win_band", 90),
        ("99.99", "end_band", 1),       # Inf - 1 ply
        ("-99.02", "end_band", 98),
        ("94.90", "end_band", 510),     # observed from the real engine in G4
        ("abc", "unknown", None),
    ],
)
def test_scan_score_bands_from_source_constants(text: str, kind: str, distance: int | None) -> None:
    score = SCAN.classify_score(text)
    assert (score.kind, score.distance_plies) == (kind, distance)
    assert score.unit == "men" and score.text == text and score.perspective == "side_to_move"


def test_generic_profile_never_interprets_bands() -> None:
    score = GENERIC.classify_score("99.5")
    assert (score.kind, score.unit, score.value, score.perspective) == ("eval", "unknown", 99.5, "unknown")


def test_profile_selection_is_by_reported_name_only() -> None:
    assert select_profile("Scan") is SCAN and select_profile(" scan ") is SCAN
    assert select_profile("Kingsrow") is GENERIC  # unverified (G1 Q3) -> generic
