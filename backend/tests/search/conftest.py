from __future__ import annotations

import json
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest

from damas_ai.config import EngineConfig
from damas_ai.rules import BOARD_8X8, BOARD_10X10, Position
from damas_ai.rules.notation import from_fen

TESTS = Path(__file__).resolve().parents[1]
BACKEND_SRC = TESTS.parent / "src"
ORACLE = TESTS / "fixtures" / "oracle"


@pytest.fixture
def internal_engine_config(tmp_path: Path) -> Callable[..., EngineConfig]:
    """Config for the internal engine process (python -m damas_ai.search.hub)."""

    def _make(variant: str = "brazilian", **overrides: object) -> EngineConfig:
        data: dict[str, object] = {
            "id": f"damasai_{variant}", "protocol": "hub", "executable": sys.executable,
            "args": ("-m", "damas_ai.search.hub"), "working_dir": tmp_path,
            "native_variant": {"brazilian": "brazilian-8x8", "international": "international-10x10"}[variant],
            "env": {"PYTHONPATH": str(BACKEND_SRC)}, "params": {"variant": variant},
            "init_timeout_s": 20.0, "search_timeout_s": 10.0, "stop_grace_s": 3.0,
        }
        data.update(overrides)
        return EngineConfig.model_validate(data)

    return _make


@cache
def oracle_positions(name: str) -> tuple[Position, ...]:
    geometry = {"brazilian": BOARD_8X8, "international": BOARD_10X10}[name]
    data = json.loads((ORACLE / f"{name}_pydraughts.json").read_text(encoding="utf-8"))
    return tuple(from_fen(geometry, r["fen"]) for r in data["positions"] if r["moves"])
