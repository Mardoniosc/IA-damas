# Rules compatibility matrix

G1 deliverable 4. Compares the **target rules (Brazilian 8x8)**, what each external engine
actually implements, and the planned internal Rules Core.

## 0. Evidence levels

| Tag | Meaning |
|---|---|
| **[E]** | verified in G1 from a primary artifact: engine source, readme, protocol file, or the author's site |
| **[S]** | from a secondary public source read in G1 (Wikipedia), not yet checked against the official federation text |
| **[K]** | general domain knowledge, not re-verified in G1. **Must be verified before it is relied upon** |
| **[?]** | unknown or conflicting |

## 1. Which engine variant is even comparable?

| Engine build | Variant(s) implemented | Board | Evidence |
|---|---|---|---|
| Scan 3.1 | `normal` (International), `killer`, `bt` (breakthrough), `frisian`, `losing` | 10x10 only (`File_Size {10}`, `Rank_Size {10}` compile-time constants in `src/common.hpp`) | [E] readme, `var.cpp`, `common.hpp`, protocol.txt `param name=variant … values="normal killer bt frisian losing"` |
| Scan 3.0 lidraughts fork (RoepStoep) | `normal`, `killer`, `bt` (+ handicap levels) | 10x10 | [E] fork readme/protocol |
| Kingsrow (English) 1.21 | English/American checkers | 8x8 | [E] edgilbert.org |
| Kingsrow Italian 1.21 | Italian checkers | 8x8 | [E] edgilbert.org |
| Kingsrow International 1.63 (+ "Kingsrow hub" 1.63) | International draughts | 10x10 | [E] edgilbert.org |
| **Any Kingsrow for Brazilian** | none published | | [E] the Kingsrow index page lists only "English and Italian 8x8 checkers, and … 10x10 international draughts" |

Lidraughts states that "Scan 3.1 only knows 100-square variants" and that it therefore offers
no computer analysis for Brazilian ([S], lidraughts.org Brazilian draughts blog post).

**Key observation.** By rule content, Brazilian draughts is International draughts played on
8x8 with 12 men per side [S]. Scan's `normal` variant therefore has the right **rule logic**
but the wrong **geometry**. Kingsrow's 8x8 builds have the right geometry but the wrong rules.
No studied engine has both.

## 2. Matrix

Columns: **BR** = Brazilian (target) · **SCAN** = Scan 3.1 `normal` · **KR-EN** = Kingsrow
English · **KR-IT** = Kingsrow Italian · **KR-INT** = Kingsrow International · **CORE** =
internal Rules Core (**implemented in G2**; see `rules-core.md` and the G2 report for tests).

