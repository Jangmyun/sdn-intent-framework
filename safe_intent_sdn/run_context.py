"""Durable, structured logging for individual experiment runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import AppSettings, PROJECT_ROOT

Decision = Literal["APPROVE", "REJECT", "HOLD"]
RunStatus = Literal["running", "succeeded", "failed"]
_SENSITIVE_KEY = re.compile(r"(api[_-]?key|password|authorization|secret|token)$", re.IGNORECASE)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_now() -> str:
    return _utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str
    media_type: str


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    date: str
    git_commit: str
    git_dirty: bool
    model_name: str
    prompt_version: str
    topology_id: str
    intent_id: str
    feature_flags: dict[str, bool]
    random_seed: int
    config_snapshot: dict[str, Any]
    input_intent: ArtifactRef | None = None
    generated_ir: ArtifactRef | None = None
    static_validation: ArtifactRef | None = None
    compiled_policy: ArtifactRef | None = None
    twin_test_results: ArtifactRef | None = None
    repair_history: ArtifactRef | None = None
    final_decision: Decision | None = None
    execution_time: dict[str, float] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    status: RunStatus = "running"
    error: dict[str, str] | None = None
    artifacts: dict[str, ArtifactRef] = Field(default_factory=dict)


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: str
    level: str
    event: str
    run_id: str
    stage: str | None = None
    duration_ms: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)


def _git_state() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return "unknown", True


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "**********" if _SENSITIVE_KEY.search(str(key)) else _redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class RunContext:
    """Own one run directory and its append-only event stream."""

    _MANIFEST_ARTIFACTS = {
        "input_intent", "generated_ir", "static_validation", "compiled_policy",
        "twin_test_results", "repair_history",
    }

    def __init__(self, settings: AppSettings, intent_id: str, topology_id: str) -> None:
        self.settings = settings
        self.started_at = perf_counter()
        now = _utc_now()
        self.run_id = f"{now.strftime('%Y%m%dT%H%M%S%f')[:-3]}Z_{uuid.uuid4().hex[:8]}"
        log_root = settings.logging.directory
        if not log_root.is_absolute():
            log_root = PROJECT_ROOT / log_root
        self.run_dir = log_root / now.strftime("%Y%m%d") / self.run_id
        self.artifact_dir = self.run_dir / "artifacts"
        self.artifact_dir.mkdir(parents=True, exist_ok=False)
        self.event_path = self.run_dir / "events.jsonl"
        self.manifest_path = self.run_dir / "manifest.json"
        self._lock = threading.Lock()
        self._secret_values = tuple(
            value for value in (
                settings.secrets.llm_api_key.get_secret_value(),
                settings.secrets.onos_password.get_secret_value(),
            ) if value
        )
        commit, dirty = _git_state()
        self.manifest = RunManifest(
            run_id=self.run_id, date=_iso_now(), git_commit=commit, git_dirty=dirty,
            model_name=settings.llm.model, prompt_version=settings.llm.prompt_version,
            topology_id=topology_id, intent_id=intent_id,
            feature_flags=settings.pipeline.model_dump(), random_seed=settings.project.random_seed,
            config_snapshot=settings.public_snapshot(),
        )
        self._write_manifest()
        self.log_event("run_started", stage="orchestration")

    def __enter__(self) -> "RunContext":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: Any) -> bool:
        if exc is not None:
            self.fail(exc)
        elif self.manifest.status == "running":
            self.finish(None, {})
        return False

    def _write_manifest(self) -> None:
        temp_path = self.manifest_path.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as output:
            output.write(self.manifest.model_dump_json(indent=2))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, self.manifest_path)

    def log_event(
        self, event: str, stage: str | None = None, *, level: str = "INFO",
        duration_ms: float | None = None, evidence_ids: list[str] | None = None, **fields: Any,
    ) -> None:
        fields = self._redact_secrets(fields)
        record = EventRecord(
            timestamp=_iso_now(), level=level, event=event, run_id=self.run_id,
            stage=stage, duration_ms=duration_ms, evidence_ids=evidence_ids or [], fields=fields,
        )
        with self._lock:
            with self.event_path.open("a", encoding="utf-8") as event_file:
                event_file.write(record.model_dump_json() + "\n")
                event_file.flush()
                os.fsync(event_file.fileno())
        if self.settings.logging.console:
            stage_text = f" [{stage}]" if stage else ""
            print(f"{record.timestamp} {level:<8}{stage_text} {event}")

    def save_artifact(self, name: str, data: Any) -> ArtifactRef:
        if not _SAFE_NAME.fullmatch(name) or "/" in name or ".." in name:
            raise ValueError(f"Unsafe artifact name: {name!r}")
        data = self._redact_secrets(data)
        supplied_path = Path(name)
        if isinstance(data, bytes):
            suffix, payload, media_type = ".bin", data, "application/octet-stream"
        elif isinstance(data, str):
            suffix, payload, media_type = ".txt", data.encode(), "text/plain"
        else:
            suffix = ".json"
            payload = (json.dumps(_redact(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            media_type = "application/json"
        artifact_path = self.artifact_dir / (name if supplied_path.suffix else name + suffix)
        artifact_path.write_bytes(payload)
        reference = ArtifactRef(
            path=artifact_path.relative_to(self.run_dir).as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(), media_type=media_type,
        )
        artifact_key = supplied_path.stem
        self.manifest.artifacts[artifact_key] = reference
        if artifact_key in self._MANIFEST_ARTIFACTS:
            setattr(self.manifest, artifact_key, reference)
        self._write_manifest()
        self.log_event("artifact_saved", stage="persistence", artifact=artifact_key, path=reference.path)
        return reference

    def _redact_secrets(self, value: Any) -> Any:
        value = _redact(value)
        if isinstance(value, dict):
            return {key: self._redact_secrets(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact_secrets(item) for item in value]
        if isinstance(value, str):
            for secret in self._secret_values:
                value = value.replace(secret, "**********")
        return value

    def finish(self, decision: Decision | None, metrics: dict[str, Any]) -> None:
        if self.manifest.status != "running":
            return
        self.manifest.status = "succeeded"
        self.manifest.final_decision = decision
        self.manifest.execution_time = {
            **{key: float(value) for key, value in metrics.get("execution_time", {}).items()},
            "total_ms": round((perf_counter() - self.started_at) * 1000, 3),
        }
        self.manifest.token_usage = {key: int(value) for key, value in metrics.get("token_usage", {}).items()}
        self._write_manifest()
        self.log_event("run_finished", stage="orchestration", decision=decision)

    def fail(self, error: BaseException) -> None:
        if self.manifest.status != "running":
            return
        self.manifest.status = "failed"
        self.manifest.error = {"type": type(error).__name__, "message": self._redact_secrets(str(error))}
        self.manifest.execution_time["total_ms"] = round((perf_counter() - self.started_at) * 1000, 3)
        self._write_manifest()
        self.log_event("run_failed", stage="orchestration", level="ERROR", error_type=type(error).__name__, error_message=str(error))


def create_run_context(settings: AppSettings, intent_id: str, topology_id: str) -> RunContext:
    return RunContext(settings=settings, intent_id=intent_id, topology_id=topology_id)
