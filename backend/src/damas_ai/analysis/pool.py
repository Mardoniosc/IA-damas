"""EnginePool: owns one adapter per configured engine, starts them lazily, enforces a CPU
thread budget and replaces dead processes (ADR-008)."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from damas_ai.config import EngineConfig
from damas_ai.engines import EngineAdapter, EngineError, create_engine

log = logging.getLogger("damas_ai.analysis.pool")


class ThreadBudgetExceeded(EngineError):
    """Starting the engine would exceed the configured thread budget."""


@dataclass(frozen=True)
class EngineStatus:
    engine_id: str
    enabled: bool
    native_variant: str
    running: bool
    name: str | None
    version: str | None
    profile: str | None
    threads: int
    problems: tuple[str, ...]
    restarts: int


def engine_threads(config: EngineConfig) -> int:
    try:
        return max(1, int(config.params.get("threads", "1")))
    except ValueError:
        return 1


class EnginePool:
    def __init__(
        self,
        configs: Iterable[EngineConfig],
        thread_budget: int | None = None,
        factory: Callable[[EngineConfig], EngineAdapter] = create_engine,
    ) -> None:
        self.configs = {c.id: c for c in configs if c.enabled}
        self.thread_budget = thread_budget or os.cpu_count() or 1
        self._factory = factory
        self._adapters: dict[str, EngineAdapter] = {}
        self._restarts: dict[str, int] = {}
        self._lock = threading.Lock()
        total = sum(engine_threads(c) for c in self.configs.values())
        if total > self.thread_budget:
            # Not fatal at construction: engines may not all be used. Checked again at start.
            log.warning("configured engine threads exceed budget",
                        extra={"ctx": {"threads": total, "budget": self.thread_budget}})

    # ---------------------------------------------------------------- access

    def engine_ids(self) -> list[str]:
        return sorted(self.configs)

    def engines_for_variant(self, variant: str) -> list[str]:
        return sorted(i for i, c in self.configs.items() if c.native_variant == variant)

    def get(self, engine_id: str) -> EngineAdapter:
        """Return a running adapter, starting (or restarting a dead one) as needed."""
        with self._lock:
            config = self.configs.get(engine_id)
            if config is None:
                raise KeyError(f"unknown or disabled engine {engine_id!r}")
            adapter = self._adapters.get(engine_id)
            if adapter is not None and adapter.running:
                return adapter
            if adapter is not None:  # existed but died (crash, timeout kill)
                self._restarts[engine_id] = self._restarts.get(engine_id, 0) + 1
                log.warning("restarting dead engine", extra={"ctx": {"engine": engine_id}})
                adapter.close()
            else:
                self._check_budget(config)
                problems = config.check_available()
                if problems:
                    raise EngineError(f"{engine_id}: " + "; ".join(problems))
                adapter = self._factory(config)
                self._adapters[engine_id] = adapter
            adapter.start()
            return adapter

    def warm_up(self, engine_ids: Iterable[str] | None = None) -> dict[str, str]:
        """Start engines ahead of time; returns ``{id: "ok" | error text}``."""
        out: dict[str, str] = {}
        for engine_id in engine_ids or self.engine_ids():
            try:
                self.get(engine_id)
                out[engine_id] = "ok"
            except (EngineError, KeyError) as exc:
                out[engine_id] = f"{type(exc).__name__}: {exc}"
        return out

    def _check_budget(self, config: EngineConfig) -> None:
        used = sum(engine_threads(self.configs[i]) for i in self._adapters)
        need = engine_threads(config)
        if used + need > self.thread_budget:
            raise ThreadBudgetExceeded(
                f"{config.id} needs {need} thread(s); {used}/{self.thread_budget} already allocated"
            )

    # ---------------------------------------------------------------- status / shutdown

    def status(self) -> list[EngineStatus]:
        out = []
        with self._lock:
            for engine_id in sorted(self.configs):
                c = self.configs[engine_id]
                a = self._adapters.get(engine_id)
                running = a is not None and a.running
                info = a.info if running and a is not None else None
                out.append(EngineStatus(
                    engine_id=engine_id, enabled=c.enabled, native_variant=c.native_variant,
                    running=running, name=info.name if info else None,
                    version=info.version if info else None, profile=info.profile if info else None,
                    threads=engine_threads(c), problems=tuple(c.check_available()),
                    restarts=self._restarts.get(engine_id, 0),
                ))
        return out

    def close(self) -> dict[str, str]:
        with self._lock:
            results = {i: a.close() for i, a in self._adapters.items()}
            self._adapters.clear()
            return results

    def __enter__(self) -> EnginePool:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
