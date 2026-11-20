# G8 report — Adaptive Search

Gate: **G8 Adaptive Search** · Date: 2026-11-20 · Status: **complete, awaiting owner review**.
Design: ADR-010. G8 delivers (1) the platform's **own search engine**, its first Brazilian
evidence source, and (2) **adaptive escalation** of analysis effort where engines diverge.

## 1. What was built

| Component | Content |
|---|---|
| `damas_ai.search.evaluation` | baseline eval: material (man 100 / king 300) + advancement (+4 per row). **Untuned** |
| `damas_ai.search.searcher.Searcher` | negamax alpha-beta, iterative deepening, TT with mate-score ply adjustment, capture extension, killers + history, repetition = draw, depth/nodes/time/stop limits, PV from the TT |
| `damas_ai.search.hub` | the engine as a **Hub v2 process** (`python -m damas_ai.search.hub`), params `variant`, `tt-entries`; search in a worker thread so `stop`/`ping` work during search |
| Profile `damasai` | depth/nodes/move-time; men; side to move; wins as `100 − plies/100` |
| `damas_ai.adaptive` | `EscalationPolicy` + `AdaptiveAnalyzer` (consensus → escalate on preference/conflict/proof gap → repeat), JSON view, CLI `python -m damas_ai.adaptive`, `POST /adaptive` |

## 2. Verification

### 2.1 Tests

```
cd backend && python -m pytest                                                 -> 201 passed, 5 skipped
cd backend && DAMAS_ENGINES_CONFIG=../config/engines.toml python -m pytest -m engine -> 5 passed (Scan, Kingsrow, internal BR, internal INTL, multi-engine)
```

New tests (22):
- **search:** best move legal on 300 oracle positions with legal PVs, forced capture and
  majority, short forced win, terminal root, **determinism at fixed depth**, limits
  (nodes/time/stop), per-depth reporting, eval colour symmetry on 1,000 positions, score
  encoding;
- **Hub server:** handshake/profile in both variants, conformance on 60 + 60 oracle positions,
  move history with a forced capture, stop returning the best move so far;
- **adaptive:** policy arithmetic, persistent preference reaching `max_steps`, ceiling, settled
  not escalated, incomplete, JSON view and API.

### 2.2 Internal engine: speed and Brazilian conformance (real process)

| Measure | Brazilian 8x8 | International 10x10 |
|---|---|---|
| Start position, 1 s | depth 9, ~30k nodes/s | depth 7, ~22.6k nodes/s |
| `engine_evidence.py`, 1,500 positions, 0.1 s per move | **1,500/1,500 ok**, 366 multi-captures, 334 with kings, 0 violations, 100% legal PVs | conformance via `pytest -m engine` (200 positions) passed |
| Probes | depth, nodes, move-time, go think, move history, `stop` on overdue search (0.54 s, interrupted, answer kept): all ok | same |

### 2.3 Quality judged by Scan and Kingsrow (100 International positions, 0.2 s per move)

Three-engine consensus (`scan, kingsrow_intl_hub, damasai_intl`):

| Measure | Result |
|---|---|
| Internal move equals Scan's / Kingsrow's / both | 50 / 56 / 47 out of 100 (Scan and Kingsrow agree with each other ≈ 70%) |
| Positions with any disagreement (cross-evaluated) | 53 |
| Cost of the internal move, judged by Scan (own units) | median 0.11; ≤ 0.10 in 26/53; ≥ 1.0 man in 9 |
| Cost judged by Kingsrow (own units) | median 0.08; ≤ 0.10 in 29/53; ≥ 1.0 man in 5 |
| Moves judged to turn the result into a proven loss | 0 |

**Reading:** the internal engine is legal, stable and clearly **weaker** than the external
engines. It makes occasional one-man errors at this time budget and no proven-losing moves in
this sample. That is expected of an untuned baseline in Python.

### 2.4 Adaptive escalation (Scan + Kingsrow, 0.2 → 0.4 → 0.8 s)

On the 39 positions that were `preference` or had a proof gap in the G7 run:

| Measure | Result |
|---|---|
| Re-run at 0.2 s (step 1) | preference 26, equivalent 4, none 9 (non-determinism, R20) |
| Escalated | 34 |
| Settled after escalation | **16/34** (e.g. `preference > equivalent` ×6, `preference > none` ×3) |
| Persistent `preference` at every level | **13** (stable disagreements: candidates for "critical positions", G9/G11) |
| Divergence revealed by more time | 3 (`none > … > preference`) |
| Proof gaps closed by more time | 7 of 14 |
| Final classes | preference 16 · equivalent 11 · none 12 |

## 3. Findings

| Finding | Consequence |
|---|---|
| About half of the divergences resolve with 4× the time; about a third persist | escalation separates noise from stable disagreement, which is the input G9 needs |
| More time can *create* a divergence | single-limit consensus can under-report divergence; escalation trajectories are the more honest record |
| A fixed-depth internal search is deterministic | a reproducible baseline exists, unlike time-limited external engines (R20) |
| The internal engine is weak | it must never be presented as authoritative. It serves as the Brazilian baseline and the G14 starting point |

## 4. Acceptance

| Criterion | Status |
|---|---|
| Internal search engine, legal by construction, integrated like any engine | **met** |
| Plays Brazilian 8x8 (first Brazilian evidence source) | **met** (1,500/1,500 conformance) |
| Adaptive analysis that allocates more effort to divergence | **met**, with evidence that it resolves about half of divergences and isolates stable ones |
| Strength measured, not assumed | **met** (judged by Scan/Kingsrow) |
| Brazilian *consensus* | **not yet**: only one Brazilian source. Needs a second independent one |

## 5. Open items

- Performance: a faster board (bitboards or a native extension), cross-checked against the
  Rules Core (ADR-006).
- Evaluation is untuned. Tuning and learning are G14.
- Brazilian draw rules are still provisional (G2). The search uses repetition only.
- A second independent Brazilian engine is still missing (discovery item, ADR-005).
