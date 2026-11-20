# Engine integration architecture

Status: design baseline from G1. **The framework is implemented in G3** (`damas_ai.engines`;
behaviour details in ADR-007 and `docs/reports/g3/g3-report.md`). G4 (SCAN) and G5
(KingsRow hub) remain. The CB-DLL rows below are out of scope (ADR-005).
Evidence for every protocol statement is in `docs/reports/g1/02-scan-report.md` and
`03-kingsrow-report.md`.

## 1. Protocols the platform must handle (verified in G1)

| Protocol | Used by | Transport | Shape | Evidence |
|---|---|---|---|---|
| **Hub v2** | Scan 3.1 (`scan hub`) | stdin/stdout text lines | UCI-like: `hub`→`id`/`param`/`wait`; `set-param`; `init`→`ready`; `pos`, `level`, `go think/ponder/analyze` → `info…`, `done move=… ponder=…`; `stop`, `ping`/`pong`, `new-game`, `quit` | Scan 3.1 `protocol.txt` |
| **Hub (dialect unverified)** | "Kingsrow hub" 1.63 (International 10x10) | stated "Hub interface" | Assumed to be Hub. Version 1 or 2 is **UNVERIFIED** | edgilbert.org download page |
| **CheckerBoard engine API** | Kingsrow English / Italian 1.21 (64-bit) | **in-process Windows DLL** | `getmove(Board8x8, color, maxtime, char str[1024], int *playnow, info, moreinfo, CBmove*)`; `enginecommand(cmd, reply[1024])`; gametype codes | `cb_interface.h` in eygilbert/CheckerBoard |
| DXP (DamExchange) | Scan (`scan dxp`), Kingsrow International | TCP | Game-playing protocol between two programs, not an analysis protocol | Scan readme (DXP options) |

DXP is game-oriented (play a match), not analysis-oriented. It is listed for G12 benchmarking
only. No analysis adapter is planned on DXP.

## 2. Layering

```
 analysis / consensus / bench           (engine-agnostic: platform types only)
              |
       EngineAdapter (interface)        capabilities(), start(), analyze(req) -> AnalysisResult, stop()
              |
  +-----------+-----------+-------------------+
  | HubAdapter            | CbDllAdapter      |   protocol translation + notation conversion
  |  (Scan, Kingsrow hub) |  (Kingsrow 8x8)   |   + score normalization
  +-----------+-----------+---------+---------+
              |                     |
     ProcessSupervisor        ProcessSupervisor -> cb_host process (loads the DLL;
     (line I/O, deadlines,                         speaks a small JSON-lines protocol)
      escalation, transcript)
```

### 2.1 `EngineAdapter` contract (G3 target, sketched in platform terms)

- `capabilities() -> EngineCapabilities`: `native_variants`, supports `depth`/`nodes`/
  `move_time`/`infinite` limits, `multipv` (False for every engine studied), `ponder`,
  `pv` output, `score_unit`, `tablebases`.
- `analyze(request) -> AnalysisResult`, where `request = (canonical position + history,
  limit, mode)` and `result = (best_move, ponder_move?, pv[], raw_score, normalized_score?,
  depth?, nodes?, time, engine_id, engine_version, transcript_ref)`.
- Every `best_move` and PV move is **re-validated by the Rules Core** (ADR-001) before it is
  used. Invalid output is flagged as an `EngineProtocolViolation` and kept as data.

### 2.2 Capability gating

The orchestrator only sends positions of variant V to engines whose `native_variants` contain V.
Today **no studied engine contains `brazilian-8x8`**. Adding an engine to Brazilian analysis
requires (a) a capability declaration and (b) a passing rules-conformance suite (G3/G4),
not just a configuration entry.

## 3. Process and resource management

| Concern | Rule | Proven in G1 PoC (against mock) |
|---|---|---|
| Startup | spawn with explicit argv and CWD (Scan reads `scan.ini` and `data/` from CWD) | yes |
| Init deadline | `init_timeout_s` (bitbase loading may take long) | yes |
| Search deadline | `move_time + search_timeout_s`. On expiry send `stop`, then escalate | timeout detected; `stop` path is G3 |
| Shutdown | `quit` → wait `quit_timeout_s` → terminate → wait → kill | yes (ignored-quit case) |
| Crash | stdout EOF → result marked failed, process reaped, exit code recorded | yes |
| stdin closed | Hub spec: engine must quit when stdin closes, so the supervisor closes stdin on teardown | spec only |
| Transcript | every line in/out timestamped, kept for audit | yes |
| Concurrency | one search per process. Parallel analysis uses separate processes; total threads are budgeted (Scan `threads`, Kingsrow up to 32 threads) | design |
| Memory | Scan TT = 16 B × 2^`tt-size` (2^26 ≈ 1 GiB); bitbases (6 pieces) ≈ 2 GiB RAM. Budget per instance is enforced in config | design |

## 4. Scores are not comparable across engines

No assumption of compatibility is allowed:

- **Scan** reports `score` in "men" (real). ±89.xx means a won/lost endgame soon and
  ±99.xx means the end of the game soon (readme). These are sentinel bands, not material.
- **Kingsrow CB DLL** returns only a WIN/LOSS/DRAW/UNKNOWN code plus a free-text `str[1024]`.
  The text format is not specified by the API (**UNVERIFIED until observed**).
- **Kingsrow hub**: score fields **UNVERIFIED**.

Adapters therefore output `raw_score` (verbatim string + declared unit) and an optional
`normalized_score` produced by a per-engine, versioned normalizer that is calibrated
empirically (G7/G12). Consensus logic (G7) must work on move agreement and rank before any
score arithmetic.

## 5. Notation boundaries

Each adapter converts between the canonical position (ADR-003) and the engine's native format:

| Engine | Native position format | Native move format |
|---|---|---|
| Scan (Hub) | side char `W`/`B` + 50 chars `w b W B e` (10x10 squares 1-50) | `32-28`; captures `from x to x captured x captured…` (captured in any order, pivots omitted) |
| Kingsrow 8x8 (CB) | `int board[8][8]` with `CB_WHITE=1, CB_BLACK=2, CB_MAN=4, CB_KING=8`; `color` arg | `CBmove` struct (from/to coords, path[], del[] captured squares) |
| Kingsrow hub | **UNVERIFIED** (expected Hub-like) | **UNVERIFIED** |

Hub capture notation omits pivot squares and lists captured squares unordered. A Hub move can
therefore be ambiguous, and adapters must resolve it **against the Rules Core's legal-move list**.
This is another reason ADR-001 is necessary.

## 6. Verification procedure for each new engine (applies to G4/G5)

1. Obtain the binary from the author and record source URL, version, SHA-256 and license.
2. Declare it in `config/engines.toml` with `native_variant`.
3. Run `scripts/poc/hub_poc.py` (Hub engines) or the CB host smoke test (G5). Archive the JSON
   report under `reports/poc-runs/` (git-ignored) and summarize it in the gate report.
4. Run the rules-conformance suite (G3): N positions with known legal-move sets, including
   forced/majority captures. The engine's chosen move must be in the Rules Core's set.
5. Record observed `info` fields and score behaviour for the normalizer.
