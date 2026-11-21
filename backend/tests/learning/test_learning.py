"""G14 learning system: fitting, metrics, evaluators, integration into search and Hub."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from damas_ai.config import EngineConfig
from damas_ai.engines import AnalysisRequest, AnalysisStatus, SearchLimit
from damas_ai.engines.hub.adapter import HubEngine
from damas_ai.learning import (
    CHEAP,
    LinearEvaluator,
    LinearModel,
    ResidualEvaluator,
    cheap_features,
    fit,
    load_evaluator,
    metrics,
)
from damas_ai.learning.linear import constant_baseline
from damas_ai.rules import BOARD_8X8, BRAZILIAN_PROVISIONAL, Color, legal_moves
from damas_ai.rules.notation import from_fen
from damas_ai.search import Searcher
from damas_ai.search.evaluation import evaluate
from damas_ai.strategy import profile

SRC = Path(__file__).resolve().parents[2] / "src"
MODELS = SRC / "damas_ai" / "learning" / "models"
ORACLE = Path(__file__).resolve().parents[1] / "fixtures" / "oracle" / "brazilian_pydraughts.json"


def oracle_positions(n: int = 300):  # type: ignore[no-untyped-def]
    data = json.loads(ORACLE.read_text(encoding="utf-8"))
    return [from_fen(BOARD_8X8, r["fen"]) for r in data["positions"] if r["moves"]][:n]


def test_fit_recovers_known_weights_with_fractional_targets() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(20000, 2))
    p = 1 / (1 + np.exp(-(0.3 + 1.2 * x[:, 0] - 0.7 * x[:, 1])))
    y = (rng.random(20000) < p).astype(float)
    y[rng.random(20000) < 0.1] = 0.5  # some draws
    m = fit(x, y, ("a", "b"), l2=0.0)
    assert m.weights[0] == pytest.approx(1.2 * 0.8, abs=0.25) and m.weights[0] > 0 > m.weights[1]
    assert metrics(m.predict(x), y)["logloss"] < constant_baseline(y, y)["logloss"]


def test_cheap_features_match_the_strategy_profile_exactly() -> None:
    for p in oracle_positions():
        d = profile(p).delta()
        sign = 1 if p.side_to_move is Color.WHITE else -1
        assert cheap_features(p) == tuple(sign * d[k] for k in CHEAP)


def test_linear_evaluator_scale_and_validation() -> None:
    model = LinearModel(CHEAP, [0.8, 0.8, 0.0, 0.0, 0.0], 0.0, 1.0)
    ev = LinearEvaluator(model)
    p = from_fen(BOARD_8X8, "W:W21,22:B1")  # side to move is a man up
    assert ev(p) == 100
    assert ev(p.with_side(Color.BLACK)) == -100
    with pytest.raises(ValueError):
        LinearEvaluator(LinearModel(("men",), [1.0], 0.0, 1.0))
    with pytest.raises(ValueError):
        LinearEvaluator(LinearModel(CHEAP, [-0.1, 0, 0, 0, 0], 0.0, 1.0))


def test_residual_evaluator_reduces_to_baseline_without_adjustments() -> None:
    model = LinearModel(ResidualEvaluator.FEATURES, [0.5, 0.0, 0.0, 0.0], 0.0, 1.0)
    ev = ResidualEvaluator(model)
    for p in oracle_positions(100):
        assert ev(p) == evaluate(p)


def test_committed_models_load_with_provenance() -> None:
    linear = load_evaluator(MODELS / "brazilian_linear_v1.json")
    residual = load_evaluator(MODELS / "brazilian_residual_v1.json")
    assert isinstance(linear, LinearEvaluator) and isinstance(residual, ResidualEvaluator)
    for ev in (linear, residual):
        assert ev.model.train["manifest_sha256"] and ev.model.train["test"]["n"] > 1000
    again = LinearModel.from_json(linear.model.to_json())
    assert again.fingerprint() == linear.model.fingerprint()


def test_search_with_learned_evaluator_is_legal_and_deterministic() -> None:
    ev = load_evaluator(MODELS / "brazilian_residual_v1.json")
    p = BRAZILIAN_PROVISIONAL.initial_position()
    a = Searcher(evaluator=ev).search(p, depth=5)
    b = Searcher(evaluator=ev).search(p, depth=5)
    assert a.best_move in legal_moves(p) and (a.best_move, a.score, a.nodes) == (b.best_move, b.score, b.nodes)


def test_hub_engine_accepts_a_learned_model(tmp_path: Path) -> None:
    cfg = EngineConfig.model_validate({
        "id": "learned", "protocol": "hub", "executable": sys.executable,
        "args": ["-m", "damas_ai.search.hub"], "working_dir": tmp_path, "native_variant": "brazilian-8x8",
        "env": {"PYTHONPATH": str(SRC)},
        "params": {"variant": "brazilian", "eval-model": str(MODELS / "brazilian_residual_v1.json")}})
    with HubEngine(cfg) as engine:
        assert "eval-model" in {p["name"] for p in engine.info.declared_params}
        r = engine.analyze(AnalysisRequest(BRAZILIAN_PROVISIONAL, BRAZILIAN_PROVISIONAL.initial_position(),
                                           SearchLimit(depth=4)))
    assert r.status is AnalysisStatus.OK and r.violations == ()
