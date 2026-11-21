"""The internal engine as a Hub v2 engine process (ADR-010):

    python -m damas_ai.search.hub

Speaking the same protocol as Scan/Kingsrow lets the platform treat it like any external
engine: own OS process, pool, conformance, consensus, adaptive analysis. Position strings use
the geometry of the ``variant`` parameter (33 chars for Brazilian 8x8, 51 for International).
"""

from __future__ import annotations

import sys
import threading

import damas_ai
from damas_ai.engines.hub import protocol as hub
from damas_ai.rules import BRAZILIAN_PROVISIONAL, INTERNATIONAL_PROVISIONAL, Position, apply_move
from damas_ai.rules.resolve import EngineMoveError, resolve_engine_move
from damas_ai.rules.zobrist import zobrist_key
from damas_ai.search.searcher import DepthInfo, Searcher, score_to_men

VARIANTS = {"brazilian": BRAZILIAN_PROVISIONAL, "international": INTERNATIONAL_PROVISIONAL}
ENGINE_NAME = "DamasAI"

_out_lock = threading.Lock()


def emit(line: str) -> None:
    with _out_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


class HubServer:
    def __init__(self) -> None:
        self.params = {"variant": "brazilian", "tt-entries": str(1 << 20), "eval-model": ""}
        self.searcher: Searcher | None = None
        self.position: Position | None = None
        self.history: tuple[int, ...] = ()
        self.limit: dict[str, str] = {"move-time": "1"}
        self.stop = threading.Event()
        self.worker: threading.Thread | None = None

    @property
    def ruleset(self):  # type: ignore[no-untyped-def]
        return VARIANTS[self.params["variant"]]

    def handle(self, msg: hub.HubMessage) -> bool:
        """Process one command; returns False to quit."""
        c, a = msg.command, msg.args
        if c == "hub":
            emit(hub.format_line("id", name=ENGINE_NAME, version=damas_ai.__version__,
                                 author="Damas Super AI", country="Brazil"))
            emit(hub.format_line("param", name="variant", value=self.params["variant"],
                                 type="enum", values="brazilian international"))
            emit(hub.format_line("param", name="tt-entries", value=self.params["tt-entries"],
                                 type="int", min=1024, max=1 << 24))
            emit(hub.format_line("param", name="eval-model", value=self.params["eval-model"],
                                 type="string"))  # G14: path to a learned linear model (JSON)
            emit("wait")
        elif c == "set-param":
            name, value = a.get("name", ""), a.get("value", "")
            if name == "variant" and value not in VARIANTS:
                emit(hub.format_line("error", message=f"unknown variant {value}"))
            elif name in self.params:
                self.params[name] = value
        elif c == "init":
            evaluator = None
            if self.params["eval-model"]:
                from pathlib import Path

                from damas_ai.learning.evaluator import load_evaluator

                try:
                    evaluator = load_evaluator(Path(self.params["eval-model"]))
                except (OSError, ValueError, KeyError) as exc:
                    emit(hub.format_line("error", message=f"eval-model: {exc}"))
            self.searcher = Searcher(int(self.params["tt-entries"]), evaluator)
            emit("ready")
        elif c == "new-game":
            if self.searcher:
                self.searcher.clear()
        elif c == "ping":
            emit("pong")
        elif c == "pos":
            self._set_position(a)
        elif c == "level":
            self.limit = dict(a)
        elif c == "go":
            self._go()
        elif c == "stop":
            self.stop.set()
        elif c == "quit":
            self.stop.set()
            return False
        return True

    def _set_position(self, a: dict[str, str]) -> None:
        geometry = self.ruleset.geometry
        try:
            pos = hub.decode_position(geometry, a.get("pos", ""))
            keys = [zobrist_key(pos)]
            for text in a.get("moves", "").split():
                report = hub.parse_move(geometry, text)
                move = resolve_engine_move(pos, report.origin, report.destination, report.captured)
                pos = apply_move(pos, move)
                keys.append(zobrist_key(pos))
        except (hub.HubSyntaxError, EngineMoveError, ValueError) as exc:
            emit(hub.format_line("error", message=f"bad pos: {exc}"))
            self.position = None
            return
        self.position, self.history = pos, tuple(keys)

    def _go(self) -> None:
        if self.position is None or self.searcher is None:
            emit(hub.format_line("error", message="go without valid pos/init"))
            return
        if self.worker is not None and self.worker.is_alive():
            emit(hub.format_line("error", message="search already running"))
            return
        self.stop.clear()
        limit = self.limit
        depth = int(limit["depth"]) if "depth" in limit else None
        nodes = int(limit["nodes"]) if "nodes" in limit else None
        move_time = float(limit["move-time"]) if "move-time" in limit else None
        if "infinite" in limit:
            depth = nodes = move_time = None
        if depth is None and nodes is None and move_time is None and "infinite" not in limit:
            move_time = 1.0
        position, history, searcher = self.position, self.history, self.searcher
        geometry = position.geometry

        def on_depth(info: DepthInfo) -> None:
            nps = info.nodes / info.time_s / 1e6 if info.time_s > 0 else 0.0
            args = {"depth": info.depth, "score": score_to_men(info.score), "nodes": info.nodes,
                    "time": f"{info.time_s:.3f}", "nps": f"{nps:.3f}"}
            if info.pv:
                args["pv"] = " ".join(hub.format_move(geometry, m) for m in info.pv)
            emit(hub.format_line("info", **args))

        def run() -> None:
            out = searcher.search(position, history, depth, nodes, move_time, self.stop, on_depth)
            if out.best_move is None:
                emit(hub.format_line("error", message="no legal moves"))
                return
            done = {"move": hub.format_move(geometry, out.best_move)}
            if len(out.pv) > 1:
                done["ponder"] = hub.format_move(apply_move(position, out.best_move).geometry, out.pv[1])
            emit(hub.format_line("done", **done))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()


def main() -> int:
    server = HubServer()
    for raw in sys.stdin:  # EOF -> quit (Hub spec)
        try:
            msg = hub.parse_line(raw)
        except hub.HubSyntaxError as exc:
            emit(hub.format_line("error", message=str(exc)))
            continue
        if msg is not None and not server.handle(msg):
            break
    server.stop.set()
    if server.worker is not None:
        server.worker.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
