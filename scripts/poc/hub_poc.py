"""G1 Task 5 - technical proof of concept for Hub-protocol engines (Scan 3.1, Kingsrow hub).

THROWAWAY DISCOVERY CODE. This is *not* the G3 engine-integration framework; it exists to
validate, with evidence, the eight PoC steps required by G1:

  1 start the engine           5 receive a result
  2 identify its version       6 interpret the output
  3 send a test position       7 validate the returned move (syntax + origin-square ownership)
  4 request analysis           8 terminate cleanly (quit -> terminate -> kill)

Protocol reference: "Hub protocol for draughts, version 2" (protocol.txt shipped with Scan 3.1).
Full legality checking is impossible before the Rules Core exists (G2) and is therefore not
claimed here.

Usage (real engine, after you obtained it yourself - see docs/reports/g1/07-poc-report.md):

    python scripts/poc/hub_poc.py --executable C:/engines/scan/scan.exe --arg hub \
        --set variant=normal --set book=false --move-time 1

Exit code 0 = all steps passed; 1 = a step failed (the JSON report says which).
"""

from __future__ import annotations

import argparse
import json
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# International (10x10) start position in Hub notation: side to move + 50 squares.
INTERNATIONAL_START = "W" + "b" * 20 + "e" * 10 + "w" * 20
HUB_MOVE_RE = re.compile(r"^(\d{1,2})(?:-(\d{1,2})|((?:x\d{1,2})+))$")


# --------------------------------------------------------------------------- protocol parsing


@dataclass(frozen=True)
class HubLine:
    command: str
    args: dict[str, str]


def parse_hub_line(line: str) -> HubLine | None:
    """Parse ``<command> <arg>=<val> ...``; flags without ``=`` get the empty string.

    Values may be double-quoted (required when they contain spaces or ``=``). Returns None for
    blank lines. Unknown commands/args are kept: the protocol says to ignore, not reject, them.
    """
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError:  # unbalanced quotes - keep the raw line for diagnostics
        return HubLine(command="<unparseable>", args={"raw": line})
    if not tokens:
        return None
    args: dict[str, str] = {}
    for token in tokens[1:]:
        key, sep, value = token.partition("=")
        args[key] = value if sep else ""
    return HubLine(command=tokens[0], args=args)


def check_move(move: str, hub_position: str) -> list[str]:
    """Syntactic + ownership validation of a Hub move against a 10x10 Hub position string.

    Hub capture notation is from x to x captured x captured ... (captured squares in any order).
    """
    problems: list[str] = []
    m = HUB_MOVE_RE.match(move)
    if not m:
        return [f"move {move!r} does not match Hub notation"]
    squares = [int(s) for s in re.findall(r"\d{1,2}", move)]
    if any(not 1 <= s <= 50 for s in squares):
        problems.append(f"square out of range 1..50 in {move!r}")
        return problems
    if len(hub_position) != 51:
        return problems + ["position is not a 51-char 10x10 Hub position; ownership not checked"]
    side = hub_position[0]
    origin_piece = hub_position[squares[0]]
    own = {"W": "wW", "B": "bB"}[side]
    if origin_piece not in own:
        problems.append(f"origin square {squares[0]} holds {origin_piece!r}, not a {side} piece")
    if len(squares) >= 2 and hub_position[squares[1]] != "e" and squares[1] != squares[0]:
        problems.append(f"destination square {squares[1]} is not empty")
    if m.group(3):
        enemy = {"W": "bB", "B": "wW"}[side]
        for captured in squares[2:]:
            if hub_position[captured] not in enemy:
                problems.append(f"captured square {captured} holds no enemy piece")
    return problems


# --------------------------------------------------------------------------- process wrapper


class EngineProcess:
    """Line-oriented subprocess with a reader thread and deadline-based reads."""

    def __init__(self, argv: list[str], cwd: Path) -> None:
        self.transcript: list[tuple[float, str, str]] = []
        self._t0 = time.monotonic()
        self._lines: queue.Queue[str | None] = queue.Queue()
        self.proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _stamp(self) -> float:
        return round(time.monotonic() - self._t0, 4)

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\r\n")
            self.transcript.append((self._stamp(), "<", line))
            self._lines.put(line)
        self._lines.put(None)  # EOF

    def send(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.transcript.append((self._stamp(), ">", line))
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def read_until(self, command: str, timeout_s: float) -> list[HubLine]:
        """Collect parsed lines until one whose command is ``command``; raise on timeout/EOF."""
        deadline = time.monotonic() + timeout_s
        collected: list[HubLine] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"no '{command}' within {timeout_s}s")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f"no '{command}' within {timeout_s}s") from exc
            if line is None:
                raise EOFError(f"engine closed stdout before '{command}'")
            parsed = parse_hub_line(line)
            if parsed is None:
                continue
            collected.append(parsed)
            if parsed.command == command:
                return collected

    def shutdown(self, quit_timeout_s: float) -> str:
        """quit -> wait -> terminate -> kill. Returns how the process ended."""
        if self.proc.poll() is not None:
            return f"already-exited(code={self.proc.returncode})"
        try:
            self.send("quit")
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=quit_timeout_s)
            return f"quit(code={self.proc.returncode})"
        except subprocess.TimeoutExpired:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=quit_timeout_s)
            return f"terminated(code={self.proc.returncode})"
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
            return f"killed(code={self.proc.returncode})"


# --------------------------------------------------------------------------- the PoC itself


@dataclass
class StepResult:
    step: str
    ok: bool
    detail: str = ""
    elapsed_s: float = 0.0


