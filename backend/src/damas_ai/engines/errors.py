"""Engine-integration exceptions. Search-time failures are reported in ``AnalysisResult``;
these exceptions are for lifecycle failures and caller mistakes."""

from __future__ import annotations


class EngineError(RuntimeError):
    """Base class."""


class EngineStartError(EngineError):
    """The engine could not be launched or failed the handshake."""


class EngineNotRunning(EngineError):
    """The engine process is not available (never started, closed, crashed or killed)."""


class CapabilityError(EngineError):
    """The request needs something the engine does not declare (e.g. another variant)."""


class EngineTimeout(EngineError):
    """A deadline expired while waiting for the engine."""


class EngineExited(EngineError):
    """The engine closed its output (process ended)."""
