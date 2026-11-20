"""Externalized configuration (standard defined in docs/conventions/configuration.md).

Two layers:

1. ``Settings`` - process-wide settings from environment variables (prefix ``DAMAS_``)
   and an optional ``.env`` file.
2. Engine definitions - a TOML file (``config/engines.toml``, never committed) whose path
   is given by ``DAMAS_ENGINES_CONFIG``. Executable paths may be overridden per engine with
   ``DAMAS_ENGINE_<ID>_EXECUTABLE`` so machine-specific paths never live in the repository.

Nothing here hardcodes an executable path, and loading a config never fails just because an
executable is missing: availability is checked explicitly with ``EngineConfig.check_available``.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EngineProtocol = Literal["hub", "cb-dll", "dxp"]


class Settings(BaseSettings):
    """Process-wide settings. Every field can be set with ``DAMAS_<FIELD_NAME>``."""

    model_config = SettingsConfigDict(env_prefix="DAMAS_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "ci"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    log_dir: Path | None = None
    engines_config: Path | None = None
    # Max sum of engine search threads running at once (None = os.cpu_count()).
    engine_thread_budget: int | None = None
    # Knowledge base (G11). SQLite by default (local-first); PostgreSQL via a postgresql+... URL.
    database_url: str | None = None


class EngineConfig(BaseModel):
    """Declarative description of one external engine process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    enabled: bool = True
    protocol: EngineProtocol
    executable: Path
    args: tuple[str, ...] = ()
    working_dir: Path | None = None
    # What the engine natively plays, e.g. "international-10x10". Must be stated explicitly:
    # the platform never assumes an engine supports Brazilian 8x8 (see rules-compatibility.md).
    native_variant: str
    params: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)  # extra environment variables
    init_timeout_s: float = Field(default=120.0, gt=0)
    # Extra time allowed beyond the search limit before 'stop' is sent.
    search_timeout_s: float = Field(default=60.0, gt=0)
    # After 'stop', how long to wait for the mandatory 'done' before killing the process.
    stop_grace_s: float = Field(default=5.0, gt=0)
    quit_timeout_s: float = Field(default=5.0, gt=0)

    @field_validator("params", mode="before")
    @classmethod
    def _stringify_params(cls, value: object) -> object:
        # Protocols such as Hub transmit every parameter as text.
        if isinstance(value, Mapping):
            return {str(k): str(v).lower() if isinstance(v, bool) else str(v) for k, v in value.items()}
        return value

    @property
    def effective_working_dir(self) -> Path:
        """Engines such as Scan load ``scan.ini`` and ``data/`` relative to the CWD."""
        return self.working_dir if self.working_dir is not None else self.executable.parent

    def check_available(self) -> list[str]:
        """Return human-readable problems; an empty list means the engine can be launched."""
        problems: list[str] = []
        if not self.executable.is_file():
            problems.append(f"executable not found: {self.executable}")
        if not self.effective_working_dir.is_dir():
            problems.append(f"working directory not found: {self.effective_working_dir}")
        return problems


class EngineConfigError(ValueError):
    """Raised when the engines TOML file is malformed."""


def _env_override_key(engine_id: str) -> str:
    return f"DAMAS_ENGINE_{engine_id.upper().replace('-', '_')}_EXECUTABLE"


def load_engine_configs(
    path: Path, environ: Mapping[str, str] | None = None
) -> dict[str, EngineConfig]:
    """Load ``[engines.<id>]`` tables from a TOML file, applying per-engine env overrides."""
    env = os.environ if environ is None else environ
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EngineConfigError(f"engines config not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise EngineConfigError(f"invalid TOML in {path}: {exc}") from exc

    engines = raw.get("engines", {})
    if not isinstance(engines, dict):
        raise EngineConfigError("'engines' must be a table of [engines.<id>] sections")

    result: dict[str, EngineConfig] = {}
    for engine_id, table in engines.items():
        if not isinstance(table, dict):
            raise EngineConfigError(f"[engines.{engine_id}] must be a table")
        data = {**table, "id": engine_id}
        override = env.get(_env_override_key(engine_id))
        if override:
            data["executable"] = override
        if "executable" not in data:
            raise EngineConfigError(
                f"[engines.{engine_id}] has no 'executable'; set it in the file or via "
                f"{_env_override_key(engine_id)}"
            )
        try:
            result[engine_id] = EngineConfig.model_validate(data)
        except ValueError as exc:
            raise EngineConfigError(f"[engines.{engine_id}] is invalid: {exc}") from exc
    return result
