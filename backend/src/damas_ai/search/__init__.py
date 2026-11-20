"""Internal search engine (G8, ADR-010): alpha-beta over the Rules Core, served over Hub."""

from damas_ai.search.evaluation import evaluate
from damas_ai.search.searcher import DepthInfo, SearchOutcome, Searcher, score_to_men

__all__ = ["DepthInfo", "SearchOutcome", "Searcher", "evaluate", "score_to_men"]
