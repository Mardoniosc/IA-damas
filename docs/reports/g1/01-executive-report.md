# G1 Deliverable 1 — Executive technical report

Gate: **G1 Foundation & Technical Discovery** · Date: 2026-11-20 · Status: **complete,
awaiting owner review**

## 1. Bottom line

1. **Neither SCAN nor KingsRow can analyse Brazilian 8x8 positions.** Scan 3.1 is hard-wired to
   10x10 at compile time. Kingsrow ships English 8x8, Italian 8x8 and International 10x10
   builds, with no Brazilian build. The project's founding assumption is false for every
   published version. The engine strategy was re-decided: ADR-005, option A (accepted).
2. Both engines are **integrable on the variants they do play**. Scan has a clean, documented
   stdin/stdout protocol (Hub v2). Kingsrow International has a "hub" build. Kingsrow 8x8 uses an
   in-process Windows DLL API that must be wrapped in a separate host process.
3. Brazilian draughts uses **International rules on an 8x8 board**. Scan therefore has the
   right rule logic with the wrong board, and Kingsrow 8x8 has the right board with the wrong
   rules. Porting Scan is technically plausible but is a GPL research project.
4. **Licensing:** Scan is GPL v3, usable as a separate unmodified process. Kingsrow is freeware
   with no published redistribution terms, so personal use only and no redistribution without
   the author's permission.
5. Foundations are in place: repository structure, conventions, externalized configuration,
   logging standard, five ADRs, a tested Hub protocol PoC harness, and 25 passing tests.

## 2. What was actually done

| Area | Done | Not done (and why) |
|---|---|---|
| SCAN research | Read readme, protocol.txt, license and source constants from the GitHub mirror and the lidraughts fork | No binary run (none available; downloading or building needs approval) |
| KingsRow research | Read the author's site pages (all three lines) and the CheckerBoard API header | No binary run (download needs approval) |
| Rules | Matrix of BR vs Scan vs KR-EN/IT/INT vs Core, with evidence levels | Official CBJD text not obtained (PDF blocked with 403). Draw rules partly unresolved |
| PoC | 8-step Hub harness + test double; 17 tests | Real-engine PoC blocked (B1–B3) |
| Repository | backend package (config, logging), config templates, PoC, docs | Frontend intentionally not scaffolded; no FastAPI, DB or Docker yet (no gate needs them) |

Test record: `cd backend && python -m pytest` → **8 passed**. `python -m pytest
scripts/poc/tests` → **17 passed** (three consecutive runs). Windows 11, Python 3.11.9,
2026-11-20.

## 3. Decisions needed from the owner

1. ~~ADR-005: engine strategy~~ **Decided 2026-11-20: option A** (Brazilian-first Rules Core;
   engine framework validated with SCAN and Kingsrow International on 10x10; search for
   Brazilian-capable engines; Kingsrow English/Italian out of scope).
2. Approval to **download** for the real PoC: Scan source (GitHub, GPL) or a binary you
   provide; `kr_hub_163.zip` from edgilbert.org.
3. Source for the **official Brazilian rules** (CBJD document, or approval to fetch FMJD
   draughts-64 rules).
4. Project license (open).
5. Approval to start **G2** (proposal in deliverable 12).

## 4. Deliverable index

See `docs/reports/g1/README.md`.
