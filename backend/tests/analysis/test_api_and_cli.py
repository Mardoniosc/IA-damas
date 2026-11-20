from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import MakeDouble
from fastapi.testclient import TestClient

from damas_ai.analysis import EnginePool
from damas_ai.analysis.__main__ import main as cli_main
from damas_ai.api import create_app
from damas_ai.config import Settings

START = "W:W31-50:B1-20"


@pytest.fixture
def client(double: MakeDouble):  # type: ignore[no-untyped-def]
    pool = EnginePool([double("a"), double("b", "--pick", "last"),
                       double("br", variant="brazilian-8x8")])
    with TestClient(create_app(Settings(_env_file=None), pool)) as c:
        yield c
    pool.close()


def body(**kw: object) -> dict:
    data: dict[str, object] = {"variant": "international-10x10", "fen": START,
                               "limit": {"move_time_s": 0.05}}
    data.update(kw)
    return data


def test_health_variants_engines(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    variants = {v["variant"]: v for v in client.get("/variants").json()}
    assert variants["brazilian-8x8"]["engines"] == ["br"]
    assert variants["brazilian-8x8"]["provisional"] is True
    engines = {e["engine_id"]: e for e in client.get("/engines").json()}
    assert set(engines) == {"a", "b", "br"} and not engines["a"]["running"]


def test_post_analysis_runs_all_capable_engines(client: TestClient) -> None:
    r = client.post("/analyses", json=body())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["requested_engines"] == ["a", "b"]
    assert [res["status"] for res in data["results"]] == ["ok", "ok"]
    assert len(data["proposals"]) == 2  # the two doubles disagree by construction
    assert "transcript" not in data["results"][0]


def test_move_history_in_either_notation(client: TestClient) -> None:
    r = client.post("/analyses", json=body(moves=["32-28", "19-23"], engines=["a"]))
    assert r.status_code == 200
    assert r.json()["position"]["fen"] != START
    r2 = client.post("/analyses", json=body(moves=["32-28", "x"], engines=["a"]))
    assert r2.status_code == 422


@pytest.mark.parametrize(
    ("patch", "fragment"),
    [
        ({"variant": "english-8x8"}, "unknown variant"),
        ({"fen": "nonsense"}, "bad FEN"),
        ({"fen": "W:W:B1"}, "terminal"),
        ({"limit": {"move_time_s": 1, "depth": 3}}, "exactly one"),
        ({"moves": ["31-30"]}, "not legal"),
    ],
)
def test_bad_requests_are_422(client: TestClient, patch: dict, fragment: str) -> None:
    r = client.post("/analyses", json=body(**patch))
    assert r.status_code == 422 and fragment in r.text


def test_brazilian_analysis_uses_only_brazilian_engines(client: TestClient) -> None:
    r = client.post("/analyses", json=body(variant="brazilian-8x8", fen="W:W21-32:B1-12"))
    data = r.json()
    assert data["requested_engines"] == ["br"] and data["results"][0]["status"] == "ok"


def test_cli_writes_one_self_contained_record_per_fen(double: MakeDouble, tmp_path: Path) -> None:
    config = tmp_path / "engines.toml"
    a, b = double("a"), double("b", "--pick", "last")
    lines = []
    for c in (a, b):
        lines += [f"[engines.{c.id}]", 'protocol = "hub"',
                  f"executable = {json.dumps(str(c.executable))}",
                  f"args = {json.dumps(list(c.args))}",
                  f"working_dir = {json.dumps(str(c.working_dir))}",
                  'native_variant = "international-10x10"',
                  f"[engines.{c.id}.env]", f"PYTHONPATH = {json.dumps(c.env['PYTHONPATH'])}"]
    config.write_text("\n".join(lines), encoding="utf-8")
    fens = tmp_path / "fens.txt"
    fens.write_text(f"# comment\n{START}\n\nW:W32,47:B28,1\nnot-a-fen\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"
    code = cli_main(["--config", str(config), "--variant", "international-10x10", "--fens", str(fens),
                     "--move-time", "0.05", "--mode", "sequential", "--out", str(out)])
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert code == 1  # one bad line reported
    assert len(records) == 2
    assert all(r["mode"] == "sequential" and len(r["results"]) == 2 for r in records)
    assert records[1]["results"][0]["best_move"]["captured"] == [28]  # forced capture 32x23
