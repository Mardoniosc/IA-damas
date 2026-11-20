"""Legal move generation: International-family rules (Brazilian 8x8, International 10x10).

Rule clauses implemented (see docs/architecture/rules-compatibility.md, BR column):

- Men move one square diagonally forward. They capture forward **and backward**.
- Kings are **flying**: they move and capture along a diagonal at any distance, and they may
  land on any empty square beyond the captured piece.
- Capture is mandatory. Among all capture sequences only those taking the **maximum number of
  pieces** are legal (*lei da maioria*). Men and kings count equally.
- A capture continues while possible. A piece may not be jumped twice. Empty squares
  (including the vacated origin) may be crossed again.
- Captured pieces are removed only **after** the move (Turkish-strike rule). Until then they
  block the diagonal.
- A man promotes only if it **ends** the move on the promotion rank. Passing through it during
  a capture leaves it a man (which then keeps capturing as a man).
- Routes with the same origin, destination and set of captured pieces are one move
  (``Move.identity``).
"""

from __future__ import annotations

from damas_ai.rules.geometry import NE, NW, SE, SW
from damas_ai.rules.moves import Move
from damas_ai.rules.position import PROMOTED, Color, Piece, Position, promotion_rank

_FORWARD = {Color.WHITE: (NE, NW), Color.BLACK: (SE, SW)}
_OWN = {Color.WHITE: (Piece.WHITE_MAN, Piece.WHITE_KING),
        Color.BLACK: (Piece.BLACK_MAN, Piece.BLACK_KING)}


def legal_moves(position: Position) -> tuple[Move, ...]:
    """All legal moves for the side to move. Empty tuple = the side to move has lost."""
    captures = _captures(position)
    if captures:
        return captures
    return _quiet_moves(position)


def apply_move(position: Position, move: Move) -> Position:
    """Apply ``move`` without legality checking (use ``game.play`` for checked play)."""
    squares = list(position.squares)
    piece = squares[move.origin]
    if piece == Piece.EMPTY:
        raise ValueError(f"no piece on origin square {move.origin}")
    squares[move.origin] = Piece.EMPTY
    for sq in move.captured:
        squares[sq] = Piece.EMPTY
    squares[move.destination] = PROMOTED[piece] if move.promotes else piece
    return Position(position.geometry, tuple(squares), position.side_to_move.opponent)


# --------------------------------------------------------------------------- quiet moves


def _quiet_moves(position: Position) -> tuple[Move, ...]:
    geometry = position.geometry
    rays = geometry.rays
    board = position.squares
    side = position.side_to_move
    man, king = _OWN[side]
    top = promotion_rank(geometry, side)
    forward = _FORWARD[side]
    moves: list[Move] = []
    for sq, piece in enumerate(board):
        if piece == man:
            for d in forward:
                ray = rays[sq][d]
                if ray and board[ray[0]] == Piece.EMPTY:
                    dest = ray[0]
                    moves.append(Move(sq, (dest,), (), geometry.rank_of(dest) == top))
        elif piece == king:
            for d in (NE, NW, SE, SW):
                for dest in rays[sq][d]:
                    if board[dest] != Piece.EMPTY:
                        break
                    moves.append(Move(sq, (dest,)))
    return tuple(moves)


# --------------------------------------------------------------------------- captures


def _captures(position: Position) -> tuple[Move, ...]:
    geometry = position.geometry
    rays = geometry.rays
    side = position.side_to_move
    man, king = _OWN[side]
    enemy = _OWN[side.opponent]
    top = promotion_rank(geometry, side)
    board = list(position.squares)

    best = 1  # minimum length worth recording; raised as longer sequences are found
    found: list[tuple[int, list[int], list[int]]] = []

    def record(origin: int, path: list[int], captured: list[int]) -> None:
        nonlocal best
        n = len(captured)
        if n > best:
            best = n
            found.clear()
        if n == best:
            found.append((origin, path[:], captured[:]))

    def man_dfs(origin: int, cur: int, path: list[int], captured: list[int]) -> None:
        extended = False
        for d in (NE, NW, SE, SW):
            ray = rays[cur][d]
            if len(ray) < 2:
                continue
            over, land = ray[0], ray[1]
            if board[over] in enemy and board[land] == Piece.EMPTY and over not in captured:
                extended = True
                path.append(land)
                captured.append(over)
                man_dfs(origin, land, path, captured)
                path.pop()
                captured.pop()
        if not extended and captured:
            record(origin, path, captured)

    def king_dfs(origin: int, cur: int, path: list[int], captured: list[int]) -> None:
        extended = False
        for d in (NE, NW, SE, SW):
            ray = rays[cur][d]
            k, n = 0, len(ray)
            while k < n and board[ray[k]] == Piece.EMPTY:
                k += 1
            if k >= n - 1 or board[ray[k]] not in enemy or ray[k] in captured:
                continue
            over = ray[k]
            j = k + 1
            while j < n and board[ray[j]] == Piece.EMPTY:
                extended = True
                path.append(ray[j])
                captured.append(over)
                king_dfs(origin, ray[j], path, captured)
                path.pop()
                captured.pop()
                j += 1
        if not extended and captured:
            record(origin, path, captured)

    for sq, piece in enumerate(position.squares):
        if piece == man or piece == king:
            board[sq] = Piece.EMPTY  # the moving piece has left its origin
            (man_dfs if piece == man else king_dfs)(sq, sq, [], [])
            board[sq] = piece

    if not found:
        return ()
    seen: set[tuple[int, int, frozenset[int]]] = set()
    moves: list[Move] = []
    for origin, path, captured in found:
        is_man = position.squares[origin] == man
        move = Move(origin, tuple(path), tuple(captured),
                    is_man and geometry.rank_of(path[-1]) == top)
        if move.identity not in seen:
            seen.add(move.identity)
            moves.append(move)
    return tuple(moves)
