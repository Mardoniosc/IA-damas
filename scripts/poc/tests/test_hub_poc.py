"""Tests for the G1 Hub PoC harness, run against the scripted mock engine (not a real engine)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR))

from hub_poc import INTERNATIONAL_START, check_move, parse_hub_line, run_poc  # noqa: E402

MOCK = [sys.executable, str(POC_DIR / "mock_hub_engine.py")]


def steps(report) -> dict[str, bool]:  # type: ignore[no-untyped-def]
    return {s.step: s.ok for s in report.steps}


# ---------------------------------------------------------------- parser (protocol.txt syntax)


def test_parse_quoted_values_and_flags() -> None:
    ln = parse_hub_line('id name=Scan version=3.1 author="Fabien Letouzey" country=France')
    assert ln is not None and ln.command == "id"
    assert ln.args == {"name": "Scan", "version": "3.1", "author": "Fabien Letouzey", "country": "France"}


def test_parse_flag_without_value_and_empty_quoted_value() -> None:
    ln = parse_hub_line('level infinite note=""')
    assert ln is not None and ln.args == {"infinite": "", "note": ""}


def test_parse_pv_with_spaces() -> None:
    ln = parse_hub_line('info depth=21 score=-0.01 pv="32-28 17-22 28x17x22"')
    assert ln is not None and ln.args["pv"] == "32-28 17-22 28x17x22"


def test_parse_blank_and_unbalanced() -> None:
    assert parse_hub_line("   ") is None
    bad = parse_hub_line('error message="unterminated')
    assert bad is not None and bad.command == "<unparseable>"


# ---------------------------------------------------------------- move checks


@pytest.mark.parametrize("move", ["32-28", "31-26", "35-30"])
def test_check_move_accepts_plausible_opening_moves(move: str) -> None:
    assert check_move(move, INTERNATIONAL_START) == []


@pytest.mark.parametrize(
    ("move", "fragment"),
    [("26-21", "origin square 26"), ("32-31", "not empty"), ("99-28", "out of range"), ("32_28", "notation")],
)
def test_check_move_rejects(move: str, fragment: str) -> None:
    assert any(fragment in p for p in check_move(move, INTERNATIONAL_START))


# ---------------------------------------------------------------- end-to-end against the mock


def test_full_poc_against_mock_passes_all_eight_steps() -> None:
    report = run_poc(MOCK, POC_DIR, set_params={"variant": "normal"}, move_time_s=0.1,
                     init_timeout_s=10, search_timeout_s=5)
    assert report.ok, report.steps
    assert list(steps(report)) == [
        "1-start", "2-identify", "3-send-position", "4-request-analysis",
        "5-receive-result", "6-interpret-output", "7-validate-move", "8-terminate",
    ]
    assert report.engine_id["name"] == "MockHub"
    assert report.done["move"] == "32-28"
    assert report.infos[-1]["pv"] == "32-28 19-23"
    assert report.termination == "quit(code=0)"
    sent = [line for _, direction, line in report.transcript if direction == ">"]
    assert sent[:2] == ["hub", 'set-param name=variant value="normal"']
    assert "go analyze" in sent and sent[-1] == "quit"


def test_undeclared_parameter_is_refused() -> None:
    report = run_poc(MOCK, POC_DIR, set_params={"threads": "4"}, init_timeout_s=10)
    assert steps(report)["2-identify"] is False
    assert steps(report)["8-terminate"] is True  # still shut down cleanly


def test_search_timeout_still_terminates() -> None:
    report = run_poc([*MOCK, "--hang-search"], POC_DIR, move_time_s=0.1,
                     init_timeout_s=10, search_timeout_s=0.5)
    assert steps(report)["5-receive-result"] is False
    assert steps(report)["8-terminate"] is True


def test_engine_crash_is_reported() -> None:
    report = run_poc([*MOCK, "--crash-on-go"], POC_DIR, move_time_s=0.1,
                     init_timeout_s=10, search_timeout_s=5)
    assert steps(report)["5-receive-result"] is False
    # Depending on timing the process is either already reaped or reaped right after 'quit'.
    assert report.termination in ("already-exited(code=3)", "quit(code=3)")
    assert steps(report)["8-terminate"] is False  # non-zero exit is not a clean termination


def test_ignored_quit_escalates_to_terminate() -> None:
    report = run_poc([*MOCK, "--ignore-quit"], POC_DIR, move_time_s=0.1,
                     init_timeout_s=10, search_timeout_s=5, quit_timeout_s=0.5)
    assert report.termination.startswith(("terminated", "killed"))
    assert steps(report)["8-terminate"] is False
    assert report.ok is False


def test_illegal_origin_square_is_caught() -> None:
    report = run_poc([*MOCK, "--bad-move"], POC_DIR, move_time_s=0.1,
                     init_timeout_s=10, search_timeout_s=5)
    assert steps(report)["7-validate-move"] is False
