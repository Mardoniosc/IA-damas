# G1 Deliverable 11 — Risk register

Scale: Likelihood (L) and Impact (I) are 1 (low) to 5 (high). Score = L × I. Review at every gate.

| ID | Risk | L | I | Score | Mitigation | Gate | Status |
|---|---|---|---|---|---|---|---|
| R01 | **No external engine supports Brazilian 8x8**. Multi-engine consensus for Brazilian has no inputs | 5 (realized) | 5 | **25** | ADR-005 option A: framework validated on 10x10; search for Brazilian engines; internal engine (G8); optional Scan port (F7) | G1→G8 | **Open**: mitigation chosen (ADR-005 option A accepted 2026-11-20); residual risk until a Brazilian-valid second source exists |
| R02 | Brazilian draw rules unresolved (sources conflict on special endgames) | 4 | 4 | 16 | Ruleset-parameterized draw rules; obtain official CBJD/FMJD text before freezing G2 | G2 | Open |
| R03 | Rules Core bugs propagate to every gate (ADR-001 makes it the authority) | 1 | 5 | 5 | Done in G2: 19 clause tests; 0 mismatches vs py-draughts on 9,029 positions; perft to depth 9; symmetry property | G2 | **Reduced** (G2): residual = shared misreading or unofficial rules |
| R04 | Kingsrow terms prohibit intended use (redistribution, service, commercial) | 3 | 4 | 12 | No redistribution (ADR-004); contact author before any such use | G5 | Open |
| R05 | Scan GPL obligations triggered unintentionally (bundling, modified build) | 1 | 4 | 4 | Separate process; unmodified source built locally into git-ignored `engines/` with its license text; no binaries in repo | G4 | Mitigated (G4 verified: `git check-ignore`) |
| R06 | Kingsrow hub Hub dialect differs from Scan's Hub v2 | 1 | 2 | 2 | Verified in G5: Hub 2.1. The real difference (no depth/nodes, silently ignored) is handled by the `kingsrow` profile | G5 | **Closed** |
| R07 | CB DLL engines crash or hang the host; 32/64-bit mismatch | 1 | 3 | 3 | Out-of-process host per DLL (ADR-002); bitness check at startup | n/a | **Dormant**: Kingsrow DLL builds out of scope (ADR-005) |
| R08 | Score scales incompatible; naive comparison yields wrong consensus | 5 | 4 | 20 | G7: consensus uses intra-engine regret by cross-evaluation (ADR-009); scale relation measured (Kingsrow ≈ 0.64 × Scan, r 0.988), descriptive only. Calibration to outcomes pending (G12/G13) | G7 | **Mitigated** |
| R20 | Time-limited searches are non-deterministic, so single-run consensus labels vary (G7: 203 vs 213 unanimous out of 300) | 5 | 2 | 10 | Records keep limits and versions; treat labels as samples; repeat runs or fixed-depth limits where stability matters | G7/G12 | Open |
| R09 | Hub move ambiguity (no pivots/order) mis-maps engine moves | 2 | 3 | 6 | `resolve_engine_move` (G2) resolves by captured set and raises on genuine ambiguity | G3 | Mitigated (G2) |
| R10 | Resource exhaustion and contention: TT (2^26 × 16 B ≈ 1 GiB), bitbases (~2 GiB), Kingsrow DBs (100+ GB disk), parallel processes (G6 measured: parallel runs cut node counts 22–33%) | 3 | 3 | 9 | G3: bounded transcripts, kill-on-timeout. G6: EnginePool with thread budget, restart, `sequential` mode for comparisons. Pending: per-engine memory budget | G6/G12 | Mostly mitigated |
| R19 | Local HTTP API has no authentication | 2 | 4 | 8 | Bind to 127.0.0.1 (documented in README and ADR-008); auth decision required before any non-local deployment | G6/G15 | Open |
| R11 | Engines' availability depends on single individual authors (no updates, sites go down: edgilbert.org's root already shows a parking page) | 3 | 3 | 9 | Record SHA-256 and versions; owner keeps local archive copies under the authors' terms; engine-agnostic core | all | Open |
| R12 | Scope creep: building G3+ features before G2 is solid | 3 | 4 | 12 | Strict gates; approval required per gate | all | Controlled |
| R13 | Windows-only components (Kingsrow DLL) limit portability (Docker/Linux) | 2 | 2 | 4 | Hub engines only (ADR-005); Kingsrow hub portability still unverified | G5 | Reduced |
| R14 | Notation/numbering mistakes (PDN numeric origin unverified) corrupt imported games | 2 | 4 | 8 | Canonical index internal; converters pinned by tests; en.wikipedia and py-draughts agree (G2) | G2/G13 | Open: official confirmation pending |
| R15 | PostgreSQL not installed locally; persistence gates blocked | 2 | 2 | 4 | Introduce in G11 (or Docker image then) | G11 | Accepted |
| R17 | Kingsrow hub writes ever-growing logs to `%USERPROFILE%\Documents\Ed Gilbert\Kingsrow International\` (≈544 KB per ~3,000 searches), outside the project | 5 | 2 | 10 | Document; periodic cleanup in benchmark runs (G12); no disabling option found | G5/G12 | Open |
| R18 | Engines silently ignore unsupported search limits (observed: Kingsrow ignores `depth`) | 4 | 4 | 16 | Verified per-engine profiles (ADR-007 amendment); the adapter refuses limits outside the profile | G5 | Mitigated |
| R16 | Learning-system (G14) data contaminated by wrong-rules engine output | 2 | 5 | 10 | Capability gating plus ADR-001 validation; dataset provenance includes `ruleset_id` | G13/G14 | Mitigated by design |
