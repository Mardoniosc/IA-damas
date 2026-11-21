"""Internal alpha-beta search (G8, ADR-010).

Negamax with iterative deepening, a transposition table, capture extension (quiescence: when a
capture is available the position is never "quiet", so captures are searched past the horizon),
killer and history move ordering, and repetition detection. Legal moves come from the Rules
Core (ADR-001), so the search cannot play an illegal move.

Scores are in hundredths of a man, side to move's view. A win in ``n`` plies scores
``WIN - n`` (printed as ``100 - n/100`` "men", the same encoding as Scan, see profiles).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from damas_ai.rules import Move, Position, apply_move, legal_moves
from damas_ai.rules.zobrist import key_after, zobrist_key
from damas_ai.search.evaluation import evaluate

WIN = 10_000
MATE_BOUND = WIN - 1_000
INF = WIN + 1
EXACT, LOWER, UPPER = 0, 1, 2
CHECK_EVERY = 512


class _Abort(Exception):
    pass


@dataclass(frozen=True)
class DepthInfo:
    depth: int
    score: int
    nodes: int
    time_s: float
    pv: tuple[Move, ...]


@dataclass
class SearchOutcome:
    best_move: Move | None
    score: int | None
    depth: int
    nodes: int
    time_s: float
    pv: tuple[Move, ...]
    infos: list[DepthInfo] = field(default_factory=list)
    stopped: bool = False


def score_to_men(score: int) -> str:
    """Hub score text: hundredths of a man -> men with 2 decimals; wins near +/-100."""
    if abs(score) >= MATE_BOUND:
        plies = WIN - abs(score)
        value = 100 - plies / 100
        return f"{value if score > 0 else -value:.2f}"
    return f"{max(-8000, min(8000, score)) / 100:.2f}"


class Searcher:
    def __init__(self, tt_entries: int = 1 << 20,
                 evaluator: Callable[[Position], int] | None = None) -> None:
        self.tt_entries = tt_entries
        # Baseline eval by default; a learned evaluator (G14) can be plugged in.
        self.evaluate = evaluator or evaluate
        self.tt: dict[int, tuple[int, int, int, tuple[int, int, frozenset[int]] | None]] = {}
        self.history: dict[tuple[int, int], int] = {}
        self.killers: dict[int, list[tuple[int, int, frozenset[int]]]] = {}
        self.nodes = 0

    def clear(self) -> None:
        self.tt.clear()
        self.history.clear()
        self.killers.clear()

    # ---------------------------------------------------------------- public

    def search(
        self,
        position: Position,
        history_keys: tuple[int, ...] = (),
        depth: int | None = None,
        nodes: int | None = None,
        move_time_s: float | None = None,
        stop: threading.Event | None = None,
        on_depth: Callable[[DepthInfo], None] | None = None,
        max_depth: int = 64,
    ) -> SearchOutcome:
        root_moves = legal_moves(position)
        t0 = time.perf_counter()
        self.nodes = 0
        self.killers.clear()
        if not root_moves:
            return SearchOutcome(None, -WIN, 0, 0, 0.0, ())
        deadline = t0 + move_time_s if move_time_s is not None else None
        stop = stop or threading.Event()
        limit_depth = min(depth, max_depth) if depth is not None else max_depth
        root_key = zobrist_key(position)
        path = set(history_keys) - {root_key}

        def check() -> None:
            if stop.is_set() or (nodes is not None and self.nodes >= nodes) or (
                    deadline is not None and time.perf_counter() >= deadline):
                raise _Abort

        result = SearchOutcome(root_moves[0], None, 0, 0, 0.0, (root_moves[0],))
        for d in range(1, limit_depth + 1):
            try:
                score = self._negamax(position, root_key, d, -INF, INF, 0, path, check)
            except _Abort:
                result.stopped = True
                break
            pv = self._pv(position, root_key, d)
            best = pv[0] if pv else root_moves[0]
            info = DepthInfo(d, score, self.nodes, round(time.perf_counter() - t0, 4), pv)
            result.infos.append(info)
            result.best_move, result.score, result.depth, result.pv = best, score, d, pv or (best,)
            if on_depth:
                on_depth(info)
            if abs(score) >= MATE_BOUND and WIN - abs(score) <= d:
                break  # forced result found within the searched horizon
        result.nodes = self.nodes
        result.time_s = round(time.perf_counter() - t0, 4)
        return result

    # ---------------------------------------------------------------- internals

    def _negamax(self, pos: Position, key: int, depth: int, alpha: int, beta: int, ply: int,
                 path: set[int], check: Callable[[], None]) -> int:
        self.nodes += 1
        if self.nodes % CHECK_EVERY == 0:
            check()
        if ply and key in path:
            return 0  # repetition: draw
        moves = legal_moves(pos)
        if not moves:
            return -WIN + ply
        quiescent = depth <= 0
        if quiescent and not moves[0].is_capture:
            return self.evaluate(pos)

        alpha0 = alpha
        tt_move = None
        entry = self.tt.get(key)
        if entry is not None and not quiescent:
            e_depth, e_score, e_flag, tt_move = entry
            if e_depth >= depth:
                s = e_score - ply if e_score >= MATE_BOUND else e_score + ply if e_score <= -MATE_BOUND else e_score
                if e_flag == EXACT or (e_flag == LOWER and s >= beta) or (e_flag == UPPER and s <= alpha):
                    return s

        killers = self.killers.get(ply, [])
        hist = self.history

        def order(m: Move) -> tuple[int, int]:
            ident = m.identity
            if ident == tt_move:
                return (0, 0)
            if m.is_capture:
                return (1, -len(m.captured))
            if ident in killers:
                return (2, 0)
            return (3, -hist.get((m.origin, m.destination), 0))

        ordered = sorted(moves, key=order) if len(moves) > 1 else moves
        best_score, best_ident = -INF, None
        path.add(key)
        try:
            for m in ordered:
                child_key = key_after(key, pos, m)
                score = -self._negamax(apply_move(pos, m), child_key, depth - 1, -beta, -alpha,
                                       ply + 1, path, check)
                if score > best_score:
                    best_score, best_ident = score, m.identity
                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    if not m.is_capture:
                        ks = self.killers.setdefault(ply, [])
                        if m.identity not in ks:
                            ks.insert(0, m.identity)
                            del ks[2:]
                        hk = (m.origin, m.destination)
                        hist[hk] = hist.get(hk, 0) + depth * depth
                    break
        finally:
            path.discard(key)

        if not quiescent:
            flag = UPPER if best_score <= alpha0 else LOWER if best_score >= beta else EXACT
            stored = best_score + ply if best_score >= MATE_BOUND else best_score - ply if best_score <= -MATE_BOUND else best_score
            if len(self.tt) >= self.tt_entries:
                self.tt.clear()  # simple replacement policy: start over when full
            self.tt[key] = (depth, stored, flag, best_ident)
        return best_score

    def _pv(self, pos: Position, key: int, max_len: int) -> tuple[Move, ...]:
        pv: list[Move] = []
        seen: set[int] = set()
        while len(pv) < max_len and key not in seen:
            seen.add(key)
            entry = self.tt.get(key)
            if entry is None or entry[3] is None:
                break
            move = next((m for m in legal_moves(pos) if m.identity == entry[3]), None)
            if move is None:
                break
            pv.append(move)
            key = key_after(key, pos, move)
            pos = apply_move(pos, move)
        return tuple(pv)
