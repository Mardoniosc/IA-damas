"""Players for benchmark games (G12, ADR-014).

A player chooses a move for a ``GameState``. Engine players go through the normal adapter, so
every engine move is validated by the Rules Core (ADR-001). Baseline players run in-process:
they are references to check that the benchmark measures strength (an engine must beat them).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from damas_ai.engines import AnalysisRequest, AnalysisStatus, EngineAdapter, SearchLimit
from damas_ai.rules import GameState, Move, apply_move, legal_moves
from damas_ai.tactics import material


@dataclass
class MoveChoice:
    move: Move | None                  # None = the player failed (forfeit)
    info: dict[str, Any] = field(default_factory=dict)
    failure: str | None = None


class Player(Protocol):
    name: str

    def new_game(self) -> None: ...

    def choose(self, state: GameState, root: GameState, history: tuple[Move, ...]) -> MoveChoice: ...


class EnginePlayer:
    """Wraps an EngineAdapter. ``limit`` applies to every move (``go think``)."""

    def __init__(self, name: str, adapter: EngineAdapter, limit: SearchLimit) -> None:
        self.name, self.adapter, self.limit = name, adapter, limit

    def new_game(self) -> None:
        if not self.adapter.running:
            self.adapter.start()
        self.adapter.new_game()

    def choose(self, state: GameState, root: GameState, history: tuple[Move, ...]) -> MoveChoice:
        if not self.adapter.running:
            return MoveChoice(None, failure="engine not running")
        request = AnalysisRequest(state.ruleset, root.position, self.limit, history, mode="think")
        r = self.adapter.analyze(request)
        fi = r.final_info
        info = {"status": r.status.value, "elapsed_s": r.elapsed_s,
                "score": fi.score.text if fi and fi.score else None,
                "score_value": fi.score.value if fi and fi.score else None,
                "score_kind": fi.score.kind if fi and fi.score else None,
                "depth": fi.depth if fi else None}
        if r.status is not AnalysisStatus.OK or r.best_move is None:
            return MoveChoice(None, info, f"{r.status.value}: {'; '.join(r.violations)[:200]}")
        return MoveChoice(r.best_move, info)


class SearchPlayer:
    """The internal search run in-process at a fixed depth (deterministic; fast data generation
    in G13). For engine comparisons use the Hub process via ``EnginePlayer`` (ADR-010)."""

    def __init__(self, depth: int | None = None, name: str | None = None, evaluator=None,  # type: ignore[no-untyped-def]
                 move_time_s: float | None = None) -> None:
        from damas_ai.search import Searcher

        if (depth is None) == (move_time_s is None):
            raise ValueError("give exactly one of depth or move_time_s")
        self.depth, self.move_time_s = depth, move_time_s
        self.name = name or (f"search@depth={depth}" if depth else f"search@{move_time_s}s")
        self.searcher = Searcher(evaluator=evaluator)

    def new_game(self) -> None:
        self.searcher.clear()

    def choose(self, state: GameState, root: GameState, history: tuple[Move, ...]) -> MoveChoice:
        out = self.searcher.search(state.position, state.keys_since_irreversible, depth=self.depth,
                                   move_time_s=self.move_time_s)
        return MoveChoice(out.best_move, {"score_value": (out.score or 0) / 100, "score_kind": "eval",
                                          "depth": out.depth})


class RandomPlayer:
    """Uniformly random legal move (seeded). A floor any real player must clear."""

    def __init__(self, seed: int = 0, name: str = "random") -> None:
        self.name, self.seed = name, seed
        self.rng = random.Random(seed)

    def new_game(self) -> None:
        pass

    def choose(self, state: GameState, root: GameState, history: tuple[Move, ...]) -> MoveChoice:
        return MoveChoice(self.rng.choice(state.legal_moves()))


class GreedyPlayer:
    """2-ply materialist: maximize material after the opponent's best (material) reply; ties
    broken by a seeded RNG. (A 1-ply version is almost random in draughts: captures are forced
    and quiet moves never change material, G12 finding.)"""

    def __init__(self, seed: int = 0, name: str = "greedy") -> None:
        self.name = name
        self.rng = random.Random(seed)

    def new_game(self) -> None:
        pass

    def choose(self, state: GameState, root: GameState, history: tuple[Move, ...]) -> MoveChoice:
        side = state.position.side_to_move
        scored = []
        for m in state.legal_moves():
            after = apply_move(state.position, m)
            replies = legal_moves(after)
            if not replies:
                scored.append((10**6, m))  # the move wins at once
                continue
            scored.append((min(material(apply_move(after, r), side) for r in replies), m))
        best = max(s for s, _ in scored)
        return MoveChoice(self.rng.choice([m for s, m in scored if s == best]))
