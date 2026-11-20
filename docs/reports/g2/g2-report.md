# G2 report — Rules Core

Gate: **G2 Rules Core** · Date: 2026-11-20 · Status: **complete, awaiting owner review**.
Scope followed `docs/reports/g1/12-g2-proposal.md` with ADR-005 option A.

## 1. What was built

`backend/src/damas_ai/rules/` (stdlib only, about 530 statements): geometry, position, moves,
movegen, rulesets, game, zobrist, notation, resolve, perft. API and invariants are in
`docs/architecture/rules-core.md`. Data-structure choice: ADR-006.

Rule clauses implemented (Brazilian = International-family rules on 8x8): men forward-only
moves and backward captures, flying kings, mandatory capture, majority rule counting men and
kings equally, mandatory continuation, no double jumping, Turkish rule, promotion only at the
end of a move, loss by no legal moves, and ruleset-driven draws (repetition, king-only limit,
material-specific endgame rule).

10x10 International geometry and ruleset are included only for SCAN/Kingsrow move validation
(ADR-005).

## 2. Verification

| Check | Method | Result |
|---|---|---|
| Rule clauses | 19 named hand-built tests (`tests/rules/test_br_rule_clauses.py`), each with its reasoning in the docstring | pass |
| Move sets vs independent implementation | 5,512 Brazilian and 3,517 International positions from random playouts. Exact comparison of (origin, destination, captured set, promotion) against py-draughts 1.10.1 | **0 mismatches** |
| Sample quality | the Brazilian sample has more than 500 positions with kings, more than 200 with multi-captures and more than 50 with promotions (asserted) | pass |
| Perft, Brazilian start | depths 1–9 vs oracle: 7 · 49 · 302 · 1,469 · 7,473 · 37,628 · 187,302 · 907,830 · 4,431,766. Depths 1–2 also verified by hand | **match** |
| Perft, International start | depths 1–6: 9 · 81 · 658 · 4,265 · 27,117 · 167,140 | **match** |
| Symmetry property | flip commutes with move generation (3,000 positions) | pass |
| Zobrist | incremental equals full recomputation over 30 random games | pass |
| Draw rules | repetition, king-only limit, 3K vs 1K, loss precedence | pass |
| Engine-move resolution | unique, Hub-style unordered captured set, ambiguous, illegal | pass |

Commands and results (Windows 11, Python 3.11.9, 2026-11-20):

```
cd backend && python -m pytest                                  -> 73 passed, 3 skipped (deep perft) in ~3.3 s
cd backend && DAMAS_SLOW_TESTS=1 python -m pytest --cov=damas_ai -> 76 passed in 160 s; coverage 96% total, rules modules 83-100%
python -m pytest scripts/poc/tests                              -> 17 passed
python scripts/oracle/pydraughts_oracle.py --out backend/tests/fixtures/oracle  -> regenerates fixtures (~16 s)
```

### Defects found during G2

| Where | Defect | Resolution |
|---|---|---|
| Oracle script | py-draughts sets `is_promotion` only when a move is pushed, so the first fixture showed 416 false "mismatches" on the promotion flag alone | promotion is now observed by playing the move; regenerated with 0 mismatches |
| My tests (4 cases) | wrong expectations: an overlooked backward continuation (a3xc5xe3), kings on a shared diagonal creating forced captures, a supposedly ambiguous position that actually allowed a 4-piece loop, and a symmetry test that compared representative routes instead of identity | tests corrected. Two positions were found by exhaustive random search rather than by hand |
| Engine code | none found | n/a |

## 3. Independence of the oracle (caveat)

py-draughts is an independent implementation, but it is still a single source. If both
implementations shared a misreading of a rule, the cross-check would not catch it. The
hand-built clause tests are the guard against that. The Turkish-rule and ambiguity positions
were found by searching for positions where a rule changes the answer, so they truly exercise
those rules.

py-draughts is used only by `scripts/oracle/` and through its generated data. `damas_ai`
never imports it (ADR-004).

## 4. Acceptance criteria (from the G2 proposal)

| # | Criterion | Status |
|---|---|---|
| 1 | Every BR rule clause has a passing named test | **met** |
| 2 | Perft matches the oracle to depth 8 or more, discrepancies explained | **met** (depth 9) |
| 3 | Draw rules implemented as a `Ruleset`, provisional values labelled | **met** (`BRAZILIAN_PROVISIONAL.provisional = True`, sources and notes in the object) |
| 4 | `damas_ai.rules` has no engine code, no I/O, stdlib only | **met** (import scan) |
| 5 | Docs and ADR updated; risks re-assessed | **met** (rules-core.md, ADR-006, §5 below) |

## 5. Risk updates

| Risk | Change |
|---|---|
| R03 Rules Core bugs | **reduced** 15 → 6: oracle agreement plus clause tests. Residual risk: shared misreadings, and rules not yet confirmed officially |
| R02 draw rules unresolved | **unchanged** (16). Still blocked on the official CBJD text. The impact is contained because limits are ruleset data |
| R14 numbering | **reduced** 12 → 8: two sources agree (en.wikipedia, py-draughts). Official confirmation still pending |
| R09 Hub move ambiguity | **mitigated**: `resolve_engine_move` resolves by captured set and reports genuine ambiguity |

## 6. Not done / deviations

- **The official Brazilian rules text is still not obtained.** Draw rules and numbering remain
  provisional (`br-provisional-2026-11`).
- International draw rules are minimal [K]. They are not needed for engine move validation.
- ruff is configured but **not installed**, so the code has not been linted (installing it
  needs a package download).
- Hub *text* parsing (`32x23x28` → canonical squares) is deliberately left for the G3 adapter.
  The rules side (`resolve_engine_move`) is done.
- Nothing is committed.

## 7. Next gate

G3 (Engine Integration Framework) requires owner approval. Its inputs are ready:
`resolve_engine_move`, numeric notation for 10x10, and the PoC harness lessons.
