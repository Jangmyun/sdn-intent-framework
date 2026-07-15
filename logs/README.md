# Runtime Logs

Each experiment is stored under `logs/runs/YYYYMMDD/<run_id>/` with:

- `manifest.json`: reproducibility metadata and artifact references
- `events.jsonl`: append-only structured events
- `artifacts/`: intent, IR, validation, policy, twin, repair, and report payloads

Raw run data is ignored by Git. JSON Schemas in `schemas/` and sanitized examples may be committed. Failed runs are retained with `status: failed`.
