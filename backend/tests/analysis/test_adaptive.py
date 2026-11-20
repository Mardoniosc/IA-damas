"""G8 adaptive escalation, with scripted doubles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import MakeDouble
from fastapi.testclient import TestClient

from damas_ai.adaptive import AdaptiveAnalyzer, EscalationPolicy
from damas_ai.adaptive.serialize import adaptive_view
from damas_ai.analysis import EnginePool
from damas_ai.api import create_app
from damas_ai.config import Settings
from damas_ai.consensus import Divergence
from damas_ai.engines import AnalysisRequest, SearchLimit
from damas_ai.rules import BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, apply_move, legal_moves

INTL = INTERNATIONAL_PROVISIONAL
START = INTL.initial_position()
AFTER_LAST = apply_move(START, legal_moves(START)[-1])


def preference_pair(double: MakeDouble, tmp_path: Path):  # type: ignore[no-untyped-def]
    table = tmp_path / "a.json"
    table.write_text(json.dumps({AFTER_LAST.to_dsa(): "0.50"}), encoding="utf-8")
    return [double("a", "--name", "Scan", "--score-table", str(table)),
            double("b", "--name", "Scan", "--pick", "last")]


def test_policy_limits() -> None:
    p = EscalationPolicy(factor=2.0, max_move_time_s=1.0)
    assert p.next_limit(SearchLimit(move_time_s=0.3)) == SearchLimit(move_time_s=0.6)
    assert p.next_limit(SearchLimit(move_time_s=0.6)) == SearchLimit(move_time_s=1.0)
    assert p.next_limit(SearchLimit(move_time_s=1.0)) is None
    assert p.next_limit(SearchLimit(depth=6)) == SearchLimit(depth=7)
    assert EscalationPolicy(factor=4.0).next_limit(SearchLimit(depth=6)) == SearchLimit(depth=8)
    assert p.next_limit(SearchLimit(nodes=1000)) == SearchLimit(nodes=2000)
    with pytest.raises(ValueError):
        EscalationPolicy(factor=1.0)


def test_persistent_preference_escalates_to_max_steps(double: MakeDouble, tmp_path: Path) -> None:
    with EnginePool(preference_pair(double, tmp_path)) as pool:
        r = AdaptiveAnalyzer(pool).analyze(AnalysisRequest(INTL, START, SearchLimit(move_time_s=0.05)))
    assert r.escalated and r.stop_reason == "max_steps"
    assert r.trajectory == ("preference", "preference", "preference")
    assert [lim.move_time_s for lim in r.limits] == [0.05, 0.1, 0.2]


def test_ceiling_stops_escalation(double: MakeDouble, tmp_path: Path) -> None:
    policy = EscalationPolicy(max_steps=5, max_move_time_s=0.1)
    with EnginePool(preference_pair(double, tmp_path)) as pool:
        r = AdaptiveAnalyzer(pool).analyze(AnalysisRequest(INTL, START, SearchLimit(move_time_s=0.05)),
                                           policy=policy)
    assert r.stop_reason == "ceiling" and len(r.steps) == 2


def test_settled_positions_are_not_escalated(double: MakeDouble) -> None:
    with EnginePool([double("a", "--name", "Scan"), double("b", "--name", "Scan", "--pick", "last")]) as pool:
        r = AdaptiveAnalyzer(pool).analyze(AnalysisRequest(INTL, START, SearchLimit(move_time_s=0.05)))
    assert not r.escalated and r.stop_reason == "settled"
    assert r.final.classification is Divergence.EQUIVALENT_ALTERNATIVES


def test_incomplete_stops_immediately(double: MakeDouble) -> None:
    with EnginePool([double("a", "--name", "Scan")]) as pool:
        r = AdaptiveAnalyzer(pool).analyze(
            AnalysisRequest(BRAZILIAN_PROVISIONAL, BRAZILIAN_PROVISIONAL.initial_position(),
                            SearchLimit(move_time_s=0.05)))
    assert r.stop_reason == "incomplete" and len(r.steps) == 1


def test_view_and_api(double: MakeDouble, tmp_path: Path) -> None:
    configs = preference_pair(double, tmp_path)
    with EnginePool(configs) as pool:
        r = AdaptiveAnalyzer(pool).analyze(AnalysisRequest(INTL, START, SearchLimit(move_time_s=0.05)),
                                           policy=EscalationPolicy(max_steps=2))
    view = json.loads(json.dumps(adaptive_view(r, START)))
    assert view["trajectory"] == ["preference", "preference"] and view["stop_reason"] == "max_steps"
    assert [s["limit"]["move_time_s"] for s in view["steps"]] == [0.05, 0.1]
    assert view["final"]["classification"] == "preference"

    pool = EnginePool(configs)
    with TestClient(create_app(Settings(_env_file=None), pool)) as client:
        resp = client.post("/adaptive", json={"variant": "international-10x10", "fen": "W:W31-50:B1-20",
                                              "limit": {"move_time_s": 0.05}, "max_steps": 2})
        assert resp.status_code == 200, resp.text
        assert resp.json()["trajectory"] == ["preference", "preference"]
        assert client.post("/adaptive", json={"variant": "international-10x10", "fen": "W:W31-50:B1-20",
                                              "limit": {"move_time_s": 0.05}, "factor": 1}).status_code == 422
    pool.close()
