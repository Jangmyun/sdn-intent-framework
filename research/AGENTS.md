# Repository Guidelines

## Project Structure & Module Organization

Core Python code lives in `safe_intent_sdn/`. Configuration models and loading are in `config.py`; durable run logging is in `run_context.py`; `schema.py` generates the JSON Schemas under `schemas/`. The root `main.py` is the minimal application entry point.

Tests live in `tests/` and mirror application behavior rather than individual private helpers. Reproducible defaults and experiment overrides are stored in `config/default.toml` and `config/experiments/`. Operational scripts for ONOS, Mininet, installation, and smoke checks are under `scripts/`. Runtime output belongs in ignored directories such as `logs/runs/` and `logs/setup/`.

## Build, Test, and Development Commands

- `uv sync --locked`: install the Python 3.11 environment from `uv.lock`.
- `uv run python main.py`: load configuration and execute the application smoke entry point.
- `uv run pytest -q`: run the complete pytest suite.
- `uv run python -m safe_intent_sdn.schema`: regenerate committed JSON Schemas after changing Pydantic logging models.
- `./scripts/installation/doctor.sh --no-write`: inspect local SDN prerequisites without writing a report.
- `./scripts/onos.sh start` and `./scripts/smoke_test.sh`: start ONOS and validate Mininet/OVS connectivity.

## Coding Style & Naming Conventions

Use four-space indentation, type annotations, and `from __future__ import annotations` in Python modules. Follow standard Python naming: `snake_case` for functions and variables, `PascalCase` for models and classes, and uppercase names for constants. Keep public APIs small and prefer explicit keyword arguments for optional metrics or configuration. No formatter or linter is currently configured; keep changes PEP 8 compatible and run `git diff --check`.

## Testing Guidelines

Use pytest and name tests `test_<behavior>`. Store generated run data in pytest `tmp_path`, never in tracked log directories. Cover successful and failed lifecycle paths, secret redaction, schema compatibility, and concurrency when modifying logging. Regenerate schemas and run the full suite before submitting.

## Commit & Pull Request Guidelines

Use the existing Conventional Commit style: `feat:`, `fix:`, `test:`, `docs:`, `build:`, or `chore:`. Keep commits focused; separate implementation, tests, and documentation when practical.

Pull requests should include a concise summary, validation commands/results, and any schema or configuration changes. Link related issues when available. Screenshots are only necessary for visual output.

## Security & Configuration

Copy `.env.example` to `.env`; never commit real API keys, passwords, raw experiment logs, or generated network state. Keep reproducible non-secret values in TOML and secrets in `SAFE_SDN_*` environment variables.
