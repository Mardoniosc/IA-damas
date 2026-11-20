from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from damas_ai.config import EngineConfig
from damas_ai.engines.hub.adapter import HubEngine

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"
DOUBLE = Path(__file__).resolve().parent / "doubles" / "hub_double.py"

MakeConfig = Callable[..., EngineConfig]


@pytest.fixture
def make_config(tmp_path: Path) -> MakeConfig:
    def _make(*flags: str, variant: str = "international-10x10", **overrides: object) -> EngineConfig:
        data: dict[str, object] = {
            "id": "double",
            "protocol": "hub",
            "executable": sys.executable,
            "args": (str(DOUBLE), *flags),
            "working_dir": tmp_path,
            "native_variant": variant,
            "env": {"PYTHONPATH": str(BACKEND_SRC)},
            "init_timeout_s": 15.0,
            "search_timeout_s": 10.0,
            "stop_grace_s": 3.0,
            "quit_timeout_s": 3.0,
        }
        data.update(overrides)
        return EngineConfig.model_validate(data)

    return _make


@pytest.fixture
def engine_factory(make_config: MakeConfig) -> Iterator[Callable[..., HubEngine]]:
    created: list[HubEngine] = []

    def _engine(*flags: str, start: bool = True, **overrides: object) -> HubEngine:
        engine = HubEngine(make_config(*flags, **overrides))
        created.append(engine)
        if start:
            engine.start()
        return engine

    yield _engine
    for engine in created:
        engine.close()
