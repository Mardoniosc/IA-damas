"""Real-engine checks. Skipped unless DAMAS_ENGINES_CONFIG points at a config with enabled,
available engines (binaries are never part of the repo, ADR-004).

    DAMAS_ENGINES_CONFIG=../config/engines.toml python -m pytest -m engine -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from damas_ai.config import load_engine_configs
from damas_ai.engines import AnalysisRequest, AnalysisStatus, SearchLimit, create_engine, run_conformance
from damas_ai.rules import RULESETS
from damas_ai.rules.notation import from_fen

pytestmark = pytest.mark.engine
ORACLE = Path(__file__).resolve().parents[1] / "fixtures" / "oracle"
ORACLE_BY_VARIANT = {"international-10x10": "international", "brazilian-8x8": "brazilian"}


def _engines() -> list:  # type: ignore[type-arg]
    path = os.environ.get("DAMAS_ENGINES_CONFIG")
    if not path:
        return []
    return [c for c in load_engine_configs(Path(path)).values()
            if c.enabled and not c.check_available() and c.native_variant in ORACLE_BY_VARIANT]


ENGINES = _engines()


@pytest.mark.skipif(not ENGINES, reason="no real engine configured (DAMAS_ENGINES_CONFIG)")
@pytest.mark.parametrize("config", ENGINES, ids=lambda c: c.id)
def test_real_engine_smoke_and_conformance(config) -> None:  # type: ignore[no-untyped-def]
    ruleset = next(r for r in RULESETS.values() if r.variant == config.native_variant)
    data = json.loads((ORACLE / f"{ORACLE_BY_VARIANT[config.native_variant]}_pydraughts.json").read_text())
    positions = [from_fen(ruleset.geometry, r["fen"]) for r in data["positions"] if r["moves"]][:200]
    with create_engine(config) as engine:
        first = engine.analyze(AnalysisRequest(ruleset, ruleset.initial_position(), SearchLimit(move_time_s=1)))
        assert first.status is AnalysisStatus.OK, first.violations
        report = run_conformance(engine, ruleset, positions, SearchLimit(move_time_s=0.2))
    assert report.passed, (report.by_status, [f.violations for f in report.failures])


@pytest.mark.skipif(len(ENGINES) < 2, reason="needs two real engines configured")
def test_real_multi_engine_analysis_parallel() -> None:
    from damas_ai.analysis import EnginePool, MultiEngineAnalyzer

    variant = ENGINES[0].native_variant
    ruleset = next(r for r in RULESETS.values() if r.variant == variant)
    with EnginePool([c for c in ENGINES if c.native_variant == variant]) as pool:
        result = MultiEngineAnalyzer(pool).analyze(
            AnalysisRequest(ruleset, ruleset.initial_position(), SearchLimit(move_time_s=0.5)))
    assert len(result.engines_ok) >= 2, [o.error or o.result.violations for o in result.outcomes]
    assert sum(len(p.engines) for p in result.proposals) == len(result.engines_ok)
