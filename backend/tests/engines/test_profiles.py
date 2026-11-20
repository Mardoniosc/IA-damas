from __future__ import annotations

import pytest

from damas_ai.engines.hub.profiles import GENERIC, KINGSROW, SCAN, select_profile


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


@pytest.mark.parametrize(
    ("text", "kind", "distance"),
    [
        ("0.00", "eval", None),
        ("1.18", "eval", None),
        ("-34.99", "eval", None),
        ("39.93", "end_band", 7),      # observed: same win-in-7 that Scan reported as 99.93
        ("-39.92", "end_band", 8),
        ("39.97", "end_band", 3),
    ],
)
def test_kingsrow_score_bands_from_g5_observation(text: str, kind: str, distance: int | None) -> None:
    score = KINGSROW.classify_score(text)
    assert (score.kind, score.distance_plies, score.perspective) == (kind, distance, "side_to_move")


def test_kingsrow_profile_refuses_unimplemented_limits() -> None:
    from damas_ai.engines.types import LimitKind

    assert KINGSROW.limits == frozenset({LimitKind.MOVE_TIME})


def test_profile_selection_is_by_reported_name_only() -> None:
    assert select_profile("Scan") is SCAN and select_profile(" scan ") is SCAN
    assert select_profile("Kingsrow") is KINGSROW
    assert select_profile("SomethingElse") is GENERIC
