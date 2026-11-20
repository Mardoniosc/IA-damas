from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from damas_ai.config import EngineConfig

TESTS = Path(__file__).resolve().parents[1]
BACKEND_SRC = TESTS.parent / "src"
DOUBLE = TESTS / "engines" / "doubles" / "hub_double.py"

MakeDouble = Callable[..., EngineConfig]


@pytest.fixture
def double(tmp_path: Path) -> MakeDouble:
    """EngineConfig for the Hub test double: double("a", "--pick", "last", variant=...)."""

    def _make(engine_id: str, *flags: str, variant: str = "international-10x10",
              **overrides: object) -> EngineConfig:
        data: dict[str, object] = {
            "id": engine_id, "protocol": "hub", "executable": sys.executable,
            "args": (str(DOUBLE), *flags), "working_dir": tmp_path, "native_variant": variant,
            "env": {"PYTHONPATH": str(BACKEND_SRC)}, "init_timeout_s": 15.0,
            "search_timeout_s": 10.0, "stop_grace_s": 3.0, "quit_timeout_s": 3.0,
        }
        data.update(overrides)
        return EngineConfig.model_validate(data)

    return _make
