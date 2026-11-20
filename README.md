# Damas Super AI

An independent, research-driven, multi-engine intelligence platform for **Brazilian draughts
(damas brasileiras, 8x8)**. The goal is not to wrap external engines in a GUI. Engines are
advisors: an internal Rules Core is the authority on legal moves, and an independent
decision-intelligence layer is the long-term product.

> **Status: G1–G4 are complete. Gate G5 (KingsRow Integration) is complete and awaiting
> review** ([G5 report](docs/reports/g5/g5-report.md)). Scan 3.1 and Kingsrow hub 1.63 both
> pass conformance on International 10x10. G6 starts only after explicit approval.

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
                         engines/ = engine adapters, Hub protocol, conformance (G3)
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

Requirements: Python 3.11+. PostgreSQL, Node/Angular and Docker are **not** needed for G1.

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
