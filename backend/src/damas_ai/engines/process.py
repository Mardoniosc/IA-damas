"""ProcessSupervisor: one engine OS process with line I/O, deadlines and shutdown escalation.

Shutdown escalation: send the quit command, close stdin (the Hub spec requires the engine to
exit on EOF), wait; then terminate, wait; then kill.
"""

from __future__ import annotations

import collections
import logging
import os
import queue
import subprocess
import threading
import time
from collections.abc import Sequence
from pathlib import Path

from damas_ai.engines.errors import EngineExited, EngineStartError, EngineTimeout
from damas_ai.engines.types import TranscriptLine

io_log = logging.getLogger("damas_ai.engine.io")
life_log = logging.getLogger("damas_ai.engine.lifecycle")

_EOF = object()


class ProcessSupervisor:
    def __init__(
        self,
        engine_id: str,
        argv: Sequence[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        transcript_limit: int = 20_000,
    ) -> None:
        self.engine_id = engine_id
        self.argv = list(argv)
        self.cwd = cwd
        self.env = env
        self._transcript: collections.deque[TranscriptLine] = collections.deque(maxlen=transcript_limit)
        self._seq = 0  # total lines ever recorded (for slicing a bounded transcript)
        self._lock = threading.Lock()
        self._lines: queue.Queue[object] = queue.Queue()
        self._proc: subprocess.Popen[str] | None = None
        self._t0 = 0.0
        self.exit_description: str | None = None

    # ---------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._proc is not None:
            raise EngineStartError(f"{self.engine_id}: already started")
        full_env = {**os.environ, **self.env} if self.env else None
        try:
            self._proc = subprocess.Popen(
                self.argv,
                cwd=str(self.cwd),
                env=full_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise EngineStartError(f"{self.engine_id}: cannot launch {self.argv[0]}: {exc}") from exc
        self._t0 = time.perf_counter()
        threading.Thread(target=self._pump_stdout, daemon=True, name=f"{self.engine_id}-stdout").start()
        threading.Thread(target=self._pump_stderr, daemon=True, name=f"{self.engine_id}-stderr").start()
        life_log.info("engine started", extra={"ctx": {"engine": self.engine_id, "pid": self._proc.pid,
                                                        "argv": self.argv, "cwd": str(self.cwd)}})

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def shutdown(self, quit_command: str | None, timeout_s: float) -> str:
        """Stop the process; returns how it ended (also stored in ``exit_description``)."""
        proc = self._proc
        if proc is None:
            return "never-started"
        if self.exit_description is not None and proc.poll() is not None:
            return self.exit_description
        if proc.poll() is not None:
            outcome = f"already-exited(code={proc.returncode})"
        else:
            if quit_command:
                try:
                    self.send(quit_command)
                except EngineExited:
                    pass
            self._close_stdin()
            try:
                proc.wait(timeout=timeout_s)
                outcome = f"quit(code={proc.returncode})"
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=timeout_s)
                    outcome = f"terminated(code={proc.returncode})"
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    outcome = f"killed(code={proc.returncode})"
        self.exit_description = outcome
        life_log.info("engine stopped", extra={"ctx": {"engine": self.engine_id, "how": outcome}})
        return outcome

    def kill(self) -> str:
        proc = self._proc
        if proc is None:
            return "never-started"
        if proc.poll() is None:
            try:  # it may be exiting already (stdout closed, not yet reaped)
                proc.wait(timeout=0.2)
                self.exit_description = f"already-exited(code={proc.returncode})"
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.exit_description = f"killed(code={proc.returncode})"
        elif self.exit_description is None:
            self.exit_description = f"already-exited(code={proc.returncode})"
        life_log.warning("engine killed", extra={"ctx": {"engine": self.engine_id,
                                                          "how": self.exit_description}})
        return self.exit_description

    # ---------------------------------------------------------------- I/O

    def send(self, line: str) -> None:
        if self._proc is None or self._proc.stdin is None or self._proc.poll() is not None:
            raise EngineExited(f"{self.engine_id}: process is not running")
        self._record(">", line)
        try:
            self._proc.stdin.write(line + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise EngineExited(f"{self.engine_id}: write failed: {exc}") from exc

    def read_line(self, deadline: float) -> str:
        """Next stdout line; ``deadline`` is a ``time.perf_counter()`` value."""
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise EngineTimeout(f"{self.engine_id}: deadline expired")
        try:
            item = self._lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise EngineTimeout(f"{self.engine_id}: no output before deadline") from exc
        if item is _EOF:
            self._lines.put(_EOF)  # keep EOF sticky for later readers
            raise EngineExited(f"{self.engine_id}: engine closed its output")
        assert isinstance(item, str)
        return item

    def drain(self) -> list[str]:
        """Discard and return any buffered stdout lines (e.g. stale output after a stop)."""
        out: list[str] = []
        while True:
            try:
                item = self._lines.get_nowait()
            except queue.Empty:
                return out
            if item is _EOF:
                self._lines.put(_EOF)
                return out
            assert isinstance(item, str)
            out.append(item)

    # ---------------------------------------------------------------- transcript

    @property
    def mark(self) -> int:
        """Opaque position in the transcript, for ``transcript_since``."""
        with self._lock:
            return self._seq

    def transcript_since(self, mark: int) -> tuple[TranscriptLine, ...]:
        with self._lock:
            n_new = self._seq - mark
            items = list(self._transcript)
        return tuple(items[-n_new:]) if n_new > 0 else ()

    def transcript(self) -> tuple[TranscriptLine, ...]:
        with self._lock:
            return tuple(self._transcript)

    # ---------------------------------------------------------------- internals

    def _record(self, direction: str, line: str) -> None:
        stamp = round(time.perf_counter() - self._t0, 4)
        with self._lock:
            self._transcript.append((stamp, direction, line))
            self._seq += 1
        io_log.debug("%s %s", direction, line, extra={"ctx": {"engine": self.engine_id}})

    def _pump_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for raw in self._proc.stdout:
            line = raw.rstrip("\r\n")
            self._record("<", line)
            self._lines.put(line)
        self._lines.put(_EOF)

    def _pump_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for raw in self._proc.stderr:
            self._record("!", raw.rstrip("\r\n"))

    def _close_stdin(self) -> None:
        if self._proc is not None and self._proc.stdin is not None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
