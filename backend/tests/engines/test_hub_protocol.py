from __future__ import annotations

import pytest

from damas_ai.engines.hub import protocol as hub
from damas_ai.rules import BOARD_8X8, BOARD_10X10, BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL
from damas_ai.rules.notation import from_algebraic, from_numeric


# ---------------------------------------------------------------- line syntax (protocol.txt)


def test_parse_id_line_with_quoted_value() -> None:
    msg = hub.parse_line('id name=Scan version=3.1 author="Fabien Letouzey" country=France')
    assert msg is not None and msg.command == "id"
    assert msg.args == {"name": "Scan", "version": "3.1", "author": "Fabien Letouzey", "country": "France"}


def test_parse_flags_empty_values_and_equals_inside_quotes() -> None:
    msg = hub.parse_line('level infinite note="" expr="a=b c"')
    assert msg is not None
    assert msg.args == {"infinite": "", "note": "", "expr": "a=b c"}


def test_backslashes_are_literal_no_escape_mechanism() -> None:
    msg = hub.parse_line(r'error message="C:\engines\scan\data missing"')
    assert msg is not None and msg.args["message"] == r"C:\engines\scan\data missing"


def test_extra_spaces_and_blank_lines() -> None:
    assert hub.parse_line("   ") is None
    msg = hub.parse_line("  done   move=32-28    ponder=17-22 ")
    assert msg is not None and msg.args == {"move": "32-28", "ponder": "17-22"}


def test_unterminated_quote_is_a_syntax_error() -> None:
    with pytest.raises(hub.HubSyntaxError):
        hub.parse_line('error message="oops')


def test_format_line_quotes_when_needed_and_round_trips() -> None:
    line = hub.format_line("set-param", name="variant", value="normal")
    assert line == "set-param name=variant value=normal"
    line = hub.format_line("pos", pos="W" + "e" * 50, moves="32-28 17-22")
    assert hub.parse_line(line).args["moves"] == "32-28 17-22"  # type: ignore[union-attr]
    assert hub.format_line("level", move_time=1.5) == "level move-time=1.5"
    assert hub.format_line("x", v="") == 'x v=""'
    with pytest.raises(hub.HubSyntaxError):
        hub.format_line("x", v='say "hi"')


# ---------------------------------------------------------------- positions


def test_international_start_position_encodes_like_the_spec_example() -> None:
    """protocol.txt example: pos pos=Wbbbbbbbbbbbbbbbbbbbbeeeeeeeeeewwwwwwwwwwwwwwwwwwww"""
    start = INTERNATIONAL_PROVISIONAL.initial_position()
    assert hub.encode_position(start) == "W" + "b" * 20 + "e" * 10 + "w" * 20
    assert hub.decode_position(BOARD_10X10, hub.encode_position(start)) == start


def test_brazilian_position_round_trip() -> None:
    start = BRAZILIAN_PROVISIONAL.initial_position()
    text = hub.encode_position(start)
    assert text == "W" + "b" * 12 + "e" * 8 + "w" * 12
    assert hub.decode_position(BOARD_8X8, text) == start
    with pytest.raises(hub.HubSyntaxError):
        hub.decode_position(BOARD_8X8, text + "e")


# ---------------------------------------------------------------- moves


def test_parse_quiet_and_capture_moves() -> None:
    g = BOARD_10X10
    quiet = hub.parse_move(g, "32-28")
    assert (quiet.origin, quiet.destination, quiet.captured) == (from_numeric(g, 32), from_numeric(g, 28), frozenset())
    cap = hub.parse_move(g, "28x19x23")  # from 28 to 19 capturing 23 (spec example)
    assert cap.origin == from_numeric(g, 28) and cap.destination == from_numeric(g, 19)
    assert cap.captured == frozenset({from_numeric(g, 23)})
    multi = hub.parse_move(g, "38x15x33x24x20")  # captured squares in any order
    assert multi.captured == frozenset(from_numeric(g, n) for n in (33, 24, 20))


def test_short_capture_form_reports_unknown_captures() -> None:
    assert hub.parse_move(BOARD_10X10, "28x19").captured is None


@pytest.mark.parametrize("bad", ["", "32", "32-", "a-b", "32-28-23", "99-28", "32x"])
def test_bad_moves_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        hub.parse_move(BOARD_10X10, bad)


def test_format_move_matches_hub_capture_notation() -> None:
    from damas_ai.rules import Move

    g = BOARD_8X8
    c3, e5, g7 = (from_algebraic(g, s) for s in ("c3", "e5", "g7"))
    d4, f6 = from_algebraic(g, "d4"), from_algebraic(g, "f6")
    move = Move(c3, (e5, g7), (d4, f6))
    text = hub.format_move(g, move)
    report = hub.parse_move(g, text)
    assert (report.origin, report.destination, report.captured) == (c3, g7, frozenset({d4, f6}))
