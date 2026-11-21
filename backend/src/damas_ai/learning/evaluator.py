"""Learned evaluation for the internal search (G14, ADR-016).

``LinearEvaluator`` computes the CHEAP features (men, kings, tempo, center, back_rank) in one
pass over the board, exactly as ``strategy.features`` defines them, from the side to move's
view. It returns ``logit / logit_per_man`` in hundredths of a man, so 1 man stays ≈ 100 and win
scores (``searcher.WIN``) remain far above any evaluation.
"""

from __future__ import annotations

from pathlib import Path

from damas_ai.learning.linear import CHEAP, LinearModel
from damas_ai.rules import Color, Position
from damas_ai.rules.position import Piece

_WM, _WK, _BM, _BK = Piece.WHITE_MAN, Piece.WHITE_KING, Piece.BLACK_MAN, Piece.BLACK_KING


def cheap_features(position: Position) -> tuple[int, int, int, int, int]:
    """(men, kings, tempo, center, back_rank) deltas from the side to move's view."""
    g = position.geometry
    size = g.size
    lo, hi = size // 4, size - 1 - size // 4
    men = kings = tempo = center = back = 0
    for sq, piece in enumerate(position.squares):
        if piece == Piece.EMPTY:
            continue
        f, r = g.coords[sq]
        white = piece in (_WM, _WK)
        s = 1 if white else -1
        if lo <= f <= hi and lo <= r <= hi:
            center += s
        if piece in (_WK, _BK):
            kings += s
            continue
        men += s
        adv = r if white else size - 1 - r
        tempo += s * adv
        if adv == 0:
            back += s
    sign = 1 if position.side_to_move is Color.WHITE else -1
    return sign * men, sign * kings, sign * tempo, sign * center, sign * back


class ResidualEvaluator:
    """Baseline hand eval plus learned positional adjustments (G14 experiment).

    The model's features are ``("baseline_eval", "tempo", "center", "back_rank")`` where
    ``baseline_eval`` is the G8 eval in men. The output keeps the baseline scale (hundredths of a
    man): ``baseline + 100 * (w_t·tempo + w_c·center + w_b·back + bias) / w_baseline``.
    """

    FEATURES = ("baseline_eval", "tempo", "center", "back_rank")

    def __init__(self, model: LinearModel) -> None:
        if model.features != self.FEATURES:
            raise ValueError(f"residual model needs features {self.FEATURES}")
        if model.weights[0] <= 0:
            raise ValueError("the baseline weight must be positive")
        self.model = model
        self.w = model.weights

    def __call__(self, position: Position) -> int:
        from damas_ai.search.evaluation import evaluate

        _, _, tempo, center, back = cheap_features(position)
        adj = self.model.bias + self.w[1] * tempo + self.w[2] * center + self.w[3] * back
        return evaluate(position) + int(round(100 * adj / self.w[0]))


class LinearEvaluator:
    def __init__(self, model: LinearModel) -> None:
        if model.features != CHEAP:
            raise ValueError(f"the search evaluator needs the CHEAP features {CHEAP}, got {model.features}")
        self.model = model
        self.w = model.weights
        men_w = model.weights[0]
        if men_w <= 0:
            raise ValueError("the model's weight for men must be positive")
        self.scale = 100.0 / men_w  # hundredths of a man per logit unit

    @classmethod
    def load(cls, path: Path) -> LinearEvaluator:
        return cls(LinearModel.from_json(path.read_text(encoding="utf-8")))

    def __call__(self, position: Position) -> int:
        f = cheap_features(position)
        w = self.w
        logit = self.model.bias + w[0] * f[0] + w[1] * f[1] + w[2] * f[2] + w[3] * f[3] + w[4] * f[4]
        return int(round(logit * self.scale))


def load_evaluator(path: Path) -> LinearEvaluator | ResidualEvaluator:
    """Load a learned model and pick the evaluator matching its feature set."""
    model = LinearModel.from_json(path.read_text(encoding="utf-8"))
    if model.features == ResidualEvaluator.FEATURES:
        return ResidualEvaluator(model)
    return LinearEvaluator(model)
