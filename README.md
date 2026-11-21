# Damas Super AI

An independent, research-driven, multi-engine intelligence platform for **Brazilian draughts
(damas brasileiras, 8x8)**. The goal is not to wrap external engines in a GUI. Engines are
advisors: an internal Rules Core is the authority on legal moves, and an independent
decision-intelligence layer is the long-term product.

> **Status: G1–G12 complete** (latest: [G12 report](docs/reports/g12/g12-report.md)). The platform has
> its own engine, which plays **Brazilian** and International (an untuned baseline, weaker than Scan
> and Kingsrow). Disagreements between engines are classified (G7) and escalated adaptively (G8),
> tactics and critical positions are detected (G9), and a decision layer recommends
> a move with confidence (G10), all evidence can be stored and queried in a knowledge base (G11), and engines play
> arbitrated tournaments with Elo estimates (G12). The owner authorized proceeding
> gate by gate with a commit at the end of each.

## Key G1 finding (read this first)

Neither SCAN nor KingsRow can play Brazilian 8x8 draughts as published today:

| Engine | What it actually plays | Brazilian 8x8 |
|---|---|---|
| Scan 3.1 (Fabien Letouzey, GPL-3.0) | 10x10 only: international, killer, breakthrough, frisian, losing | **No.** The board size is a compile-time constant (10x10) |
| Kingsrow (Ed Gilbert, freeware) | English 8x8, Italian 8x8 (CheckerBoard DLL); International 10x10 (own GUI + "hub" build) | **No.** No Brazilian build exists |

**Decided (ADR-005, option A):** Brazilian 8x8 stays the target. SCAN and Kingsrow
International are integrated on 10x10 International to validate the engine framework, and
Brazilian-capable engines are searched for separately. See
[ADR-005](docs/architecture/decisions/ADR-005.md) and the
[feasibility report](docs/reports/g1/05-feasibility-report.md).

## Repository layout

```
backend/                 Python package `damas_ai`
  src/damas_ai/          config.py, logging_config.py (G1); rules/ = Rules Core (G2);
                         engines/ = engine adapters, Hub protocol, conformance (G3);
                         analysis/ = engine pool, multi-engine runs, batch CLI (G6);
                         consensus/ = cross-evaluation, divergence classes (G7);
                         search/ = internal engine, Hub server (G8);
                         adaptive/ = escalation on divergence (G8);
                         tactics/ = threats, shots, criticality (G9);
                         strategy/, decision/ = profile, recommended move (G10);
                         kb/ = knowledge base, Alembic migrations in backend/alembic (G11);
                         bench/ = tournaments, Elo, PDN (G12);
                         api/ = local HTTP API (G6-G11)
  tests/                 pytest suite; tests/fixtures/oracle = independent reference data
frontend/                Angular app - intentionally NOT scaffolded yet (see frontend/README.md)
config/                  *.example files only; real config is git-ignored
scripts/poc/             G1 proof-of-concept (superseded by damas_ai.engines; kept as a record)
scripts/oracle/          dev-only: regenerates Rules Core reference data with py-draughts (GPL, ADR-004)
scripts/engines/         build_scan.ps1 (Scan 3.1 from source, MSVC); engine_evidence.py
engines/                 git-ignored: locally built third-party engines (never committed)
docs/
  architecture/          system overview, engine integration, position representation,
                         rules compatibility, technical discovery, ADRs
  conventions.md         coding, testing, configuration and logging standards
  reports/g1/            the 12 G1 deliverables (index: docs/reports/g1/README.md)
```

## Quick start (development)

Requirements: Python 3.11+. The knowledge base runs on SQLite by default; PostgreSQL is supported
by URL but not yet verified. Node/Angular and Docker are not needed yet.

```bash
cd backend
python -m pip install -e ".[dev]"
python -m pytest
```

Deep perft regression (about 2 minutes):

```bash
cd backend && DAMAS_SLOW_TESTS=1 python -m pytest tests/rules
```

```bash
python -m pytest scripts/poc/tests
```

Real-engine checks (skipped unless engines are configured and present):

