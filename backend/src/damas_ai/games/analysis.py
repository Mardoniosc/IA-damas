"""Game analysis (G13, ADR-015): judge every move of a replayed game with one analysis engine.

For each ply, the engine searches the position (its best move and value). If the played move
differs, the engine also searches the position after the played move (G7 cross-evaluation).
The move's regret is in that engine's own units. Moves are labelled with provisional
thresholds (parameters, not truths):

    best (same move) | good (≤ 0.10) | inaccuracy (≤ 0.50) | mistake (≤ 1.50) | blunder (> 1.50
    or the move throws away a proven result)

A per-player summary counts the labels and the average regret ("accuracy" = share of best/good).
Regrets that span a proven result (≥ WIN/2) are counted as blunders but left out of the mean.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from damas_ai.consensus.values import WIN, OutcomeClass, root_value, terminal_win, value_after_move
from damas_ai.engines import AnalysisRequest, AnalysisStatus, EngineAdapter, SearchLimit
from damas_ai.games.pdn import ReplayedGame
from damas_ai.rules import Color, apply_move, legal_moves
from damas_ai.rules.notation import format_move

MATE_LIKE = WIN / 2


@dataclass(frozen=True)
class Labels:
    good: float = 0.10
    inaccuracy: float = 0.50
    mistake: float = 1.50

    def label(self, regret: float | None, same: bool, class_drop: bool) -> str:
        if same:
            return "best"
        if regret is None:
            return "unknown"
        if class_drop:
            return "blunder"
        if regret <= self.good:
            return "good"
        if regret <= self.inaccuracy:
            return "inaccuracy"
        if regret <= self.mistake:
            return "mistake"
        return "blunder"


@dataclass(frozen=True)
class PlyAnalysis:
    ply: int
    player: str
    side: str
    played: str
    best: str | None
    value_best: float | None     # engine utility of its best move, mover's view
    value_played: float | None   # engine utility of the played move, mover's view
    regret: float | None
    label: str
    forced: bool                 # only one legal move


@dataclass
class GameAnalysis:
    white: str
    black: str
    result: str
    engine: str
    plies: list[PlyAnalysis] = field(default_factory=list)

    def summary(self) -> dict[str, dict[str, float | int]]:
        out: dict[str, dict[str, float | int]] = {}
        for name in (self.white, self.black):
            mine = [p for p in self.plies if p.player == name and not p.forced]
            counts = Counter(p.label for p in mine)
            regrets = [p.regret for p in mine if p.regret is not None and p.regret < MATE_LIKE]
            n = len(mine)
            out[name] = {"moves": n, **{k: counts.get(k, 0) for k in
                                        ("best", "good", "inaccuracy", "mistake", "blunder", "unknown")},
                         "accuracy": round((counts["best"] + counts["good"]) / n, 4) if n else 0.0,
                         "mean_regret": round(sum(regrets) / len(regrets), 4) if regrets else 0.0}
        return out


def analyze_game(game: ReplayedGame, engine: EngineAdapter, limit: SearchLimit,
                 labels: Labels | None = None) -> GameAnalysis:
    if not game.ok:
        raise ValueError(f"cannot analyse a game that failed to replay: {game.error}")
    labels = labels or Labels()
    tags = game.pdn.tags
    ga = GameAnalysis(tags.get("White", "?"), tags.get("Black", "?"), game.pdn.result,
                      engine.info.name if engine.running else engine.engine_id)
    rs, g = game.ruleset, game.start.geometry
    for i, move in enumerate(game.moves):
        state = game.states[i]
        pos = state.position
        player = ga.white if pos.side_to_move is Color.WHITE else ga.black
        played = format_move(g, move)
        if len(legal_moves(pos)) == 1:
            ga.plies.append(PlyAnalysis(i + 1, player, pos.side_to_move.value, played, played,
                                        None, None, 0.0, "best", True))
            continue
        engine.new_game()
        req = AnalysisRequest(rs, game.start, limit, tuple(game.moves[:i]))
        r = engine.analyze(req)
        if r.status is not AnalysisStatus.OK or r.best_move is None:
            ga.plies.append(PlyAnalysis(i + 1, player, pos.side_to_move.value, played, None,
                                        None, None, None, "unknown", False))
            continue
        best = r.best_move
        root = root_value(r.final_info.score if r.final_info else None)
        if best.identity == move.identity:
            ga.plies.append(PlyAnalysis(i + 1, player, pos.side_to_move.value, played,
                                        format_move(g, best), root.utility, root.utility, 0.0, "best", False))
            continue

        def value_of(m):  # type: ignore[no-untyped-def]
            after = apply_move(pos, m)
            if not legal_moves(after):
                return terminal_win()
            engine.new_game()
            rr = engine.analyze(AnalysisRequest(rs, game.start, limit, (*game.moves[:i], m)))
            return value_after_move(rr.final_info.score if rr.status is AnalysisStatus.OK and rr.final_info else None)

        vb, vp = value_of(best), value_of(move)
        regret = (vb.utility - vp.utility) if vb.utility is not None and vp.utility is not None else None
        class_drop = (vb.outcome is OutcomeClass.WIN and vp.outcome is not OutcomeClass.WIN) or (
            vb.outcome is not OutcomeClass.LOSS and vp.outcome is OutcomeClass.LOSS)
        if regret is not None and regret < 0:
            regret = 0.0  # the played move looked better on re-search: no error
            class_drop = False
        ga.plies.append(PlyAnalysis(i + 1, player, pos.side_to_move.value, played, format_move(g, best),
                                    vb.utility, vp.utility, regret,
                                    labels.label(regret, False, class_drop), False))
    return ga