@dataclass
class PocReport:
    argv: list[str]
    position: str
    steps: list[StepResult] = field(default_factory=list)
    engine_id: dict[str, str] = field(default_factory=dict)
    engine_params: list[dict[str, str]] = field(default_factory=list)
    infos: list[dict[str, str]] = field(default_factory=list)
    done: dict[str, str] = field(default_factory=dict)
    termination: str = ""
    transcript: list[tuple[float, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(s.ok for s in self.steps)


def run_poc(
    argv: list[str],
    cwd: Path,
    position: str = INTERNATIONAL_START,
    set_params: dict[str, str] | None = None,
    move_time_s: float = 1.0,
    init_timeout_s: float = 180.0,
    search_timeout_s: float = 60.0,
    quit_timeout_s: float = 5.0,
) -> PocReport:
    report = PocReport(argv=argv, position=position)

    def step(name: str, fn) -> bool:  # type: ignore[no-untyped-def]
        t = time.monotonic()
        try:
            detail = fn() or ""
            report.steps.append(StepResult(name, True, detail, round(time.monotonic() - t, 4)))
            return True
        except Exception as exc:  # noqa: BLE001 - every failure must land in the report
            report.steps.append(
                StepResult(name, False, f"{type(exc).__name__}: {exc}", round(time.monotonic() - t, 4))
            )
            return False

    engine: EngineProcess | None = None

    def start() -> str:
        nonlocal engine
        engine = EngineProcess(argv, cwd)
        return f"pid={engine.proc.pid}"

    def identify() -> str:
        assert engine is not None
        engine.send("hub")
        lines = engine.read_until("wait", init_timeout_s)
        for ln in lines:
            if ln.command == "id":
                report.engine_id = ln.args
            elif ln.command == "param":
                report.engine_params.append(ln.args)
        if not report.engine_id:
            raise RuntimeError("engine sent no 'id' line")
        declared = {p.get("name") for p in report.engine_params}
        for name, value in (set_params or {}).items():
            if name not in declared:
                raise RuntimeError(f"engine does not declare parameter {name!r}")
            engine.send(f'set-param name={name} value="{value}"')
        engine.send("init")
        engine.read_until("ready", init_timeout_s)
        return f"{report.engine_id.get('name')} {report.engine_id.get('version')}"

    def send_position() -> str:
        assert engine is not None
        engine.send("new-game")
        engine.send(f"pos pos={position}")
        engine.send(f"level move-time={move_time_s}")
        return position

    def request_analysis() -> str:
        assert engine is not None
        engine.send("go analyze")
        return "go analyze"

    def receive() -> str:
        assert engine is not None
        lines = engine.read_until("done", move_time_s + search_timeout_s)
        report.infos = [ln.args for ln in lines if ln.command == "info"]
        report.done = lines[-1].args
        errors = [ln.args for ln in lines if ln.command == "error"]
        if errors:
            raise RuntimeError(f"engine reported errors: {errors}")
        return f"{len(report.infos)} info line(s); done={report.done}"

    def interpret() -> str:
        if "move" not in report.done:
            raise RuntimeError("'done' has no move")
        last = report.infos[-1] if report.infos else {}
        score = last.get("score")
        if score is not None:
            float(score)  # Scan reports score in "men" as a real number
        return f"move={report.done['move']} score={score} depth={last.get('depth')} pv={last.get('pv')!r}"

    def validate() -> str:
        problems = check_move(report.done["move"], position)
        if problems:
            raise RuntimeError("; ".join(problems))
        return "syntax + origin/destination/captured-square checks passed (not full legality: G2)"

    def terminate() -> str:
        assert engine is not None
        report.termination = engine.shutdown(quit_timeout_s)
        if report.termination not in ("quit(code=0)", "already-exited(code=0)"):
            raise RuntimeError(f"engine did not exit cleanly: {report.termination}")
        return report.termination

    try:
        for name, fn in [
            ("1-start", start),
            ("2-identify", identify),
            ("3-send-position", send_position),
            ("4-request-analysis", request_analysis),
            ("5-receive-result", receive),
            ("6-interpret-output", interpret),
            ("7-validate-move", validate),
        ]:
            if not step(name, fn):
                break
    finally:
        if engine is not None:
            if not any(s.step == "8-terminate" for s in report.steps):
                step("8-terminate", terminate)
            report.transcript = engine.transcript
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executable", required=True, type=Path)
    ap.add_argument("--arg", action="append", default=[], help="engine CLI argument (repeatable)")
    ap.add_argument("--cwd", type=Path, help="working dir (default: executable's folder)")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--position", default=INTERNATIONAL_START)
    ap.add_argument("--move-time", type=float, default=1.0)
    ap.add_argument("--init-timeout", type=float, default=180.0)
    ap.add_argument("--out", type=Path, help="write the JSON report here")
    ns = ap.parse_args(argv)
    ns.executable = ns.executable.resolve()  # the engine runs with its own folder as CWD

    if not ns.executable.is_file():
        print(f"BLOCKED: executable not found: {ns.executable}", file=sys.stderr)
        return 2
    params = dict(kv.split("=", 1) for kv in ns.set)
    cmd = [str(ns.executable), *ns.arg]
    if ns.executable.suffix == ".py":
        cmd = [sys.executable, *cmd]
    report = run_poc(
        cmd,
        ns.cwd or ns.executable.parent,
        position=ns.position,
        set_params=params,
        move_time_s=ns.move_time,
        init_timeout_s=ns.init_timeout,
    )
    data = asdict(report) | {"ok": report.ok}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if ns.out:
        ns.out.parent.mkdir(parents=True, exist_ok=True)
        ns.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
