# Canonical position representation

Decision record: ADR-003. Implementation: G2 (`damas_ai.rules`).

## 1. Goals

1. One internal representation, independent of every engine and every notation.
2. A cheap, stable key for the knowledge base (G11) and for experiment logs.
3. Enough game state to apply draw rules. A bare position is not enough.
4. Geometry that can be parameterized. Brazilian 8x8 is primary. International 10x10 is
   supported for engine validation (ADR-005 option A, accepted).

## 2. Board geometry (Brazilian 8x8)

- Files `a`–`h` (f = 0..7) and ranks `1`–`8` (r = 0..7), seen from White.
- **Square a1 is dark/playable.** Per pt.wikipedia "Damas" and en.wikipedia "Brazilian
  draughts", the lower-left corner square from each player's side is dark. **UNVERIFIED against
  the official CBJD text.** G2 must confirm this before freezing fixtures.
- Playable squares are those where `(f + r) % 2 == 0`. There are 32 of them.
- **Canonical index** `i = 4*r + f // 2`, range 0..31:

```
rank 8 |   28    29    30    31        b8 d8 f8 h8
rank 7 | 24    25    26    27          a7 c7 e7 g7
rank 6 |   20    21    22    23        b6 d6 f6 h6
rank 5 | 16    17    18    19          a5 c5 e5 g5
rank 4 |   12    13    14    15        b4 d4 f4 h4
rank 3 |  8     9    10    11          a3 c3 e3 g3
rank 2 |    4     5     6     7        b2 d2 f2 h2
rank 1 |  0     1     2     3          a1 c1 e1 g1
          a  b  c  d  e  f  g  h
```

- Start position: White men on 0..11 (ranks 1–3), Black men on 20..31 (ranks 6–8), and
  **White moves first** (pt/en Wikipedia, which agree. CBJD confirmation is pending as above).
- Diagonal neighbours are precomputed tables per geometry. There is no arithmetic on indices
  outside the geometry module.

## 3. Symmetry

- Rotating 180° and swapping colors and side to move maps index `i → 31 − i`. This was
  verified algebraically: (f,r) → (7−f, 7−r) maps the formula above to 31 − i on both rank
  parities. It is the only board symmetry the knowledge base may use for normalization.
- A left-right mirror is **not** a symmetry: it maps a1 (dark) to h1 (light) and changes
  which long diagonal is the main one.

## 4. Data model

```
Piece          = EMPTY | WHITE_MAN | WHITE_KING | BLACK_MAN | BLACK_KING
Position       = (geometry_id, squares: tuple[Piece, ...] (len 32), side_to_move: WHITE|BLACK)   # immutable
GameState      = (position, history_keys: tuple[int, ...], counters: DrawCounters, ruleset_id)
DrawCounters   = (king_moves_without_capture_or_man_move, endgame_counter?, ...)   # exact fields set by G2 once draw rules are confirmed
Move           = (origin, destination, path: tuple[int,...], captured: tuple[int,...] (ordered), promotes: bool)
```

- `Move.captured` is stored **in capture order** together with the landing squares (`path`).
  Engine notations that drop pivots or order (Hub) are resolved by matching against the
  legal-move list (engine-integration.md §5).
- `ruleset_id` names the rule set version (e.g. `br-cbjd-<date>`). Draw-rule parameters live in
  the rule set and are not hardcoded, because the sources disagree today
  (rules-compatibility.md §3).

## 5. Serializations

| Name | Use | Format |
|---|---|---|
| **DSA string** (canonical) | logs, fixtures, KB natural key | `<side>` + 32 chars in canonical index order. `w`/`W` white man/king, `b`/`B` black man/king, `e` empty. Example start: `W` + `w`×12 + `e`×8 + `b`×12 |
| **Zobrist key** | hashing, repetition, KB index | 64-bit, fixed seed versioned with the ruleset |
| **PDN FEN** | interchange with other tools | `W:W<squares>:B<squares>` (kings prefixed `K`), using the PDN numeric numbering for GameType 26 (Brazilian). **The numeric numbering origin is UNVERIFIED**: en.wikipedia says square 29 is at White's left corner. G2 must confirm against PDN 3.0 / CBJD sources and pin it with tests |
| **Algebraic** | human I/O | `c3-d4`, captures `c3xe5xg7`. Common in Brazilian literature (**UNVERIFIED** as the official CBJD notation) |

Note that the DSA string is deliberately **not** the Hub string. Hub's square order and its
10x10 length are engine-specific, and conflating them would invite silent bugs.

## 6. Engine conversions (adapter responsibility, G3+)

| Target | Conversion |
|---|---|
| Hub (Scan, 10x10) | geometry-specific square map + `W`/`B` side char. Only meaningful for 10x10 positions |
| CheckerBoard `Board8x8` | `(x, y)` coordinates. CB's square-number↔coordinate map differs per gametype (`numbertocoors` in `cb_interface.h` has separate branches for Italian, Spanish and Czech and a default for the others), so the adapter must use the engine's declared gametype |
