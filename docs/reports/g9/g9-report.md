# G9 report — Tactical Intelligence

Gate: **G9 Tactical Intelligence** · Date: 2026-11-20 · Status: **complete** (the owner
authorized committing each gate and continuing). Design: ADR-011.

## 1. What was built — `damas_ai.tactics`

| Component | Content |
|---|---|
| `forcing.material` | material balance (man 100, king 300) |
| `forcing.threats_against` | the opponent's captures in a null-move view: max pieces, threatened squares, moves |
| `forcing.find_shots` | forcing-line search: opponent replies only while capture is mandatory; S's quiet moves only if they force a capture (≤ 2); stand pat; shots = first moves gaining ≥ 1 man, with the line, the gain and a `sacrifice` flag |
| `critical.evaluate_moves` | internal-engine value of every legal move (a full-width "multi-PV") |
| `critical.assess` | `CriticalityReport`: flags `shot` (only with a real choice), `threat`, `only move`, `volatile`, `divergence`/`proof gap` (optional G7 input), with reasons and evidence |
| Interfaces | `python -m damas_ai.tactics` (JSONL; `--config` adds the consensus signal), `POST /tactics` |

## 2. Verification

### 2.1 Tests (12 new)

Material; threats derived from the Rules Core; a sacrifice shot **independently re-derived from
the Rules Core** (the opponent's every reply is a capture, then a 3-piece capture nets +2);
quiet moves that force nothing are not shots; a forced single move is not a decision; move
values cover every legal move and the internal engine finds the shot; flags consistent with
their evidence on 40 oracle positions; terminal rejected; divergence input; view, CLI and API;
colour symmetry of the detector.

```
cd backend && python -m pytest   -> 213 passed, 5 skipped
```

### 2.2 Precision judged by Scan and Kingsrow (International, 0.2 s per move)

Script: `scripts/engines/tactics_evidence.py`. The detector found 152 sacrifice shots and 45
capture-choice shots in the International oracle sample. For each, every judge picks its own
move; if it differs, the judge cross-evaluates the shot move against its own (G7 regret, judge
units).

| Kind | n | Judge plays the shot move | Judge regret ≤ 0.10 | Regret ≥ 1 man | Accepted by **both** judges |
|---|---|---|---|---|---|
| Sacrifice | 150 | Scan 114 · Kingsrow 114 | Scan 126 · Kingsrow 127 | Scan 14 · Kingsrow 8 | **122 (81%)** |
| Capture choice | 45 | Scan 39 · Kingsrow 40 | 41 · 41 | 2 · 2 | **41 (91%)** |

Median regret when a judge disagrees: Scan 0.48 / 0.36 · Kingsrow 0.23 / 0.15 (sacrifice /
capture choice).

**False positives inspected:** they come from play after the forced line ends. For example, a
promoting quiet move (`7-2`) "wins a man" within the line but both judges see a **proven loss**
afterwards.

### 2.3 Brazilian (no external judge)

| Measure | Result |
|---|---|
| Sacrifice shots in the Brazilian oracle sample | 245 |
| Internal engine at depth 8 plays the shot move | 123/150 (82%), consistent with the International precision |
| Criticality on 300 Brazilian positions (depth 6) | **35% critical**: volatile 62 · only move 30 · shot 26 · threat 9 |
| Speed | shots ≈ 1 ms per position; full assessment ≈ 0.15 s per position (depth 6) |

## 3. Findings during G9

| Finding | Action |
|---|---|
| First version flagged 64% of positions critical: alpha-beta odd/even flicker counted as "volatility", and forced single captures counted as "shots" | volatile = a final choice new to the last 2 depths (or a big swing); shots count only with a real choice; single legal move = no decision. Result: 35% |
| Detector horizon: counter-shots after the forced line are missed | documented (ADR-011). The report always includes the internal engine's move values next to the shot for cross-checking |
| `volatile` remains the most frequent flag | provisional; depends on internal-engine depth (revisit in G14) |

## 4. Acceptance

| Criterion | Status |
|---|---|
| Tactical detection usable for Brazilian (and International) | **met** |
| Critical-position identification with explained reasons | **met** |
| Measured precision, not assumed | **met** (81–91% acceptance by both external judges, International) |
| Brazilian precision measured by an independent judge | **not possible** (no external Brazilian engine). Internal self-consistency 82% |

## 5. Open items

- A verification step that runs the internal engine (or judges) on the position at the end of
  the forced line, to cut false positives.
- Thresholds calibrated on outcomes (G12/G13).
- Tactics are inputs for G10 (strategy and decision) and G11 (knowledge base of critical
  positions).
