"""Generate tracked JSON Schemas for experiment records."""

from __future__ import annotations

import json
from pathlib import Path

from .config import PROJECT_ROOT
from .run_context import EventRecord, RunManifest


def generate_schemas(output_dir: Path | None = None) -> list[Path]:
    target = output_dir or PROJECT_ROOT / "schemas"
    target.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for name, model in (("run_manifest", RunManifest), ("event_record", EventRecord)):
        path = target / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        generated.append(path)
    return generated


if __name__ == "__main__":
    for schema_path in generate_schemas():
        print(schema_path)
