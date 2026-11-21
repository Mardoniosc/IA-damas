"""Benchmarks and tournaments (G12, ADR-014)."""

from damas_ai.bench.game import GameRecord, play_game
from damas_ai.bench.match import MatchResult, round_robin, run_match, standings, to_pdn, write_outputs
from damas_ai.bench.openings import Opening, generate_openings
from damas_ai.bench.players import EnginePlayer, GreedyPlayer, MoveChoice, Player, RandomPlayer, SearchPlayer
from damas_ai.bench.stats import LogisticFit, MatchStats, fit_logistic, match_stats

__all__ = [
    "EnginePlayer", "GameRecord", "GreedyPlayer", "LogisticFit", "MatchResult", "MatchStats",
    "MoveChoice", "Opening", "Player", "RandomPlayer", "SearchPlayer", "fit_logistic", "generate_openings",
    "match_stats", "play_game", "round_robin", "run_match", "standings", "to_pdn", "write_outputs",
]
