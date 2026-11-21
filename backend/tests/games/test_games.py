"""G13: PDN replay, game analysis, datasets (leakage control), KB storage, CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from damas_ai.bench import GreedyPlayer, RandomPlayer, SearchPlayer, generate_openings, play_game, to_pdn
from damas_ai.config import EngineConfig
from damas_ai.engines import SearchLimit, create_engine
from damas_ai.games import Labels, SourceGame, analyze_game, build_dataset, parse_pdn, replay
from damas_ai.games.pdn import game_text
from damas_ai.games.__main__ import main as games_cli
from damas_ai.kb import KnowledgeBase
from damas_ai.rules import BRAZILIAN_PROVISIONAL

BR = BRAZILIAN_PROVISIONAL
SRC = Path(__file__).resolve().parents[2] / "src"


def make_games(n: int = 6, seed: int = 3) -> str:
    openings = generate_openings(BR, n, seed=seed)
    pdns = []
    for i, op in enumerate(openings):
        g = play_game(SearchPlayer(2), GreedyPlayer(i), BR, op.position, max_plies=120, opening_id=op.id)
        pdns.append(to_pdn(g, "test", i + 1))
    return "\n".join(pdns)


def internal_engine(tmp_path: Path):  # type: ignore[no-untyped-def]
    cfg = EngineConfig.model_validate({
        "id": "damasai_br", "protocol": "hub", "executable": sys.executable,
        "args": ["-m", "damas_ai.search.hub"], "working_dir": tmp_path, "native_variant": "brazilian-8x8",
        "env": {"PYTHONPATH": str(SRC)}, "params": {"variant": "brazilian"}})
    return create_engine(cfg)


# ---------------------------------------------------------------- PDN


def test_pdn_round_trip_replays_through_the_rules_core() -> None:
    games = parse_pdn(make_games())
    assert len(games) == 6
    for g in games:
        r = replay(g)
        assert r.ok, r.error
        assert len(r.states) == len(r.moves) + 1 and r.ruleset is BR


def test_pdn_parser_handles_comments_variations_nags_and_reports_illegal_moves() -> None:
    text = ('[GameType "26"]\n[Result "1-0"]\n\n1. 22-18 {a comment} 11-15 (1... 12-16 2. 21-17) '
            '2. 18x11 $1 8x15 1-0\n\n[GameType "26"]\n[Result "*"]\n\n1. 22-18 22-17 *\n')
    first, second = parse_pdn(text)
    assert first.moves == ["22-18", "11-15", "18x11", "8x15"] and first.result == "1-0"
    assert replay(first).ok
    bad = replay(second)
    assert not bad.ok and bad.error.startswith("ply 2")


def test_unknown_gametype_needs_an_explicit_ruleset() -> None:
    (g,) = parse_pdn('[GameType "21"]\n\n1. 9-14 *\n')
    with pytest.raises(ValueError):
        replay(g)


# ---------------------------------------------------------------- analysis


def test_labels() -> None:
    lb = Labels()
    assert lb.label(None, True, False) == "best"
    assert [lb.label(r, False, False) for r in (0.05, 0.3, 1.0, 2.0)] == ["good", "inaccuracy", "mistake", "blunder"]
    assert lb.label(0.01, False, True) == "blunder"  # throwing away a proven result


def test_game_analysis_flags_a_random_players_errors(tmp_path: Path) -> None:
    op = generate_openings(BR, 1, seed=5)[0]
    g = play_game(SearchPlayer(3, "strong"), RandomPlayer(1, "weak"), BR, op.position, max_plies=60)
    (pdn_game,) = parse_pdn(to_pdn(g, "t", 1))
    engine = internal_engine(tmp_path)
    engine.start()
    try:
        ga = analyze_game(replay(pdn_game), engine, SearchLimit(depth=3))
    finally:
        engine.close()
    assert len(ga.plies) == len(g.moves)
    s = ga.summary()
    assert s["strong"]["accuracy"] >= s["weak"]["accuracy"]  # the analyser agrees with itself more
    assert s["weak"]["mistake"] + s["weak"]["blunder"] >= 1


# ---------------------------------------------------------------- dataset


def test_dataset_split_by_game_without_leakage(tmp_path: Path) -> None:
    games = parse_pdn(make_games(8, seed=9))
    srcs = [SourceGame(f"g{i}", replay(g)) for i, g in enumerate(games)]
    srcs.append(SourceGame("dup", replay(games[0])))  # the same game again: must not leak
    m = build_dataset(srcs, tmp_path, fractions=(0.5, 0.25, 0.25), seed=1)
    rows = {s: [json.loads(x) for x in (tmp_path / f"{s}.jsonl").read_text(encoding="utf-8").splitlines()]
            for s in ("train", "val", "test")}
    train_keys = {r["canonical_dsa"] for r in rows["train"]}
    assert not any(r["canonical_dsa"] in train_keys for r in rows["val"] + rows["test"])
    assert {r["game_id"] for r in rows["train"]}.isdisjoint({r["game_id"] for r in rows["test"]})
    r0 = (rows["train"] or rows["val"] or rows["test"])[0]
    assert set(r0["features"]) >= {"material", "tempo", "mobility"} and r0["outcome"] in (0.0, 0.5, 1.0)
    assert all(v["sha256"] for v in m["files"].values())


def test_kb_stores_games_and_links_positions() -> None:
    kb = KnowledgeBase(create=True)
    text = make_games(2, seed=4)
    with kb.session() as s:
        for g in parse_pdn(text):
            kb.record_game(s, replay(g), "test", game_text(g))
    st = kb.stats()
    assert st["games"] == 2 and st["game_positions"] == sum(len(replay(g).moves) for g in parse_pdn(text))


def test_cli_selfplay_replay_dataset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "sp"
    assert games_cli(["selfplay", "--variant", "brazilian-8x8", "--games", "4", "--depth", "2",
                      "--out", str(out)]) == 0
    assert games_cli(["replay", str(out / "games.pdn")]) == 0
    capsys.readouterr()
    assert games_cli(["dataset", str(out / "games.pdn"), "--jsonl", str(out / "games.jsonl"),
                      "--out", str(tmp_path / "ds")]) == 0
    rows = [json.loads(x) for s in ("train", "val", "test")
            for x in (tmp_path / "ds" / f"{s}.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows and any("eval" in r for r in rows)  # mover's own eval carried from the JSONL


def test_game_text_round_trip() -> None:
    (g,) = parse_pdn(make_games(1, seed=6))
    (again,) = parse_pdn(game_text(g))
    assert again.moves == g.moves and again.result == g.result and replay(again).ok


def test_game_ids_are_unique_across_same_named_files(tmp_path: Path) -> None:
    from damas_ai.games.__main__ import _load

    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "games.pdn").write_text(make_games(1, seed=8), encoding="utf-8")
    ids = [gid for gid, _ in _load([tmp_path / "a" / "games.pdn", tmp_path / "b" / "games.pdn"])]
    assert ids == ["a/games#1", "b/games#1"]
