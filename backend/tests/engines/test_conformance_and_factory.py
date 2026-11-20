from __future__ import annotations

import json
from pathlib import Path

import pytest

from damas_ai.config import EngineConfig
from damas_ai.engines import AnalysisStatus, SearchLimit, create_engine, run_conformance
from damas_ai.engines.hub.adapter import HubEngine
from damas_ai.rules import BOARD_8X8, BOARD_10X10, BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL
from damas_ai.rules.notation import from_fen

ORACLE = Path(__file__).resolve().parents[1] / "fixtures" / "oracle"


def sample(name: str, geometry, n: int, captures_only: bool = False):  # type: ignore[no-untyped-def]
    data = json.loads((ORACLE / f"{name}_pydraughts.json").read_text(encoding="utf-8"))
    records = [r for r in data["positions"] if r["moves"]]
    if captures_only:
        records = [r for r in records if r["moves"][0][2]]
    return [from_fen(geometry, r["fen"]) for r in records[:n]]


def test_legal_double_passes_conformance_on_international_positions(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory()
    report = run_conformance(engine, INTERNATIONAL_PROVISIONAL, sample("international", BOARD_10X10, 40),
                             SearchLimit(move_time_s=0.05))
    assert report.passed and report.total == 40 and report.legal_rate == 1.0


def test_legal_double_passes_conformance_on_brazilian_capture_positions(engine_factory) -> None:  # type: ignore[no-untyped-def]
    engine = engine_factory(variant="brazilian-8x8")
    report = run_conformance(engine, BRAZILIAN_PROVISIONAL,
                             sample("brazilian", BOARD_8X8, 30, captures_only=True),
                             SearchLimit(move_time_s=0.05))
    assert report.passed, report.by_status


def test_rules_blind_engine_fails_conformance(engine_factory) -> None:  # type: ignore[no-untyped-def]
    """A double that ignores mandatory capture (like an engine with other rules) is caught."""
    engine = engine_factory("--rules-blind")
    report = run_conformance(engine, INTERNATIONAL_PROVISIONAL,
                             sample("international", BOARD_10X10, 25, captures_only=True),
                             SearchLimit(move_time_s=0.05))
    assert not report.passed
    assert report.by_status.get(AnalysisStatus.ILLEGAL_MOVE.value, 0) > 0
    assert report.failures and report.failures[0].best_move is None


# ---------------------------------------------------------------- factory


def cfg(**kw: object) -> EngineConfig:
    base: dict[str, object] = {"id": "x", "protocol": "hub", "executable": "x.exe",
                               "native_variant": "international-10x10"}
    return EngineConfig.model_validate(base | kw)


def test_factory_builds_hub_engines() -> None:
    assert isinstance(create_engine(cfg()), HubEngine)


def test_factory_refuses_out_of_scope_protocols_and_unknown_variants() -> None:
    with pytest.raises(NotImplementedError, match="ADR-005"):
        create_engine(cfg(protocol="cb-dll", native_variant="international-10x10"))
    with pytest.raises(NotImplementedError):
        create_engine(cfg(protocol="dxp"))
    with pytest.raises(ValueError, match="no Rules Core ruleset"):
        create_engine(cfg(native_variant="english-8x8"))
