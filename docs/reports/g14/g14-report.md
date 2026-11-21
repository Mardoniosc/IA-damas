# G14 report — Learning System

Gate: **G14** · Date: 2026-11-20 · Status: **complete** (the gate is delivered; **no learned
model is adopted**, by the evidence rule in ADR-016).

## 1. What was built — `damas_ai.learning`

| Component | Content |
|---|---|
| `linear` | dataset loading; logistic regression with fractional targets and L2 (NumPy Newton); metrics (log-loss, Brier, decisive accuracy); constant baseline |
| `evaluator` | `LinearEvaluator` (CHEAP features computed in one pass, scaled so 1 man ≈ 100); `ResidualEvaluator` (baseline eval + learned terms); `load_evaluator` |
| Search integration | `Searcher(evaluator=…)`; Hub engine parameter `eval-model`; `SearchPlayer(evaluator, move_time_s)` |
| CLI | `python -m damas_ai.learning compare | train | match` |
| Models (committed, JSON with provenance) | `models/brazilian_linear_v1.json`, `models/brazilian_residual_v1.json` |

G13 fix included: game ids now include the source folder (two `games.pdn` files produced
colliding ids). The dataset was regenerated: train 18,808 · val 2,588 · test 2,063 positions
(320/44/32 games), with 120 leaking positions removed.

## 2. Held-out prediction (Brazilian test set, 2,063 positions from unseen games)

| Model | Log-loss ↓ | Brier ↓ | Decisive accuracy |
|---|---|---|---|
| Constant (base rate) | 0.693 | 0.152 | 0.506 |
| Material only | 0.668 | 0.124 | **0.765** |
| Baseline hand eval (G8), logistic-mapped | 0.661 | 0.123 | 0.761 |
| Residual (baseline + learned terms) | 0.651 | 0.121 | 0.747 |
| Linear CHEAP (used by the search) | 0.616 | 0.116 | 0.746 |
| Linear FULL (+ mobility, runaways) | 0.603 | 0.113 | 0.742 |
| **MLP, piece-square planes (PyTorch, CUDA)** | **0.589** | **0.108** | 0.754 |

Learned linear CHEAP weights (logit per unit): men 0.805, **kings 0.835**, tempo −0.051,
center +0.091, back_rank −0.044. The model values **a king ≈ a man** (the baseline uses 3).

## 3. Does it play better? (learned search vs baseline search, paired openings)

| Learned model | Control | Games | W-D-L | Elo (95% CI) | LOS |
|---|---|---|---|---|---|
| Linear CHEAP | depth 4 | 32 | 13-4-15 | −22 [−141, +93] | 0.35 |
| Linear CHEAP | 0.05 s | 32 | 9-6-17 | **−89 [−215, +17]** | 0.06 |
| Residual | depth 4 | 32 | 14-8-10 | +44 [−60, +156] | 0.79 |
| Residual | 0.05 s | 32 | 12-8-12 | 0 [−108, +108] | 0.50 |
| **Residual** | **depth 4** | **128 (new openings)** | **55-28-45** | **+27 [−26, +82]** | **0.84** |

**Verdict:** better outcome prediction did **not** translate into demonstrably stronger play.
- The pure linear model is probably **worse** (LOS 0.06 at equal time). This is consistent with
  its "king ≈ man" valuation: promotion is worth almost nothing to it.
- The residual model shows a **possible small gain** that is **not significant** at 95%.
- Per ADR-016, **the baseline stays the default.**

## 4. Verification

7 new tests:
- recovery of known weights with fractional targets;
- **CHEAP features equal the strategy profile exactly** (300 positions);
- evaluator scale and validation;
- residual reduces to the baseline;
- committed models load with provenance (fingerprint round trip);
- search with a learned evaluator is legal and deterministic;
- the Hub engine accepts `eval-model`.

```
cd backend && python -m pytest   -> 255 passed, 5 skipped
```

## 5. Acceptance

| Criterion | Status |
|---|---|
| Learn from the platform's datasets with held-out evaluation | **met** |
| Compare model families (linear, residual, neural) | **met** (MLP best at prediction) |
| Integrate a learned model into the engine | **met** (pluggable evaluator, Hub param) |
| Demonstrate a playing-strength improvement | **not met**: measured, and not significant (best +27 Elo, CI includes 0) |

## 6. Next steps (not done here)

More and deeper self-play data (the outcome labels come from depth-4 games); search-aware
targets (for example deeper-search values instead of final outcomes); a faster board to afford
the FULL features or a small network in search; larger matches (≥ 500 games) to detect gains
below 30 Elo.
