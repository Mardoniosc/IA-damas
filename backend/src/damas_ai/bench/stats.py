"""Match statistics and score calibration (G12, ADR-014)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class MatchStats:
    games: int
    wins: int
    draws: int
    losses: int
    score: float                 # fraction for player A
    elo: float | None            # A minus B
    elo_low: float | None        # 95% CI
    elo_high: float | None
    los: float | None            # likelihood of superiority (A better than B)
    draw_rate: float


def _elo(score: float) -> float | None:
    if score <= 0.0 or score >= 1.0:
        return None
    return -400.0 * math.log10(1.0 / score - 1.0)


def match_stats(results: Sequence[float]) -> MatchStats:
    """``results`` are player A's game scores (1, 0.5, 0)."""
    n = len(results)
    w = sum(1 for r in results if r == 1.0)
    d = sum(1 for r in results if r == 0.5)
    lo_ = sum(1 for r in results if r == 0.0)
    if n == 0:
        return MatchStats(0, 0, 0, 0, 0.0, None, None, None, None, 0.0)
    s = sum(results) / n
    var = sum(r * r for r in results) / n - s * s
    se = math.sqrt(var / n) if n > 1 else 0.0
    # A bound outside (0, 1) means the Elo interval is unbounded on that side: report None.
    # Zero variance (e.g. all draws) does not mean certainty: the interval is not estimable.
    lo_s, hi_s = s - 1.96 * se, s + 1.96 * se
    los = None
    if w + lo_ > 0:
        los = 0.5 * (1.0 + math.erf((w - lo_) / math.sqrt(2.0 * (w + lo_))))
    low = _round(_elo(lo_s)) if se > 0 else None
    high = _round(_elo(hi_s)) if se > 0 else None
    return MatchStats(n, w, d, lo_, round(s, 4), _round(_elo(s)), low, high,
                      None if los is None else round(los, 4), round(d / n, 4))


def _round(x: float | None) -> float | None:
    return None if x is None else round(x, 1)


@dataclass(frozen=True)
class LogisticFit:
    n: int
    intercept: float | None
    slope: float | None          # per eval unit: P(result) = sigmoid(intercept + slope * eval)
    converged: bool


def fit_logistic(evals: Sequence[float], outcomes: Sequence[float], iterations: int = 50) -> LogisticFit:
    """1-D logistic regression of game outcome (1 / 0.5 / 0 for the evaluated side) on an eval.
    Draws enter as 0.5 targets (fractional logistic regression). Newton-Raphson (IRLS)."""
    data = [(float(x), float(y)) for x, y in zip(evals, outcomes) if math.isfinite(x)]
    n = len(data)
    if n < 5 or len({y for _, y in data}) < 2:
        return LogisticFit(n, None, None, False)
    a = b = 0.0
    for _ in range(iterations):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in data:
            p = 1.0 / (1.0 + math.exp(-(a + b * x)))
            r = y - p
            wgt = p * (1 - p)
            ga += r
            gb += r * x
            haa += wgt
            hab += wgt * x
            hbb += wgt * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            return LogisticFit(n, a, b, False)
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a + da, b + db
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            return LogisticFit(n, round(a, 4), round(b, 4), True)
    return LogisticFit(n, round(a, 4), round(b, 4), False)
