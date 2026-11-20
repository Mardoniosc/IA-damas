# G1 Deliverable 3 — KingsRow technical report

Evidence keys (K1…K6) refer to `docs/architecture/technical-discovery.md` §2.
Investigated 2026-11-20. **No Kingsrow binary was downloaded or executed in G1** (downloads
need owner approval; none were present locally).

> **G5 update (2026-11-20):** Kingsrow hub 1.63 was downloaded (approved) and run. Its
> "UNVERIFIED" items are now resolved:
> - Protocol: Hub 2.1.
> - `level` supports only move-time and time controls: no depth or nodes, and depth is
>   silently ignored.
> - Multi-PV is supported.
> - Score is from the side to move's point of view, on a scale of about 1.2 per man; wins are
>   encoded as 40 − plies/100.
> - 1,500/1,500 conformance.
>
> See `docs/reports/g5/g5-report.md`.

## Which "KingsRow"?

Ed Gilbert publishes three engine lines [K1]:

| Build | Latest version | Board | Interface |
|---|---|---|---|
| Kingsrow (English/American checkers) | **1.21** 64-bit (2026-11-19); 1.19e 32-bit (frozen, 2021-11-23) | 8x8 | CheckerBoard engine DLL |
| Kingsrow Italian | **1.21** 64-bit (2026-11-19); 1.19e 32-bit | 8x8 | CheckerBoard engine DLL |
| Kingsrow International | **1.63** 32/64-bit, plus **"Kingsrow hub" 1.63** (no GUI, "can be controlled with a Hub interface") | 10x10 | own GUI; Hub build; DXP-related tools on the same page |

**None of them is a Brazilian build.** The index page describes the family as "versions for
English and Italian 8x8 checkers, and for 10x10 international draughts" [K1].

## Field-by-field

| Field | 8x8 builds (English / Italian) | International / hub build |
|---|---|---|
| Version | 1.21 (64-bit) [K2, K3] | 1.63 [K4] |
| OS | Windows (installers `KingsrowSetup64.1.21.exe`, `KingsrowItalianSetup64.1.21.exe`). A 2022 review reports it runs under Wine on Linux (secondary, unverified) | Windows (installers `KingsrowIntlSetup32/64.163.exe`; `kr_hub_163.zip`) [K4] |
| Executable requirements | DLL loaded by a host (CheckerBoard 1.79 or our own host). Bitness must match (64-bit 1.21) [K2, K5] | GUI exe, or hub build. Contents of `kr_hub_163.zip` **UNVERIFIED** |
| Supported variants | English; Italian [K1–K3] | International [K4] |
| **Brazilian compatibility** | **None.** English/Italian rules differ fundamentally (rules-compatibility.md INC-2). The CB API *defines* `GT_BRAZILIAN 26`, but that is a GUI/API constant, not a Kingsrow capability [K5] | **None** (10x10) |
| Board representation (interface) | `typedef int Board8x8[8][8]`; `CB_WHITE 1`, `CB_BLACK 2`, `CB_MAN 4`, `CB_KING 8`, `CB_FREE 0` [K5] | **UNVERIFIED** |
| Position input | `getmove(board, color, …)`: full board plus side to move. `CB_RESET_MOVES` flag in `info` signals a new game/history reset [K5] | **UNVERIFIED** (expected Hub `pos`) |
| Communication protocol | **In-process DLL calls** (WINAPI): `getmove`, `enginecommand(const char*, char reply[1024])`, optional `islegal` [K5] | "Hub interface" (v1 or v2 **UNVERIFIED**) [K4] |
| Analysis commands | `getmove` is the only search entry point. `enginecommand` strings: the header documents `"get gametype"` and `"get book"`/`"set book"`. The rest of the vocabulary is **UNVERIFIED** [K5] | **UNVERIFIED** |
| Search controls | `maxtime` (seconds, double); `*playnow` flag polled for interruption; `CB_EXACT_TIME` flag; up to 32 threads (1.21) [K1, K5] | **UNVERIFIED** |
| Time controls | Per-move `maxtime`; incremental time packed into `info` bits 2–3 and `moreinfo` (remaining/increment as 16-bit fields in 0.001/0.01/0.1 s units) [K5] | **UNVERIFIED** |
| Depth controls | **None in the API** (time-based only) [K5] | **UNVERIFIED** |
| Multi-variation | **None in the API** [K5] | **UNVERIFIED** |
| Evaluation output | Return code `CB_WIN 1`, `CB_LOSS 2`, `CB_DRAW 0`, `CB_UNKNOWN 3`, plus free text in `str[1024]`. **The text format is not specified by the API, so it is UNVERIFIED until observed** [K5] | **UNVERIFIED** |
| Principal variation | Only possibly inside the free text (**UNVERIFIED**) | **UNVERIFIED** |
| Move output | `CBmove` struct: `jumps`, `from`, `to`, `path[12]`, `del[12]`, `delpiece[12]`, `oldpiece`, `newpiece` [K5] | **UNVERIFIED** |
| Process behaviour | Synchronous call that blocks until the move is chosen; interruption via `*playnow` | **UNVERIFIED** |
| Persistent process | Yes, as long as the host keeps the DLL loaded (hash tables and egdb caches persist) | expected yes (Hub) |
| Tablebases | WLD 10-piece English (102 GB re-compressed), **12-piece English** (2026-09), 8-piece Chinook/Fierz DBs; Italian WLD up to 10 pieces; DTW and MTC auxiliary DBs. Downloads via Mega [K2, K3] | WLD 7–8 pieces (4-piece bundled); DTW 2–7 (37 GB); MTC 2–8 (28 GB) [K4] |
| Opening book | English 3.5M positions; Italian 1.7M (built by dropout expansion) [K2, K3] | **UNVERIFIED** |
| Licensing | "free programs" / "free downloads". **No license or redistribution terms found** (ADR-004) | same |
| Integration limitations | Windows-only DLL; must be hosted out-of-process (ADR-002); no depth/MultiPV control; free-text evaluation; **wrong rules for Brazilian** | Hub dialect unverified; 10x10 only |

## Related source available

- `eygilbert/CheckerBoard` (GUI source, updated 2026-11-20; **no license detected**): it
  documents the engine API (`source/cb_interface.h`). We read it for interface facts only.
- `eygilbert/egdb_8x8` (BSL-1.0): probing code for Kingsrow English/Italian databases.
- `eygilbert/egdb_intl`: international DB access.

## Verdict

Kingsrow is state-of-the-art for English checkers and strong for Italian and International.
**None of its builds can analyse Brazilian positions.** The International hub build is the most
practical Kingsrow integration target for validating the framework on 10x10 (ADR-005 option A).
