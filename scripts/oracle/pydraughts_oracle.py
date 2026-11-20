"""DEV-ONLY: generate independent reference data with py-draughts (GPL-3.0) for Rules Core tests.

ADR-004: py-draughts is never imported by ``damas_ai``. This script runs it as a separate
tool and writes plain-data fixtures (perft counts, FEN + legal-move sets) that the test suite
reads. The output is data (facts about positions), not py-draughts code.

Usage:
    python scripts/oracle/pydraughts_oracle.py --out backend/tests/fixtures/oracle

Requires ``pip install py-draughts`` (tested with 1.10.1).
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import random
import sys
from pathlib import Path

from draughts import BrazilianBoard, StandardBoard


def perft(board, depth: int) -> int:  # type: ignore[no-untyped-def]
    if depth == 0:
        return 1
    moves = board.legal_moves
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total


def fen_of(board) -> str:  # type: ignore[no-untyped-def]
    text = board.fen
    return text.split('"')[1] if '"' in text else text


def move_record(board, move) -> list:  # type: ignore[no-untyped-def]
    """py-draughts sets ``is_promotion`` only when a move is pushed, so promotion is observed
    by playing the move: a man (|value| 1) whose destination holds a king (|value| 2)."""
    squares = [s + 1 for s in move.square_list]
    was_man = abs(board[move.square_list[0]]) == 1
    board.push(move)
    promoted = was_man and abs(board[move.square_list[-1]]) == 2
    board.pop()
    return [squares[0], squares[-1], sorted(c + 1 for c in move.captured_list), promoted]


def sample_positions(board_cls, games: int, max_plies: int, seed: int) -> list[dict]:  # type: ignore[no-untyped-def]
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[dict] = []
    for _ in range(games):
        board = board_cls()
        for _ply in range(max_plies):
            moves = board.legal_moves
            fen = fen_of(board)
            if fen not in seen:
                seen.add(fen)
                out.append({"fen": fen, "moves": sorted(move_record(board, m) for m in moves)})
            if not moves or board.game_over:
                break
            board.push(rng.choice(moves))  # uniform random playout
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--br-perft-depth", type=int, default=9)
    ap.add_argument("--intl-perft-depth", type=int, default=6)
    ap.add_argument("--games", type=int, default=120)
    ns = ap.parse_args()

    provenance = {
        "tool": "py-draughts",
        "tool_version": importlib.metadata.version("py-draughts"),
        "tool_license": "GPL-3.0 (used as an external oracle only; ADR-004)",
        "generated": dt.date.today().isoformat(),
        "seed": ns.seed,
        "command": " ".join([Path(sys.argv[0]).as_posix(), *sys.argv[1:]]),
        "move_record": "[origin, destination, sorted captured squares, promotes]; PDN numeric squares",
        "dedup_convention": "moves with equal origin, destination and captured set are one move",
    }
    ns.out.mkdir(parents=True, exist_ok=True)
    for name, cls, depth, games in (
        ("brazilian", BrazilianBoard, ns.br_perft_depth, ns.games),
        ("international", StandardBoard, ns.intl_perft_depth, ns.games // 3),
    ):
        board = cls()
        data = {
            "provenance": provenance | {"variant_class": cls.__name__},
            "start_fen": fen_of(board),
            "perft": {str(d): perft(board, d) for d in range(1, depth + 1)},
            "positions": sample_positions(cls, games, 200, ns.seed),
        }
        path = ns.out / f"{name}_pydraughts.json"
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print(f"{path}: perft to {depth}, {len(data['positions'])} positions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
