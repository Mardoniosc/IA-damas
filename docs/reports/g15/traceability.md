# Traceability: vision → gates → code → evidence

Date: 2026-11-20. Every row cites where the claim is implemented and where it is evidenced.
"Not met" rows are listed alongside the met ones.

## 1. Vision capabilities

| # | Capability (master prompt) | Status | Where | Evidence |
|---|---|---|---|---|
| 1 | Integrate SCAN and KingsRow, subject to technical and licensing verification | **Met on the variants they play** (International 10x10). **Impossible for Brazilian**: neither engine plays it | G1 research, G3 framework, G4 Scan (built from GPL source), G5 Kingsrow hub | G4: 1,500/1,500 conformance; G5: 1,500/1,500; licensing in G1 deliverable 6 / ADR-004 |
| 2 | Brazilian checkers rules on 8x8 | **Met** (draw rules and numbering provisional pending the official CBJD text) | G2 `damas_ai.rules` | 0 move-set mismatches vs py-draughts on 9,029 positions; perft to depth 9; 19 rule-clause tests |
| 3 | Compare different engines | **Met** | G6 multi-engine, G12 tournaments | G6: 600/600 ok; G12: International round-robin (Scan–Kingsrow 16 draws) |
| 4 | Detect disagreement | **Met** | G7 consensus (cross-evaluation, intra-engine regret) | 300 positions: 0 contradictions, 14 proof gaps, tolerance sensitivity reported |
| 5 | Adaptive analysis | **Met** | G8 `damas_ai.adaptive` | 16/34 divergences settle with more time; 13 stable |
| 6 | Investigate critical positions | **Met** | G9 tactics/criticality; G8 stable divergences; G11 tags | shot claims accepted by both judges in 81% (sacrifices) / 91% (capture choices) |
| 7 | Build a position knowledge base | **Met on SQLite**; PostgreSQL not verified | G11 `damas_ai.kb` + Alembic | 1,339 evidence records + 444 games; migration parity test; in-place 0001→0002 |
| 8 | Analyse games | **Met** | G13 `damas_ai.games` | all 144 G12 games and 300 self-play games replay; per-player accuracy ordering matches the tournament |
| 9 | Controlled benchmarks | **Met** | G12 `damas_ai.bench` | Brazilian 4-player ordering exact; Elo with intervals |
| 10 | Learn from datasets and experiments | **Infrastructure met; no playing gain established** | G13 datasets, G14 learning | held-out log-loss 0.661 → 0.589 (MLP); matches: best +27 Elo [−26, +82], not adopted |
| 11 | Independent decision intelligence layer | **Met** (International); single-source for Brazilian | G10 `damas_ai.decision` | 39 hard positions: fewer errors than any single engine; confidence informative |

## 2. Architectural principles

| # | Principle | How it is enforced | Evidence |
|---|---|---|---|
| 1 | Modular architecture | one package per gate concern (`rules`, `engines`, `analysis`, `consensus`, `search`, `adaptive`, `tactics`, `strategy`, `decision`, `kb`, `bench`, `games`, `learning`, `api`) | system-overview module map |
| 2 | Engine-agnostic core | `EngineAdapter` + platform types; profiles per engine (ADR-002/007) | `damas_ai.rules` imports no engine code (checked in G2/G3) |
| 3 | Rules Core as legal-move authority | every engine move resolved by `resolve_engine_move`; games arbitrated by `GameState.play` (ADR-001/014) | rules-blind double fails conformance (G3); forfeit tests (G12) |
| 4 | Canonical position representation | DSA string, canonical index, Zobrist, colour-twin grouping (ADR-003) | symmetry property tests; KB `canonical_dsa` |
| 5 | Engine Adapter Pattern | `HubEngine` for Scan, Kingsrow and the internal engine | 3 engines, one code path |
| 6 | Independent engine processes | `ProcessSupervisor`; the internal engine is a Hub process too (ADR-010) | escalation and crash tests |
| 7 | Strict resource management | deadlines, stop → kill, thread budget, sequential mode (ADR-007/008) | G6 contention measurement (−22–33% nodes in parallel) |
| 8 | Test-driven development | 255 tests + slow perft + real-engine tests | G15 validation run |
| 9 | Reproducible experiments | run ids, config fingerprints, seeds, dataset SHA-256, model provenance | G6, G12, G13, G14 outputs |
| 10 | Documented decisions | ADR-001 … ADR-016 | `docs/architecture/decisions/` |
| 11 | Benchmark-driven evolution | G14 adoption rule: matches decide, not loss | G14: no model adopted |
| 12 | Licensing compliance | no third-party code/binaries committed; Scan built locally (GPL); Kingsrow not redistributed | `git check-ignore` checks each gate |

## 3. Technology stack

| Item | Status |
|---|---|
| Python, Pydantic, pytest | used throughout |
| FastAPI | local HTTP API (G6–G11) |
| SQLAlchemy + Alembic | knowledge base (G11, G13 migration) |
| **PostgreSQL** | **not verified**: no server or driver installed (needs owner approval) |
| **Angular + TypeScript** | workspace and UI source written (G15); **not built or browser-verified**: npm dependencies need a download approval |
| PyTorch | MLP comparison in G14 (CUDA available) |
| Redis, Docker | not introduced (no measured need) |

## 4. Open items at the end of G15

1. A **second, independent Brazilian engine**: Brazilian consensus and decisions stay single-source (R01).
2. **Official Brazilian rules text** (CBJD/FMJD): draw rules and numbering are provisional (R02, R14).
3. **npm dependency install** for the Angular UI (owner approval for downloads).
4. **PostgreSQL** verification (R22).
5. **Kingsrow terms** for anything beyond local use (Q5, R04).
6. **API authentication** before any non-local deployment (R19).
7. **Learned evaluation**: no significant gain yet (G14). The internal engine remains weak (R21).
