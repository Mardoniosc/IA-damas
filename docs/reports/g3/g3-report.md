# G3 report — Engine Integration Framework

Gate: **G3 Engine Integration Framework** · Date: 2026-11-20 · Status: **complete, awaiting
owner review**. Design: ADR-002 (adapters, processes) and ADR-007 (search semantics).
Scope follows ADR-005 option A: Hub engines only; the CheckerBoard DLL host is out of scope.

## 1. What was built — `backend/src/damas_ai/engines/`

| Module | Content |
|---|---|
| `types.py` | platform types: `SearchLimit`, `AnalysisRequest` (validates its move history with the Rules Core), `AnalysisResult`, `AnalysisStatus`, `SearchInfo`, `RawScore`, `EngineCapabilities`, `EngineInfo` |
| `base.py` | `EngineAdapter` ABC (start, info, capabilities, analyze, new_game, running, close; context manager) |
| `process.py` | `ProcessSupervisor`: one OS process; separate stdout/stderr pumps; deadline reads; sticky EOF; bounded timestamped transcript with marks; quit → close stdin → terminate → kill escalation |
| `hub/protocol.py` | Hub v2 codec written to protocol.txt (quoting, flags, no escapes), position encode/decode for any geometry, move parse/format |
| `hub/profiles.py` | `scan` profile (evidence-based) and `generic-hub` |
| `hub/adapter.py` | `HubEngine`: handshake with declared-parameter validation; `pos/level/go`; info/PV/score parsing; **every best, ponder and PV move resolved by the Rules Core** (ADR-001); variant and limit gating; stop/grace/kill; restart; ping |
| `conformance.py` | `run_conformance(engine, ruleset, positions, limit)` → `ConformanceReport` (the ADR-002 §6 gate) |
| `factory.py` | `create_engine(EngineConfig)`. Refuses CB-DLL (ADR-005), DXP, and variants with no ruleset |

Config additions (`EngineConfig`): `env`, `stop_grace_s`.

## 2. Verification

All against test doubles. **No real engine was run** (no binaries; downloads not approved).

| Area | Tests | Highlights |
|---|---|---|
| Hub codec | 18 | spec examples (start position string, `28x19x23`); quoted values with `=`; literal backslashes; unterminated quote; bad moves |
| Process supervisor | 7 | send/read, deadline, crash detection (sticky EOF), stderr separation, escalation against a process that ignores quit and EOF, transcript marks |
| Hub adapter | 21 | handshake/params/no-id/slow-init; Scan profile; validated move + PV + ponder + score; move history; depth/nodes limits; variant gating (8x8 request to a 10x10 engine refused); terminal refusal; illegal move rejected; garbage; bad PV truncated; short-capture warning; error lines and stderr; stop → interrupted answer kept; deaf engine → timeout → killed → restart; crash; ignored quit |
| Conformance + factory | 5 | legal double passes 40 International and 30 Brazilian capture positions; **rules-blind double (ignores mandatory capture) fails** with `illegal_move` results |
| Profiles | 10 | Scan ±89/±99 bands; generic never interprets |
| Real engines | 1 (skipped) | runs automatically when `DAMAS_ENGINES_CONFIG` lists an available engine: smoke test + conformance on 200 oracle positions |

The test double (`tests/engines/doubles/hub_double.py`) picks moves with the Rules Core, so in
its default mode it is correct by construction. It proves the framework, not engine
behaviour. Its Hub encoding is written independently of the adapter's codec.

Commands and results (Windows 11, Python 3.11.9, 2026-11-20):

```
cd backend && python -m pytest                 -> 134 passed, 4 skipped (3 deep perft, 1 real engine)
cd backend && python -m pytest tests/engines   -> 61 passed, 1 skipped (engine tests stable over 3 runs, ~8 s)
coverage (fast suite): engines package 85-100% per module; total 94%
python -m pytest scripts/poc/tests             -> 17 passed
```

### Defect found during G3

`ProcessSupervisor.kill()` reported "killed" for a process that had already exited but was
not yet reaped (its stdout had closed first). It now waits briefly before killing, so the
exit description is truthful. Found by `test_process_exit_is_reported_and_sticky`.

## 3. Acceptance criteria (G3 scope from engine-integration.md / ADR-002)

| Criterion | Status |
|---|---|
| Engine-agnostic interface; no engine types cross it | **met** (`damas_ai.rules` has no engine imports; adapters return platform types) |
| One OS process per engine, deadlines, escalation, transcript | **met** |
| Hub adapter with Rules-Core validation of every engine move | **met** |
| Capability gating by variant and limit | **met** |
| Raw scores with unit, no cross-engine comparison | **met** (`RawScore`; normalization deferred to G7) |
| Conformance suite that catches wrong-rules engines | **met** (rules-blind double fails) |
| Verified against a real engine | **not met: blocked** (no binary). The test is in place and skips |

## 4. Risk updates

| Risk | Change |
|---|---|
| R06 Kingsrow hub dialect | unchanged; the generic profile plus tolerant parsing limit the impact. Needs the G5 download |
| R08 score incompatibility | mitigated by design: `RawScore` with unit and kind, never compared |
| R09 Hub ambiguity | mitigated: resolution plus the short-form warning path tested |
| R10 resources | partly mitigated: bounded transcripts and kill-on-timeout. A pool and memory budgets are still G6 |

## 5. Not done / open

- **No real-engine evidence yet.** G4 (SCAN) needs a Scan 3.1 binary, or approval to clone
  and build the GPL source. G5 needs approval to download `kr_hub_163.zip`.
- The G1 PoC (`scripts/poc/`) is superseded by `damas_ai.engines` and kept only as a record.
- ruff still not installed or run. Nothing committed yet for G3.
