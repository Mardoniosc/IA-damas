import json
import logging
from pathlib import Path

from damas_ai.config import Settings
from damas_ai.logging_config import JsonFormatter, configure_logging


def test_json_formatter_includes_context() -> None:
    record = logging.LogRecord("damas_ai.engine.io", logging.INFO, __file__, 1, "sent", None, None)
    record.ctx = {"engine": "scan", "line": "hub"}
    payload = json.loads(JsonFormatter().format(record))
    assert payload["logger"] == "damas_ai.engine.io"
    assert payload["msg"] == "sent"
    assert payload["ctx"] == {"engine": "scan", "line": "hub"}


def test_file_handler_writes_json_lines(tmp_path: Path) -> None:
    configure_logging(Settings(_env_file=None, log_dir=tmp_path, log_level="DEBUG"))
    log = logging.getLogger("damas_ai.test")
    log.debug("hello", extra={"ctx": {"k": 1}})
    for handler in logging.getLogger("damas_ai").handlers:
        handler.flush()
    lines = (tmp_path / "damas_ai.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["ctx"] == {"k": 1}
    # Release the file handle (Windows) by reconfiguring without a file handler.
    configure_logging(Settings(_env_file=None))
