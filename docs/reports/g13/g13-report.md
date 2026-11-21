# G13 report — Game Analysis & Dataset

Gate: **G13** · Date: 2026-11-20 · Status: **complete**. Design: ADR-015.

## 1. What was built — `damas_ai.games`

| Component | Content |
|---|---|
| `pdn.parse_pdn` / `replay` / `game_text` | PDN reader (comments, variations, NAGs, move numbers), replay through the Rules Core with error reporting, canonical per-game PDN text |
| `analysis.analyze_game` | per-ply judgement by one engine (best move, cross-evaluation, regret, label) and per-player summary (accuracy, counts, mean regret) |
| `dataset.build_dataset` | position records (features from the side to move's view, outcome label, optional mover eval), split by game, leakage removal by canonical position, manifest with SHA-256 |
| `bench.SearchPlayer` | in-process fixed-depth internal search (fast, deterministic self-play) |
| CLI | `python -m damas_ai.games replay | analyze | selfplay | dataset` |
| KB | migration `0002` (`games`, `game_positions`); `record_game`; `python -m damas_ai.kb ingest --kind pdn` |

## 2. Verification

### 2.1 Tests (9 new)

PDN round trip of generated games; parser robustness (comments, nested variations, NAGs) and
an illegal move reported at its ply; unknown `GameType`; label thresholds; analysis of a
strong-vs-random game (the random side gets more mistakes); **dataset without leakage**
(a duplicated game must not leak, split by game, features/labels present, hashes); KB games
with position links; CLI self-play → replay → dataset with evals carried over; `game_text`
round trip. The migration ↔ ORM parity test now covers revision `0002`.

```
cd backend && python -m pytest   -> 247 passed, 5 skipped
```

### 2.2 Real data

| Step | Result |
|---|---|
| Replay of all G12 PDN games | Brazilian 96/96, International 48/48 |
| Self-play, Brazilian, internal depth 4, 300 balanced openings (306 s) | 300 games: 134 white wins / 110 black wins / 56 draws, mean 64 plies; 300/300 replay |
| Dataset (self-play + G12 Brazilian games) | **23,372 records**: train 18,736 · val 2,606 · test 2,030 (310/48/38 games); **leakage removed: 138 val + 69 test** positions; outcome balance in train 6,675 wins · 6,534 losses · 5,527 draws |
| Knowledge base (migrated in place 0001 → 0002, G11 data preserved) | 444 games, 29,406 game positions, 29,114 distinct positions (23,232 Brazilian); 24 s; 14.9 MB |

### 2.3 Game analysis — 6 International games judged by Scan (0.1 s per position)

| Player | Non-forced moves | Accuracy (best + good) | Inaccuracies | Mistakes | Blunders |
|---|---|---|---|---|---|
| Scan | 204 | **97.1%** | 5 | 0 | 1 |
| Kingsrow | 207 | **93.7%** | 11 | 1 | 1 |
| Internal engine | 148 | **57.4%** | 33 | 21 | 9 |

The ordering agrees with the G12 tournament (the internal engine lost every game to both).
Scan judging itself is **biased in its own favour**: the 97.1% vs 93.7% gap between Scan and
Kingsrow is not evidence that Scan is stronger (G12 had them drawing 16/16).

## 3. Findings

| Finding | Consequence |
|---|---|
| Leakage is real even within one generator: 207 positions of val/test also appeared in train (shared openings and transpositions) | canonical-position leakage removal is necessary, not cosmetic |
| The first KB ingestion stored the whole PDN file per game | per-game `game_text` |
| A single-judge analysis favours the judge | reports state the judge. A multi-judge analysis (G7 machinery) is the unbiased extension |

## 4. Acceptance

| Criterion | Status |
|---|---|
| Analyse games move by move with explained labels | **met** |
| Build reproducible, leakage-controlled datasets | **met** (23k Brazilian positions) |
| Games in the knowledge base | **met** (444 games) |
| Independent (non-self) judgement of Brazilian games | **not possible**: the only Brazilian judge is the internal engine |
