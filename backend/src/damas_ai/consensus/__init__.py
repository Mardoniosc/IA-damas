"""Consensus & divergence across engines (G7, ADR-009)."""

from damas_ai.consensus.analyzer import (
    DEFAULT_TOLERANCE,
    Candidate,
    ConsensusAnalyzer,
    ConsensusResult,
    Divergence,
)
from damas_ai.consensus.calibration import ScaleFit, fit_scale
from damas_ai.consensus.values import MoveValue, OutcomeClass

__all__ = [
    "DEFAULT_TOLERANCE", "Candidate", "ConsensusAnalyzer", "ConsensusResult", "Divergence",
    "MoveValue", "OutcomeClass", "ScaleFit", "fit_scale",
]
