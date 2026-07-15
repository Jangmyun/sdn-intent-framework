from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

import safe_intent_sdn.config as config_module
from safe_intent_sdn.config import load_settings
from safe_intent_sdn.run_context import RunManifest, create_run_context
from safe_intent_sdn.schema import generate_schemas


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = "test-api-secret"
    monkeypatch.setenv("SAFE_SDN_LLM_API_KEY", secret)
    monkeypatch.setenv("SAFE_SDN_ONOS_PASSWORD", "test-onos-secret")
    return secret


def settings_for_logs(tmp_path: Path, api_key: str):
    settings = load_settings()
    logging_settings = settings.logging.model_copy(update={"directory": tmp_path, "console": False})
    return settings.model_copy(update={"logging": logging_settings})


class ArtifactKind(Enum):
    INTENT = "intent"


@dataclass
class ArtifactChild:
    count: int


class ArtifactPayload(BaseModel):
    path: Path
    created_at: datetime
    kind: ArtifactKind
    child: ArtifactChild
    api_key: str


def test_default_and_b0_override(api_key: str) -> None:
    default = load_settings()
    baseline = load_settings("config/experiments/b0.toml")
    assert default.project.experiment_id == "proposed"
    assert default.pipeline.digital_twin is True
    assert baseline.project.experiment_id == "b0"
    assert baseline.pipeline.digital_twin is False
    assert baseline.repair.max_iterations == 0


def test_environment_config_path(monkeypatch: pytest.MonkeyPatch, api_key: str) -> None:
    monkeypatch.setenv("SAFE_SDN_CONFIG", "config/experiments/b0.toml")
    assert load_settings().project.experiment_id == "b0"


