"""G10 strategy features and decision layer (scripted doubles)."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import MakeDouble
from fastapi.testclient import TestClient

from damas_ai.analysis import EnginePool
from damas_ai.api import create_app
from damas_ai.config import Settings
from damas_ai.decision import DecisionMaker
from damas_ai.decision.serialize import decision_view
from damas_ai.engines import AnalysisRequest, SearchLimit
from damas_ai.rules import (
    BOARD_8X8,
    BRAZILIAN_PROVISIONAL,
    INTERNATIONAL_PROVISIONAL,
    Color,
    apply_move,
    legal_moves,
)
from damas_ai.rules.notation import from_fen
from damas_ai.strategy import profile

INTL = INTERNATIONAL_PROVISIONAL
START = INTL.initial_position()
FIRST, LAST = legal_moves(START)[0], legal_moves(START)[-1]
AFTER_FIRST, AFTER_LAST = apply_move(START, FIRST), apply_move(START, LAST)
FAST = SearchLimit(move_time_s=0.05)


def table(tmp_path: Path, name: str, scores: dict) -> str:  # type: ignore[type-arg]
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps({k.to_dsa(): v for k, v in scores.items()}), encoding="utf-8")
    return str(p)


def decide(configs, position=START, ruleset=INTL, **kw):  # type: ignore[no-untyped-def]
    with EnginePool(configs) as pool:
        return DecisionMaker(pool).decide(AnalysisRequest(ruleset, position, FAST), **kw)


# ---------------------------------------------------------------- strategy features


def test_start_position_profile_is_symmetric() -> None:
    sp = profile(BRAZILIAN_PROVISIONAL.initial_position())
    assert all(v == 0 for v in sp.delta().values()) and sp.notes() == []
    assert sp.white.men == 12 and sp.white.back_rank == 4 and sp.white.mobility == 7


def test_runaway_and_kings_block() -> None:
    p = from_fen(BOARD_8X8, "W:W9:B25")  # white man near promotion, black man far behind it
    assert profile(p).white.runaways == 1
    q = from_fen(BOARD_8X8, "W:W9:BK25")  # a black king can intercept from anywhere
    assert profile(q).white.runaways == 0


def test_mobility_matches_rules_core_and_notes_describe_differences() -> None:
    p = from_fen(BOARD_8X8, "W:W21,22,K29:B1")
    sp = profile(p)
    assert sp.white.mobility == len(legal_moves(p))
    assert sp.black.mobility == len(legal_moves(p.with_side(Color.BLACK)))
    assert "White has 1 more kings" in sp.notes()


# ---------------------------------------------------------------- decisions


def test_unanimous_engines_give_high_confidence(double: MakeDouble) -> None:
    d = decide([double("a", "--name", "Scan"), double("b", "--name", "Scan")])
    assert d.move == FIRST and d.confidence == "high"


def test_minimax_regret_picks_the_move_nobody_dislikes(double: MakeDouble, tmp_path: Path) -> None:
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {AFTER_LAST: "0.50"}))
    b = double("b", "--name", "Scan", "--pick", "last")
    d = decide([a, b])
    assert d.move == FIRST and d.confidence == "high"  # b also accepts FIRST (regret 0)
    last = next(c for c in d.candidates if c.move == LAST)
    assert last.normalized_regret["a"] == 7.5  # 0.75 men / 0.10 tolerance


def test_weights_change_the_choice(double: MakeDouble, tmp_path: Path) -> None:
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {AFTER_LAST: "0.50"}))
    b = double("b", "--name", "Scan", "--pick", "last",
               "--score-table", table(tmp_path, "b", {AFTER_FIRST: "0.30"}))
    assert decide([a, b]).move == FIRST  # max regret: FIRST 5.5 (b) < LAST 7.5 (a)
    weighted = decide([a, b], weights={"a": 0.5})
    assert weighted.move == LAST  # LAST 3.75 (a, halved) < FIRST 5.5 (b)
    assert weighted.confidence in ("medium", "low")


def test_proven_loss_is_vetoed_and_contradiction_lowers_confidence(double: MakeDouble, tmp_path: Path) -> None:
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {AFTER_LAST: "99.90"}))
    b = double("b", "--name", "Scan", "--pick", "last")
    d = decide([a, b])
    last = next(c for c in d.candidates if c.move == LAST)
    assert last.vetoed_by == ("a",) and d.move == FIRST
    assert d.confidence == "low" and any("contradict" in r for r in d.reasons)


def test_single_source_is_capped_at_low(double: MakeDouble) -> None:
    br = BRAZILIAN_PROVISIONAL
    d = decide([double("br", "--name", "Scan", variant="brazilian-8x8")],
               position=br.initial_position(), ruleset=br)
    assert d.move in legal_moves(br.initial_position()) and d.confidence == "low"
    assert any("single evidence source" in r for r in d.reasons)


def test_tactical_shot_joins_the_candidates(double: MakeDouble) -> None:
    br = BRAZILIAN_PROVISIONAL
    sac = from_fen(BOARD_8X8, "W:W17,19,22,23,24,25,26,28,29,30,32:B1,4,5,9,10,12")
    d = decide([double("x", "--name", "Scan", variant="brazilian-8x8"),
                double("y", "--name", "Scan", "--pick", "last", variant="brazilian-8x8")],
               position=sac, ruleset=br)
    shot = next(c for c in d.candidates if "tactics" in c.sources)
    assert set(shot.values) == {"x", "y"} and d.shot is not None


def test_only_legal_move_and_no_engines() -> None:
    forced = from_fen(BOARD_8X8, "W:W22:B18,1")
    d = decide([], position=forced, ruleset=BRAZILIAN_PROVISIONAL)
    assert d.confidence == "high" and d.reasons == ("only legal move",)
    none = decide([], position=BRAZILIAN_PROVISIONAL.initial_position(), ruleset=BRAZILIAN_PROVISIONAL)
    assert none.move is None and none.confidence == "none"


def test_view_and_api(double: MakeDouble) -> None:
    configs = [double("a", "--name", "Scan"), double("b", "--name", "Scan", "--pick", "last")]
    view = json.loads(json.dumps(decision_view(decide(configs), START)))
    assert view["confidence"] in ("high", "medium", "low") and view["move"]["numeric"]
    assert view["strategy"]["white"]["men"] == 20
    pool = EnginePool(configs)
    with TestClient(create_app(Settings(_env_file=None), pool)) as client:
        r = client.post("/decision", json={"variant": "international-10x10", "fen": "W:W31-50:B1-20",
                                           "limit": {"move_time_s": 0.05}})
        assert r.status_code == 200 and r.json()["move"] is not None
        s = client.post("/strategy", json={"variant": "brazilian-8x8", "fen": "W:W21-32:B1-12"})
        assert s.status_code == 200 and s.json()["delta"]["men"] == 0
    pool.close()
