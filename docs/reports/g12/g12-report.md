# G12 report — Benchmark & Tournament System

Gate: **G12** · Date: 2026-11-20 · Status: **complete**. Design: ADR-014.

## 1. What was built — `damas_ai.bench`

| Component | Content |
|---|---|
| `players` | `EnginePlayer` (any adapter, `go think`, full history), `SearchPlayer` (internal search in-process, fixed depth), `RandomPlayer`, `GreedyPlayer` (2-ply materialist) |
| `game.play_game` | **the Rules Core is the arbiter**: results, ruleset draws, forfeits (illegal, timeout, crash), move-cap adjudication |
| `openings` | seeded random walks filtered to be balanced by the internal engine (\|score\| ≤ 0.40 men at depth 4) |
| `match` | paired colours per opening, sequential games, round-robin, standings, PDN writer (`GameType` 20/26) |
| `stats` | W/D/L, score, Elo with 95% interval (unbounded or non-estimable sides reported as `None`), LOS, draw rate; logistic score→result calibration |
| CLI | `python -m damas_ai.bench --players …` → `games.pdn`, `games.jsonl`, `summary.json` |

## 2. Verification

### 2.1 Tests (9 new)

Elo/LOS and interval edge cases (perfect score is unbounded; all draws are not estimable);
logistic fit recovers a known relation; game ends by the Rules Core; forfeit and illegal move
lose; move cap; ruleset repetition draw; deterministic, distinct, balanced openings; colour
swapping and outputs; CLI with the internal engine as a Hub process (depth 3 vs random).

```
cd backend && python -m pytest   -> 246 passed, 5 skipped (G13 tests included in the working tree)
```

### 2.2 Brazilian round-robin (96 games; 8 openings × 2 colours × 6 pairings)

`python -m damas_ai.bench --variant brazilian-8x8 --players "engine:damasai_br@depth=6" "engine:damasai_br@depth=3" greedy random --openings 8`

| Pairing | W-D-L | Score | Elo (95% CI) | LOS |
|---|---|---|---|---|
| internal d6 vs internal d3 | 15-1-0 | 0.969 | **+597** [+401, unbounded) | 0.9999 |
| internal d3 vs greedy | 11-3-2 | 0.781 | **+221** [+77, +526] | 0.994 |
| internal d6 vs greedy / random | 16-0-0 / 16-0-0 | 1.0 | unbounded | 1.0 |
| internal d3 vs random | 16-0-0 | 1.0 | unbounded | 1.0 |
| greedy vs random | 16-0-0 | 1.0 | unbounded | 1.0 |

Standings: d6 47.5/48 · d3 29/48 · greedy 19.5/48 · random 0/48. **The benchmark orders the
players exactly by expected strength**, including the depth scaling of the internal engine.
Terminations: 92 by "no legal moves", 4 by the (provisional) 40-ply king-only rule.

### 2.3 International round-robin (48 games, 0.1 s per move)

| Pairing | W-D-L | Note |
|---|---|---|
| Scan vs Kingsrow | **0-16-0** | 100% draws: no strength difference measurable at this budget (Scan's readme itself notes many draws under international rules). The Elo interval is **not estimable** |
| Scan vs internal | 16-0-0 | |
| Kingsrow vs internal | 16-0-0 | |

48 games, mean 121 plies, 580 s total. Terminations: 32 by no legal moves, 13 by the 50-ply
king-only rule, 3 by repetition. All 48 PDN games replay through the Rules Core.

### 2.4 Score → result calibration

| Player | n evals | Fit |
|---|---|---|
| Scan | 2,042 | slope 1.09 per man |
| Kingsrow | 1,692 | slope 3.02 per Kingsrow unit |
| internal (Brazilian, d6 / d3) | 925 / 1,142 | slope 1.34 / 0.61 |

**Not trustworthy yet.** The decisive games are one-sided (strong vs weak), and the balanced
pairing (Scan vs Kingsrow) produced only draws. The fits therefore mostly reflect who was
playing. Meaningful calibration needs many games between players of similar strength, which
is a known limitation that G13/G14 can address with self-play data.

## 3. Findings and fixes

| Finding | Fix |
|---|---|
| A 1-ply "greedy" player is almost random in draughts (captures are forced; quiet moves never change material). It lost 3–5 to random | `GreedyPlayer` is now 2-ply (it then beats random 16-0) |
| An Elo upper bound printed as "2400" when the interval hit 100% | unbounded sides are reported as `None` |
| 16 draws gave a zero-width interval `[0, 0]`, which looks like certainty | zero variance makes the interval non-estimable (`None`) |
| Generated benchmark outputs were not git-ignored | `reports/bench/` and `reports/*.log` are now ignored |

## 4. Acceptance

| Criterion | Status |
|---|---|
| Controlled engine-vs-engine benchmarks with the platform as arbiter | **met** |
| Tournaments with paired openings and statistics with uncertainty | **met** |
| Shown to measure strength (sanity ordering) | **met** (Brazilian four-player ordering) |
| Reproducible outputs (PDN, JSONL, provenance) | **met** |
| Distinguish Scan from Kingsrow | **not at 0.1 s / 16 games** (all draws). Needs longer controls or more games |
| Score calibration | **implemented, not yet reliable** (data bias explained) |
