# G11 report — Position Knowledge Base

Gate: **G11** · Date: 2026-11-20 · Status: **complete** (PostgreSQL not verified, see §5).
Design: ADR-013.

## 1. What was built — `damas_ai.kb`

| Component | Content |
|---|---|
| `models.py` | SQLAlchemy 2.0 schema: positions, engine_analyses, consensus_records, tactical_records, decisions, tags |
| `backend/alembic/` | Alembic environment (`DAMAS_DATABASE_URL`), migration `0001_initial_kb` |
| `store.KnowledgeBase` | upsert positions (dedupe, canonical twin grouping); record G6/G7/G8/G9/G10 JSON views; automatic tags; queries (`stats`, `find`, `get`) |
| `migrate.py` | programmatic `upgrade`/`downgrade` |
| CLI | `python -m damas_ai.kb migrate | ingest --kind … | stats | find | show` |
| API | `GET /kb/stats`, `GET /kb/positions`, `GET /kb/positions/{id}` (503 when no DB is configured) |
| Settings | `DAMAS_DATABASE_URL`. Runtime dependencies: SQLAlchemy and Alembic (already installed) |

## 2. Verification

### 2.1 Tests (5 new)

- **The migration matches the ORM exactly** (Alembic autogenerate diff is empty); downgrade
  removes all tables.
- Signed Zobrist, position dedupe, and the colour-flipped twin sharing `canonical_dsa`.
- Recording **real** outputs produced in-test by the G7 consensus, G8 adaptive, G10 decision
  and G9 tactics code; stats, tags (`stable_divergence`, `critical`), `find` by tag,
  classification and criticality, and the detail view.
- API routes, including 503 without a DB.
- CLI migrate/ingest/find/show.

```
cd backend && python -m pytest   -> 229 passed, 5 skipped
```

### 2.2 Real data: outputs of G6–G9 ingested

| Input (JSONL from earlier gates) | Records |
|---|---|
| G6 multi-engine analyses (parallel + sequential, 300 positions each) | 600 |
| G7 consensus (300) + G8 three-engine consensus (100) | 400 |
| G8 adaptive trajectories | 39 |
| G9 Brazilian criticality (300 positions, new run, 49 s) | 300 |
| **Total** | **1,339 records in 8 s, 0 errors; SQLite file 2.1 MB** |

Result: **600 distinct positions** (300 International shared across the runs, 300 Brazilian),
2,178 engine analyses, 439 consensus records, 300 tactical records. Tags: critical 106,
divergence:preference 77, proof_gap 30, stable_divergence 13, tactics:volatile 62 /
only_move 30 / shot 26 / threat 9.

### 2.3 Cross-gate questions the KB can now answer

| Question | Answer |
|---|---|
| How often does each engine change its best move between repeated runs (same 300 positions, 0.2 s)? | **Scan 2.3%, Kingsrow 4.3%**. This quantifies R20 per engine |
| Were G8's stable divergences already visible in the single G7 run? | yes, 13/13 |
| Brazilian critical positions with a sacrifice shot | 18 (e.g. `B:W12,13,21,…:B1,…,11`, shot `6-9`, +1 man) |
| Colour-flipped twins stored | none in this sample (600 canonical positions = 600 stored) |

## 3. Findings and fixes

| Finding | Fix |
|---|---|
| In-memory SQLite gave each thread its own empty database (FastAPI worker threads) | `StaticPool` + `check_same_thread=False` for `:memory:` |
| Alembic deprecation warning (`path_separator`) | set in alembic.ini |

## 4. Acceptance

| Criterion | Status |
|---|---|
| Persistent position knowledge base with provenance | **met** |
| Schema managed by migrations, parity proven | **met** |
| Ingestion of the platform's own evidence, with queries across gates | **met** (1,339 real records) |
| SQLAlchemy + Alembic per the stack | **met** |
| **PostgreSQL** per the stack | **NOT verified**: no server or driver installed, and installing needs owner approval (R22) |

## 5. How to verify PostgreSQL once approved

1. Install a PostgreSQL server (or `docker run postgres`) and `pip install psycopg[binary]`.
2. `DAMAS_DATABASE_URL=postgresql+psycopg://user:pass@localhost/damas python -m damas_ai.kb migrate`
3. Re-run `tests/analysis/test_kb.py` with the URL pointed at PostgreSQL (the test helper
   accepts any URL), then ingest the same JSONL files and compare `stats`.
