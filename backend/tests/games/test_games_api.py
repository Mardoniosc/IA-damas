"""Game review API: PDN parsing (PlayOK-style algebraic notation) and single-game analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from damas_ai.analysis import EnginePool
from damas_ai.api import create_app
from damas_ai.bench import GreedyPlayer, SearchPlayer, generate_openings, play_game
from damas_ai.config import EngineConfig, Settings
from damas_ai.rules import BRAZILIAN_PROVISIONAL, GameState
from damas_ai.rules.notation import format_move, parse_move

SRC = Path(__file__).resolve().parents[2] / "src"


def playok_style_pdn() -> str:
    """A real-rules game written like PlayOK exports: algebraic moves, GameType '26,W,8,8,A0,0'."""
    rs = BRAZILIAN_PROVISIONAL
    op = generate_openings(rs, 1, seed=21)[0]
    g = play_game(SearchPlayer(2), GreedyPlayer(3), rs, op.position, max_plies=24)
    state = GameState.new(rs, op.position)
    alg = []
    for numeric in g.moves:
        m = parse_move(state.position, numeric)
        alg.append(format_move(rs.geometry, m, "algebraic"))
        state = state.play(m)
    body = " ".join(f"{i // 2 + 1}. {m}" if i % 2 == 0 else m for i, m in enumerate(alg))
    fen = g.start_fen
    return (f'[Event "?"]\n[Site "PlayOK"]\n[White "alice"]\n[Black "bob"]\n[Result "{g.result}"]\n'
            f'[GameType "26,W,8,8,A0,0"]\n[FEN "{fen}"]\n\n{body} {g.result}\n\n'
            '[White "x"]\n[Black "y"]\n[Result "*"]\n[GameType "26,W,8,8,A0,0"]\n\n1. c3-b4 c3-d4 *\n')


@pytest.fixture
def client(tmp_path: Path):  # type: ignore[no-untyped-def]
    cfg = EngineConfig.model_validate({
        "id": "damasai_br", "protocol": "hub", "executable": sys.executable,
        "args": ["-m", "damas_ai.search.hub"], "working_dir": tmp_path, "native_variant": "brazilian-8x8",
        "env": {"PYTHONPATH": str(SRC)}, "params": {"variant": "brazilian"}})
    pool = EnginePool([cfg])
    with TestClient(create_app(Settings(_env_file=None), pool)) as c:
        yield c
    pool.close()


def test_parse_reports_each_game_and_replay_status(client: TestClient) -> None:
    r = client.post("/games/parse", json={"pdn": playok_style_pdn()})
    assert r.status_code == 200
    first, second = r.json()["games"]
    assert first["ok"] and first["variant"] == "brazilian-8x8" and first["white"] == "alice"
    assert not second["ok"] and second["error"].startswith("ply 2")


def test_analyze_returns_every_ply_with_positions_and_algebraic_moves(client: TestClient) -> None:
    pdn = playok_style_pdn()
    r = client.post("/games/analyze", json={"pdn": pdn, "index": 0, "limit": {"depth": 2}})
    assert r.status_code == 200, r.text
    data = r.json()
    plies = data["plies"]
    n = client.post("/games/parse", json={"pdn": pdn}).json()["games"][0]["plies"]
    assert len(plies) == n
    assert all(p["fen_before"] and p["played"]["algebraic"][0].isalpha() for p in plies)
    assert {p["label"] for p in plies} <= {"best", "good", "inaccuracy", "mistake", "blunder", "unknown"}
    assert set(data["summary"]) == {"alice", "bob"}
    assert data["engine"]["name"] == "DamasAI" and any("single judge" in c for c in data["caveats"])
    assert data["final_fen"]


def test_analyze_errors(client: TestClient) -> None:
    pdn = playok_style_pdn()
    assert client.post("/games/analyze", json={"pdn": pdn, "index": 9}).status_code == 422
    assert client.post("/games/analyze", json={"pdn": pdn, "index": 1}).status_code == 422  # illegal game
    assert client.post("/games/analyze", json={"pdn": pdn, "index": 0, "engine": "scan"}).status_code == 422
    bad_limit = {"pdn": pdn, "index": 0, "limit": {"depth": 2, "move_time_s": 1}}
    assert client.post("/games/analyze", json=bad_limit).status_code == 422


def test_unknown_gametype_needs_a_variant_override(client: TestClient) -> None:
    pdn = '[White "a"]\n[Black "b"]\n[Result "*"]\n\n1. c3-b4 f6-g5 *\n'
    first = client.post("/games/parse", json={"pdn": pdn}).json()["games"][0]
    assert not first["ok"] and "GameType" in first["error"]
    again = client.post("/games/parse", json={"pdn": pdn, "variant": "brazilian-8x8"}).json()["games"][0]
    assert again["ok"]