| Aspect | BR (target) | SCAN `normal` | KR-EN | KR-IT | KR-INT | CORE (G2) |
|---|---|---|---|---|---|---|
| Board | 8x8, dark squares, a1 dark [S] | **10x10** [E] | 8x8 [E] | 8x8 [E] | 10x10 [E] | 8x8, geometry parameterized (10x10 optional per ADR-005) |
| Pieces per side | 12 [S] | 20 [K] | 12 [K] | 12 [K] | 20 [K] | 12 (8x8) |
| First move | White [S] | White [K] (Hub start pos `W…`) [E] | Black [K] | White [K] | White [K] | White, per ruleset |
| Man movement | 1 square diagonally forward [S] | same [K] | same [K] | same [K] | same [K] | as BR |
| Man captures backward | **Yes** [S] | Yes [K] | **No** [K] | **No** [K] | Yes [K] | Yes |
| Man may capture a king | Yes [S] ("A peça e a dama têm o mesmo valor") | Yes [K] | Yes [K] | **No** [K] | Yes [K] | Yes |
| Capture mandatory | Yes [S] | Yes [K] | Yes [K] | Yes [K] | Yes [K] | Yes |
| Choice among captures | **Majority: must take the maximum number of pieces** (*lei da maioria*) [S] | Majority [K] | **Free choice** (no majority rule) [K] | Hierarchical priority (most pieces, then capture with king, then most kings, then earliest king) [K] | Majority [K] | Majority |
| King vs man value in the majority count | Equal [S] | Equal [K] | n/a | Kings weigh in the tie-breaks [K] | Equal [K] | Equal |
| Multi-capture | Mandatory continuation [S] | same [K] | same [K] | same [K] | same [K] | same |
| Removal timing | After the whole move (Turkish-strike rule) [S] | same [K] | n/a in practice (non-flying kings) [K] | [K] | same [K] | after move |
| Same piece jumped twice | Forbidden. Empty squares may be crossed more than once [S] | same [K] | [K] | [K] | same [K] | forbidden |
| Promotion | Only if the man **ends** the move on the last row. Passing through mid-capture does not promote [S] | same [K] | Promotion ends the move [K] | [K] | same [K] | as BR |
| King movement | **Flying** (any distance diagonally) [S] | Flying [K] | **1 square** [K] | **1 square** [K] | Flying [K] | Flying |
| King capture landing | Any empty square beyond the captured piece (subject to majority) [S] | same [K] | adjacent only [K] | adjacent only [K] | same [K] | as BR |
| Newly promoted king moves | Only on the next turn [S] | same [K] | same [K] | [K] | same [K] | as BR |
| Win | Opponent has no legal move (no pieces or blocked) [S] | same [K] | same [K] | same [K] | same [K] | same |
| Draw: repetition | 3-fold, same side to move. pt.wiki: must be claimed, and only when the game is being scored [S] | Hub sends king moves so the engine can detect repetition [E]; exact engine rule [?] | [K] | [K] | [K] | ruleset parameter |
| Draw: king-move rule | **20** successive king moves without capture or man move [S] (pt.wiki; corroborated by a regulation found by web search but not read directly) | International rule differs (25 moves) [K] | different (e.g. 40-move rule in English play) [K] | [?] | 25 [K] | ruleset parameter |
| Draw: special endgames | **[?] CONFLICT**: pt.wiki says "3 kings vs 1: 20 moves". A competition regulation found by web search mentions faster draws "after 5 moves" in some king endings. The official CBJD text was **not obtained** (403) | International has its own counts (e.g. 16 moves for 3 kings vs 1) [K] | n/a | [?] | as International [K] | ruleset parameter, **blocked on official text** |
| Position input | n/a | Hub string: `W`/`B` + 50 chars [E] | CB `int[8][8]` + color [E] | CB `int[8][8]` + color [E] | **[?]** (Hub dialect) | DSA string (ADR-003) |
| Move output | n/a | `a-b`, `axbxc…` (captured squares, unordered, no pivots) [E] | `CBmove` struct (from, to, path, del) [E] | same [E] | **[?]** | `Move` with ordered path + captured |
| Notation squares | algebraic or numeric 1–32 [S]; numbering origin [?] | 1–50 [E] | 1–32 (CB default mapping) [E] | 1–32 (Italian mapping) [E] | 1–50 [K] | canonical 0–31 + converters |

## 3. Explicit incompatibilities

| ID | Incompatibility | Consequence |
|---|---|---|
| INC-1 | Scan's geometry is fixed at compile time to 10x10, and its eval weights, opening book and bitbases are 10x10 data | Scan **cannot analyse a Brazilian position**. Porting would need code changes, plus a new eval trained on 8x8, plus new bitbases, plus dropping or rebuilding the book. A port would be a GPL-3.0 derivative |
| INC-2 | Kingsrow 8x8 builds play English or Italian rules: men cannot capture backward, kings are not flying, and there is no majority rule (English) or a different priority rule (Italian) | Any Brazilian position sent to them would be analysed under the **wrong rules**. Moves could be illegal in BR, or legal BR moves could be missing |
| INC-3 | Kingsrow International is 10x10 | Same as INC-1 for geometry |
| INC-4 | Hub capture notation omits pivots and order | A Hub move may be ambiguous; it must be resolved against the Rules Core |
| INC-5 | Brazilian draw-rule details are unresolved across sources | The Rules Core must make draw rules ruleset-parameterized; G2 cannot freeze them until the official CBJD text is obtained |
| INC-6 | Score semantics differ (Scan: men + sentinel bands; CB: WIN/LOSS/DRAW/UNKNOWN + free text) | No cross-engine score comparison without calibration (engine-integration.md §4) |

## 4. Required action before G2 freezes rules

1. Obtain the official CBJD rules text (or FMJD "Official Rules of the game in draughts-64",
   which en.wikipedia cites). Confirm: board orientation, numbering, every draw rule.
2. Replace every [S] in the BR column with an [E] citation (document + article number).
3. Under ADR-005 option A, the **SCAN `normal` and KR-INT columns are in scope**. Their [K]
   items must be verified against the FMJD International rules before G4/G5 conformance tests
   rely on them. The KR-EN and KR-IT columns are out of scope and stay informational.
