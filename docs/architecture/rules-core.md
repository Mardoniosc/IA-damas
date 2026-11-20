# Rules Core (`damas_ai.rules`)

Delivered in G2. It is the platform's sole legal-move authority (ADR-001). Standard library
only: no I/O and no engine code.

## Modules

| Module | Responsibility |
|---|---|
| `geometry` | `Geometry` (8x8 `BOARD_8X8`, 10x10 `BOARD_10X10`): canonical index `i = r*(N/2) + f//2`, precomputed diagonal rays (direction order NE, NW, SE, SW), `rotate180` |
| `position` | `Color`, `Piece`, immutable `Position` (DSA string I/O, `flipped`, `material`) |
| `moves` | immutable `Move(origin, path, captured, promotes)`; `identity = (origin, destination, frozenset(captured))` |
| `movegen` | `legal_moves(position)`, `apply_move(position, move)` (unchecked) |
| `rulesets` | `Ruleset`, `EndgameDrawRule`, `BRAZILIAN_PROVISIONAL`, `INTERNATIONAL_PROVISIONAL` |
| `game` | immutable `GameState` (`new`, `play` = checked, `result`), `Outcome`, `GameResult` |
| `zobrist` | `zobrist_key`, incremental `key_after`; `ZOBRIST_VERSION = 1` |
| `notation` | numeric (PDN) and algebraic squares; move format/parse; PDN FEN |
| `resolve` | `resolve_engine_move(position, origin, destination, captured=None)` for adapters |
| `perft` | `perft`, `divide` |

## Invariants

1. `legal_moves` returns captures only if any capture exists, and only those of maximum length.
2. Moves with equal `identity` appear once (the first route found is kept as representative).
3. A `Move.captured` is in capture order and has the same length as `path`.
4. `Position` rejects unpromoted men on their promotion rank and wrong square counts.
5. `GameState.result()` checks "no legal moves" (a loss) before any draw rule.
6. Draw limits are in **plies** and come from the `Ruleset`.
7. Symmetry: `legal_moves(p.flipped())` equals the rotated `legal_moves(p)` by identity
   (property-tested on 3,000 positions).

## Usage

```python
from damas_ai.rules import BRAZILIAN_PROVISIONAL, GameState
from damas_ai.rules.notation import parse_move, format_move

state = GameState.new(BRAZILIAN_PROVISIONAL)
state = state.play(parse_move(state.position, "c3-d4"))   # or "22-18"
print([format_move(state.position.geometry, m, "algebraic") for m in state.legal_moves()])
print(state.result())
```

## Provisional items (do not rely on them as official)

| Item | Current value | Source | Status |
|---|---|---|---|
| Numeric square numbering (8x8) | 1 = b8 … 29 = a1 … 32 = g1 | en.wikipedia; matches py-draughts | [S] needs CBJD/PDN confirmation |
| King-only draw limit | 40 plies ("20 lances" read as 20 per side) | pt.wikipedia | interpretation UNVERIFIED |
| 3 kings vs 1 king | 40 plies | pt.wikipedia | conflicts with a "5-move" mention elsewhere |
| Repetition | 3-fold, automatic | pt.wikipedia (over the board it must be claimed) | [S] |
| International draw rules | 50 plies king-only; no endgame rules | [K] | only used for engine move validation |

## Performance (measured 2026-11-20, Python 3.11.9, Windows 11)

Perft from the Brazilian start position, bulk-counted at the leaves: depth 7 (187,302) in
about 1.2 s and depth 8 (907,830) in about 6 s, i.e. about 150k leaves/s. This is adequate for
validation. Search (G8) will need its own fast internals (ADR-006).
