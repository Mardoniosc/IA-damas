# G15 report — Super AI Interface & Final Validation

Gate: **G15** · Date: 2026-11-21 · Status: **final validation complete; interface source written
but NOT built or browser-verified** (npm dependencies need the owner's download approval).
Design: ADR-017. Capability-by-capability traceability: [traceability.md](traceability.md).

## 1. Interface (`frontend/damas-ui`, Angular 21)

| Item | Status |
|---|---|
| Workspace scaffolded with the installed Angular CLI 21.0.2 (`--skip-install`) | done |
| Board model (FEN parsing, numbering shared with the backend), API client, workbench page (decision + confidence + candidates/regrets, tactics, strategy, engines, KB), evidence warnings for single-source variants | written |
| Unit tests for the board model (`app.spec.ts`) | written, **not run** |
| Dev proxy `/api` → `127.0.0.1:8765`; launch configs (`.claude/launch.json`: `damas-api`, `damas-ui`) | done |
| `npm install --offline` | **failed**: the cache lacks packages (`@babel/helper-annotate-as-pure` first). A registry download needs approval |
| Build, browser verification | **pending** |

### Backend side of the interface: verified end to end over HTTP (uvicorn, real engines, real KB)

| Call (what the UI does) | Result |
|---|---|
| `GET /variants` | brazilian-8x8 → [damasai_br]; international-10x10 → [damasai_intl, kingsrow_intl_hub, scan] |
| `POST /decision` International start, 0.2 s | `34-30` (proposed by Scan), accepted by **3/3** engines, confidence **high**, 3.3 s |
| `POST /decision` Brazilian start, 0.2 s | `22-17`, confidence **low**, reason "single evidence source", 1.1 s |
| `POST /tactics` Brazilian sacrifice position | critical: "shot: sacrifice gaining 2.00 men", "only move"; line `19-16 12x19 24x15x6x13` |
| `POST /strategy` | descriptive notes (men, tempo, mobility, center, back rank) |
| `GET /kb/stats` | 29,114 positions, 444 games |
| Terminal position | 422 |

## 2. Final validation (2026-11-21)

| Suite | Result |
|---|---|
| Backend, all tests including slow ones (perft to depth 9, deep International perft), with coverage | **258 passed**, 2 skipped (the real-engine tests, which need `DAMAS_ENGINES_CONFIG` and ran separately below), 263 s; line coverage **85%** |
| Real engines (`pytest -m engine`): Scan 3.1, Kingsrow hub 1.63, internal Brazilian, internal International, multi-engine parallel | **5 passed** (176 s) |
| G1 PoC harness | **17 passed** |

Third-party material check: no engine binaries, engine data, local config, generated datasets
or databases are tracked (`git check-ignore` verified at every gate).

## 3. Project state at the end of the plan

The platform meets its vision **for International draughts end to end** (multi-engine analysis,
disagreement detection, adaptive escalation, tactics, decisions with calibrated confidence,
knowledge base, benchmarks, game analysis, datasets, learning experiments). **For Brazilian
draughts** it has a verified rules core, a working (weak, untuned) internal engine, tactics,
benchmarks, datasets and learning infrastructure. Every Brazilian decision, however, is
**single-source**, because no external Brazilian engine exists among those studied (G1/ADR-005).

## 4. Open items (owner decisions or external inputs)

1. Approve `npm install` for `frontend/damas-ui` (registry download), then build and verify in
   the browser.
2. Provide or approve a second, independent Brazilian engine (discovery item).
3. Provide the official CBJD (or FMJD draughts-64) rules text: draw rules and numbering are
   provisional.
4. Approve a PostgreSQL server and driver for verification (R22).
5. Kingsrow terms before any distribution or hosted use (Q5).
6. Decide on API authentication before any non-local deployment (R19).
7. Further learning work: more and deeper data, search-aware targets, larger matches (G14).

## 5. Acceptance

| Criterion | Status |
|---|---|
| Interface over the platform's capabilities | **source complete; not built or verified** (blocked on approval) |
| Final validation of the whole system | **met** (all suites green, real engines included) |
| Traceability of the vision to evidence | **met** (traceability.md) |