```bash
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml python -m pytest -m engine -v
```

Run the G1 PoC harness against the mock engine:

```bash
python scripts/poc/hub_poc.py --executable scripts/poc/mock_hub_engine.py --set variant=normal --move-time 0.1
```

Build Scan 3.1 locally from source (needs Visual Studio with the C++ x64 toolset), then
point `config/engines.toml` at `engines/scan31/bin/scan.exe`:

```bash
powershell -ExecutionPolicy Bypass -File scripts/engines/build_scan.ps1
```

```bash
python scripts/engines/engine_evidence.py --config config/engines.toml --engine scan --positions 1500 --move-time 0.1 --out reports/poc-runs/scan-evidence.json
```

Multi-engine batch analysis (one FEN per line → JSONL; use `--mode sequential` for fair
engine comparisons, ADR-008):

```bash
cd backend && python -m damas_ai.analysis --config ../config/engines.toml --variant international-10x10 --fens ../reports/poc-runs/g6-fens.txt --move-time 0.2 --mode sequential --out ../reports/poc-runs/results.jsonl
```

Consensus batch (cross-evaluation on disagreements, sequential by default, ADR-009):

```bash
cd backend && python -m damas_ai.consensus --config ../config/engines.toml --variant international-10x10 --fens ../reports/poc-runs/g6-fens.txt --move-time 0.2 --out ../reports/poc-runs/consensus.jsonl
```

The internal engine is a Hub engine (configure it like any other; see `config/engines.example.toml`):

```bash
cd backend && PYTHONPATH=src python -m damas_ai.search.hub
```

Adaptive analysis (escalates the limit while engines diverge, ADR-010):

```bash
cd backend && python -m damas_ai.adaptive --config ../config/engines.toml --variant international-10x10 --fens ../reports/poc-runs/g6-fens.txt --move-time 0.2 --factor 2 --max-steps 3 --out ../reports/poc-runs/adaptive.jsonl
```

Tournament (Rules Core as arbiter; paired openings; Elo with 95% interval):

```bash
cd backend && python -m damas_ai.bench --config ../config/engines.toml --variant brazilian-8x8 --players "engine:damasai_br@depth=6" "engine:damasai_br@depth=3" greedy random --openings 8 --out ../reports/bench/br
```

Knowledge base (ingest any gate's JSONL, then query):

```bash
cd backend && python -m damas_ai.kb --db sqlite:///../var/damas_kb.sqlite3 migrate
```

```bash
cd backend && python -m damas_ai.kb --db sqlite:///../var/damas_kb.sqlite3 ingest --kind consensus ../reports/poc-runs/consensus.jsonl
```

Local HTTP API (no authentication; keep it on 127.0.0.1). It reads `DAMAS_ENGINES_CONFIG` and
`DAMAS_DATABASE_URL`:

```bash
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml python -m uvicorn --factory damas_ai.api.app:create_app --app-dir src --host 127.0.0.1 --port 8765
```

## Configuration

All configuration is external. Environment variables use the `DAMAS_` prefix (see
`config/.env.example`). Engines are declared in a git-ignored TOML file (template:
`config/engines.example.toml`). No executable path is hardcoded anywhere. Details:
[docs/conventions.md](docs/conventions.md).

## Licensing

This repository contains **no third-party engine code or binaries**. Scan is GPL-3.0.
Kingsrow is freeware with no published redistribution terms. See
[docs/reports/g1/06-licensing.md](docs/reports/g1/06-licensing.md) and
[ADR-004](docs/architecture/decisions/ADR-004.md). A license for this project itself has not
been chosen yet; that is an owner decision.

## Development gates

G1 Foundation & Discovery (this gate) → G2 Rules Core → G3 Engine Integration Framework →
G4 SCAN → G5 KingsRow → G6 Multi-Engine Analysis → G7 Consensus & Divergence →
G8 Adaptive Search → G9 Tactical → G10 Strategic & Decision → G11 Knowledge Base →
G12 Benchmarks → G13 Game Analysis & Dataset → G14 Learning → G15 Interface & Final Validation.
