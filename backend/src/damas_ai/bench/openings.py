"""Benchmark openings (G12): seeded random walks from the start position, kept only when the
internal engine judges them roughly balanced. Each opening is later played with both colours,
so a residual imbalance cancels out between the two games.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from damas_ai.rules import Position, Ruleset, apply_move, legal_moves
from damas_ai.rules.notation import format_move, to_fen
from damas_ai.search import Searcher


@dataclass(frozen=True)
class Opening:
    id: str
    position: Position
    moves: tuple[str, ...]
    internal_score: int  # internal engine, hundredths of a man, side to move


def generate_openings(ruleset: Ruleset, count: int, plies: int = 6, seed: int = 2026,
                      max_abs_score: int = 40, depth: int = 4, max_tries: int = 2000) -> list[Opening]:
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[Opening] = []
    tries = 0
    while len(out) < count and tries < max_tries:
        tries += 1
        p = ruleset.initial_position()
        moves: list[str] = []
        for _ in range(plies):
            ms = legal_moves(p)
            if not ms:
                break
            m = rng.choice(ms)
            moves.append(format_move(p.geometry, m))
            p = apply_move(p, m)
        if not legal_moves(p) or p.to_dsa() in seen:
            continue
        score = Searcher().search(p, depth=depth).score or 0
        if abs(score) > max_abs_score:
            continue
        seen.add(p.to_dsa())
        out.append(Opening(f"{ruleset.variant}-s{seed}-{len(out) + 1:03d}", p, tuple(moves), score))
    return out


def opening_fens(openings: list[Opening]) -> list[str]:
    return [to_fen(o.position) for o in openings]
