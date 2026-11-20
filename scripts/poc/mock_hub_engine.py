"""TEST DOUBLE - a scripted fake engine that speaks Hub protocol v2 (Scan 3.1 protocol.txt).

It is NOT a draughts engine and NOT a substitute for evidence from a real engine. It exists so
the PoC harness's process handling, parsing and shutdown logic can be tested without any
third-party binary. Its replies are hard-coded and only plausible for the 10x10 start position.

Behaviour switches (command-line flags):
  --hang-search   never answer 'go' (tests search timeout + forced termination)
  --ignore-quit   ignore 'quit' (tests terminate/kill escalation)
  --crash-on-go   exit with code 3 on 'go' (tests EOF handling)
  --bad-move      answer with a move whose origin square is empty
"""

from __future__ import annotations

import sys


def emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main() -> int:
    flags = set(sys.argv[1:])
    for raw in sys.stdin:  # EOF -> exit, as protocol.txt requires
        line = raw.strip()
        cmd = line.split(" ", 1)[0] if line else ""
        if cmd == "hub":
            emit('id name=MockHub version=0.0-test author="Damas Super AI tests" country=None')
            emit('param name=variant value=normal type=enum values="normal killer bt frisian losing"')
            emit("param name=book value=true type=bool")
            emit("wait")
        elif cmd == "init":
            emit("some free-form loading text the GUI must ignore")
            emit("ready")
        elif cmd == "ping":
            emit("pong")
        elif cmd == "go":
            if "--crash-on-go" in flags:
                return 3
            if "--hang-search" in flags:
                continue
            emit("info depth=1 score=0.00 nodes=10 time=0.001 nps=0.0")
            emit('info depth=2 mean-depth=2.0 score=0.05 nodes=120 time=0.002 nps=0.1 pv="32-28 19-23"')
            emit("done move=" + ("26-21" if "--bad-move" in flags else "32-28") + " ponder=19-23")
        elif cmd == "quit":
            if "--ignore-quit" in flags:
                continue
            return 0
        # set-param, pos, level, new-game, stop, unknown commands: silently accepted/ignored
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
