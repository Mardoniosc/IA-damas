"""TEST DOUBLE - a scripted Hub v2 engine for framework tests. NOT a draughts engine.

It chooses moves with the Rules Core itself (first legal move), so in its default mode it is
"correct by construction". It proves the *framework* (process handling, protocol, validation),
never engine quality or rules correctness. Its Hub encoding/decoding is written here
independently of ``damas_ai.engines.hub.protocol``, so codec bugs are not masked.

Requires ``damas_ai`` importable (tests pass PYTHONPATH). Flags:
  --name NAME        id name (default HubDouble; "Scan" exercises the Scan profile)
  --rules-blind      ignore mandatory/majority capture: play a quiet move when one exists
  --hang             do not answer 'go' until 'stop', then answer
  --deaf             never answer 'go' nor 'stop'
  --crash-on-go      exit(3) on 'go'
  --ignore-quit      ignore 'quit' and stdin EOF
  --garbage          answer 'done move=zz'
  --bad-pv           second PV move is illegal
  --short-capture    write captures as 'from x to' (no captured squares)
  --error-line       emit an 'error' line before 'done'
  --stderr           write diagnostics to stderr
  --no-id            omit the 'id' line
  --slow-init S      sleep S seconds before 'ready'
"""

from __future__ import annotations

import argparse
import sys
import time

from damas_ai.rules import BOARD_8X8, BOARD_10X10, apply_move, legal_moves
from damas_ai.rules.movegen import _quiet_moves
from damas_ai.rules.notation import from_numeric, to_numeric
from damas_ai.rules.position import Color, Piece, Position

CHARS = {"w": Piece.WHITE_MAN, "W": Piece.WHITE_KING, "b": Piece.BLACK_MAN, "B": Piece.BLACK_KING}


def emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def decode(text: str) -> Position:
    geometry = {33: BOARD_8X8, 51: BOARD_10X10}[len(text)]
    pieces = {from_numeric(geometry, i): CHARS[c] for i, c in enumerate(text[1:], 1) if c != "e"}
    return Position.from_pieces(geometry, pieces, Color(text[0]))


def fmt(position: Position, move, short: bool = False) -> str:  # type: ignore[no-untyped-def]
    g = position.geometry
    n = lambda s: str(to_numeric(g, s))  # noqa: E731
    if not move.is_capture:
        return f"{n(move.origin)}-{n(move.destination)}"
    if short:
        return f"{n(move.origin)}x{n(move.destination)}"
    return "x".join([n(move.origin), n(move.destination), *(n(c) for c in sorted(move.captured))])


def apply_text(position: Position, text: str) -> Position:
    for m in legal_moves(position):
        if fmt(position, m) == text or fmt(position, m, short=True) == text:
            return apply_move(position, m)
    raise ValueError(f"double cannot apply {text}")


def parse_args_line(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    rest = line.split(" ", 1)[1] if " " in line else ""
    i = 0
    while i < len(rest):
        if rest[i] == " ":
            i += 1
            continue
        eq = rest.find("=", i)
        sp = rest.find(" ", i)
        if eq < 0 or (0 <= sp < eq):
            end = sp if sp >= 0 else len(rest)
            out[rest[i:end]] = ""
            i = end
            continue
        key = rest[i:eq]
        if eq + 1 < len(rest) and rest[eq + 1] == '"':
            close = rest.index('"', eq + 2)
            out[key] = rest[eq + 2:close]
            i = close + 1
        else:
            end = rest.find(" ", eq)
            end = end if end >= 0 else len(rest)
            out[key] = rest[eq + 1:end]
            i = end
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="HubDouble")
    for flag in ("rules-blind", "hang", "deaf", "crash-on-go", "ignore-quit", "garbage", "bad-pv",
                 "short-capture", "error-line", "stderr", "no-id"):
        ap.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--slow-init", type=float, default=0.0)
    opt = ap.parse_args()

    position: Position | None = None
    pending_answer = False

    def answer() -> None:
        assert position is not None
        moves = legal_moves(position)
        chosen = moves[0]
        if opt.rules_blind:
            quiet = _quiet_moves(position)
            if quiet:
                chosen = quiet[0]
        if opt.garbage:
            emit("done move=zz")
            return
        after = apply_move(position, chosen)
        reply = legal_moves(after)
        pv = [fmt(position, chosen, opt.short_capture)]
        if reply:
            pv.append("1-1" if opt.bad_pv else fmt(after, reply[0]))
        emit("info depth=1 score=0.00 nodes=12 time=0.001 nps=0.0")
        emit(f'info depth=2 mean-depth=2.0 score=-0.25 nodes=140 time=0.002 nps=0.1 pv="{" ".join(pv)}"')
        if opt.error_line:
            emit('error message="double: synthetic error"')
        ponder = f" ponder={fmt(after, reply[0])}" if reply else ""
        emit(f"done move={pv[0]}{ponder}")

    for raw in sys.stdin:
        line = raw.strip()
        cmd = line.split(" ", 1)[0] if line else ""
        if opt.stderr:
            sys.stderr.write(f"double got: {cmd}\n")
            sys.stderr.flush()
        if cmd == "hub":
            if not opt.no_id:
                emit(f'id name={opt.name} version=0.0-test author="Damas Super AI tests" country=None')
            emit('param name=variant value=normal type=enum values="normal killer bt frisian losing"')
            emit("param name=book value=true type=bool")
            emit("wait")
        elif cmd == "init":
            time.sleep(opt.slow_init)
            emit("loading data (ignored by GUI)")
            emit("ready")
        elif cmd == "ping":
            emit("pong")
        elif cmd == "pos":
            args = parse_args_line(line)
            position = decode(args["pos"])
            for text in args.get("moves", "").split():
                position = apply_text(position, text)
        elif cmd == "go":
            if opt.crash_on_go:
                return 3
            if opt.deaf:
                continue
            if opt.hang:
                pending_answer = True
                continue
            answer()
        elif cmd == "stop":
            if pending_answer and not opt.deaf:
                pending_answer = False
                answer()
        elif cmd == "quit":
            if not opt.ignore_quit:
                return 0
    # stdin closed
    if opt.ignore_quit:
        while True:
            time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
