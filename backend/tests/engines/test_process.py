from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from damas_ai.engines.errors import EngineExited, EngineStartError, EngineTimeout
from damas_ai.engines.process import ProcessSupervisor

ECHO = (
    "import sys\n"
    "for line in sys.stdin:\n"
    "    line = line.strip()\n"
    "    if line == 'quit': break\n"
    "    if line == 'err': sys.stderr.write('oops\\n'); sys.stderr.flush(); continue\n"
    "    if line == 'die': sys.exit(5)\n"
    "    print('echo ' + line, flush=True)\n"
)
STUBBORN = "import time\nwhile True: time.sleep(1)\n"  # ignores quit and EOF


def sup(tmp_path: Path, code: str) -> ProcessSupervisor:
    s = ProcessSupervisor("t", [sys.executable, "-c", code], tmp_path)
    s.start()
    return s


def test_send_read_and_clean_quit(tmp_path: Path) -> None:
    s = sup(tmp_path, ECHO)
    s.send("hello")
    assert s.read_line(time.perf_counter() + 5) == "echo hello"
    assert s.shutdown("quit", 5) == "quit(code=0)"
    assert not s.running
    directions = [d for _, d, _ in s.transcript()]
    assert directions == [">", "<", ">"]


def test_deadline_expiry_raises_timeout(tmp_path: Path) -> None:
    s = sup(tmp_path, ECHO)
    t0 = time.perf_counter()
    with pytest.raises(EngineTimeout):
        s.read_line(time.perf_counter() + 0.3)
    assert time.perf_counter() - t0 < 2
    s.shutdown("quit", 5)


def test_process_exit_is_reported_and_sticky(tmp_path: Path) -> None:
    s = sup(tmp_path, ECHO)
    s.send("die")
    with pytest.raises(EngineExited):
        s.read_line(time.perf_counter() + 5)
    with pytest.raises(EngineExited):
        s.read_line(time.perf_counter() + 5)
    s.kill()
    assert s.exit_description == "already-exited(code=5)"
    with pytest.raises(EngineExited):
        s.send("x")


def test_stderr_goes_to_transcript_not_stdout(tmp_path: Path) -> None:
    s = sup(tmp_path, ECHO)
    s.send("err")
    s.send("after")
    assert s.read_line(time.perf_counter() + 5) == "echo after"
    time.sleep(0.2)
    assert ("!", "oops") in [(d, line) for _, d, line in s.transcript()]
    s.shutdown("quit", 5)


def test_shutdown_escalates_when_engine_ignores_quit_and_eof(tmp_path: Path) -> None:
    s = sup(tmp_path, STUBBORN)
    how = s.shutdown("quit", 0.5)
    assert how.startswith(("terminated", "killed"))
    assert not s.running


def test_transcript_since_mark(tmp_path: Path) -> None:
    s = sup(tmp_path, ECHO)
    s.send("a")
    s.read_line(time.perf_counter() + 5)
    mark = s.mark
    s.send("b")
    s.read_line(time.perf_counter() + 5)
    assert [line for _, _, line in s.transcript_since(mark)] == ["b", "echo b"]
    s.shutdown("quit", 5)


def test_unlaunchable_executable(tmp_path: Path) -> None:
    s = ProcessSupervisor("t", [str(tmp_path / "missing.exe")], tmp_path)
    with pytest.raises(EngineStartError):
        s.start()
