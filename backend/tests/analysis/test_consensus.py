"""G7 consensus & divergence, with scripted doubles (each scenario built deliberately)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import MakeDouble
from fastapi.testclient import TestClient

from damas_ai.analysis import EnginePool
from damas_ai.api import create_app
from damas_ai.config import Settings
from damas_ai.consensus import ConsensusAnalyzer, Divergence, OutcomeClass, fit_scale
from damas_ai.consensus.serialize import consensus_view
from damas_ai.consensus.values import WIN, root_outcome, value_after_move
from damas_ai.engines import AnalysisRequest, RawScore, SearchLimit
from damas_ai.rules import BOARD_10X10, BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, apply_move, legal_moves
from damas_ai.rules.notation import from_fen

INTL = INTERNATIONAL_PROVISIONAL
START = INTL.initial_position()
FIRST, LAST = legal_moves(START)[0], legal_moves(START)[-1]
AFTER_FIRST, AFTER_LAST = apply_move(START, FIRST), apply_move(START, LAST)
FAST = SearchLimit(move_time_s=0.05)


def table(tmp_path: Path, name: str, scores: dict) -> str:  # type: ignore[type-arg]
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({p.to_dsa(): s for p, s in scores.items()}), encoding="utf-8")
    return str(path)


def run(configs, position=START, ruleset=INTL, **kw):  # type: ignore[no-untyped-def]
    with EnginePool(configs) as pool:
        return ConsensusAnalyzer(pool).analyze(AnalysisRequest(ruleset, position, FAST), **kw)


# ---------------------------------------------------------------- value model (unit)


def scan_score(text: str) -> RawScore:
    from damas_ai.engines.hub.profiles import SCAN

    return SCAN.classify_score(text)


def test_value_after_move_negates_and_maps_decisive_bands() -> None:
    assert value_after_move(scan_score("0.40")).utility == pytest.approx(-0.40)
    loss = value_after_move(scan_score("99.90"))   # opponent wins in 10 plies
    assert loss.outcome is OutcomeClass.LOSS and loss.utility == -(WIN - 10)
    win = value_after_move(scan_score("-99.97"))   # opponent loses in 3 plies
    assert win.outcome is OutcomeClass.WIN and win.utility == WIN - 3
    assert value_after_move(RawScore("1.0", "unknown", 1.0, "eval")).outcome is OutcomeClass.UNKNOWN
    assert root_outcome(scan_score("99.5")) is OutcomeClass.WIN
    assert root_outcome(scan_score("-1.2")) is OutcomeClass.EVAL


def test_fit_scale_recovers_a_known_relation() -> None:
    pairs = [(x / 10, 1.2 * x / 10) for x in range(-30, 31) if x]
    fit = fit_scale(pairs)
    assert fit.slope_through_origin == pytest.approx(1.2)
    assert fit.median_ratio == pytest.approx(1.2)
    assert fit.pearson_r == pytest.approx(1.0) and fit.sign_agreement == 1.0
    assert fit_scale([(1.0, 1.0)]).slope_through_origin is None


# ---------------------------------------------------------------- classifications


def test_unanimous_is_none_and_skips_cross_evaluation(double: MakeDouble) -> None:
    r = run([double("a", "--name", "Scan"), double("b", "--name", "Scan")])
    assert r.classification is Divergence.NONE and r.unanimous and r.agreement_ratio == 1.0
    assert not r.cross_checked


def test_cross_check_always_on_unanimous_gives_zero_regret(double: MakeDouble) -> None:
    r = run([double("a", "--name", "Scan"), double("b", "--name", "Scan")], cross_check="always")
    assert r.classification is Divergence.NONE and r.cross_checked
    assert r.candidates[0].regret == {"a": 0.0, "b": 0.0}


def test_different_moves_judged_equal_are_equivalent_alternatives(double: MakeDouble) -> None:
    r = run([double("a", "--name", "Scan"), double("b", "--name", "Scan", "--pick", "last")])
    assert r.classification is Divergence.EQUIVALENT_ALTERNATIVES
    assert not r.unanimous and r.agreement_ratio == 0.5
    assert {c.move for c in r.candidates} == {FIRST, LAST}
    assert all(v == 0.0 for c in r.candidates for v in c.regret.values())


def test_preference_when_an_engine_dislikes_the_other_move(double: MakeDouble, tmp_path: Path) -> None:
    # Engine a: after LAST the opponent stands +0.50 (mover -0.50); after FIRST mover +0.25.
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {AFTER_LAST: "0.50"}))
    b = double("b", "--name", "Scan", "--pick", "last")
    r = run([a, b])
    assert r.classification is Divergence.PREFERENCE
    last = next(c for c in r.candidates if c.move == LAST)
    assert last.regret["a"] == pytest.approx(0.75) and last.regret["b"] == 0.0
    assert r.max_regret()["a"] == pytest.approx(0.75)
    # The same disagreement is "equivalent" under a looser tolerance for engine a.
    r2 = run([a, b], tolerance={"a": 1.0, "b": 0.1})
    assert r2.classification is Divergence.EQUIVALENT_ALTERNATIVES


def test_outcome_conflict_on_a_candidate(double: MakeDouble, tmp_path: Path) -> None:
    # Engine a says LAST loses (opponent wins in 10 plies); engine b sees an ordinary eval.
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {AFTER_LAST: "99.90"}))
    b = double("b", "--name", "Scan", "--pick", "last")
    r = run([a, b])
    assert r.classification is Divergence.OUTCOME_CONFLICT
    last = next(c for c in r.candidates if c.move == LAST)
    assert last.values["a"].outcome is OutcomeClass.LOSS and last.values["b"].outcome is OutcomeClass.EVAL


def test_outcome_conflict_at_root_even_when_moves_agree(double: MakeDouble, tmp_path: Path) -> None:
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {START: "99.95"}))
    r = run([a, double("b", "--name", "Scan")])
    assert r.unanimous and r.classification is Divergence.OUTCOME_CONFLICT
    assert r.root_outcomes == {"a": OutcomeClass.WIN, "b": OutcomeClass.EVAL}


def test_proof_gap_is_not_a_conflict(double: MakeDouble, tmp_path: Path) -> None:
    """One engine proves a win, the other evaluates the same side clearly better (G7 finding)."""
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {START: "99.95"}))
    b = double("b", "--name", "Scan", "--score-table", table(tmp_path, "b", {START: "1.50"}))
    r = run([a, b])
    assert r.classification is Divergence.NONE and r.proof_gap
    assert r.root_outcomes == {"a": OutcomeClass.WIN, "b": OutcomeClass.EVAL}


def test_contradiction_and_proof_gap_rules() -> None:
    from damas_ai.consensus.values import MoveValue, contradicts, proof_gap

    win = MoveValue(WIN - 5, OutcomeClass.WIN, "99.95", 5)
    loss = MoveValue(-(WIN - 5), OutcomeClass.LOSS, "-99.95", 5)
    up, down, even = (MoveValue(v, OutcomeClass.EVAL, str(v)) for v in (2.0, -2.0, 0.0))
    unknown = MoveValue(None, OutcomeClass.UNKNOWN, None)
    assert contradicts(win, loss) and contradicts(win, down) and contradicts(win, even)
    assert contradicts(loss, up) and not contradicts(loss, down)
    assert not contradicts(win, up) and not contradicts(win, unknown) and not contradicts(up, down)
    assert proof_gap(win, up) and proof_gap(loss, down)
    assert not proof_gap(win, down) and not proof_gap(up, down) and not proof_gap(win, win)


def test_unknown_perspective_is_never_guessed(double: MakeDouble) -> None:
    """Generic-profile engines report no perspective, so their regret is unknown."""
    r = run([double("a"), double("b", "--pick", "last")])
    assert r.classification is Divergence.PREFERENCE
    assert all(v is None for c in r.candidates for v in c.regret.values())
    assert any("unknown" in n for n in r.notes)


def test_move_that_ends_the_game_is_a_terminal_win(double: MakeDouble) -> None:
    position = from_fen(BOARD_10X10, "W:W32,47:B28")  # 32x23 captures the last black piece
    r = run([double("a", "--name", "Scan"), double("b", "--name", "Scan")], position=position,
            cross_check="always")
    value = r.candidates[0].values["a"]
    assert value.source == "terminal" and value.outcome is OutcomeClass.WIN
    assert r.classification is Divergence.NONE


def test_incomplete_with_one_engine_or_brazilian(double: MakeDouble) -> None:
    assert run([double("a", "--name", "Scan")]).classification is Divergence.INCOMPLETE
    r = run([double("a", "--name", "Scan")], position=BRAZILIAN_PROVISIONAL.initial_position(),
            ruleset=BRAZILIAN_PROVISIONAL)
    assert r.classification is Divergence.INCOMPLETE and "brazilian-8x8" in " ".join(r.notes)


def test_sequential_is_the_default_mode(double: MakeDouble) -> None:
    r = run([double("a", "--name", "Scan"), double("b", "--name", "Scan")])
    assert r.analysis.mode == "sequential"


# ---------------------------------------------------------------- serialization and API


def test_consensus_view_and_api(double: MakeDouble, tmp_path: Path) -> None:
    a = double("a", "--name", "Scan", "--score-table", table(tmp_path, "a", {AFTER_LAST: "0.50"}))
    b = double("b", "--name", "Scan", "--pick", "last")
    r = run([a, b])
    view = json.loads(json.dumps(consensus_view(r, START)))
    assert view["classification"] == "preference" and view["cross_checked"] is True
    from damas_ai.rules.notation import format_move

    expected = {format_move(BOARD_10X10, m) for m in (FIRST, LAST)}
    assert {c["move"]["numeric"] for c in view["candidates"]} == expected
    assert view["analysis"]["mode"] == "sequential"

    pool = EnginePool([a, b])
    with TestClient(create_app(Settings(_env_file=None), pool)) as client:
        resp = client.post("/consensus", json={"variant": "international-10x10", "fen": "W:W31-50:B1-20",
                                               "limit": {"move_time_s": 0.05}})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["classification"] == "preference" and data["max_regret"]["a"] == pytest.approx(0.75)
        bad = client.post("/consensus", json={"variant": "international-10x10", "fen": "W:W31-50:B1-20",
                                              "limit": {"move_time_s": 0.05}, "tolerance": -1})
        assert bad.status_code == 422
    pool.close()
