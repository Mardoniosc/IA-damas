"""Tactical intelligence (G9, ADR-011): threats, shots, critical positions."""

from damas_ai.tactics.critical import CriticalityReport, MoveValue, Thresholds, assess, evaluate_moves
from damas_ai.tactics.forcing import Shot, Threat, find_shots, material, threats_against

__all__ = [
    "CriticalityReport", "MoveValue", "Shot", "Threat", "Thresholds", "assess", "evaluate_moves",
    "find_shots", "material", "threats_against",
]
