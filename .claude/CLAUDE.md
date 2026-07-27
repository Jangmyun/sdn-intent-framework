# Repository Guidelines

## Project Structure & Module Organization

This repo holds two independent subsystems that must not be conflated. Both share the single repo-root `.env`.

**Pipeline app — repository root.** An End-to-End application turning natural-language intent into ONOS FlowRules (LLM/RAG, Digital Twin, XAI, Web UI). Entry points are `main.py` (CLI) and `api.py` (FastAPI + Web UI); its config loader is the root `config.py`. Application code lives in `models/` (IntentIR, topology) and `pipeline/stage1_intent` through `pipeline/stage6_deploy`; Web UI assets in `static/`, datasets in `data/`, helper scripts in `scripts/`. Tests live in `tests/`. GOLD-350 quantitative evaluation (Exp-1, treatments T-A~T-D) lives in `experiments/eval/`. Runtime output goes to the ignored `logs/`. Dependencies are pip-managed via `requirements.txt`. See `docs/PIPELINE_GUIDE.md` for full usage.

**Research track — `research/`, self-contained.** Paper reproducibility code. Core Python lives in `research/safe_intent_sdn/`; configuration models in `research/safe_intent_sdn/config.py`, durable run logging in `run_context.py`, and `schema.py` generates the JSON Schemas under `research/schemas/`. `research/main.py` is the minimal smoke entry point. Tests live in `research/tests/` and mirror application behavior rather than individual private helpers. Reproducible defaults and experiment overrides are in `research/config/default.toml` and `research/config/experiments/`. Operational scripts for ONOS, Mininet, installation, and smoke checks are under `research/scripts/`. Runtime output belongs in ignored directories such as `research/logs/runs/` and `research/logs/setup/`. Paper-facing experiments live in `research/experiments/{e1,e2,e3,gold}`, with figures/tables under `research/paper/`.

Do not confuse the root `config.py` (pipeline) with `research/safe_intent_sdn/config.py` (research), nor the root `tests/` with `research/tests/`.

## Build, Test, and Development Commands

Pipeline app — run from the repository root:

- `pip install -r requirements.txt`: install pipeline dependencies.
- `python main.py --intent "..."`: run the pipeline CLI.
- `uvicorn api:app --reload --port 8000`: serve the REST API and Web UI.
- `pytest -q tests`: run the pipeline test suite.

Research track — run from `research/`:

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
