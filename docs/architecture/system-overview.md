# System overview

Status: G1 baseline. Components marked *(Gx)* do not exist yet. They are listed only to fix
boundaries early.

## 1. Purpose

Damas Super AI is a platform that **reasons about Brazilian draughts positions** using several
independent sources of evidence: external engines, its own search and knowledge, and data.
It compares them, detects disagreement, and investigates. External engines are advisors and
never authorities.

## 2. Context

```
              +-------------------+
   user ----> | Angular UI (G15)  |
              +---------+---------+
                        | HTTP/JSON (FastAPI)
              +---------v-----------------------------------------------+
              |                  Backend (Python)                       |
              |                                                         |
              |  +-------------+   +-------------------------------+    |
              |  | Rules Core  |<--| Analysis orchestration (G6-8) |    |
              |  |   (G2)      |   |  consensus/divergence (G7)    |    |
              |  | legal-move  |   |  tactical/strategic (G9-10)   |    |
              |  | authority   |   +---------------+---------------+    |
              |  +------^------+                   |                    |
              |         | validate every           | engine-agnostic    |
              |         | engine move              | EngineAdapter API  |
              |  +------+---------------------------v---------------+   |
              |  |      Engine Integration Framework (G3)          |   |
              |  |  HubAdapter | CbDllAdapter (via host proc) | ... |   |
              |  +------+-------------------+-----------------------+  |
              |         | stdin/stdout      | stdin/stdout             |
              |  Knowledge base (G11, PostgreSQL) . Benchmarks (G12)    |
              |  Game analysis & datasets (G13) . Learning (G14)        |
              +---------|-------------------|---------------------------+
                        v                   v
                +--------------+    +------------------+
                | engine proc  |    | engine host proc |   one OS process per engine
                | (e.g. Scan)  |    |  (loads CB DLL)  |   instance; killable, isolated
                +--------------+    +------------------+
```

## 3. Architectural principles, and how G1 applies them

| # | Principle | G1 status |
|---|---|---|
| 1 | Modular architecture | Module boundaries fixed in this document. Only config/logging implemented |
| 2 | Engine-agnostic core | ADR-002: no engine type crosses the adapter boundary |
| 3 | Rules Core as legal-move authority | ADR-001 |
| 4 | Canonical position representation | ADR-003, `position-representation.md` |
| 5 | Engine Adapter Pattern | `engine-integration.md` |
| 6 | Independent engine processes | ADR-002 (DLL engines get a dedicated host process) |
| 7 | Strict resource management | PoC harness proves quit → terminate → kill escalation with deadlines |
| 8 | Test-driven development | 25 tests in G1 (config, logging, PoC harness) |
| 9 | Reproducible experiments | Logging standard requires config hash + engine versions (G12+) |
| 10 | Documented decisions | ADR-001…005 |
| 11 | Benchmark-driven evolution | Deferred to G12. Requires engines that play the target variant (ADR-005) |
| 12 | Licensing compliance | ADR-004, licensing report; zero third-party code in repo |

## 4. Module map (target) and the gate that introduces each

| Module (package `damas_ai.*`) | Responsibility | Gate |
|---|---|---|
| `config`, `logging_config` | Externalized settings, logging standard | **G1 (exists)** |
| `rules` | Board geometry, position, move generation, game state, draw rules, notation | G2 |
| `engines` | `EngineAdapter` interface, process supervisor, protocol adapters, score normalization | G3 |
| `engines.scan`, `engines.kingsrow` | Engine-specific adapters + capability declarations | G4, G5 |
| `analysis` | Engine pool, multi-engine fan-out (parallel/sequential), proposals, JSONL batch CLI | **G6 (exists)** |
| `consensus` | Cross-evaluation, per-engine regret, divergence classes, proof gaps, scale fit (ADR-009) | **G7 (exists)** |
| `search` | Internal alpha-beta engine over the Rules Core, served over Hub (ADR-010) | **G8 (exists)** |
| `adaptive` | Escalate consensus effort on divergence; trajectories (ADR-010) | **G8 (exists)** |
| `tactics` | Threats, forcing-shot detector, criticality report (ADR-011) | **G9 (exists)** |
| `strategy` | Descriptive strategic profile (ADR-012) | **G10 (exists)** |
| `decision` | Minimax normalized-regret decision with confidence (ADR-012) | **G10 (exists)** |
| `kb` | Position knowledge base (PostgreSQL + SQLAlchemy + Alembic) | G11 |
| `bench` | Matches, tournaments, statistical evaluation | G12 |
| `games`, `datasets` | PDN import, game annotation, dataset builds | G13 |
| `learning` | Training/evaluation pipelines (PyTorch, optional) | G14 |
| `api` | FastAPI app: health, variants, engines, analyses (local only, ADR-008) | **G6 (exists)** |

## 5. Dependency introduction policy

A dependency is added in the gate that first uses it, with a one-line justification in that
gate's report:

| Dependency | Planned gate | Reason |
|---|---|---|
| pydantic, pydantic-settings | G1 (added) | config validation |
| pytest, pytest-cov | G1 (dev) | tests |
| ruff | G2 (dev) | lint/format |
| FastAPI + uvicorn (+ httpx dev) | **G6 (added)** | HTTP API |
| SQLAlchemy, Alembic, psycopg | G11 (or earlier if persistence of analyses is required in G6-G7) | knowledge base |
| PostgreSQL server | same as above | **not installed on the dev machine today** (`psql` not found, 2026-11-20) |
| Angular | G6/G15 | UI |
| Redis, Docker, PyTorch | only if a measured need appears | |

## 6. Runtime model

- Local-first. A single backend process supervises N engine child processes.
- Each engine process has explicit deadlines for init, search and quit. Hung processes are
  terminated and then killed. A crash is recorded as a result, not propagated as a platform
  failure.
- Engines are configured, not discovered. Each declares its `native_variant`. The
  orchestrator refuses to send a position of variant V to an engine that does not declare V.

## 7. Environment observed in G1 (2026-11-20)

Windows 11 Pro; Python 3.11.9 (64-bit); Node v26.13.1; npm 11.20.0; git 2.51; Docker 28.4.0;
PostgreSQL client not installed. Python packages already present for the user: FastAPI 0.140.13,
Pydantic 2.12.3, SQLAlchemy 2.0.44, Alembic 1.17.1, pytest 9.1.1, py-draughts 1.10.1.
No SCAN or KingsRow binaries were found on disk (see technical-discovery.md §3).
