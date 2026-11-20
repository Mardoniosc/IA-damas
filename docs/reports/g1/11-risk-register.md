# G1 Deliverable 11 — Risk register

Scale: Likelihood (L) and Impact (I) are 1 (low) to 5 (high). Score = L × I. Review at every gate.

| ID | Risk | L | I | Score | Mitigation | Gate | Status |
|---|---|---|---|---|---|---|---|
| R01 | **No external engine supports Brazilian 8x8**. Multi-engine consensus for Brazilian has no inputs | 5 (realized) | 5 | **25** | ADR-005 option A: framework validated on 10x10; search for Brazilian engines; internal engine (G8); optional Scan port (F7) | G1→G8 | **Open**: mitigation chosen (ADR-005 option A accepted 2026-11-20); residual risk until a Brazilian-valid second source exists |
| R02 | Brazilian draw rules unresolved (sources conflict on special endgames) | 4 | 4 | 16 | Ruleset-parameterized draw rules; obtain official CBJD/FMJD text before freezing G2 | G2 | Open |
| R03 | Rules Core bugs propagate to every gate (ADR-001 makes it the authority) | 1 | 5 | 5 | Done in G2: 19 clause tests; 0 mismatches vs py-draughts on 9,029 positions; perft to depth 9; symmetry property | G2 | **Reduced** (G2): residual = shared misreading or unofficial rules |
| R04 | Kingsrow terms prohibit intended use (redistribution, service, commercial) | 3 | 4 | 12 | No redistribution (ADR-004); contact author before any such use | G5 | Open |
| R05 | Scan GPL obligations triggered unintentionally (bundling, modified build) | 2 | 4 | 8 | Separate process; no binaries in repo; any port lives in a separate GPL repo | G4 | Mitigated by policy |
| R06 | Kingsrow hub Hub dialect differs from Scan's Hub v2 | 3 | 2 | 6 | Protocol adapter tolerant of unknown fields; verify with PoC (Q3) | G5 | Open |
| R07 | CB DLL engines crash or hang the host; 32/64-bit mismatch | 1 | 3 | 3 | Out-of-process host per DLL (ADR-002); bitness check at startup | n/a | **Dormant**: Kingsrow DLL builds out of scope (ADR-005) |
| R08 | Score scales incompatible; naive comparison yields wrong consensus | 5 | 4 | 20 | Raw score + unit; versioned per-engine normalizers calibrated empirically; consensus on move/rank first | G7 | Mitigated by design |
| R09 | Hub move ambiguity (no pivots/order) mis-maps engine moves | 2 | 3 | 6 | `resolve_engine_move` (G2) resolves by captured set and raises on genuine ambiguity | G3 | Mitigated (G2) |
| R10 | Resource exhaustion: TT (2^26 × 16 B ≈ 1 GiB), bitbases (~2 GiB), Kingsrow DBs (100+ GB disk), many parallel processes | 3 | 3 | 9 | Per-instance memory/thread budgets in config; supervisor limits instance count | G3/G6 | Open |
| R11 | Engines' availability depends on single individual authors (no updates, sites go down: edgilbert.org's root already shows a parking page) | 3 | 3 | 9 | Record SHA-256 and versions; owner keeps local archive copies under the authors' terms; engine-agnostic core | all | Open |
| R12 | Scope creep: building G3+ features before G2 is solid | 3 | 4 | 12 | Strict gates; approval required per gate | all | Controlled |
| R13 | Windows-only components (Kingsrow DLL) limit portability (Docker/Linux) | 2 | 2 | 4 | Hub engines only (ADR-005); Kingsrow hub portability still unverified | G5 | Reduced |
| R14 | Notation/numbering mistakes (PDN numeric origin unverified) corrupt imported games | 2 | 4 | 8 | Canonical index internal; converters pinned by tests; en.wikipedia and py-draughts agree (G2) | G2/G13 | Open: official confirmation pending |
| R15 | PostgreSQL not installed locally; persistence gates blocked | 2 | 2 | 4 | Introduce in G11 (or Docker image then) | G11 | Accepted |
| R16 | Learning-system (G14) data contaminated by wrong-rules engine output | 2 | 5 | 10 | Capability gating plus ADR-001 validation; dataset provenance includes `ruleset_id` | G13/G14 | Mitigated by design |
