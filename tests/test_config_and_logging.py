from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

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
