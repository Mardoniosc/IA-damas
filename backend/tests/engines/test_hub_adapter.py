"""HubEngine against the scripted test double (tests/engines/doubles/hub_double.py)."""

from __future__ import annotations

import pytest

from damas_ai.engines import (
    AnalysisRequest,
    AnalysisStatus,
    CapabilityError,
    EngineNotRunning,
    EngineStartError,
    LimitKind,
    SearchLimit,
)
from damas_ai.engines.hub.adapter import HubEngine
from damas_ai.rules import BOARD_10X10, BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, legal_moves
from damas_ai.rules.notation import from_fen, parse_move

INTL = INTERNATIONAL_PROVISIONAL
FAST = SearchLimit(move_time_s=0.1)


def req(position=None, ruleset=INTL, limit=FAST, moves=()):  # type: ignore[no-untyped-def]
    return AnalysisRequest(ruleset, position or ruleset.initial_position(), limit, moves)


# A 10x10 position where white must capture (32x23 over 28): a rules-blind engine plays quietly.
FORCED = from_fen(BOARD_10X10, "W:W32,47:B28,1")


# ---------------------------------------------------------------- lifecycle


def test_handshake_identifies_engine_and_sets_declared_params(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory(params={"variant": "normal", "book": False})
    info = engine.info
    assert (info.name, info.version, info.profile) == ("HubDouble", "0.0-test", "generic-hub")
    assert {p["name"] for p in info.declared_params} == {"variant", "book"}
    sent = [line for _, d, line in engine.transcript if d == ">"]
    assert sent[:4] == ["hub", "set-param name=variant value=normal",
                        "set-param name=book value=false", "init"]
    assert engine.ping() < 5
    assert engine.close() == "quit(code=0)"
    assert engine.close() == "quit(code=0)"  # idempotent
    assert not engine.running


def test_undeclared_param_fails_start_and_kills_process(engine_factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(EngineStartError, match="threads"):
        engine_factory(params={"threads": "4"})


def test_missing_id_fails_start(engine_factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(EngineStartError, match="no 'id'"):
        engine_factory("--no-id")


def test_slow_init_beyond_deadline_fails_start(engine_factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(EngineStartError, match="handshake failed"):
        engine_factory("--slow-init", "3", init_timeout_s=0.5)


def test_scan_profile_is_selected_from_the_id_line(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--name", "Scan")
    assert engine.info.profile == "scan"
    caps = engine.capabilities()
    assert caps.score_unit == "men" and LimitKind.NODES in caps.limits and not caps.multipv


def test_context_manager_closes(make_config) -> None:  # type: ignore[no-untyped-def]
    with HubEngine(make_config()) as engine:
        assert engine.running
    assert not engine.running


# ---------------------------------------------------------------- analysis


def test_analysis_returns_rules_validated_move_pv_ponder_and_score(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--name", "Scan")
    result = engine.analyze(req())
    assert result.status is AnalysisStatus.OK, result.violations
    start = INTL.initial_position()
    assert result.best_move in legal_moves(start)
    assert result.ponder_move is not None
    final = result.final_info
    assert final is not None and final.depth == 2 and len(final.pv) == 2
    assert final.score is not None and final.score.value == -0.25 and final.score.unit == "men"
    assert result.violations == ()
    sent = [line for _, d, line in result.transcript if d == ">"]
    assert sent == [f"pos pos={'W' + 'b' * 20 + 'e' * 10 + 'w' * 20}", "level move-time=0.1", "go analyze"]


def test_move_history_is_sent_and_analysis_is_of_the_resulting_position(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory()
    start = INTL.initial_position()
    m1 = parse_move(start, "32-28")
    from damas_ai.rules import apply_move

    m2 = parse_move(apply_move(start, m1), "19-23")
    result = engine.analyze(req(moves=(m1, m2)))
    assert result.status is AnalysisStatus.OK
    assert 'moves="32-28 19-23"' in [line for _, d, line in result.transcript if d == ">"][0]
    assert result.best_move in legal_moves(apply_move(apply_move(start, m1), m2))


def test_depth_and_nodes_limits(engine_factory) -> None:  # type: ignore[no-untyped-def]
    scan = engine_factory("--name", "Scan")
    assert scan.analyze(req(limit=SearchLimit(depth=5))).status is AnalysisStatus.OK
    assert scan.analyze(req(limit=SearchLimit(nodes=1000))).status is AnalysisStatus.OK
    generic = engine_factory()
    with pytest.raises(CapabilityError, match="nodes"):
        generic.analyze(req(limit=SearchLimit(nodes=1000)))


def test_kingsrow_profile_refuses_depth_instead_of_letting_it_be_ignored(engine_factory) -> None:  # type: ignore[no-untyped-def]
    """G5: the real Kingsrow hub silently ignores 'level depth'; the adapter must refuse it."""
    engine = engine_factory("--name", "Kingsrow")
    assert engine.info.profile == "kingsrow"
    with pytest.raises(CapabilityError, match="depth"):
        engine.analyze(req(limit=SearchLimit(depth=6)))
    assert engine.analyze(req()).status is AnalysisStatus.OK  # move-time works


def test_variant_gating_refuses_positions_the_engine_does_not_play(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory()  # declares international-10x10
    with pytest.raises(CapabilityError, match="brazilian-8x8"):
        engine.analyze(req(ruleset=BRAZILIAN_PROVISIONAL))


def test_terminal_position_is_refused(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory()
    with pytest.raises(ValueError, match="terminal"):
        engine.analyze(req(position=from_fen(BOARD_10X10, "W:W:B1")))


def test_brazilian_engine_double_works_on_8x8(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory(variant="brazilian-8x8")
    result = engine.analyze(req(ruleset=BRAZILIAN_PROVISIONAL))
    assert result.status is AnalysisStatus.OK
    assert result.best_move in legal_moves(BRAZILIAN_PROVISIONAL.initial_position())


# ---------------------------------------------------------------- engine misbehaviour


def test_illegal_engine_move_is_rejected_not_applied(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--rules-blind")
    result = engine.analyze(req(position=FORCED))
    assert result.status is AnalysisStatus.ILLEGAL_MOVE
    assert result.best_move is None and result.best_move_text is not None
    assert any("rejected by Rules Core" in v for v in result.violations)
    assert engine.running  # an illegal answer is data, not a crash


def test_garbled_move_is_a_protocol_error(engine_factory) -> None:  # type: ignore[no-untyped-def]
    result = engine_factory("--garbage").analyze(req())
    assert result.status is AnalysisStatus.PROTOCOL_ERROR and result.best_move is None


def test_illegal_pv_is_truncated_and_reported(engine_factory) -> None:  # type: ignore[no-untyped-def]
    result = engine_factory("--bad-pv").analyze(req())
    assert result.status is AnalysisStatus.OK
    assert len(result.final_info.pv) == 1  # type: ignore[union-attr]
    assert any("pv move 2" in v for v in result.violations)


def test_short_capture_notation_is_resolved_with_a_warning(engine_factory) -> None:  # type: ignore[no-untyped-def]
    result = engine_factory("--short-capture").analyze(req(position=FORCED))
    assert result.status is AnalysisStatus.OK
    assert result.best_move is not None and result.best_move.is_capture
    assert any("non-standard" in v for v in result.violations)


def test_engine_error_lines_and_stderr_are_recorded(engine_factory) -> None:  # type: ignore[no-untyped-def]
    result = engine_factory("--error-line", "--stderr").analyze(req())
    assert result.status is AnalysisStatus.OK
    assert any("synthetic error" in v for v in result.violations)
    assert any(d == "!" for _, d, _ in result.transcript)


def test_overdue_search_is_stopped_and_the_answer_kept(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--hang", search_timeout_s=0.3)
    result = engine.analyze(req())
    assert result.status is AnalysisStatus.OK and result.interrupted
    assert "stop" in [line for _, d, line in result.transcript if d == ">"]
    assert engine.running


def test_unresponsive_engine_times_out_is_killed_and_can_restart(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--deaf", search_timeout_s=0.3, stop_grace_s=0.3)
    result = engine.analyze(req())
    assert result.status is AnalysisStatus.TIMEOUT and result.best_move is None
    assert not engine.running
    with pytest.raises(EngineNotRunning):
        engine.analyze(req())
    engine.restart()
    assert engine.running


def test_crash_during_search_is_reported(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--crash-on-go")
    result = engine.analyze(req())
    assert result.status is AnalysisStatus.CRASHED
    assert not engine.running


def test_engine_ignoring_quit_is_terminated_on_close(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory("--ignore-quit", quit_timeout_s=0.5)
    assert engine.close().startswith(("terminated", "killed"))
