from __future__ import annotations

import pytest
from helpers import pos

from damas_ai.rules import (
    BOARD_10X10,
    INTERNATIONAL_PROVISIONAL,
    EngineMoveAmbiguous,
    EngineMoveNotLegal,
    resolve_engine_move,
)
from damas_ai.rules.notation import from_algebraic, from_numeric


def sq(name: str) -> int:
    from damas_ai.rules import BOARD_8X8

    return from_algebraic(BOARD_8X8, name)


def test_unique_quiet_move_resolves() -> None:
    p = INTERNATIONAL_PROVISIONAL.initial_position()
    g = BOARD_10X10
    m = resolve_engine_move(p, from_numeric(g, 32), from_numeric(g, 28), captured=[])
    assert (m.origin, m.destination) == (from_numeric(g, 32), from_numeric(g, 28))


def test_hub_style_capture_resolves_with_unordered_captured_set() -> None:
    p = pos("c3", "d4 f6")
    m = resolve_engine_move(p, sq("c3"), sq("g7"), captured={sq("f6"), sq("d4")})
    assert m.captured == (sq("d4"), sq("f6"))  # Rules Core supplies the order


def test_ambiguous_report_without_captured_set() -> None:
    """Kc5 -> d8 via e3/g5 (takes d4, f4, e7) or via f2/h4 (takes d4, g3, e7)."""
    p = pos("Kc5", "a3 d4 e7 f4 g3")
    with pytest.raises(EngineMoveAmbiguous) as exc:
        resolve_engine_move(p, sq("c5"), sq("d8"))
    assert len(exc.value.candidates) == 2
    m = resolve_engine_move(p, sq("c5"), sq("d8"), captured={sq("d4"), sq("e7"), sq("g3")})
    assert set(m.captured) == {sq("d4"), sq("e7"), sq("g3")}


def test_illegal_report_is_rejected() -> None:
    p = pos("c3", "d4 f6")
    with pytest.raises(EngineMoveNotLegal):
        resolve_engine_move(p, sq("c3"), sq("e5"))  # stops after 1 capture: violates majority
    with pytest.raises(EngineMoveNotLegal):
        resolve_engine_move(p, sq("c3"), sq("b4"), captured=[])  # quiet move while capture exists
