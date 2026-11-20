# G1 deliverables index

| # | Deliverable | Location |
|---|---|---|
| 1 | Executive technical report | [01-executive-report.md](01-executive-report.md) |
| 2 | SCAN technical report | [02-scan-report.md](02-scan-report.md) |
| 3 | KingsRow technical report | [03-kingsrow-report.md](03-kingsrow-report.md) |
| 4 | Rules compatibility matrix | [../../architecture/rules-compatibility.md](../../architecture/rules-compatibility.md) |
| 5 | Integration feasibility report | [05-feasibility-report.md](05-feasibility-report.md) |
| 6 | Licensing and usage considerations | [06-licensing.md](06-licensing.md) |
| 7 | Technical proof-of-concept report | [07-poc-report.md](07-poc-report.md) |
| 8 | Architecture documentation | [system-overview](../../architecture/system-overview.md), [engine-integration](../../architecture/engine-integration.md), [position-representation](../../architecture/position-representation.md), [technical-discovery](../../architecture/technical-discovery.md) |
| 9 | Initial repository structure | [../../../README.md](../../../README.md) (layout section), [conventions](../../conventions.md) |
| 10 | ADRs | [ADR-001](../../architecture/decisions/ADR-001.md) Rules Core authority · [ADR-002](../../architecture/decisions/ADR-002.md) out-of-process adapters · [ADR-003](../../architecture/decisions/ADR-003.md) canonical position · [ADR-004](../../architecture/decisions/ADR-004.md) licensing policy · [ADR-005](../../architecture/decisions/ADR-005.md) variant & engine strategy (**accepted: option A**) |
| 11 | Risk register | [11-risk-register.md](11-risk-register.md) |
| 12 | G2 implementation proposal | [12-g2-proposal.md](12-g2-proposal.md) |

## Acceptance criteria check

| Criterion | Met? | Where |
|---|---|---|
| SCAN investigated | Yes (documents and source; no binary run) | 02 |
| KingsRow investigated | Yes (author site and API header; no binary run) | 03 |
| Rules compatibility documented | Yes, with evidence levels and open conflicts | 04 |
| Protocols investigated | Yes: Hub v2 fully; CB API from header; Kingsrow-hub dialect open (Q3) | engine-integration |
| Licensing investigated | Yes | 06, ADR-004 |
| Feasibility established or blockers documented | Yes | 05, 07 |
| Architecture documentation exists | Yes | 8 |
| Decisions recorded | Yes (ADR-005 decided by the owner: option A, 2026-11-20) | 10 |
| Risks documented | Yes | 11 |
| Deliverables reviewed | Self-review done (§ below). **Owner review pending** | here |

## Self-review notes

- Every engine claim cites evidence or is marked UNVERIFIED. Rules claims carry
  [E]/[S]/[K]/[?] tags.
- No engine capability was inferred: Kingsrow-hub fields and the CB free-text format are
  explicitly unknown.
- Results from the test double are reported separately from real-engine results (there are
  none of the latter).
