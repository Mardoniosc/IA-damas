from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import MakeDouble

from damas_ai.analysis import EnginePool, MultiEngineAnalyzer, ThreadBudgetExceeded
from damas_ai.analysis.serialize import multi_view
from damas_ai.engines import AnalysisRequest, SearchLimit
from damas_ai.rules import BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, legal_moves

INTL = INTERNATIONAL_PROVISIONAL
FAST = SearchLimit(move_time_s=0.05)


def req(ruleset=INTL):  # type: ignore[no-untyped-def]
    return AnalysisRequest(ruleset, ruleset.initial_position(), FAST)


# ---------------------------------------------------------------- pool


def test_pool_starts_lazily_and_closes(double: MakeDouble) -> None:
    with EnginePool([double("a"), double("b")]) as pool:
        assert all(not s.running for s in pool.status())
        pool.get("a")
        status = {s.engine_id: s for s in pool.status()}
        assert status["a"].running and status["a"].name == "HubDouble" and not status["b"].running
    assert all(not s.running for s in pool.status())


def test_disabled_engines_are_not_in_the_pool(double: MakeDouble) -> None:
    pool = EnginePool([double("a"), double("b", enabled=False)])
    assert pool.engine_ids() == ["a"]
    with pytest.raises(KeyError):
        pool.get("b")


def test_thread_budget_is_enforced(double: MakeDouble) -> None:
    pool = EnginePool([double("a", params={"threads": "2"}), double("b", params={"threads": "2"})],
                      thread_budget=3)
    try:
        pool.get("a")
        with pytest.raises(ThreadBudgetExceeded):
            pool.get("b")
    finally:
        pool.close()


def test_dead_engine_is_restarted_on_next_use(double: MakeDouble) -> None:
    with EnginePool([double("a", "--crash-on-go")]) as pool:
        analyzer = MultiEngineAnalyzer(pool)
        first = analyzer.analyze(req())
        assert first.outcomes[0].result.status.value == "crashed"  # type: ignore[union-attr]
        analyzer.analyze(req())
        assert pool.status()[0].restarts == 1


def test_missing_executable_is_reported_not_raised(double: MakeDouble, tmp_path: Path) -> None:
    with EnginePool([double("ghost", executable=tmp_path / "nope.exe")]) as pool:
        result = MultiEngineAnalyzer(pool).analyze(req())
        assert result.outcomes[0].error and "not found" in result.outcomes[0].error


# ---------------------------------------------------------------- orchestration


def test_two_engines_side_by_side_with_proposals(double: MakeDouble) -> None:
    with EnginePool([double("first"), double("last", "--pick", "last"), double("first2")]) as pool:
        result = MultiEngineAnalyzer(pool).analyze(req())
    assert result.engines_ok == ("first", "first2", "last")
    start_moves = legal_moves(INTL.initial_position())
    assert [p.engines for p in result.proposals] == [("first", "first2"), ("last",)]
    assert result.proposals[0].move == start_moves[0] and result.proposals[1].move == start_moves[-1]
    assert result.config_fingerprint and result.run_id


def test_parallel_runs_overlap_and_sequential_does_not(double: MakeDouble) -> None:
    with EnginePool([double("a", "--delay", "0.6"), double("b", "--delay", "0.6")]) as pool:
        pool.warm_up()
        analyzer = MultiEngineAnalyzer(pool)
        par = analyzer.analyze(req(), mode="parallel")
        seq = analyzer.analyze(req(), mode="sequential")
    assert par.engines_ok == seq.engines_ok == ("a", "b")
    assert par.elapsed_s < 1.0 <= seq.elapsed_s


def test_variant_without_engines_is_explicit(double: MakeDouble) -> None:
    with EnginePool([double("intl")]) as pool:
        result = MultiEngineAnalyzer(pool).analyze(req(BRAZILIAN_PROVISIONAL))
    assert result.requested_engines == () and result.outcomes == ()
    assert "no configured engine plays brazilian-8x8" in result.note


def test_explicitly_requested_wrong_variant_or_unknown_engine(double: MakeDouble) -> None:
    with EnginePool([double("intl"), double("br", variant="brazilian-8x8")]) as pool:
        result = MultiEngineAnalyzer(pool).analyze(req(), engines=["intl", "br", "nobody"])
    errors = {o.engine_id: o.error for o in result.outcomes}
    assert errors["intl"] is None
    assert "plays brazilian-8x8" in (errors["br"] or "")
    assert "unknown" in (errors["nobody"] or "")


def test_brazilian_capable_double_is_used_for_brazilian(double: MakeDouble) -> None:
    with EnginePool([double("intl"), double("br", variant="brazilian-8x8")]) as pool:
        result = MultiEngineAnalyzer(pool).analyze(req(BRAZILIAN_PROVISIONAL))
    assert result.engines_ok == ("br",) and result.note == ""


def test_serialization_is_json_and_self_describing(double: MakeDouble) -> None:
    with EnginePool([double("a"), double("b", "--pick", "last")]) as pool:
        r = req()
        result = MultiEngineAnalyzer(pool).analyze(r)
    view = multi_view(result, r.position, transcript=True)
    text = json.dumps(view)
    back = json.loads(text)
    assert back["schema_version"] == 1 and back["variant"] == "international-10x10"
    assert back["position"]["fen"].startswith("W:W31")
    assert {x["engine"]["id"] for x in back["results"]} == {"a", "b"}
    res = back["results"][0]
    assert res["status"] == "ok" and res["best_move"]["numeric"] and res["final_info"]["pv"]
    assert res["final_info"]["score"]["unit"] == "unknown"  # generic profile: never guessed
    assert res["transcript"]
