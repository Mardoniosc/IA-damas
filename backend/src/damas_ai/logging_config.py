"""Logging standard (docs/conventions/logging.md).

- stdlib ``logging`` only; loggers are named ``damas_ai.<area>`` (e.g. ``damas_ai.engine.io``).
- ``text`` format for humans, ``json`` (one object per line) for machines/experiments.
- Structured context is passed with ``extra={"ctx": {...}}`` and rendered in both formats.
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from damas_ai.config import Settings

ROOT_LOGGER = "damas_ai"


class JsonFormatter(logging.Formatter):
    """Minimal dependency-free JSON-lines formatter."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        ctx = getattr(record, "ctx", None)
        if isinstance(ctx, dict):
            payload["ctx"] = ctx
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        ctx = getattr(record, "ctx", None)
        if isinstance(ctx, dict) and ctx:
            base += " | " + " ".join(f"{k}={v}" for k, v in ctx.items())
        return base


def configure_logging(settings: Settings) -> None:
    """Configure the ``damas_ai`` logger tree. Safe to call more than once."""
    formatter = "json" if settings.log_format == "json" else "text"
    handlers: dict[str, dict[str, Any]] = {
        "console": {"class": "logging.StreamHandler", "formatter": formatter},
    }
    if settings.log_dir is not None:
        Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",  # files are always machine-readable
            "filename": str(Path(settings.log_dir) / "damas_ai.jsonl"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "text": {"()": TextFormatter},
                "json": {"()": JsonFormatter},
            },
            "handlers": handlers,
            "loggers": {
                ROOT_LOGGER: {
                    "level": settings.log_level,
                    "handlers": list(handlers),
                    "propagate": False,
                }
            },
        }
    )
