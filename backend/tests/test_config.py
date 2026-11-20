from pathlib import Path

import pytest

from damas_ai.config import EngineConfigError, Settings, load_engine_configs

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_settings_read_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAMAS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DAMAS_LOG_FORMAT", "json")
    settings = Settings(_env_file=None)
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "json"
    assert settings.engines_config is None


def test_example_engine_config_is_valid_and_declares_native_variants() -> None:
    engines = load_engine_configs(REPO_ROOT / "config" / "engines.example.toml", environ={})
    assert set(engines) == {"scan", "kingsrow_intl_hub", "kingsrow_english"}
    scan = engines["scan"]
    assert scan.protocol == "hub"
    assert scan.args == ("hub",)
    assert scan.params == {"variant": "normal", "book": "false"}
    # G1 finding encoded in the example: nothing claims Brazilian support.
    assert all("brazilian" not in e.native_variant for e in engines.values())
    # Placeholder paths are reported as unavailable instead of failing the load.
    assert scan.check_available()


def test_env_override_replaces_executable(tmp_path: Path) -> None:
    exe = tmp_path / "engine.exe"
    exe.write_bytes(b"")
    cfg = tmp_path / "engines.toml"
    cfg.write_text(
        '[engines.scan]\nprotocol = "hub"\nnative_variant = "international-10x10"\n',
        encoding="utf-8",
    )
    engines = load_engine_configs(cfg, environ={"DAMAS_ENGINE_SCAN_EXECUTABLE": str(exe)})
    assert engines["scan"].executable == exe
    assert engines["scan"].effective_working_dir == tmp_path
    assert engines["scan"].check_available() == []


def test_missing_executable_is_a_clear_error(tmp_path: Path) -> None:
    cfg = tmp_path / "engines.toml"
    cfg.write_text('[engines.x]\nprotocol = "hub"\nnative_variant = "v"\n', encoding="utf-8")
    with pytest.raises(EngineConfigError, match="DAMAS_ENGINE_X_EXECUTABLE"):
        load_engine_configs(cfg, environ={})


def test_unknown_keys_and_protocols_are_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / "engines.toml"
    cfg.write_text(
        '[engines.x]\nprotocol = "uci"\nexecutable = "a"\nnative_variant = "v"\n',
        encoding="utf-8",
    )
    with pytest.raises(EngineConfigError, match="invalid"):
        load_engine_configs(cfg, environ={})


def test_bool_params_are_stringified_for_text_protocols(tmp_path: Path) -> None:
    cfg = tmp_path / "engines.toml"
    cfg.write_text(
        '[engines.x]\nprotocol = "hub"\nexecutable = "a"\nnative_variant = "v"\n'
        "[engines.x.params]\nbook = false\nthreads = 2\n",
        encoding="utf-8",
    )
    assert load_engine_configs(cfg, environ={})["x"].params == {"book": "false", "threads": "2"}
