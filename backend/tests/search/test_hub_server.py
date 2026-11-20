"""The internal engine as a Hub process, through the standard adapter and conformance suite."""

from __future__ import annotations

import pytest
from conftest import oracle_positions

from damas_ai.engines import AnalysisRequest, AnalysisStatus, LimitKind, SearchLimit, run_conformance
from damas_ai.engines.hub.adapter import HubEngine
from damas_ai.rules import BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, legal_moves
from damas_ai.rules.notation import parse_move

RULESETS = {"brazilian": BRAZILIAN_PROVISIONAL, "international": INTERNATIONAL_PROVISIONAL}


@pytest.mark.parametrize("variant", ["brazilian", "international"])
def test_handshake_profile_and_analysis(internal_engine_config, variant: str) -> None:  # type: ignore[no-untyped-def]
    rs = RULESETS[variant]
    with HubEngine(internal_engine_config(variant)) as engine:
        assert engine.info.name == "DamasAI" and engine.info.profile == "damasai"
        caps = engine.capabilities()
        assert caps.limits == frozenset({LimitKind.DEPTH, LimitKind.NODES, LimitKind.MOVE_TIME})
        r = engine.analyze(AnalysisRequest(rs, rs.initial_position(), SearchLimit(depth=4)))
        assert r.status is AnalysisStatus.OK and r.violations == ()
        assert r.best_move in legal_moves(rs.initial_position())
        assert [i.depth for i in r.infos] == [1, 2, 3, 4]
        assert r.final_info.score.unit.startswith("men") and r.final_info.score.perspective == "side_to_move"


@pytest.mark.parametrize("variant", ["brazilian", "international"])
def test_conformance_on_oracle_positions(internal_engine_config, variant: str) -> None:  # type: ignore[no-untyped-def]
    with HubEngine(internal_engine_config(variant)) as engine:
        report = run_conformance(engine, RULESETS[variant], oracle_positions(variant)[:60],
                                 SearchLimit(depth=2))
    assert report.passed, report.by_status


def test_move_history_is_applied(internal_engine_config) -> None:  # type: ignore[no-untyped-def]
    rs = BRAZILIAN_PROVISIONAL
    start = rs.initial_position()
    m1 = parse_move(start, "22-18")
    from damas_ai.rules import apply_move

    m2 = parse_move(apply_move(start, m1), "11-15")
    with HubEngine(internal_engine_config()) as engine:
        r = engine.analyze(AnalysisRequest(rs, start, SearchLimit(depth=3), (m1, m2)))
    after = apply_move(apply_move(start, m1), m2)
    assert r.status is AnalysisStatus.OK and r.best_move in legal_moves(after)
    assert r.best_move.is_capture  # 18x11 is forced after 22-18 11-15


def test_stop_returns_best_so_far(internal_engine_config) -> None:  # type: ignore[no-untyped-def]
    rs = BRAZILIAN_PROVISIONAL
    with HubEngine(internal_engine_config(search_timeout_s=0.4)) as engine:
        r = engine.analyze(AnalysisRequest(rs, rs.initial_position(), SearchLimit(depth=40)))
    assert r.status is AnalysisStatus.OK and r.interrupted
    assert r.best_move in legal_moves(rs.initial_position())
