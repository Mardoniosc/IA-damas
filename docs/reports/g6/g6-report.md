# G6 report — Multi-Engine Analysis

Gate: **G6 Multi-Engine Analysis** · Date: 2026-11-20 · Status: **complete, awaiting owner
review**. Design: ADR-008. Engines available: Scan 3.1 and Kingsrow hub 1.63, both
International 10x10 only (ADR-005). **No engine plays Brazilian; the platform reports this
explicitly.**

## 1. What was built

| Component | Content |
|---|---|
| `damas_ai.analysis.pool.EnginePool` | one adapter per enabled engine; lazy start, `warm_up`, status, restart of dead processes, CPU thread budget (`DAMAS_ENGINE_THREAD_BUDGET`, default CPU count) |
| `damas_ai.analysis.orchestrator.MultiEngineAnalyzer` | one position on N engines, `parallel` or `sequential`; variant-based selection; per-engine errors captured as outcomes; `proposals` (moves grouped by engine); run metadata and config fingerprint |
| `damas_ai.analysis.serialize` | JSON views (`schema_version 1`): moves in numeric and algebraic notation, captured squares, score with unit/kind/distance/perspective, PV, violations, optional transcript |
| `python -m damas_ai.analysis` | batch CLI: FEN file → JSONL, one self-contained record per position |
| `damas_ai.api` (FastAPI) | `GET /health`, `GET /variants`, `GET /engines`, `POST /analyses` (FEN + optional move history in either notation + limit + engines + mode); 422 on invalid input |
| `.claude/launch.json` | dev launcher for the API on 127.0.0.1:8765 |

Dependencies added: `fastapi`, `uvicorn` (runtime) and `httpx` (dev). All three were already
installed on this machine.

## 2. Verification

### 2.1 Tests (doubles)

| Area | Tests |
|---|---|
| Pool | lazy start/close, disabled engines, thread budget, restart after crash, missing executable reported |
| Orchestrator | side-by-side proposals (doubles that disagree), **parallel overlaps / sequential does not** (two 0.6 s engines: < 1.0 s vs ≥ 1.0 s), Brazilian with no engines → explicit note, wrong-variant and unknown engines reported, Brazilian-capable double used for Brazilian, JSON round trip |
| API | health/variants/engines, analysis of all capable engines, move history in both notations, 422 cases (unknown variant, bad FEN, terminal position, two limits, illegal move), Brazilian routing |
| CLI | records per FEN, comments/blank lines skipped, bad line reported (exit 1), forced capture resolved |

```
cd backend && python -m pytest                                                  -> 164 passed, 4 skipped
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml python -m pytest -m engine -> 3 passed (Scan, Kingsrow, multi-engine)
```

### 2.2 Real engines: batch CLI, 300 International positions, 0.2 s per move

Positions: every ~12th oracle position (83 with a capture available). Command:
`python -m damas_ai.analysis --config ../config/engines.toml --variant international-10x10 --fens ../reports/poc-runs/g6-fens.txt --move-time 0.2 --mode {parallel|sequential} --out ...`

| Measure | Parallel | Sequential |
|---|---|---|
| Results `ok` | 600/600 | 600/600 |
| Violations | 0 | 0 |
| Wall time | 81 s | 129 s |
| Same best move (descriptive) | 212/300 (70.7%) | 211/300 (70.3%) |
| Scan: mean depth / median nodes | 26.50 / 1,204,087 | 27.05 / 1,545,962 |
| Kingsrow: mean depth / median nodes | 16.52 / 1,701,920 | 17.34 / 2,524,568 |

**Finding: parallel runs cut search effort** (nodes −22% for Scan, −33% for Kingsrow) even at
one thread each on 16 cores. Equal time is not equal effort, so comparisons must use
`sequential` mode (ADR-008 §3).

Depth numbers are **not comparable across engines**: each engine counts depth its own way.

### 2.3 Real HTTP API (uvicorn on 127.0.0.1:8765)

`POST /analyses` (International start position + `32-28 19-23`, 0.5 s): both engines `ok`,
both proposed `28x19` (a forced capture). Scores: Scan `0.01` (unit `men`), Kingsrow `0.00`
(unit `men (empirical)`). 1.0 s including starting both engines. Brazilian request: no engines,
with the explicit note. Invalid limit: 422.

## 3. Findings and fixes during G6

| Finding | Handling |
|---|---|
| Parallel contention reduces engine effort | ADR-008: `sequential` mode required for comparisons; recorded in R10 |
| The test double did not declare `threads` → strict handshake refused it (correct behaviour) | double now declares `threads`; two G3 tests updated to use another undeclared parameter |
| `python -m damas_ai.analysis` needs the package importable | use `pip install -e backend` (README) or `PYTHONPATH=backend/src` |
| Starlette deprecation warning: `httpx` with TestClient ("install httpx2") | harmless today; revisit when upgrading Starlette |

## 4. Acceptance (G6)

| Criterion | Status |
|---|---|
| Analyse one position with several engines; side-by-side validated results | **met** |
| Engine lifecycle and resource governance (pool, budget, restart) | **met** |
| Fair-comparison mode | **met** (`sequential`), justified by measured contention |
| Variant gating, with Brazilian unavailability made explicit | **met** |
| Reproducible records (metadata, fingerprint, JSONL) | **met** |
| External interface | **met** (HTTP API, local only) |
| Brazilian multi-engine analysis | **not possible** with the engines available (ADR-005). Needs a Brazilian engine (discovery item) or the internal engine (G8) |

## 5. Open items for G7 and later

- Consensus and divergence metrics, score calibration (Scan "men" vs Kingsrow empirical
  scale and win bands), and Kingsrow multi-PV for ranked move lists: **G7**.
- The API has no authentication: local only until a deployment decision.
- Results are persisted only as JSONL. The database comes with G11.
