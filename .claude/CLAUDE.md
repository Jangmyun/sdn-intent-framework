# Repository Guidelines

## Project Structure & Module Organization

This repo holds two independent subsystems that must not be conflated. Both share the single repo-root `.env`.

**Pipeline app — repository root.** An End-to-End application turning natural-language intent into ONOS FlowRules (LLM/RAG, Digital Twin, XAI, Web UI). All code is a real installable package under `src/xai_pipeline/` (editable-installed by `uv sync` — no `sys.path` hacks anywhere; every internal import is `from xai_pipeline...`). Its config loader is `src/xai_pipeline/config.py`, whose `BASE_DIR` is `Path.cwd()` — commands must be run from the repository root, since that's where `.env`, `data/`, `logs/`, `results/` live (package-shipped assets like `static/` instead resolve relative to `__file__`, inside the package). The root `main.py` and `evaluate.py` are thin wrappers (`from xai_pipeline.main import main`, etc.) kept for `uv run python main.py` convenience; `api.py` has no root wrapper — run it via `uv run uvicorn xai_pipeline.api:app`. Application code: `src/xai_pipeline/models/` (IntentIR, topology) and `src/xai_pipeline/pipeline/stage1_intent` through `stage6_deploy`; Web UI assets in `src/xai_pipeline/static/`. Datasets in `data/`, helper scripts in `scripts/`, tests in `tests/` (import `xai_pipeline.*` directly — no path setup needed). GOLD-350 quantitative evaluation (Exp-1, treatments T-A~T-D) lives in `research/experiments/eval/` — it sits under `research/` for topical grouping but is a *pipeline-app* consumer: it imports `xai_pipeline`, so run it from the repository root in the root uv environment (`uv run python research/experiments/eval/run_exp1.py ...`), not from `research/`. Runtime output goes to the ignored `logs/`. Dependencies are uv-managed via the root `pyproject.toml` (hatchling build backend) — a separate uv project from `research/`, with its own lockfile and `.venv`. See `docs/PIPELINE_GUIDE.md` for full usage.

**Research track — `research/`, self-contained.** Paper reproducibility code. Core Python lives in `research/safe_intent_sdn/`; configuration models in `research/safe_intent_sdn/config.py`, durable run logging in `run_context.py`, and `schema.py` generates the JSON Schemas under `research/schemas/`. `research/main.py` is the minimal smoke entry point. Tests live in `research/tests/` and mirror application behavior rather than individual private helpers. Reproducible defaults and experiment overrides are in `research/config/default.toml` and `research/config/experiments/`. Operational scripts for ONOS, Mininet, installation, and smoke checks are under `research/scripts/`. Runtime output belongs in ignored directories such as `research/logs/runs/` and `research/logs/setup/`. Paper-facing experiments live in `research/experiments/{e1,e2,e3,gold}`, with figures/tables under `research/paper/`.

Do not confuse `src/xai_pipeline/config.py` (pipeline) with `research/safe_intent_sdn/config.py` (research), nor the root `tests/` with `research/tests/`.

## Build, Test, and Development Commands

Pipeline app — run from the repository root:

- `uv sync`: install the Python 3.11 environment, editable-install `xai_pipeline`, and install pipeline dependencies (add `--group reports` for `python-pptx`).
- `uv run python main.py --intent "..."`: run the pipeline CLI (or `uv run xai-pipeline --intent "..."` via the console-script entry point).
- `uv run uvicorn xai_pipeline.api:app --reload --port 8000`: serve the REST API and Web UI.
- `uv run pytest -q`: run the pipeline test suite.

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
