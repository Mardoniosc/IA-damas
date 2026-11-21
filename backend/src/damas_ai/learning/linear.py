"""Linear (logistic) value models (G14, ADR-016).

P(outcome for the side to move) = sigmoid(b + w·x), trained on fractional targets (draw = 0.5)
with L2 regularization (Newton's method, NumPy). Features come from the side to move's view
(G13 dataset). The model is small, interpretable and cheap enough for the internal search.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

CHEAP = ("men", "kings", "tempo", "center", "back_rank")           # O(squares) per position
FULL = ("men", "kings", "tempo", "center", "back_rank", "mobility", "runaways")


def load_split(path: Path, features: Sequence[str]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    x = np.array([[r["features"][f] for f in features] for r in rows], dtype=float)
    y = np.array([r["outcome"] for r in rows], dtype=float)
    return x, y, rows


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


@dataclass
class LinearModel:
    features: tuple[str, ...]
    weights: list[float]
    bias: float
    l2: float
    train: dict[str, Any] = field(default_factory=dict)  # provenance: dataset hashes, sizes, metrics

    def predict(self, x: np.ndarray) -> np.ndarray:
        return _sigmoid(self.bias + x @ np.array(self.weights))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> LinearModel:
        d = json.loads(text)
        return cls(tuple(d["features"]), list(d["weights"]), float(d["bias"]), float(d["l2"]), d.get("train", {}))

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps([self.features, self.weights, self.bias]).encode()).hexdigest()[:12]


def fit(x: np.ndarray, y: np.ndarray, features: Sequence[str], l2: float = 1.0, iterations: int = 50) -> LinearModel:
    n, k = x.shape
    a = np.zeros(k + 1)
    xa = np.hstack([np.ones((n, 1)), x])
    reg = np.eye(k + 1) * l2
    reg[0, 0] = 0.0  # do not penalize the bias
    for _ in range(iterations):
        p = _sigmoid(xa @ a)
        grad = xa.T @ (y - p) - reg @ a
        hess = (xa * (p * (1 - p))[:, None]).T @ xa + reg
        step = np.linalg.solve(hess, grad)
        a += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return LinearModel(tuple(features), [float(v) for v in a[1:]], float(a[0]), l2)


def metrics(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Log-loss and Brier on fractional targets; accuracy on decisive positions only."""
    eps = 1e-9
    logloss = float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    brier = float(np.mean((p - y) ** 2))
    decisive = y != 0.5
    acc = float(np.mean((p[decisive] > 0.5) == (y[decisive] > 0.5))) if decisive.any() else float("nan")
    return {"logloss": round(logloss, 5), "brier": round(brier, 5), "decisive_accuracy": round(acc, 4),
            "n": int(len(y))}


def constant_baseline(y_train: np.ndarray, y: np.ndarray) -> dict[str, float]:
    return metrics(np.full_like(y, float(np.mean(y_train))), y)
