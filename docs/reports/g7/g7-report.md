# G7 report — Consensus & Divergence

Gate: **G7 Consensus & Divergence** · Date: 2026-11-20 · Status: **complete, awaiting owner
review**. Design: ADR-009. Engines: Scan 3.1 and Kingsrow hub 1.63 (International 10x10 only;
there is still **no Brazilian engine**, so Brazilian requests return `incomplete` with an
explicit note).

## 1. What was built — `damas_ai.consensus`

| Module | Content |
|---|---|
| `values.py` | intra-engine utilities (eval / proven win / loss / terminal); root and after-move conversion; `contradicts`, `proof_gap` |
| `analyzer.py` | `ConsensusAnalyzer`: stage 1 = multi-engine proposals (G6), stage 2 = cross-evaluation (each engine × each candidate); per-engine regret; classification; `proof_gap` flag; tolerance per engine |
| `calibration.py` | `fit_scale`: descriptive scale relation between two engines (slope through origin, median ratio, Pearson r, sign agreement) |
| `serialize.py` | JSON view (`schema_version 1`) including candidates, values, regrets, root values, embedded G6 analysis |
| `__main__.py` | batch CLI `python -m damas_ai.consensus` → JSONL |
| API | `POST /consensus` (same body as `/analyses` plus `cross_check`, `tolerance`; sequential by default) |

Test double extended with `--score-table` (scripted scores per position), so each divergence
scenario is constructed deliberately.

## 2. Verification

### 2.1 Tests

15 new consensus tests: value conversions, contradiction and proof-gap rules, scale fit on a
known relation, every classification built with scripted doubles (`none`, `none` with
cross-check, `equivalent_alternatives`, `preference` and its tolerance flip, `outcome_conflict`
on a candidate and at the root, `proof_gap`), unknown perspective never guessed, terminal-win
candidate, `incomplete` (one engine; Brazilian), sequential default, JSON view and API.

```
cd backend && python -m pytest   -> 179 passed, 5 skipped
```

### 2.2 Real engines: 300 International positions, 0.2 s per move, sequential

`python -m damas_ai.consensus --config ../config/engines.toml --variant international-10x10 --fens ../reports/poc-runs/g6-fens.txt --move-time 0.2 --out ../reports/poc-runs/g7-consensus.jsonl`
(203 s.)

| Measure | Result |
|---|---|
| Classification (tolerance 0.10) | **none 213 · equivalent_alternatives 56 · preference 31 · outcome_conflict 0** |
| Cross-evaluated positions | 87 |
| `proof_gap` | 14 (8 with unanimous moves, 6 with a preference) |
| Median max-regret (own units) | Scan 0.040 (p75 0.110) · Kingsrow 0.020 (p75 0.060) |
| Scale relation, Kingsrow vs Scan (241 positions where both give an eval) | slope 0.644 · median ratio 0.739 · **r = 0.988** · sign agreement 100% |

Tolerance sensitivity (recomputed from the stored regrets):

| Tolerance | equivalent | preference |
|---|---|---|
| 0.05 | 40 | 47 |
| **0.10 (default)** | 56 | 31 |
| 0.25 | 74 | 13 |
| 0.50 | 76 | 11 |
| 1.00 | 78 | 9 |

## 3. Findings during G7

| Finding | Action |
|---|---|
| The first classification labelled 14 positions `outcome_conflict`. All were **one engine proving a result (Scan "win/loss in N plies") while the other gave a large eval in the same direction** (e.g. Kingsrow 10.6) | split into **contradiction** (`outcome_conflict`) and the **`proof_gap`** flag. Result: 0 contradictions, 14 proof gaps |
| **Run-to-run non-determinism**: the same 300 positions gave 203 and then 213 unanimous positions | documented in ADR-009. Single-run labels are samples. Repeated runs or fixed-depth limits (Scan only) are needed when stability matters |
| Most disagreements are small: the median regret is a few hundredths of each engine's unit | the default tolerance (0.10) is provisional. Its choice moves about 20 positions between `equivalent` and `preference` |
| Kingsrow's scale is about 0.64–0.74 of Scan's | descriptive only. Never used to compare raw scores (R08) |

## 4. Acceptance

| Criterion | Status |
|---|---|
| Agreement metrics (unanimity, agreement ratio) | **met** |
| Divergence detection and classification | **met**, including the distinction between contradiction and proof gap |
| No unvalidated cross-engine score comparison | **met** (intra-engine regret; scale fit descriptive) |
| Exposed via library, CLI and API, with reproducible records | **met** |
| Evidence on real engines | **met** (300 positions) |
| Brazilian consensus | **not possible** (no Brazilian engine; ADR-005) |

## 5. Open items

- Calibration against game outcomes (G12/G13) would make tolerance and scale meaningful in
  absolute terms.
- Kingsrow multi-PV is not used (ADR-009 §8).
- A Brazilian evidence source is still missing. The internal engine (G8) will be the first one.
