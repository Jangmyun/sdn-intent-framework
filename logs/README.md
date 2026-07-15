# Runtime Logs

Each experiment is stored under `logs/runs/YYYYMMDD/<run_id>/` with:

- `manifest.json`: reproducibility metadata and artifact references
- `events.jsonl`: append-only structured events
- `artifacts/`: intent, IR, validation, policy, twin, repair, and report payloads

Raw run data is ignored by Git. JSON Schemas in `schemas/` and sanitized examples may be committed. Failed runs are retained with `status: failed`.

## Basic Usage

```python
from safe_intent_sdn import create_run_context, load_settings

settings = load_settings()
with create_run_context(settings, intent_id="intent-001") as run:
    run.log_event("intent_received", stage="ingestion", source="cli")
    run.save_artifact("input_intent", "allow h1 to reach h2")

    with run.stage("translation"):
        generated_ir = {"source": "h1", "destination": "h2"}
        run.save_artifact("generated_ir", generated_ir)

    run.finish(
        "APPROVE",
        token_usage={"input": 10, "output": 5, "total": 15},
    )
```

`topology_id` defaults to `settings.topology.topology_id`. Leaving the context without calling `finish()` marks the run as succeeded with no decision. An exception marks it as failed and is re-raised.

## Events and Levels

`logging.level` is the minimum level written to both `events.jsonl` and the console. Supported levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. The event file is created even when every event is filtered.

`run.stage(name)` binds the stage to nested events and emits `stage_started`, `stage_completed`, or `stage_failed` with elapsed time. An explicit `stage=` on an event overrides the bound stage.

## Artifacts

- Pydantic models, dataclasses, enums, paths, dates, UUIDs, and JSON values are normalized to JSON.
- Structured values use `.json`; strings and bytes retain a supplied extension or default to `.txt` and `.bin`.
- Repeated names are preserved as `result.json`, `result_2.json`, and so on. Dedicated manifest fields point to the newest version.
- Configured secrets and sensitive fields are redacted before persistence.

A completed or failed run is closed. Further events, artifacts, or terminal state changes raise `RuntimeError`.

The former nested metrics form remains supported:

```python
run.finish("APPROVE", {
    "execution_time": {"translation_ms": 12.5},
    "token_usage": {"total": 15},
})
```
