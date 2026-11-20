"""Engine Integration Framework (G3, ADR-002).

Engines are advisors: every move they report is validated by the Rules Core (ADR-001).
"""

from damas_ai.engines.base import EngineAdapter
from damas_ai.engines.conformance import ConformanceReport, run_conformance
from damas_ai.engines.errors import (
    CapabilityError,
    EngineError,
    EngineExited,
    EngineNotRunning,
    EngineStartError,
    EngineTimeout,
)
from damas_ai.engines.factory import create_engine
from damas_ai.engines.types import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    EngineCapabilities,
    EngineInfo,
    LimitKind,
    RawScore,
    SearchInfo,
    SearchLimit,
)

__all__ = [
    "AnalysisRequest", "AnalysisResult", "AnalysisStatus", "CapabilityError", "ConformanceReport",
    "EngineAdapter", "EngineCapabilities", "EngineError", "EngineExited", "EngineInfo",
    "EngineNotRunning", "EngineStartError", "EngineTimeout", "LimitKind", "RawScore", "SearchInfo",
    "SearchLimit", "create_engine", "run_conformance",
]
