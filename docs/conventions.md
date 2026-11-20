# Engineering conventions

Established in G1. Changes require an ADR when they affect more than one module.

## 1. Coding (Python backend)

- Python **3.11+**, `src/` layout, package `damas_ai`. Type hints on all public functions.
  Use `from __future__ import annotations`.
- Style: PEP 8, line length 100. Lint/format with **ruff** (config in `backend/pyproject.toml`).
  Ruff is configured but not installed yet (installing needs a package download), so it was
  not run in G1 or G2.
- Modules are added only when a gate needs them. No empty placeholder packages.
- Domain types are immutable (`frozen` dataclasses / Pydantic models) unless mutation is
  measured to matter (move generation in G2 may use mutable internals behind an immutable API).
- **No engine-specific type crosses the adapter boundary** (ADR-002). Engine output is
  translated into platform types in the adapter that received it.
- Errors: raise specific exception classes and never swallow exceptions silently. Engine
  failures are data (recorded in results), not crashes of the platform.
- Naming: `snake_case` modules/functions, `PascalCase` classes, `UPPER_CASE` constants.
  Rules vocabulary uses English names with the Brazilian term in the docstring
  (e.g. `majority_capture` = *lei da maioria*).

## 2. Testing

- **pytest**. Tests live in `backend/tests/` and mirror the package layout. PoC tests live in
  `scripts/poc/tests/`.
- TDD for the Rules Core: each rule clause from `rules-compatibility.md` gets at least one
  named test that cites the clause (`test_br_capture_majority_counts_men_and_kings_equally`).
- Reference data (perft counts, positions) is stored as versioned fixture files with their
  provenance (which tool, which version, which date). Values are never copied from memory.
- Tests that need a real engine binary carry `@pytest.mark.engine` and skip automatically when
  the engine is not configured. CI never depends on third-party binaries.
- Test doubles (e.g. `scripts/poc/mock_hub_engine.py`) are labelled as such in their
  docstring. Results obtained with doubles are never reported as engine evidence.
- Every gate report records the exact test command, the count of passed/failed/skipped tests
  and the date.

## 3. Configuration

- Process settings come from environment variables with prefix `DAMAS_` and an optional `.env`
  (template `config/.env.example`), loaded by `damas_ai.config.Settings` (pydantic-settings).
- Engines are declared in a TOML file referenced by `DAMAS_ENGINES_CONFIG`
  (template `config/engines.example.toml`). Machine-specific paths can be overridden per engine
  with `DAMAS_ENGINE_<ID>_EXECUTABLE`.
- **No hardcoded executable paths, no committed real config, no committed secrets.**
  `config/engines.toml`, `.env` and `engines/` are git-ignored.
- Every engine declaration must state `native_variant` explicitly. The platform never infers
  rule support.
- Loading config never fails because a binary is absent. Availability is checked explicitly
  (`EngineConfig.check_available()`) and reported.

## 4. Logging

- stdlib `logging`, configured once through `damas_ai.logging_config.configure_logging`.
- Logger names: `damas_ai.<area>[.<sub>]`, e.g. `damas_ai.rules`, `damas_ai.engine.lifecycle`,
  `damas_ai.engine.io`.
- Formats: `text` (console, humans) and `json` (one object per line, machines). File logs are
  always JSON lines (`<log_dir>/damas_ai.jsonl`, rotated at 10 MB x 5).
- Structured context goes in `extra={"ctx": {...}}`, never in string interpolation that hides
  fields.
- Levels:
  - `DEBUG`: raw engine I/O lines (`damas_ai.engine.io`) and search internals.
  - `INFO`: lifecycle (engine started/ready/stopped), experiment start/end.
  - `WARNING`: recoverable anomalies (engine timeout, unparseable line, retry).
  - `ERROR`: a failed operation the caller must handle.
- Never log secrets, tokens or personal data. Engine transcripts may be logged in full.
- Experiments (G12+) must log the config hash, engine versions and code revision for
  reproducibility.

## 5. Documentation and decisions

- Architecture decisions go in `docs/architecture/decisions/ADR-NNN.md` (context, decision,
  consequences, status).
- Every claim about an external engine cites evidence (file, URL and access date) or is marked
  **UNVERIFIED**.
