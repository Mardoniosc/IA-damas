# G1 Deliverable 5 — Integration feasibility report

## 1. Feasibility by integration path

| # | Path | Technical feasibility | Rules validity for Brazilian | Licensing | Verdict |
|---|---|---|---|---|---|
| F1 | Scan 3.1 via Hub for **Brazilian** | n/a | **Impossible**: 10x10 compile-time geometry | GPL-3.0 | **NOT FEASIBLE** |
| F2 | Kingsrow English/Italian via CB DLL for **Brazilian** | Feasible (host process) | **Invalid**: different rules (no backward man captures, short kings, no majority rule / different priority) | no terms → personal use only | **NOT FEASIBLE** (wrong rules) |
| F3 | Kingsrow International for **Brazilian** | n/a | **Impossible**: 10x10 | as F2 | **NOT FEASIBLE** |
| F4 | Scan 3.1 via Hub for **International 10x10** | **Feasible**: protocol fully documented. PoC harness ready and tested against a double | valid for 10x10 | GPL-3.0, OK as a separate process | **FEASIBLE**, pending a binary |
| F5 | Kingsrow hub 1.63 for **International 10x10** | **Likely feasible**: author states a Hub interface. Dialect unverified | valid for 10x10 | no terms; personal-use download | **LIKELY FEASIBLE**, pending download + PoC |
| F6 | Kingsrow English/Italian via CB DLL host for their **own** variants | Feasible: API documented in `cb_interface.h`; needs a 64-bit host process | n/a (not the target variant) | as F2 | Feasible but **of low value** to a Brazilian platform |
| F7 | Port Scan to Brazilian 8x8 (GPL fork) | Plausible: same rule logic, but geometry constants, eval retraining, bitbase generation and a new book are needed | would be valid if done correctly | GPL-3.0 derivative, separate repo | **RESEARCH PROJECT** (G8/G14 scale) |
| F8 | Other Brazilian-capable engines | Unknown. Candidates are not yet investigated | unknown | unknown | **OPEN** (discovery item) |

## 2. What this means for the gate plan

**Decision taken: ADR-005 option A (2026-11-20).** The selected paths are F4 and F5, plus the
F8 discovery item. F6 is out of scope, and F7 is a deferred research track.

- **G2 (Rules Core)** is unaffected and is the critical path regardless of engine choice.
- **G3 (framework)** is unaffected. It can be built and tested against F4/F5 and doubles.
- **G4 (SCAN)** and **G5 (KingsRow)** can only meet their goals on 10x10 International (F4/F5).
  Their acceptance criteria must be re-scoped (ADR-005).
- **G6/G7 (multi-engine, consensus)** for Brazilian need **at least two Brazilian-valid
  evidence sources**. Today only the future internal engine (G8) is certain. F7/F8 would add
  more. Without them, G6/G7 can be developed and validated on International and applied to
  Brazilian once sources exist.

## 3. Preconditions to close the remaining unknowns

| Unknown | Precondition | Owner action needed |
|---|---|---|
| F4 real-engine PoC | A Scan 3.1 Windows build plus `scan.ini` + `data/` | Provide a binary, **or** approve cloning `rhalbersma/scan` and installing a C++ toolchain to build it |
| F5 real-engine PoC | `kr_hub_163.zip` from edgilbert.org | Approve the download (official author site) |
| F8 | Candidate list and access | Approve investigation of e.g. Aurora Draughts (installed demo) and others |
| Brazilian draw rules | Official CBJD text or FMJD draughts-64 rules | Provide the document, or approve fetching the FMJD PDF |
