# Technical discovery record (G1)

Date of all observations: **2026-11-20**. This document records *how* G1 established its
findings, *what evidence* backs them and *what is still open*. Per-engine detail is in
`docs/reports/g1/02-scan-report.md` and `03-kingsrow-report.md`.

## 1. Method

1. Primary artifacts first: engine source, readme, protocol and license files fetched from the
   authors' repositories and websites. Their content was read, not inferred from search snippets.
2. Secondary sources (Wikipedia, lidraughts blog) only for the rules of the game, and tagged as
   such.
3. Local machine inspection for existing binaries and tooling.
4. A proof of concept of the protocol mechanics against a scripted test double, because no real
   binary was available (see §3 and the PoC report).
5. Anything not observed is marked **UNVERIFIED**. Nothing was filled in from memory as a
   fact about an engine.

## 2. Evidence log

| # | Source | What it established |
|---|---|---|
| S1 | `https://raw.githubusercontent.com/rhalbersma/scan/master/readme.txt` (mirror of Scan 3.1, GPL-3.0, last push 2019-11-09) | Scan 3.1 (2019-07-06) by Fabien Letouzey; 10x10 international engine; text/DXP/Hub modes; `scan.ini` options; variants; bitbases; C++14; scoring note (±89.xx/±99.xx) |
| S2 | `…/rhalbersma/scan/master/protocol.txt` | Hub protocol v2: syntax, init, `pos`/`level`/`go`, `info`/`done`, commands during search |
| S3 | `…/rhalbersma/scan/master/src/common.hpp`, `src/var.cpp` | `File_Size {10}`, `Rank_Size {10}`, `Square_Size {63}` (13x10 padded); variant names `normal killer bt/breakthrough frisian losing` |
| S4 | `…/rhalbersma/scan/master/license.txt`; GitHub API `license.spdx_id = GPL-3.0` | License |
| S5 | `https://github.com/RoepStoep/scan` readme/protocol/commits (GPL-3.0; last push 2023-08-27) | lidraughts fork based on Scan 3.0: `level handicap=0-3`, WASM/PNaCl builds, "Planned changes: multipv support" (not implemented); an attempted upgrade to 3.1 was reverted on 2023-08-27 |
| S6 | `https://lidraughts.org/blog/X3i0pBIAACQAUFWO/brazilian-draughts` (via search result text) | Lidraughts: Brazilian supported "with the exception of computer analysis (Scan 3.1 only knows 100-square variants)" |
| K1 | `http://www.edgilbert.org/Checkers/KingsRow.htm` | Kingsrow versions exist for English, Italian (8x8) and International (10x10); news 2026-11-19: Kingsrow 1.21 (English/Italian), CheckerBoard 1.79, up to 32 search threads, 12-piece English DB (2026-09-28) |
| K2 | `https://edgilbert.org/EnglishCheckers/KingsRowEnglish.htm` | Kingsrow English 1.21 (64-bit), 1.19e (32-bit, frozen); designed for CheckerBoard; "free programs"; opening book 3.5M positions; WLD 10-piece (and 12-piece) databases; DTW/MTC auxiliary DBs |
| K3 | `https://edgilbert.org/ItalianCheckers/KingsRowItalian.htm` | Kingsrow Italian 1.21; CheckerBoard; book 1.7M positions; WLD up to 10 pieces; DTW 2–8, MTC 2–10 |
| K4 | `https://edgilbert.org/InternationalDraughts/download_links.htm` (page revised 2022-10-13) | Kingsrow International 1.63 (32/64-bit); 4-piece DB in installer; WLD 7–8 piece; DTW 2–7; MTC 2–8; **"Kingsrow hub version 1.63 – the kingsrow engine without a user interface. It can be controlled with a Hub interface."**; Tmgr 1.03 Hub tournament manager |
| K5 | `https://raw.githubusercontent.com/eygilbert/CheckerBoard/master/source/cb_interface.h` | CheckerBoard engine API: `getmove`, `enginecommand`, `islegal`, `Board8x8`, piece codes, return codes, gametype constants (`GT_ENGLISH 21`, `GT_ITALIAN 22`, `GT_SPANISH 24`, `GT_RUSSIAN 25`, `GT_BRAZILIAN 26`, `GT_CZECH 29`), incremental time packing |
| K6 | GitHub API for `eygilbert/*` | CheckerBoard repo: no license detected; `egdb_8x8`: BSL-1.0; `egdb_intl` exists (international DB access) |
| R1 | `https://pt.wikipedia.org/wiki/Damas` (raw wikitext) | Brazilian rules text (Portuguese): orientation, movement, *lei da maioria*, Turkish rule, promotion, draw rules (20 king moves; 3-fold; 3 kings vs 1 in 20 moves) |
| R2 | `https://en.wikipedia.org/wiki/Brazilian_draughts` (raw; tagged "single source" March 2026) | Brazilian = International rules on 8x8, 12 men; numbering (29 at White's left corner); cites FMJD "Official Rules of the game in draughts-64" |
| R3 | Web search snippet of a FENAE 2025 damas regulation (PDF returned HTTP 403, so **not read**) | Mentions *lei da maioria*, 20 king moves, and faster "5-move" draws in some king endings. **Conflicts with R1 on special endgames** |

Raw copies of S1–S5 and K1–K5 were saved during G1 to the session scratchpad. They are not
committed (third-party text). Re-fetch them from the URLs above.

## 3. Local environment findings

- Full search of `%USERPROFILE%`, `C:\Program Files` and `C:\Program Files (x86)` (depth 5)
  for `scan*.exe`, `*kingsrow*`, `hub*.exe` and related names found **no SCAN or Kingsrow
  binary**.
- Found but **not investigated** (out of G1 scope): *Aurora Draughts 3.9.2 demo* (a
  multi-variant commercial program; preset files in `Documents\Aurora Draughts`). It could be a
  candidate Brazilian-capable engine. Its interface and licensing are unknown.
- `py-draughts 1.10.1` (GPL-3.0) is installed in the user site-packages. It claims Brazilian
  support and a HUB client. It is a candidate **independent test oracle** for G2 (dev-only,
  never a product dependency, see ADR-004). Its correctness for Brazilian is **UNVERIFIED**.

## 4. Open questions (carried into risks and G2)

| ID | Question | Blocks | How to close |
|---|---|---|---|
| Q1 | Engine strategy given that no engine plays Brazilian | G4, G5, G6+ | **Owner decision** (ADR-005) |
| Q2 | Exact Brazilian draw rules (special endgames) and official numbering/orientation | G2 freeze | obtain the official CBJD text / FMJD draughts-64 rules |
| Q3 | Kingsrow hub: Hub v1 or v2? Score/PV fields? | G5 (10x10 path only) | download `kr_hub_163.zip` (needs owner approval) and run `hub_poc.py` |
| Q4 | Kingsrow CB `str[1024]` info format; `enginecommand` vocabulary actually supported | G5 (8x8 English/Italian path only) | run the DLL in a host process (G5) |
| Q5 | Kingsrow redistribution/usage terms | any bundling | ask the author (contact listed on edgilbert.org) |
| Q6 | Scan official Windows binary location for 3.1 | G4 | owner provides one, or build from GPL source (needs a C++14 toolchain; none verified on this machine) |
