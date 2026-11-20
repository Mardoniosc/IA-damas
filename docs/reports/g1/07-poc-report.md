# G1 Deliverable 7 — Technical proof-of-concept report

> **G4 update (2026-11-20):** the real-SCAN column is no longer blocked. Scan 3.1 was built
> from source and **passed all 8 steps** with this harness (`docs/reports/g4/g4-report.md`
> §2.1). **G5 update:** Kingsrow hub 1.63 also passed all 8 steps (`docs/reports/g5/g5-report.md`
> §3.1).

## 1. Summary

| PoC step | Against a real SCAN | Against a real Kingsrow | Against the test double |
|---|---|---|---|
| 1 Start engine | **BLOCKED** | **BLOCKED** | PASS |
| 2 Identify version | BLOCKED | BLOCKED | PASS (`MockHub 0.0-test`) |
| 3 Send test position | BLOCKED | BLOCKED | PASS (10x10 start position) |
| 4 Request analysis | BLOCKED | BLOCKED | PASS (`go analyze`) |
| 5 Receive result | BLOCKED | BLOCKED | PASS (2 `info` + `done`) |
| 6 Interpret output | BLOCKED | BLOCKED | PASS (move, score, depth, PV) |
| 7 Validate returned move | BLOCKED | BLOCKED | PASS (syntax, origin, destination, captured squares. Full legality needs G2) |
| 8 Terminate cleanly | BLOCKED | BLOCKED | PASS (`quit(code=0)`), plus escalation tested |

**No real engine was run in G1.** The test-double results prove the *harness* (process
handling, Hub parsing, deadlines, shutdown escalation). They are **not** evidence about Scan's
or Kingsrow's behaviour.

## 2. Blockers

| Blocker | Detail |
|---|---|
| B1: no binaries on the machine | Disk search (user profile, Program Files x64/x86, depth 5) found no Scan or Kingsrow files |
| B2: downloads need owner approval | Kingsrow installers / `kr_hub_163.zip` (edgilbert.org) and Scan source (GitHub) were not downloaded. Policy requires explicit approval for each download |
| B3: no Brazilian-capable engine | Even with binaries, a **Brazilian** PoC is impossible for both engines (feasibility F1–F3). A real PoC can only target 10x10 International (Scan, Kingsrow hub) or English/Italian (Kingsrow DLL) |
| B4: Rules Core absent | Step 7 can only check syntax and square ownership until G2 delivers legal-move generation |

## 3. What was built and tested

- `scripts/poc/hub_poc.py`: a generic Hub v2 client implementing all 8 steps. It writes a JSON
  report with per-step result, timings, `id`/`param` declarations, `info`/`done` fields,
  termination mode and a full timestamped transcript.
- `scripts/poc/mock_hub_engine.py`: a **test double** implementing the Hub v2 dialogue from
  `protocol.txt`, with failure modes `--hang-search`, `--ignore-quit`, `--crash-on-go` and
  `--bad-move`.
- `scripts/poc/tests/test_hub_poc.py`: 17 tests (parser, move checks, end-to-end success and
  failure modes).

Test results (2026-11-20, Windows 11, Python 3.11.9):

```
python -m pytest scripts/poc/tests      -> 17 passed (run 3 times, stable)
cd backend && python -m pytest          -> 8 passed
python scripts/poc/hub_poc.py --executable scripts/poc/mock_hub_engine.py --set variant=normal --move-time 0.1
                                        -> exit 0, all 8 steps ok, termination quit(code=0)
python scripts/poc/hub_poc.py --executable C:/does/not/exist/scan.exe
                                        -> exit 2, "BLOCKED: executable not found"
```

One defect was found and fixed while testing: the PoC CLI resolved relative executable paths
against the engine's working directory. It now resolves them first.

Known PoC limitations: values are parsed with POSIX `shlex`, so a backslash inside an
engine-sent value would be treated as an escape. Hub defines no escapes, so the G3 parser must
be written to spec.

## 4. Verification procedure (to run once binaries are available)

### 4.1 Scan 3.1 (International 10x10)

Prerequisites:

1. A Scan 3.1 Windows executable, obtained by one of:
   - (a) the owner supplies an existing build; or
   - (b) clone `https://github.com/rhalbersma/scan` (GPL-3.0) and build with Visual Studio or
     MinGW (C++14). **No C++ toolchain was verified on this machine.**
2. `scan.ini` and `data/` (book, eval) next to the executable. Bitbases are optional
   (`bb-size = 0` disables them).
3. Put the folder **outside** this repository, e.g. `C:\engines\scan31\`.

Run:

```bash
python scripts/poc/hub_poc.py --executable "C:/engines/scan31/scan.exe" --arg hub --set variant=normal --set book=false --move-time 1 --out reports/poc-runs/scan31.json
```

Pass criteria: exit code 0. The `id` line shows `version=3.1`. `done.move` passes step 7.
Termination is `quit(code=0)`. Archive the JSON and summarize it in the G4 report (SHA-256 of
the executable, `id`, `param` list, observed `info` fields).

### 4.2 Kingsrow hub 1.63 (International 10x10)

Prerequisites: download `https://edgilbert.org/InternationalDraughts/downloads/kr_hub_163.zip`
(owner approval required) and extract it to e.g. `C:\engines\kingsrow_hub\`. Read its
included documentation to find the executable name and command-line arguments.

Run the same harness (with `--arg` as the docs require). Then record the Hub dialect: if the
engine rejects `hub` or answers in Hub-1 form, step 2 fails with the transcript showing why.
That is the evidence needed to close question Q3.

### 4.3 Kingsrow English/Italian DLL (out of scope under ADR-005 option A; kept for reference)

Requires the G5 CB host process (64-bit). Smoke test: load `kingsrow64.dll` (name to be
confirmed from the installer) and call `enginecommand("get gametype")` (documented in
`cb_interface.h`; expect 21 or 22). Other command strings such as a name query are
**UNVERIFIED**; take them from the engine's help or from CheckerBoard's source. Then call `getmove` on the start position with `maxtime=1`. Record the returned
`str` text verbatim to define the parser.
