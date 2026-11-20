# G1 Deliverable 12 — G2 (Rules Core) implementation proposal

**Not started. This proposal requires owner approval.**

## 1. Objective

Deliver `damas_ai.rules`, a correct, tested and documented implementation of Brazilian 8x8 draughts
rules. Per ADR-001 it is the platform's sole legal-move authority.

## 2. Entry conditions

| Condition | Status |
|---|---|
| G1 reviewed and approved | pending |
| ADR-005 decided (determines whether 10x10 geometry is in G2 scope) | **done**: option A, so minimal 10x10 geometry is in scope |
| Official Brazilian rules text available (CBJD, or FMJD draughts-64) | **missing**. G2 can start, but draw rules and numbering stay provisional until it arrives |

## 3. Scope

In scope:

1. `geometry`: 8x8 tables (neighbours and rays per direction), canonical indexing (ADR-003),
   and the `i → 31 − i` symmetry. A **10x10 International geometry** is also included (ADR-005
   option A), limited to what move validation for SCAN/Kingsrow International needs:
   geometry, position, move generation and Hub-notation resolution. It carries its own
   ruleset (FMJD) and its own perft reference.
2. `position`: immutable `Position`, `Piece`, DSA string I/O, Zobrist keys.
3. `movegen`: men moves, flying-king moves, captures with:
   mandatory capture; **maximum-capture (lei da maioria)** with men and kings counted equally;
   multi-jump continuation; no double-jumping of a piece (empty squares may be revisited);
   removal after the move (Turkish rule); promotion only when the move *ends* on the last rank.
4. `game`: `GameState`, `apply(move)`, termination (no legal moves = loss), and draw detection
   driven by a **`Ruleset`** object (repetition count, king-move limit, special-endgame rules)
   so that unresolved draw rules are configuration, not code.
5. `notation`: algebraic (`c3-d4`, `c3xe5`) and PDN FEN/numeric. The numeric numbering is
   provisional until it is verified (R14).
6. `resolve_engine_move(position, from, to, captured_set)`: the matching function adapters
   will use (needed by ADR-001, and it is a pure rules function).

Out of scope: engines, search, evaluation, API, database, UI.

## 4. Test strategy (TDD)

| Layer | Tests |
|---|---|
| Rule clauses | One or more named tests per row of the BR column in `rules-compatibility.md` (e.g. backward man capture, majority with kings counted equally, promotion pass-through does not promote, Turkish-rule blocking, flying-king landing choices) |
| Hand-built positions | Fixture file of positions with their complete legal-move sets, each with provenance (built by hand from rule text; cited article) |
| Perft | Perft(1..N) from the start position and selected tactical positions. Reference counts are **generated** with an independent implementation (py-draughts 1.10.1, run as a dev-only tool) and cross-checked by hand at low depth. **No values copied from memory.** Discrepancies are investigated, never auto-accepted |
| Properties | Symmetry: `legal_moves(flip(p)) == flip(legal_moves(p))`; apply/serialize round-trips; Zobrist incremental = full recompute |
| Draw rules | Parameterized tests per `Ruleset` |

## 5. Deliverables

- `backend/src/damas_ai/rules/…` and tests (target: 100% of rule clauses covered; coverage
  reported).
- `docs/architecture/rules-core.md` (API and invariants).
- ADR-006 (move-generation data structure, e.g. bitboards vs arrays, with measured perft speed).
- G2 report: rules text sources (replacing [S] with [E]), test counts, perft table with
  provenance, open issues.

## 6. Acceptance criteria

1. Every BR rule clause has a passing named test.
2. Perft matches the independent oracle to the agreed depth (proposed: 8 or more), with any
   discrepancy explained.
3. Draw rules are implemented as a `Ruleset` and the provisional values are clearly labelled.
4. No engine code, no I/O, and no dependencies beyond the standard library in `damas_ai.rules`.
5. Documentation and ADR updated, risks R02/R03/R14 re-assessed.

## 7. Estimate

Medium. Move generation with majority capture and flying kings is the bulk. The rest is
straightforward. The 10x10 geometry (ADR-005 A) adds a small increment, because the rule
logic is shared.
