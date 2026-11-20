# G1 Deliverable 6 — Licensing and usage considerations

> Not legal advice. This is a factual summary of the terms found on 2026-11-20 and the policy
> adopted (ADR-004). Seek legal review before public distribution or commercial use.

## 1. Terms found

| Item | License / terms | Source | Implications |
|---|---|---|---|
| Scan 3.1 (Letouzey) | **GPL v3** | `license.txt`, readme "distributed under the GNU General Public License version 3" | Free to use and run. Distributing binaries requires GPL compliance. Modified versions that are distributed must be GPL v3 with source |
| Scan 3.0 lidraughts fork | **GPL v3** ("sources are distributed under the same license") | fork readme | same |
| Hub GUI (Letouzey) | not examined (not needed) | n/a | n/a |
| Kingsrow English / Italian / International / hub | "free programs", "free downloads". **No license file or redistribution terms found** on the pages examined | edgilbert.org | Treat as all rights reserved. Personal download and use are clearly intended. **Do not redistribute.** Ask the author before bundling or any service/commercial use |
| Kingsrow endgame databases, opening books | **No terms found**. Hosted on Mega | edgilbert.org | same as above. Also very large (10-piece English 102 GB; 12-piece larger) |
| CheckerBoard source (GitHub `eygilbert/CheckerBoard`) | **No license detected** | GitHub API | Default copyright applies. Do not copy code. Reading the interface to interoperate is how G1 used it |
| `egdb_8x8` (Kingsrow DB probing code) | **BSL-1.0** (permissive) | GitHub API | Could legally be used if direct DB probing is ever needed. Attribution is required |
| py-draughts 1.10.1 | **GPL v3** | package metadata | Dev-only test oracle. Never a runtime dependency of `damas_ai` |

## 2. Policy (from ADR-004)

1. Zero third-party engine code, binaries or data in this repository.
2. Engines run as separate, unmodified processes (Scan) or inside our own host process (DLLs),
   configured per machine.
3. Any Scan modification (for example an 8x8 port) lives in a separate GPL v3 repository.
4. Written permission from Ed Gilbert is required before any Kingsrow redistribution,
   bundling, hosted service or commercial use.
5. Published benchmark results cite engine name, version, settings and source URL.

## 3. Owner decisions still open

- This project's own license (currently none, so all rights reserved by default).
- Whether a hosted or multi-user deployment is planned. That would change the Kingsrow
  question from "personal use" to "service", which needs the author's permission.
