"""The engine-agnostic adapter interface (ADR-002)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from damas_ai.engines.types import AnalysisRequest, AnalysisResult, EngineCapabilities, EngineInfo


class EngineAdapter(ABC):
    """One external engine instance (one OS process).

    Contract:
    - ``start()`` launches and initialises the engine, or raises ``EngineStartError``.
    - ``analyze()`` never returns an engine move that the Rules Core has not validated.
      Search-time failures (timeout, crash, illegal or garbled answers) are reported through
      ``AnalysisResult.status``, not raised.
    - Requests for a variant the engine does not declare raise ``CapabilityError``.
    - ``close()`` is idempotent.
    """

    engine_id: str

    @abstractmethod
    def start(self) -> EngineInfo: ...

    @property
    @abstractmethod
    def info(self) -> EngineInfo: ...

    @abstractmethod
    def capabilities(self) -> EngineCapabilities: ...

    @abstractmethod
    def analyze(self, request: AnalysisRequest) -> AnalysisResult: ...

    @abstractmethod
    def new_game(self) -> None: ...

    @property
    @abstractmethod
    def running(self) -> bool: ...

    @abstractmethod
    def close(self) -> str: ...

    def __enter__(self) -> EngineAdapter:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
