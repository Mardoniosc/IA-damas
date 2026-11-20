# G4 report — SCAN Integration

Gate: **G4 SCAN Integration** · Date: 2026-11-20 · Status: **complete, awaiting owner review**.
Scope per ADR-005 option A: Scan 3.1 integrated and conformance-tested **on International
10x10**, the only family of variants it plays. Scan cannot analyse Brazilian positions; the
framework refuses such requests (`CapabilityError`, tested in G3).

## 1. Obtaining Scan (owner decision: build from source)

| Item | Value |
|---|---|
| Source | `https://github.com/rhalbersma/scan` (mirror of Scan 3.1, GPL-3.0) |
| Commit | `7aae17e7b7bfc47744601afb1ee7655e18983ce5` (2019-07-06, "Scan 3.1 by Fabien Letouzey.") |
| Location | `engines/scan31/{src,obj,bin}` inside the repo, **git-ignored** (ADR-004: never committed or redistributed) |
| Build | `scripts/engines/build_scan.ps1`: MSVC 19.50.35725 x64 (Visual Studio 2026 Community, already installed; nothing new was installed) |
| Flags | `/O2 /Oi /GL /EHsc /std:c++14 /GR- /DNDEBUG /MT /W3`, `/LTCG ws2_32.lib` |
| Output SHA-256 | `E84C910612207BB555F137CE4509FE2D9CAAC820893907C5F33F58BFAE9EF805` (recorded in `engines/scan31/bin/BUILD-INFO.txt`) |
| Warnings | printf format width (`%ld` for int64), deprecated `inet_addr`, size_t→int, missing return in `var::variant_name`. All are in upstream code and harmless for Hub use. No source was modified |
| Not used | the prebuilt `scan.exe` shipped inside the mirror was **not executed** |
| Data | `data/` (book and eval for all variants) from the same commit; **no bitbases** (`bb-size = 0`) |

The local config `config/engines.toml` (git-ignored) declares the engine with `native_variant =
"international-10x10"` and params `variant=normal`, `book=false`, `threads=1`.

## 2. Evidence from the real engine

### 2.1 G1 PoC harness (`scripts/poc/hub_poc.py`): all 8 steps pass

`id name=Scan version=3.1 author="Fabien Letouzey" country=France`. From the 10x10 start
position at 1 s per move: 24 `info` lines, depth 20, score −0.01, 11.9M nodes, ~12.6 MNPS,
`done move=34-30 ponder=20-25`, then `quit(code=0)`.

### 2.2 Framework (`damas_ai.engines`)

| Check | Result |
|---|---|
| `pytest -m engine` (smoke + conformance on 200 oracle positions, 0.2 s per move) | **passed** (50 s) |
| `engine_evidence.py`: 1,500 positions, captures first, 0.1 s per move | **1,500/1,500 `ok`**: 231 multi-capture moves, 271 positions with kings, **0 violations** |
| PV legality | 100% of reported PVs fully legal under the Rules Core (mean 16.1 moves) |
| Limits | `depth=6` → depth 6, 3,669 nodes, 3.2 ms. `nodes=20000` → stopped at 16,337 nodes |
| `go think` | ok |
| Move history (`moves="31-27 16-21"`) | accepted and analysed correctly |
| Overdue search (depth 40, 0.5 s budget) | `stop` sent; `done` arrived; answer kept (`interrupted`); 0.53 s |
| Shutdown | `quit(code=0)` every time |
| Throughput | 1,500 analyses in 217 s (mean 0.143 s per call at 0.1 s move time, so about 40 ms overhead per call including `new-game`) |

### 2.3 Facts verified, replacing G1 assumptions

| Topic | G1 status | Verified in G4 |
|---|---|---|
| Declared params | readme listed options | `variant` (enum: normal killer bt frisian losing), `book`, `book-ply` (0–20), `book-margin` (0–100), `ponder`, `threads` (1–16), `tt-size` (16–30), `bb-size` (0–7) |
| `info` fields | from protocol.txt | always `depth score nodes pv`; usually `mean-depth`; `time` only when ≥ 1 ms; `nps` only when non-zero (source `search.cpp` Output_Hub) |
| PV quoting | spec | single-move PVs are sent **unquoted** (`pv=31-27`); handled |
| Free-form init output | spec says "ignore" | `init eval` line before `ready` |
| **Score encoding** | readme: ±89.xx / ±99.xx | **source `score.hpp`**: printed value = internal/100, with `Eval_Inf = 8000`, `BB_Inf = 9000`, `Inf = 10000`. Hence \|s\| ≤ 80 is an evaluation (clamped), 80 < \|s\| ≤ 90 is a bitbase win/loss at (90−\|s\|)·100 plies, and 90 < \|s\| ≤ 100 is a search win/loss at (100−\|s\|)·100 plies. Observed `94.90`, a win 510 plies away, which the readme's description did not cover |
| **Score perspective** | unknown | **side to move**: same position gives W to move +99.93 and B to move −99.92 |

The Scan profile was corrected accordingly (`RawScore.distance_plies`, `perspective`), with
tests (`tests/engines/test_profiles.py`).

## 3. Defects found during G4

| Defect | Fix |
|---|---|
| Scan profile classified only 89.xx/99.xx (from the readme), so `94.90` was mislabelled "eval" | bands now follow the source constants; distance decoded |
| Elapsed times of 0.0 s: on Windows `time.monotonic()` has 15.6 ms resolution | engine package switched to `time.perf_counter()` (0.1 µs) |
| `.gitignore` pattern `engines/` matched **every** folder named `engines`, so the G3/G4 code (`backend/src/damas_ai/engines/`, `backend/tests/engines/`, `scripts/engines/`) would never have been committed | anchored to `/engines/`. Verified with `git check-ignore`: code is trackable, while `engines/scan31/*`, `config/engines.toml` and `reports/poc-runs/*` stay ignored |

## 4. Tests

```
cd backend && python -m pytest                                              -> 135 passed, 4 skipped
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml python -m pytest -m engine -> 1 passed (real Scan)
python scripts/engines/engine_evidence.py --config config/engines.toml --engine scan --positions 1500 --move-time 0.1 --out reports/poc-runs/scan-evidence.json
                                                                            -> exit 0, 1500/1500 ok
```

## 5. Acceptance (ADR-005 re-scoped G4)

| Criterion | Status |
|---|---|
| Scan integrated through the engine-agnostic framework | **met** |
| Conformance-tested on its native variant (International 10x10) | **met** (1,500 + 200 positions, 0 illegal) |
| Every Scan move validated by the Rules Core | **met** (ADR-001) |
| Build reproducible and licence-compliant | **met** (pinned commit, script, local only, GPL text kept next to the binary) |
| Brazilian analysis | **not applicable**: impossible for Scan (ADR-005) and refused by capability gating |

## 6. Limitations and open items

- No bitbases. Their behaviour (the `win_band` path) is decoded from source but **not yet
  observed**. Bitbases are a separate download (needs approval).
- Throughput was measured single-threaded only. Multi-instance and multi-thread budgets are G6.
- Scan's strength claims are not evaluated here (that is G12).
- G1 question Q6 (Scan binary) is closed. Kingsrow hub (G5) still needs a download approval.