def test_invalid_config_is_rejected(tmp_path: Path, api_key: str) -> None:
    override = tmp_path / "invalid.toml"
    override.write_text("[llm]\ntemperature = 3.0\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_settings(override)


def test_missing_api_key_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SAFE_SDN_LLM_API_KEY", raising=False)
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    with pytest.raises(ValidationError):
        load_settings()


def test_successful_run_writes_valid_manifest_and_redacts(tmp_path: Path, api_key: str) -> None:
    settings = settings_for_logs(tmp_path, api_key)
    with create_run_context(settings, "intent-001", "topology_a") as run:
        first_run_id = run.run_id
        reference = run.save_artifact("input_intent", "allow h1 to reach h2")
        secret_artifact = run.save_artifact("llm_raw_output", {"api_key": api_key, "result": f"response included {api_key}"})
        run.log_event("llm_completed", stage="translation", message=f"Bearer {api_key}")
        run.finish(
            "APPROVE",
            {"execution_time": {"translation_ms": 12.5}, "token_usage": {"input": 10, "output": 5, "total": 15}},
        )

    manifest = RunManifest.model_validate_json(run.manifest_path.read_text(encoding="utf-8"))
    assert manifest.run_id == first_run_id
    assert manifest.status == "succeeded"
    assert manifest.final_decision == "APPROVE"
    assert manifest.input_intent == reference
    assert manifest.token_usage["total"] == 15
    artifact_bytes = (run.run_dir / reference.path).read_bytes()
    assert hashlib.sha256(artifact_bytes).hexdigest() == reference.sha256
    secret_payload = (run.run_dir / secret_artifact.path).read_text(encoding="utf-8")
    assert api_key not in secret_payload
    assert api_key not in run.event_path.read_text(encoding="utf-8")
    assert all(json.loads(line) for line in run.event_path.read_text(encoding="utf-8").splitlines())


def test_failed_run_is_retained(tmp_path: Path, api_key: str) -> None:
    settings = settings_for_logs(tmp_path, api_key)
    with pytest.raises(RuntimeError, match="deliberate"):
        with create_run_context(settings, "intent-fail", "topology_a") as run:
            run.save_artifact("generated_ir", {"partial": True})
            raise RuntimeError("deliberate failure")

    manifest = RunManifest.model_validate_json(run.manifest_path.read_text(encoding="utf-8"))
    assert manifest.status == "failed"
    assert manifest.error == {"type": "RuntimeError", "message": "deliberate failure"}
    assert (run.run_dir / manifest.generated_ir.path).exists()


def test_run_ids_are_unique(tmp_path: Path, api_key: str) -> None:
    settings = settings_for_logs(tmp_path, api_key)
    first = create_run_context(settings, "one", "topology_a")
    second = create_run_context(settings, "two", "topology_a")
    first.finish(None, {})
    second.finish(None, {})
    assert first.run_id != second.run_id


def test_schema_generation(tmp_path: Path) -> None:
    generated = generate_schemas(tmp_path)
    assert {path.name for path in generated} == {"run_manifest.schema.json", "event_record.schema.json"}
    for path in generated:
        assert json.loads(path.read_text(encoding="utf-8"))["type"] == "object"


def test_log_level_filters_file_and_console(
    tmp_path: Path, api_key: str, capsys: pytest.CaptureFixture[str],
) -> None:
    settings = settings_for_logs(tmp_path, api_key)
    logging_settings = settings.logging.model_copy(update={"level": "ERROR", "console": True})
    settings = settings.model_copy(update={"logging": logging_settings})
    with create_run_context(settings, "level-test") as run:
        run.log_event("filtered_info")
        run.log_event("retained_error", level="ERROR")

    events = [json.loads(line) for line in run.event_path.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["retained_error"]
    console = capsys.readouterr().out
    assert "retained_error" in console
    assert "filtered_info" not in console


def test_high_log_level_still_creates_empty_event_file(tmp_path: Path, api_key: str) -> None:
    settings = settings_for_logs(tmp_path, api_key)
    logging_settings = settings.logging.model_copy(update={"level": "CRITICAL"})
    settings = settings.model_copy(update={"logging": logging_settings})
    with create_run_context(settings, "empty-events") as run:
        pass
    assert run.event_path.is_file()
    assert run.event_path.read_text(encoding="utf-8") == ""


def test_invalid_event_level_is_rejected(tmp_path: Path, api_key: str) -> None:
    run = create_run_context(settings_for_logs(tmp_path, api_key), "invalid-level")
    with pytest.raises(ValueError, match="Unsupported log level"):
        run.log_event("typo", level="INOF")  # type: ignore[arg-type]
    run.finish()


def test_default_topology_and_keyword_metrics(tmp_path: Path, api_key: str) -> None:
    settings = settings_for_logs(tmp_path, api_key)
    run = create_run_context(settings, "default-topology")
    run.finish("APPROVE", execution_time={"translation_ms": 2}, token_usage={"total": 7})
    assert run.manifest.topology_id == settings.topology.topology_id
    assert run.manifest.execution_time["translation_ms"] == 2.0
    assert run.manifest.token_usage == {"total": 7}


def test_duplicate_metric_forms_are_rejected_without_closing_run(
    tmp_path: Path, api_key: str,
) -> None:
    run = create_run_context(settings_for_logs(tmp_path, api_key), "duplicate-metrics")
    with pytest.raises(ValueError, match="both metrics"):
        run.finish(metrics={"execution_time": {}}, execution_time={})
    assert run.manifest.status == "running"
    run.finish()


def test_structured_artifacts_are_serialized_redacted_and_versioned(
    tmp_path: Path, api_key: str,
) -> None:
    run = create_run_context(settings_for_logs(tmp_path, api_key), "artifact-types")
    payload = ArtifactPayload(
        path=Path("input/file.txt"),
        created_at=datetime(2026, 7, 15, 12, 30),
        kind=ArtifactKind.INTENT,
        child=ArtifactChild(count=2),
        api_key=api_key,
    )
    first = run.save_artifact("generated_ir", payload)
    second = run.save_artifact("generated_ir.json", payload)
    with pytest.raises(ValueError, match=r"\.json extension"):
        run.save_artifact("invalid.yaml", payload)
    run.finish()

    assert first.path == "artifacts/generated_ir.json"
    assert second.path == "artifacts/generated_ir_2.json"
    assert set(run.manifest.artifacts) == {"generated_ir", "generated_ir_2"}
    assert run.manifest.generated_ir == second
    saved = json.loads((run.run_dir / second.path).read_text(encoding="utf-8"))
    assert saved == {
        "api_key": "**********",
        "child": {"count": 2},
        "created_at": "2026-07-15T12:30:00",
        "kind": "intent",
        "path": "input/file.txt",
    }


def test_closed_run_rejects_all_writes(tmp_path: Path, api_key: str) -> None:
    run = create_run_context(settings_for_logs(tmp_path, api_key), "closed-run")
    run.finish()
    operations = (
        lambda: run.log_event("late"),
        lambda: run.save_artifact("late", {"value": 1}),
        lambda: run.finish(),
        lambda: run.fail(RuntimeError("late")),
    )
    for operation in operations:
        with pytest.raises(RuntimeError, match="already succeeded"):
            operation()


def test_context_preserves_exception_after_explicit_finish(tmp_path: Path, api_key: str) -> None:
    run = create_run_context(settings_for_logs(tmp_path, api_key), "original-error")
    with pytest.raises(ValueError, match="application error"):
        with run:
            run.finish()
            raise ValueError("application error")


def test_stage_binds_events_and_records_duration(tmp_path: Path, api_key: str) -> None:
    with create_run_context(settings_for_logs(tmp_path, api_key), "stage-success") as run:
        with run.stage("translation"):
            run.log_event("llm_called")
            run.log_event("override", stage="custom")
        run.finish(token_usage={"total": 3})

    events = [json.loads(line) for line in run.event_path.read_text(encoding="utf-8").splitlines()]
    stages = {event["event"]: event["stage"] for event in events}
    assert stages["stage_started"] == "translation"
    assert stages["llm_called"] == "translation"
    assert stages["override"] == "custom"
    assert stages["stage_completed"] == "translation"
    assert run.manifest.execution_time["translation_ms"] >= 0


def test_failed_stage_is_recorded_and_redacted(tmp_path: Path, api_key: str) -> None:
    with pytest.raises(RuntimeError, match="stage failed"):
        with create_run_context(settings_for_logs(tmp_path, api_key), "stage-failure") as run:
            with run.stage("validation"):
                raise RuntimeError(f"stage failed {api_key}")

    events_text = run.event_path.read_text(encoding="utf-8")
    events = [json.loads(line) for line in events_text.splitlines()]
    assert [event["event"] for event in events][-2:] == ["stage_failed", "run_failed"]
    assert api_key not in events_text
    assert run.manifest.status == "failed"
    assert "validation_ms" in run.manifest.execution_time


def test_nested_stage_restores_parent_binding(tmp_path: Path, api_key: str) -> None:
    with create_run_context(settings_for_logs(tmp_path, api_key), "nested-stage") as run:
        with run.stage("outer"):
            with run.stage("inner"):
                run.log_event("inside_inner")
            run.log_event("back_in_outer")

    events = [json.loads(line) for line in run.event_path.read_text(encoding="utf-8").splitlines()]
    event_stages = {event["event"]: event["stage"] for event in events}
    assert event_stages["inside_inner"] == "inner"
    assert event_stages["back_in_outer"] == "outer"
    assert "outer_ms" in run.manifest.execution_time
    assert "inner_ms" in run.manifest.execution_time


def test_concurrent_artifact_versions_are_all_retained(tmp_path: Path, api_key: str) -> None:
    run = create_run_context(settings_for_logs(tmp_path, api_key), "concurrent-artifacts")
    with ThreadPoolExecutor(max_workers=4) as executor:
        references = list(executor.map(lambda value: run.save_artifact("result", {"value": value}), range(8)))
    run.finish()

    assert len({reference.path for reference in references}) == 8
    assert len(run.manifest.artifacts) == 8
    assert all((run.run_dir / reference.path).is_file() for reference in references)
