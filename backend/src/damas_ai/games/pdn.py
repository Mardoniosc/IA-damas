"""PDN reading and replay (G13, ADR-015).

``parse_pdn`` tokenizes PDN text into games (tags, move tokens, result), skipping comments
``{...}``, NAGs ``$n``, move numbers and variations ``(...)``. ``replay`` validates every move
with the Rules Core. A game that cannot be replayed is reported with the ply and the reason,
never silently repaired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from damas_ai.rules import (
    BRAZILIAN_PROVISIONAL,
    INTERNATIONAL_PROVISIONAL,
    GameState,
    IllegalMoveError,
    Move,
    Position,
    Ruleset,
)
from damas_ai.rules.notation import NotationError, from_fen, parse_move

GAMETYPES: dict[int, Ruleset] = {20: INTERNATIONAL_PROVISIONAL, 26: BRAZILIAN_PROVISIONAL}
RESULTS = {"1-0", "0-1", "1/2-1/2", "*", "2-0", "0-2", "1-1"}
_TAG = re.compile(r'\[(\w+)\s+"((?:[^"\\]|\\.)*)"\]')
_MOVE = re.compile(r"^\d{1,2}(?:[-x]\d{1,2})+$|^[a-j]\d{1,2}(?:[-x][a-j]\d{1,2})+$")


@dataclass
class PdnGame:
    tags: dict[str, str]
    moves: list[str]
    result: str = "*"


@dataclass
class ReplayedGame:
    pdn: PdnGame
    ruleset: Ruleset
    start: Position
    moves: list[Move] = field(default_factory=list)
    states: list[GameState] = field(default_factory=list)  # state before each move, plus the final
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _strip(text: str) -> str:
    text = re.sub(r"\{[^}]*\}", " ", text)
    depth, out = 0, []
    for ch in text:  # remove (possibly nested) variations
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def parse_pdn(text: str) -> list[PdnGame]:
    games: list[PdnGame] = []
    tags: dict[str, str] = {}
    body: list[str] = []

    def flush() -> None:
        nonlocal tags, body
        if tags or body:
            moves, result = [], tags.get("Result", "*")
            for tok in _strip(" ".join(body)).split():
                tok = re.sub(r"^\d+\.(\.\.)?", "", tok)  # "12." or "12..." prefixes
                tok = tok.rstrip("!?*+#")
                if not tok or tok.startswith("$"):
                    continue
                if tok in RESULTS:
                    result = tok
                    continue
                if _MOVE.match(tok):
                    moves.append(tok)
            games.append(PdnGame(dict(tags), moves, result))
        tags, body = {}, []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            if body:  # a tag after movetext starts a new game
                flush()
            for k, v in _TAG.findall(stripped):
                tags[k] = v
        elif stripped:
            body.append(stripped)
    flush()
    return games


def game_text(game: PdnGame) -> str:
    """Canonical PDN text of one game (tags, numbered moves, result)."""
    head = "\n".join(f'[{k} "{v}"]' for k, v in game.tags.items())
    body = " ".join(f"{i // 2 + 1}. {m}" if i % 2 == 0 else m for i, m in enumerate(game.moves))
    return f"{head}\n\n{body} {game.result}\n".lstrip()


def ruleset_for(game: PdnGame, default: Ruleset | None = None) -> Ruleset:
    gt = game.tags.get("GameType", "").split(",")[0].strip()
    if gt.isdigit() and int(gt) in GAMETYPES:
        return GAMETYPES[int(gt)]
    if default is None:
        raise ValueError(f"unsupported or missing GameType {gt!r}")
    return default


def replay(game: PdnGame, ruleset: Ruleset | None = None) -> ReplayedGame:
    rs = ruleset or ruleset_for(game)
    fen = game.tags.get("FEN")
    try:
        start = from_fen(rs.geometry, fen) if fen else rs.initial_position()
    except (NotationError, ValueError) as exc:
        return ReplayedGame(game, rs, rs.initial_position(), error=f"bad FEN: {exc}")
    out = ReplayedGame(game, rs, start)
    state = GameState.new(rs, start)
    out.states.append(state)
    for ply, token in enumerate(game.moves, 1):
        try:
            move = parse_move(state.position, token)
            state = state.play(move)
        except (NotationError, IllegalMoveError) as exc:
            out.error = f"ply {ply} ({token}): {exc}"
            break
        out.moves.append(move)
        out.states.append(state)
    return out
