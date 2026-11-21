# G15 report — Super AI Interface & Final Validation

Gate: **G15** · Date: 2026-11-21 · Status: **complete**. The interface was built and verified in the
browser after the owner approved `npm install` (see §1.1).
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

### 1.1 Interface build and browser verification (after approval, 2026-11-21)

| Check | Result |
|---|---|
| `npm install` | 470 packages, 278 MB. Install scripts of 4 packages blocked by npm 11 and **not approved**; not needed |
| `ng build` | OK, 193 kB initial / 54 kB transferred, no warnings |
| `ng test` (Vitest) | 3/3 board-model tests pass (numbering a1 = 29 on 8x8, a1 = 46 on 10x10, FEN parsing, move squares) |
| Browser, Brazilian start | decision `22-17` (c3-b4) highlighted, **low** confidence with the single-source reason and warning, tactics and strategy panels, KB counts |
| Browser, International start | variant switch to a 10x10 board; decision `34-30` (h4-i5), **high** confidence, accepted by 3/3 engines, per-engine regret table |
| Server logs (API and UI) | no errors |
| Phone-width layout | **not verified** (browser pane closed) |
| Observation | the `volatile` criticality flag also fires on start positions at depth 5: the known G9 noise, now visible in the UI |

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

### 1.2 Game review screen (added after G15 at the owner's request, 2026-11-21)

A second tab, **Game review**, analyses whole games exported by other sites (the owner's
PlayOK file was the driver). New backend routes: `POST /games/parse` (lists the games in a PDN
text, with a replay status per game) and `POST /games/analyze` (replays one game through the
Rules Core and judges every ply with one engine, reusing the G13 `analyze_game`). New UI
components: `BoardView` (shared board, played move framed in blue, engine's preferred move
dashed in green) and `GameReview` (file upload or paste, games table, judge engine and depth,
per-player accuracy and inaccuracy/mistake/blunder counts, board with first/previous/next/last
and arrow keys, move list coloured by label, caveats).

| Check | Result |
|---|---|
| Backend tests | `tests/games/test_games_api.py` 4/4 (parse status, per-ply review with positions and algebraic moves, error cases, unknown GameType needs a variant override); API-related suites 63/63 |
| Rules fix found by the owner's file | 2 of 28 PlayOK games did not replay: PlayOK writes a different but equivalent king capture route (`g1xd4xa7` for `g1xe3xa7`). `parse_move` now matches a full written path by move identity (commit `87f6c20`); 28/28 replay |
| `ng build` / `ng test` | OK, 210 kB initial / 58.5 kB transferred; 3/3 |
| Browser | PlayOK games pasted and loaded (84 and 60 plies, ok); game analysed with `damasai_br` depth 5 in a few seconds; summary cards, labels, navigation and both highlights checked (e.g. 12… c5-d4 blunder, engine prefers e7-f6, costs 1.68 men) |
| Limits | one judge only (the weak internal engine on Brazilian), provisional label thresholds and Brazilian draw rules: all shown on screen as caveats. Personal game files are not stored in the repository |

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

1. ~~Approve `npm install`~~: done 2026-11-21; UI built and verified.
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
| Interface over the platform's capabilities | **met**: built, unit-tested, browser-verified on both variants (phone layout not verified) |
| Final validation of the whole system | **met** (all suites green, real engines included) |
| Traceability of the vision to evidence | **met** (traceability.md) |
