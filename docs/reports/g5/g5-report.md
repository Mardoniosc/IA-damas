# G5 report — KingsRow Integration

Gate: **G5 KingsRow Integration** · Date: 2026-11-20 · Status: **complete, awaiting owner review**.
Scope per ADR-005 option A: **Kingsrow hub 1.63 (International 10x10)** through the Hub
adapter. Kingsrow English/Italian (CheckerBoard DLL) remain out of scope. No Kingsrow build
plays Brazilian draughts; such requests are refused by capability gating.

## 1. Obtaining the engine (owner approved: start G5)

| Item | Value |
|---|---|
| Source | `https://edgilbert.org/InternationalDraughts/downloads/kr_hub_163.zip` (author's official site; Last-Modified 2021-07-01) |
| Size / SHA-256 | 13,739,700 bytes / `b7b4c58c1dec4e6e9aa6d6ca67395e964b4029e1ecf90cf654bd029943c859d7` |
| Contents | `kr_hub.exe` (629,760 B), `kr_hub.ini`, `kr_hub.pdf` (manual), `weights.bin` (8.5 MB), `KingsRow.odb` (opening book, 1,423,444 positions) |
| Location | `engines/kingsrow_hub/{download,bin}`, git-ignored. Extracted with a path-traversal check. **Not redistributed** (ADR-004: freeware, no published redistribution terms) |
| Run | no command-line arguments; run with the `bin` folder as working directory (it reads `kr_hub.ini` from the CWD) |
| Local config | `config/engines.toml` (git-ignored): `egdb-wld=false` (no endgame db installed), `book=false`, `threads=1` |

## 2. Manual facts (kr_hub.pdf, v1.63, 2020-10-11). Closes G1 question Q3

- Protocol: **"Fabien Letouzey's Hub 2.1 protocol"**, the same family as Scan's Hub v2. It
  also implements `pos start`.
- `level`: `moves`, `time`, `inc`, `move-time`, `infinite`. **Not `depth` or `nodes`.**
- `go think | analyze | ponder`. Ponder moves only for think/ponder.
- **Multi-PV** (`multi-pv=true`): at each depth, one `info` per move with `move`, `move-num`,
  `move-count`; `nodes` and `mean-depth` omitted.
- Params (all observed in the handshake): `egdb-wld`, `egdb-wld-pieces` (2–8), `egdb-wld-mem`,
  `egdb-wld-path`, `egdb-parallel-init`, `egdb-aux`, `egdb-aux-path`, `book`, `book-quality`
  (best/good/allkinds), `threads` (1–16), `tt-mem` (32–1024 MiB), `tt-load`, `multi-pv`,
  `ponder`. Egdb and `tt-mem` settings only before `init`.
- Side effect: writes logs to `%USERPROFILE%\Documents\Ed Gilbert\Kingsrow International\`.

## 3. Evidence from the real engine

### 3.1 G1 PoC harness: all 8 steps pass

`id name=Kingsrow version=1.63 author="Ed Gilbert" country=USA`. Start position at 1 s:
9 `info` lines, depth 18, score 0.00, 13.4M nodes (~18.6 MNPS), `done move=31-26` (it used
0.75 s of the 1 s budget), then `quit(code=0)`.

### 3.2 Framework

| Check | Result |
|---|---|
| `pytest -m engine` (smoke + conformance on 200 positions) | **passed** for Kingsrow and Scan (89 s for both) |
| `engine_evidence.py`: 1,500 positions, captures first, 0.1 s per move | **1,500/1,500 `ok`**: 231 multi-capture moves, 271 positions with kings, **0 violations** |
| PV legality | 100% fully legal (mean 9.4 moves) |
| `info` fields | always `depth mean-depth score nodes time nps pv` |
| Timing | mean 0.103 s per call at 0.1 s move time (honours move-time closely); 1,500 calls in 155 s |
| `go think`, move history | ok |
| `level depth=6` (before the profile fix) | **silently ignored**: searched to depth 14 and answered |
| `level depth` / `level nodes` (after the profile fix) | refused by the adapter with `CapabilityError` |

### 3.3 Score semantics (empirical, profile `kingsrow`)

| Fact | Evidence |
|---|---|
| Perspective: side to move | same position (White a man up): W to move +1.18, B to move −1.20 |
| Scale ≈ "men", but **not the same as Scan** | a one-man advantage: Kingsrow ±1.18–1.20 vs Scan ±1.30–1.32. The internal log shows `value -112` for the reported −1.12 (hundredths) |
| Win encoding `40 − plies/100` | 39.93 / −39.92 / 39.97 = win/loss in 7 / 8 / 3 plies: the **same distances** Scan reported as 99.93 / −99.92 / 99.97 on the same positions |
| Eval/win boundary | over 11,455 info lines: evals stayed below 35 (one value in [30,35)), none in [35, 39.5), and all decisive scores in [39.5, 40). The boundary is set at 35. **This is empirical, not documented** |
| Endgame-db win band | not observable (no db installed). Not encoded |

## 4. Defects / risks found

| Finding | Action |
|---|---|
| **An engine can silently ignore a search limit it does not implement.** The generic profile let `depth` through, and Kingsrow ignored it, which changes a result's meaning without any error | `kingsrow` profile allows `move_time` only. The adapter now refuses depth/nodes for Kingsrow (tested with the double and the real engine). ADR-007 amended: every real engine needs a verified profile before its results are relied upon |
| The G1 PoC harness mangled `\db_intl\wld_v2` (shlex escapes) | already fixed in the G3 codec (spec parsing keeps backslashes). The PoC harness is superseded |
| Kingsrow writes a growing log to the user's Documents folder (≈ 544 KB per ~3,000 searches; plus one log per process start) | new risk **R17**; no option found to disable it |
| Book file loaded even with `book=false` (log line) | informational |

## 5. Tests

```
cd backend && python -m pytest                                                  -> 143 passed, 4 skipped
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml python -m pytest -m engine -> 2 passed (Scan, Kingsrow)
python scripts/engines/engine_evidence.py --config config/engines.toml --engine kingsrow_intl_hub --positions 1500 --move-time 0.1 --out reports/poc-runs/kingsrow-evidence.json
                                                                                -> exit 0, 1500/1500 ok
```

New tests: Kingsrow score bands and limits (`test_profiles.py`), plus an adapter test that the
`kingsrow` profile refuses depth (`test_hub_adapter.py`).

## 6. Acceptance (ADR-005 re-scoped G5)

| Criterion | Status |
|---|---|
| Kingsrow integrated through the engine-agnostic framework | **met** (Kingsrow hub 1.63) |
| Conformance-tested on its native variant (International 10x10) | **met** (1,500 + 200 positions, 0 illegal) |
| Protocol dialect verified (G1 Q3) | **met**: Hub 2.1 per manual, confirmed in operation |
| Every move validated by the Rules Core | **met** |
| License-compliant use | **met** for local use; redistribution or service use still needs the author's permission (Q5 open) |
| Brazilian analysis | **not applicable** (no Brazilian build) |

## 7. Open items

- **Q5 (Kingsrow terms) remains open.** Fine for local research; contact the author before
  any distribution or hosted use.
- Multi-PV is supported by the engine but not yet by the adapter. It is a candidate for G6/G7
  (a ranked move list per engine is valuable for consensus).
- Endgame databases (WLD 2–8 pieces) are not installed: large downloads that need approval.
- Raw scores of the two engines are on **different scales** (≈1.2 vs ≈1.3 per man; wins near
  40 vs near 100). Comparison requires G7 calibration, as planned (R08).
