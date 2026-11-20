"""G11 knowledge base: migrations, recording real gate outputs, queries, API and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import MakeDouble
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from damas_ai.adaptive import AdaptiveAnalyzer, EscalationPolicy
from damas_ai.adaptive.serialize import adaptive_view
from damas_ai.analysis import EnginePool
from damas_ai.api import create_app
from damas_ai.config import Settings
from damas_ai.consensus import ConsensusAnalyzer
from damas_ai.consensus.serialize import consensus_view
from damas_ai.decision import DecisionMaker
from damas_ai.decision.serialize import decision_view
from damas_ai.engines import AnalysisRequest, SearchLimit
from damas_ai.kb import Base, KnowledgeBase
from damas_ai.kb.__main__ import main as kb_cli
from damas_ai.kb.migrate import downgrade, upgrade
from damas_ai.kb.models import to_signed64
from damas_ai.rules import BOARD_8X8, BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, apply_move, legal_moves
from damas_ai.rules.notation import from_fen
from damas_ai.tactics import Thresholds, assess
from damas_ai.tactics.serialize import criticality_view

INTL = INTERNATIONAL_PROVISIONAL
START = INTL.initial_position()
AFTER_LAST = apply_move(START, legal_moves(START)[-1])
FAST = SearchLimit(move_time_s=0.05)
SACRIFICE = "W:W17,19,22,23,24,25,26,28,29,30,32:B1,4,5,9,10,12"


def preference_engines(double: MakeDouble, tmp_path: Path):  # type: ignore[no-untyped-def]
    t = tmp_path / "a.json"
    t.write_text(json.dumps({AFTER_LAST.to_dsa(): "0.50"}), encoding="utf-8")
    return [double("a", "--name", "Scan", "--score-table", str(t)),
            double("b", "--name", "Scan", "--pick", "last")]


# ---------------------------------------------------------------- schema / migrations


def test_migration_matches_orm_models_and_downgrades(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'kb.sqlite3'}"
    upgrade(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff
    assert set(inspect(engine).get_table_names()) >= {"positions", "engine_analyses", "consensus_records",
                                                       "tactical_records", "decisions", "tags"}
    downgrade(url)
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}


def test_signed_zobrist_and_position_dedupe() -> None:
    assert to_signed64((1 << 64) - 1) == -1 and to_signed64(5) == 5
    kb = KnowledgeBase(create=True)
    p = BRAZILIAN_PROVISIONAL.initial_position()
    with kb.session() as s:
        a = kb.upsert_position(s, p, BRAZILIAN_PROVISIONAL)
        b = kb.upsert_position(s, p, BRAZILIAN_PROVISIONAL)
        twin = kb.upsert_position(s, p.flipped(), BRAZILIAN_PROVISIONAL)
        assert a.id == b.id and twin.id != a.id
        assert twin.canonical_dsa == a.canonical_dsa  # colour-flipped twin grouped together
    assert kb.stats()["positions"] == 2


# ---------------------------------------------------------------- recording real gate outputs


def test_record_all_gate_outputs_and_query(double: MakeDouble, tmp_path: Path) -> None:
    kb = KnowledgeBase(create=True)
    configs = preference_engines(double, tmp_path)
    with EnginePool(configs) as pool:
        req = AnalysisRequest(INTL, START, FAST)
        cons = consensus_view(ConsensusAnalyzer(pool).analyze(req), START)
        adap = adaptive_view(AdaptiveAnalyzer(pool).analyze(req, policy=EscalationPolicy(max_steps=2)), START)
        dec = decision_view(DecisionMaker(pool).decide(req), START)
    tac = criticality_view(assess(from_fen(BOARD_8X8, SACRIFICE), Thresholds(depth=3)))
    with kb.session() as s:
        kb.record_consensus(s, cons)
        kb.record_adaptive(s, adap)
        kb.record_decision(s, dec, INTL.variant)
        kb.record_tactics(s, tac, BRAZILIAN_PROVISIONAL.variant)

    st = kb.stats()
    assert st["positions"] == 2 and st["positions_by_variant"] == {"international-10x10": 1, "brazilian-8x8": 1}
    assert st["consensus_records"] == 2 and st["decisions"] == 1 and st["tactical_records"] == 1
    assert st["engine_analyses"] == 4  # 2 engines x (consensus + adaptive final step)
    assert st["tags"]["stable_divergence"] == 1 and st["tags"]["critical"] == 1

    stable = kb.find(tag="stable_divergence")
    assert len(stable) == 1 and stable[0].variant == "international-10x10"
    assert [r.variant for r in kb.find(critical=True)] == ["brazilian-8x8"]
    assert len(kb.find(classification="preference")) == 1
    detail = kb.get(stable[0].id)
    assert detail is not None and {a["engine_id"] for a in detail["analyses"]} == {"a", "b"}
    assert detail["consensus"][1]["trajectory"] == ["preference", "preference"]
    assert detail["decisions"][0]["confidence"] in ("high", "medium", "low")
    assert kb.get(9999) is None


def test_api_kb_routes(tmp_path: Path) -> None:
    kb = KnowledgeBase(create=True)
    tac = criticality_view(assess(from_fen(BOARD_8X8, SACRIFICE), Thresholds(depth=3)))
    with kb.session() as s:
        kb.record_tactics(s, tac, "brazilian-8x8")
    with TestClient(create_app(Settings(_env_file=None), EnginePool([]), kb)) as client:
        assert client.get("/kb/stats").json()["positions"] == 1
        rows = client.get("/kb/positions", params={"critical": True}).json()
        assert len(rows) == 1 and client.get(f"/kb/positions/{rows[0]['id']}").status_code == 200
        assert client.get("/kb/positions/999").status_code == 404
    with TestClient(create_app(Settings(_env_file=None), EnginePool([]))) as client:
        assert client.get("/kb/stats").status_code == 503


def test_cli_migrate_ingest_query(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    url = f"sqlite:///{tmp_path / 'cli.sqlite3'}"
    tac = criticality_view(assess(from_fen(BOARD_8X8, SACRIFICE), Thresholds(depth=3)))
    jsonl = tmp_path / "t.jsonl"
    jsonl.write_text(json.dumps(tac) + "\n", encoding="utf-8")
    assert kb_cli(["--db", url, "migrate"]) == 0
    assert kb_cli(["--db", url, "ingest", "--kind", "tactics", str(jsonl)]) == 2  # variant missing
    assert kb_cli(["--db", url, "ingest", "--kind", "tactics", "--variant", "brazilian-8x8", str(jsonl)]) == 0
    capsys.readouterr()
    assert kb_cli(["--db", url, "find", "--critical", "yes"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["variant"] == "brazilian-8x8"
    assert kb_cli(["--db", url, "show", "1"]) == 0
