# G1 Deliverable 2 — SCAN technical report

Evidence keys (S1…S6) refer to `docs/architecture/technical-discovery.md` §2.
Investigated 2026-11-20. **No Scan binary was executed in G1** (none available; see PoC report).

> **G4 update (2026-11-20):** Scan 3.1 was built from source and run. The protocol facts
> below were confirmed, and the score encoding was refined from source and observation:
> evals are clamped at ±80.00, the score is from the side to move's point of view, and win
> distances are decoded. See `docs/reports/g4/g4-report.md` §2.3.

## Version intended for integration

**Scan 3.1** (released 2019-07-06) by Fabien Letouzey. This is the latest version found in the
GitHub mirror `rhalbersma/scan` (last push 2019-11-09) [S1]. The lidraughts fork
`RoepStoep/scan` is based on **3.0**. Its attempt to upgrade to 3.1 was reverted on
2023-08-27 [S5]. No later upstream version was found. If the owner has a different build,
its `id` line will reveal it (the PoC records it).

## Field-by-field

| Field | Finding | Evidence |
|---|---|---|
| Version | 3.1 (2019-07-06); Hub `id name=Scan version=3.1 author="Fabien Letouzey" country=France` | S1, S2 |
| OS compatibility | Source "should be mostly cross-platform"; Clang Makefile (Mac), compatible with Linux/GCC, "known to work with Visual Studio". Windows console app | S1 |
| Executable requirements | Console app. Needs `scan.ini` and a `data/` directory (opening book, eval weights, bitbases) **relative to the working directory**. Bitbases are a **separate download**. Build: C++14 | S1 |
| Supported variants | `normal` (International, a "legacy feature" per author), `killer`, `bt`, `frisian` (needs Hub 2.1 GUI to display), `losing`. BT and losing are "experimental" | S1, S3 |
| **Brazilian compatibility** | **None.** Geometry is compile-time 10x10: `File_Size {10}`, `Rank_Size {10}`, `Dense_Size = 50`, `Square_Size {63}` (13x10 padded). No 8x8 variant in `var.cpp`. Lidraughts: "Scan 3.1 only knows 100-square variants" | S3, S6 |
| Board representation | Internal padded 13x10 board, bitboards (from "bitboard iterators", "bitboard move generation") | S1, S3 |
| Position input | Hub: `pos pos=<side W/B><50 chars w b W B e> [moves="…"]` in standard 1–50 square order. Moves are needed for repetition detection (Hub sends king moves only) | S2 |
| Command interface | Modes: text (default, single-letter commands), `scan dxp`, **`scan hub`** | S1 |
| Communication protocol | **Hub v2** (UCI-like, line-based, `cmd arg=val …`, double-quoted values, flags without value, unknown commands/args ignored), over stdin/stdout. DXP over TCP for matches | S2 |
| Analysis commands | `go analyze` (engine may skip book, search single legal moves, not avoid draws); `go think`; `go ponder` + `ponder-hit`; `stop`; `level infinite` for open-ended analysis | S2 |
| Search controls | `level depth=`, `level nodes=` (3.1 adds node limit), `threads`, `tt-size` (2^n entries × 16 B), `bb-size` | S1, S2 |
| Time controls | `level move-time=`; `level [moves=] time= [inc=]` (sudden death, x/y, Fischer); seconds as reals | S2 |
| Depth controls | `level depth=<max depth>` | S2 |
| Multi-variation (MultiPV) | **Not supported** in the protocol or options. The lidraughts fork lists "multipv support" only as *planned* | S2, S5 |
| Evaluation output | `info … score=<real, in men>`; ±89.xx = winning/losing endgame soon, ±99.xx = end of game soon | S1, S2 |
| Principal variation | `info … pv="<moves space-separated>"`; also `depth`, `mean-depth`, `nodes`, `time`, `nps` (MNPS) | S2 |
| Final answer | `done move=<m> [ponder=<m>]`; must always be sent, even after `stop` | S2 |
| Process behaviour | Engine may stop at any time and answer `done` (even in infinite/ponder). During search accepts only `ping`, `ponder-hit`, `stop`. Must quit if stdin closes. `new-game` clears TT. GUI never sends terminal positions | S2 |
| Persistent process | **Yes.** A game or analysis session is a sequence of searches in one process; parameters are set before `init` (Hub GUI never changes them after init) | S2 |
| Tablebase support | Win/loss/draw **bitbases** up to `bb-size` pieces: 6 recommended (7 for BT, 5 for Frisian), about 2 GiB RAM. Distributed separately | S1 |
| Licensing | **GPL v3** (Scan and the lidraughts fork) | S4, S5 |
| Integration limitations | (1) 10x10 only; (2) no MultiPV; (3) captures in Hub notation omit pivots and order; (4) no official 3.1 Windows binary located in G1; (5) settings are fixed after `init`, so changing variant means restarting the process; (6) memory of TT + bitbases per instance | all |

## Lidraughts fork extras (3.0-based)

`level handicap=0..3` progressively disables quiescence features and bitbases. There are also
WASM/asm.js/PNaCl builds. These matter only for browser deployment, which is out of scope.

## Verdict

Scan is an excellent, well-documented **10x10** engine with a clean protocol. It is **not
usable for Brazilian positions** without a GPL derivative port (ADR-005 option B).
