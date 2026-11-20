"""Descriptive scale relation between two engines' heuristic evals (ADR-009).

This is NOT a calibration to truth: it only says how engine B's numbers relate to engine A's
on the same positions. Calibration against game outcomes needs result data (G12/G13).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleFit:
    n: int
    slope_through_origin: float | None   # least-squares b in  y ≈ b·x
    median_ratio: float | None           # median of y/x over pairs with |x| >= min_abs
    pearson_r: float | None
    sign_agreement: float | None         # share of pairs with the same sign (both |.| >= min_abs)


def fit_scale(pairs: Iterable[tuple[float, float]], min_abs: float = 0.2) -> ScaleFit:
    """Fit y (engine B) against x (engine A) for heuristic evals of the same positions."""
    data = [(x, y) for x, y in pairs if math.isfinite(x) and math.isfinite(y)]
    n = len(data)
    if n < 3:
        return ScaleFit(n, None, None, None, None)
    sxx = sum(x * x for x, _ in data)
    slope = sum(x * y for x, y in data) / sxx if sxx else None
    ratios = [y / x for x, y in data if abs(x) >= min_abs]
    median_ratio = statistics.median(ratios) if ratios else None
    xs, ys = [x for x, _ in data], [y for _, y in data]
    try:
        r = statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        r = None
    signed = [(x, y) for x, y in data if abs(x) >= min_abs and abs(y) >= min_abs]
    sign = (sum((x > 0) == (y > 0) for x, y in signed) / len(signed)) if signed else None
    return ScaleFit(n, slope, median_ratio, r, sign)
