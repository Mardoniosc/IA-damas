"""HubEngine: EngineAdapter for Hub protocol v2 engines (Scan 3.1; Kingsrow hub pending Q3)."""

from __future__ import annotations

import logging
import threading
import time

from damas_ai.config import EngineConfig
from damas_ai.engines.base import EngineAdapter
from damas_ai.engines.errors import (
    CapabilityError,
    EngineExited,
    EngineNotRunning,
    EngineStartError,
    EngineTimeout,
)
from damas_ai.engines.hub import protocol as hub
from damas_ai.engines.hub.profiles import GENERIC, HubProfile, select_profile
from damas_ai.engines.process import ProcessSupervisor
from damas_ai.engines.types import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    EngineCapabilities,
    EngineInfo,
    SearchInfo,
    SearchLimit,
)
from damas_ai.rules import (
    EngineMoveError,
    Move,
    Position,
    apply_move,
    legal_moves,
    resolve_engine_move,
)

log = logging.getLogger("damas_ai.engine.lifecycle")


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class HubEngine(EngineAdapter):
    def __init__(self, config: EngineConfig) -> None:
        if config.protocol != "hub":
            raise ValueError(f"{config.id}: HubEngine needs protocol 'hub', got {config.protocol!r}")
        self.config = config
        self.engine_id = config.id
        self._sup: ProcessSupervisor | None = None
        self._info: EngineInfo | None = None
        self._profile: HubProfile = GENERIC
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- lifecycle

    @property
    def running(self) -> bool:
        return self._sup is not None and self._sup.running and self._info is not None

    @property
    def info(self) -> EngineInfo:
        if self._info is None:
            raise EngineNotRunning(f"{self.engine_id}: not started")
        return self._info

    @property
    def transcript(self):  # type: ignore[no-untyped-def]
        return self._sup.transcript() if self._sup else ()

    def start(self) -> EngineInfo:
        if self.running:
            return self.info
        cfg = self.config
        sup = ProcessSupervisor(cfg.id, [str(cfg.executable), *cfg.args], cfg.effective_working_dir,
                                env=dict(cfg.env) or None)
        sup.start()
        self._sup = sup
        try:
            self._info = self._handshake(sup)
        except (EngineTimeout, EngineExited, hub.HubSyntaxError, EngineStartError) as exc:
            how = sup.kill()
            tail = "\n".join(f"{d} {line}" for _, d, line in sup.transcript()[-15:])
            self._sup, self._info = None, None
            raise EngineStartError(f"{cfg.id}: handshake failed ({exc}); process {how}\n{tail}") from exc
        log.info("engine ready", extra={"ctx": {"engine": cfg.id, "name": self._info.name,
                                                 "version": self._info.version,
                                                 "profile": self._info.profile}})
        return self._info

    def _handshake(self, sup: ProcessSupervisor) -> EngineInfo:
        deadline = time.perf_counter() + self.config.init_timeout_s
        sup.send("hub")
        ident: dict[str, str] | None = None
        params: list[dict[str, str]] = []
        while True:
            msg = hub.parse_line(sup.read_line(deadline))
            if msg is None:
                continue
            if msg.command == "id":
                ident = msg.args
            elif msg.command == "param":
                params.append(msg.args)
            elif msg.command == "wait":
                break
        if ident is None:
            raise EngineStartError("engine sent no 'id' line")
        declared = {p.get("name") for p in params}
        for name, value in self.config.params.items():
            if name not in declared:
                raise EngineStartError(f"parameter {name!r} is not declared by the engine "
                                       f"(declared: {sorted(n for n in declared if n)})")
            sup.send(hub.format_line("set-param", name=name, value=value))
        sup.send("init")
        while True:
            msg = hub.parse_line(sup.read_line(deadline))
            if msg is not None and msg.command == "ready":
                break  # everything else during init is informational and ignored (spec)
        self._profile = select_profile(ident.get("name", ""))
        return EngineInfo(
            name=ident.get("name", ""),
            version=ident.get("version", ""),
            author=ident.get("author", ""),
            declared_params=tuple(params),
            profile=self._profile.name,
        )

    def close(self) -> str:
        with self._lock:
            if self._sup is None:
                return "not-running"
            how = self._sup.shutdown("quit", self.config.quit_timeout_s)
            self._info = None
            return how

    def restart(self) -> EngineInfo:
        """Replace a dead or killed process with a fresh one (new handshake)."""
        self.close()
        return self.start()

    def new_game(self) -> None:
        self._require_running().send("new-game")

    def ping(self, timeout_s: float = 5.0) -> float:
        """Round-trip time of ping/pong in seconds (only valid between searches)."""
        with self._lock:
            sup = self._require_running()
            t0 = time.perf_counter()
            sup.send("ping")
            deadline = t0 + timeout_s
            while True:
                msg = hub.parse_line(sup.read_line(deadline))
                if msg is not None and msg.command == "pong":
                    return time.perf_counter() - t0

    def capabilities(self) -> EngineCapabilities:
        p = self._profile
        return EngineCapabilities(
            native_variants=frozenset({self.config.native_variant}),
            limits=p.limits,
            multipv=False,  # not in Hub v2 (G1 SCAN report)
            ponder=p.ponder,
            reports_pv=True,
            score_unit=p.score_unit,
        )

    def _require_running(self) -> ProcessSupervisor:
        if self._sup is None or not self._sup.running or self._info is None:
            raise EngineNotRunning(f"{self.engine_id}: engine is not running")
        return self._sup

    # ---------------------------------------------------------------- analysis

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        caps = self.capabilities()
        if request.ruleset.variant not in caps.native_variants:
            raise CapabilityError(
                f"{self.engine_id} plays {sorted(caps.native_variants)}, not {request.ruleset.variant}"
            )
        if request.limit.kind not in caps.limits:
            raise CapabilityError(f"{self.engine_id} does not support {request.limit.kind.value} limits")
        if not request.state.legal_moves():
            raise ValueError("cannot analyse a terminal position (Hub spec)")
        with self._lock:
            sup = self._require_running()
            return self._search(sup, request)

    def _level_line(self, limit: SearchLimit) -> str:
        if limit.depth is not None:
            return hub.format_line("level", depth=limit.depth)
        if limit.nodes is not None:
            return hub.format_line("level", nodes=limit.nodes)
        return hub.format_line("level", move_time=limit.move_time_s)  # type: ignore[arg-type]

    def _search(self, sup: ProcessSupervisor, request: AnalysisRequest) -> AnalysisResult:
        geometry = request.root.geometry
        sup.drain()  # discard stray output from earlier interactions
        mark = sup.mark
        t0 = time.perf_counter()
        violations: list[str] = []
        lines: list[hub.HubMessage] = []
        interrupted = False
        status: AnalysisStatus | None = None

        pos_args = {"pos": hub.encode_position(request.root)}
        if request.moves:
            history, p = [], request.root
            for m in request.moves:
                history.append(hub.format_move(geometry, m))
                p = apply_move(p, m)
            pos_args["moves"] = " ".join(history)
        sup.send(hub.format_line("pos", **pos_args))
        sup.send(self._level_line(request.limit))
        sup.send(f"go {request.mode}")

        budget = (request.limit.move_time_s or 0.0) + self.config.search_timeout_s
        deadline = t0 + budget
        done: hub.HubMessage | None = None
        while done is None:
            try:
                raw = sup.read_line(deadline)
            except EngineTimeout:
                if interrupted:
                    sup.kill()
                    status = AnalysisStatus.TIMEOUT
                    violations.append(f"no 'done' within {self.config.stop_grace_s}s after 'stop'")
                    break
                interrupted = True
                violations.append(f"search exceeded {budget:.1f}s; sent 'stop'")
                try:
                    sup.send("stop")
                except EngineExited:
                    status = AnalysisStatus.CRASHED
                    break
                deadline = time.perf_counter() + self.config.stop_grace_s
                continue
            except EngineExited:
                status = AnalysisStatus.CRASHED
                violations.append(f"engine exited during search ({sup.kill()})")
                break
            try:
                msg = hub.parse_line(raw)
            except hub.HubSyntaxError as exc:
                violations.append(str(exc))
                continue
            if msg is None:
                continue
            if msg.command == "done":
                done = msg
            elif msg.command in ("info", "error"):
                lines.append(msg)
                if msg.command == "error":
                    violations.append(f"engine error: {msg.get('message', msg.raw)}")
            elif msg.command == "pong":
                continue
            # anything else: ignored per spec

        position = request.position
        infos = tuple(self._info_from(msg, position, violations) for msg in lines if msg.command == "info")
        best: Move | None = None
        ponder: Move | None = None
        best_text = done.get("move") if done is not None else None
        if status is None:
            if best_text is None:
                status = AnalysisStatus.PROTOCOL_ERROR
                violations.append("'done' without a move")
            else:
                best, status = self._resolve(position, best_text, violations)
                ponder_text = done.get("ponder") if done is not None else None
                if best is not None and ponder_text:
                    after = apply_move(position, best)
                    if legal_moves(after):
                        ponder, _ = self._resolve(after, ponder_text, violations, "ponder")
        info = self.info if self._info is not None else EngineInfo("", "")
        return AnalysisResult(
            engine_id=self.engine_id,
            engine_name=info.name,
            engine_version=info.version,
            variant=request.ruleset.variant,
            position_dsa=position.to_dsa(),
            limit=request.limit,
            status=status,
            best_move=best,
            best_move_text=best_text,
            ponder_move=ponder,
            infos=infos,
            interrupted=interrupted,
            elapsed_s=round(time.perf_counter() - t0, 4),
            violations=tuple(violations),
            transcript=sup.transcript_since(mark),
        )

    def _resolve(self, position: Position, text: str, violations: list[str],
                 what: str = "move") -> tuple[Move | None, AnalysisStatus]:
        try:
            report = hub.parse_move(position.geometry, text)
        except (hub.HubSyntaxError, ValueError) as exc:
            violations.append(f"{what} {text!r}: {exc}")
            return None, AnalysisStatus.PROTOCOL_ERROR
        captured = report.captured
        if captured is None:
            violations.append(f"{what} {text!r}: capture without captured squares (non-standard Hub)")
        try:
            move = resolve_engine_move(position, report.origin, report.destination, captured)
        except EngineMoveError as exc:
            violations.append(f"{what} {text!r} rejected by Rules Core: {exc}")
            return None, AnalysisStatus.ILLEGAL_MOVE
        return move, AnalysisStatus.OK

    def _info_from(self, msg: hub.HubMessage, position: Position, violations: list[str]) -> SearchInfo:
        pv_text = msg.get("pv", "") or ""
        pv: list[Move] = []
        p = position
        for k, token in enumerate(pv_text.split()):
            if not legal_moves(p):
                violations.append(f"pv continues after a terminal position at move {k + 1}")
                break
            move, _ = self._resolve(p, token, [], "pv")
            if move is None:
                violations.append(f"pv move {k + 1} ({token}) not legal; pv truncated")
                break
            pv.append(move)
            p = apply_move(p, move)
        score_text = msg.get("score")
        return SearchInfo(
            depth=_int(msg.get("depth")),
            score=self._profile.classify_score(score_text) if score_text is not None else None,
            nodes=_int(msg.get("nodes")),
            time_s=_float(msg.get("time")),
            pv_text=pv_text,
            pv=tuple(pv),
            raw=dict(msg.args),
        )
