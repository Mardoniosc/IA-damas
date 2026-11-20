"""G9 tactical intelligence. Positions are hand-built or taken from the oracle fixtures; every
claim of the detector is cross-checked against the Rules Core directly in the test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from damas_ai.analysis import EnginePool
from damas_ai.api import create_app
from damas_ai.config import Settings
from damas_ai.rules import BOARD_8X8, Color, apply_move, legal_moves
from damas_ai.rules.notation import format_move, from_fen
from damas_ai.tactics import Thresholds, assess, evaluate_moves, find_shots, material, threats_against
from damas_ai.tactics.__main__ import main as cli_main
from damas_ai.tactics.serialize import criticality_view

ORACLE = Path(__file__).resolve().parents[1] / "fixtures" / "oracle"
SACRIFICE = "W:W17,19,22,23,24,25,26,28,29,30,32:B1,4,5,9,10,12"  # from the Brazilian oracle sample


def br(fen: str):  # type: ignore[no-untyped-def]
    return from_fen(BOARD_8X8, fen)


def test_material_counts_men_and_kings() -> None:
    p = br("W:W21,22,K29:B1,K5")
    assert material(p, Color.WHITE) == 200 + 300 - 100 - 300
    assert material(p, Color.BLACK) == -material(p, Color.WHITE)


def test_threats_are_the_opponents_captures_in_a_null_move_view() -> None:
    p = br("W:W18,30:B14")  # expected threats are derived from the Rules Core below
    threat = threats_against(p)
    assert threat.max_pieces >= 1  # black 14 can take white 18 if it were black's move
    flipped_caps = [m for m in legal_moves(p.with_side(Color.BLACK)) if m.is_capture]
    assert threat.max_pieces == max((len(m.captured) for m in flipped_caps), default=0)
    assert threat.squares == frozenset(s for m in flipped_caps for s in m.captured)


def test_sacrifice_shot_is_found_and_is_really_forced() -> None:
    p = br(SACRIFICE)
    shots = find_shots(p)
    top = shots[0]
    assert top.sacrifice and top.gain == 200
    assert format_move(BOARD_8X8, top.first_move) == "19-16"
    # Independent check with the Rules Core: after 19-16 black's every move is a capture...
    after = apply_move(p, top.first_move)
    replies = legal_moves(after)
    assert replies and all(m.is_capture for m in replies)
    # ...and after black's best reply white captures 3 pieces, netting +2 men.
    worst_for_white = min(
        max((len(m.captured) for m in legal_moves(apply_move(after, r))), default=0) - len(r.captured)
        for r in replies)
    assert worst_for_white == 2


def test_a_quiet_move_that_forces_nothing_is_not_a_shot() -> None:
    p = br("W:W21:B4")  # far apart: nothing can be forced
    assert find_shots(p) == ()


def test_single_forced_move_is_not_a_decision() -> None:
    p = br("W:W22:B18,1")  # 22x13 is the only legal move (forced capture)
    assert len(legal_moves(p)) == 1
    report = assess(p, Thresholds(depth=4))
    assert not any(r.startswith(("shot", "only move", "volatile")) for r in report.reasons)
    assert report.move_values == ()


def test_move_values_cover_every_legal_move_best_first() -> None:
    p = br(SACRIFICE)
    values = evaluate_moves(p, 4)
    assert {v.move for v in values} == set(legal_moves(p))
    assert [v.score for v in values] == sorted((v.score for v in values), reverse=True)
    assert values[0].move == find_shots(p)[0].first_move  # the internal engine also finds the shot


def test_sacrifice_position_is_critical_with_shot_reason() -> None:
    report = assess(br(SACRIFICE), Thresholds(depth=4))
    assert report.critical and any(r.startswith("shot: sacrifice") for r in report.reasons)


def test_report_flags_are_consistent_with_their_evidence() -> None:
    data = json.loads((ORACLE / "brazilian_pydraughts.json").read_text(encoding="utf-8"))
    t = Thresholds(depth=4)
    for rec in [r for r in data["positions"] if r["moves"]][:40]:
        rep = assess(br(rec["fen"]), t)
        reasons = " | ".join(rep.reasons)
        assert rep.critical == bool(rep.reasons)
        assert ("threat:" in reasons) == (rep.threat.max_pieces >= t.threat_pieces)
        if "only move" in reasons:
            assert rep.gap is not None and rep.gap >= t.only_move_gap


def test_terminal_position_is_rejected() -> None:
    with pytest.raises(ValueError):
        assess(br("W:W:B1"))


def test_divergence_input_becomes_a_reason() -> None:
    rep = assess(br("W:W21:B4"), Thresholds(depth=3), divergence="preference", proof_gap=True)
    assert rep.critical
    assert any("preference" in r for r in rep.reasons) and any("proof gap" in r for r in rep.reasons)


def test_view_cli_and_api(tmp_path: Path) -> None:
    view = json.loads(json.dumps(criticality_view(assess(br(SACRIFICE), Thresholds(depth=4)))))
    assert view["critical"] and view["shots"][0]["line"][0] == "19-16" and view["shots"][0]["gain_men"] == 2.0

    fens = tmp_path / "f.txt"
    fens.write_text(f"{SACRIFICE}\nW:W21:B4\nW:W:B1\n", encoding="utf-8")
    out = tmp_path / "o.jsonl"
    code = cli_main(["--variant", "brazilian-8x8", "--fens", str(fens), "--depth", "3", "--out", str(out)])
    lines = out.read_text(encoding="utf-8").splitlines()
    assert code == 1 and len(lines) == 2  # terminal line reported, two records written

    with TestClient(create_app(Settings(_env_file=None), EnginePool([]))) as client:
        r = client.post("/tactics", json={"variant": "brazilian-8x8", "fen": SACRIFICE, "depth": 4})
        assert r.status_code == 200 and r.json()["critical"]
        assert client.post("/tactics", json={"variant": "brazilian-8x8", "fen": "W:W:B1"}).status_code == 422


def test_shot_detector_is_colour_symmetric() -> None:
    p = br(SACRIFICE)
    f = p.flipped()
    a, b = find_shots(p), find_shots(f)
    rot = p.geometry.rotate180
    assert [(rot(s.first_move.origin), rot(s.first_move.destination), s.gain) for s in a] == \
           [(s.first_move.origin, s.first_move.destination, s.gain) for s in b]

