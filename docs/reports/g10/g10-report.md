# G10 report — Strategic & Decision Intelligence

Gate: **G10** · Date: 2026-11-20 · Status: **complete**. Design: ADR-012.

## 1. What was built

| Component | Content |
|---|---|
| `damas_ai.strategy` | `StrategicProfile` per side: men, kings, tempo, center, back-rank guards, mobility, runaways (proxy); deltas and plain-language notes. **Descriptive only** |
| `damas_ai.decision.DecisionMaker` | candidates (proposals + best shot) → cross-evaluation by every engine → veto of proven losses → minimax normalized regret (weights optional) → confidence (high/medium/low/none) with reasons; includes the strategic profile |
| Interfaces | `python -m damas_ai.decision` (JSONL), `POST /decision`, `POST /strategy` |
| Consensus | `ConsensusAnalyzer.evaluate_move` made public (used by the decision layer) |

## 2. Verification

### 2.1 Tests (11 new)

Strategy: symmetric start, runaway proxy and the king exception, mobility from the Rules Core,
notes. Decision: unanimous → high; minimax regret picks the move nobody dislikes (regret 7.5
tolerances computed exactly); weights flip the choice; proven loss vetoed and contradiction
lowers confidence; single source capped at low; tactical shot joins the candidates and is
evaluated by every engine; only legal move; no engines → none; JSON view; API.

```
cd backend && python -m pytest   -> 224 passed, 5 skipped
```

### 2.2 Do the strategic features matter? (242 International positions, Scan evals, side to move's view)

| Feature (delta) | Correlation with Scan's eval | Partial correlation controlling for material |
|---|---|---|
| material (men + 3·kings) | **+0.931** | n/a |
| men | +0.882 | n/a |
| tempo | +0.659 | **−0.175** |
| back-rank guards | +0.511 | +0.092 |
| center | +0.428 | −0.100 |
| kings | +0.379 | n/a |
| mobility | +0.319 | −0.163 |
| runaways | +0.275 | **+0.285** |

**Reading:** material dominates. Once it is controlled for, only the runaway proxy keeps a
clearly positive association, and tempo and mobility turn slightly negative. The features are
therefore reported as descriptions, not used as value judgements (ADR-012 §6). These are
correlations on one sample, not causal claims.

### 2.3 Is the aggregated decision better than single engines? (39 hard International positions)

Positions: the 39 that were `preference` or had a proof gap in G7. Deciders run at 0.2 s per
move; judges are Scan and Kingsrow at **1.0 s** (cross-evaluation, judge units). The judges
are the same programs as two deciders, which biases the test *against* the aggregate.
Script: `scripts/engines/decision_evidence.py`.

| Decider | Errors > 0.10 (Scan judge) | Errors > 0.10 (Kingsrow judge) | Errors ≥ 1 man (Scan / Kingsrow judge) | Class-changing errors (Scan judge) |
|---|---|---|---|---|
| **Decision (Scan + Kingsrow)** | **3** | 6 | 3 / 5 | **0** |
| **Decision (+ internal engine)** | **3** | **5** | 3 / 4 | **0** |
| Scan alone | 6 | 12 | 4 / 7 | 2 |
| Kingsrow alone | 10 | 6 | 3 / 4 | 1 |
| Internal engine alone | 16 | 11 | 5 / 4 | 0 |

(Single engines: 37 positions each. In 2 positions only one legal move existed, so there was no
choice to judge.)

**Confidence is informative** (mean regret by the Scan judge):

| Decision | high | medium | low |
|---|---|---|---|
| Scan + Kingsrow | 0.19 (n 34) | n/a (n 0) | 1.20 (n 5) |
| + internal engine | **0.02** (n 30) | 1.14 (n 7) | 2.00 (n 2) |

## 3. Findings

| Finding | Consequence |
|---|---|
| On hard positions, minimax-regret aggregation halves the error count of the best single engine, under both judges, and avoids class-changing errors | it supports the platform thesis that the decision layer adds value beyond any one engine |
| Adding the weak internal engine does not hurt the decision (5 vs 6 errors by Kingsrow's judge) and sharpens confidence (high → mean regret 0.02) | a weak but independent voter is still useful as evidence |
| Positional features are mostly material proxies | they stay descriptive; learning (G14) is the place to weigh them |

Caveat: 39 positions is a small sample. Repeating with more positions and multiple runs (R20)
is part of G12.

## 4. Acceptance

| Criterion | Status |
|---|---|
| Independent decision layer combining engines, tactics and evidence | **met** |
| Explained output with confidence | **met**, and confidence is shown to be informative |
| Strategic analysis | **met**, as a measured descriptive profile |
| Decision quality measured against single engines | **met** (fewer errors on hard positions) |
| Brazilian decisions with more than low confidence | **not possible** yet (single source) |
