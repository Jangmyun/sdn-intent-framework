"""Typed application configuration loaded from TOML and environment secrets."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.toml"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectSettings(StrictModel):
    environment: str = "development"
    experiment_id: str = "proposed"
    random_seed: int = Field(default=42, ge=0)


class LLMSettings(StrictModel):
    provider: str
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0.0)
    retries: int = Field(ge=0, le=10)
    prompt_version: str


class ControllerSettings(StrictModel):
    kind: Literal["onos", "ryu"] = "onos"
    host: str = "127.0.0.1"
    openflow_port: int = Field(default=6653, ge=1, le=65535)
    rest_port: int = Field(default=8181, ge=1, le=65535)


class TopologySettings(StrictModel):
    topology_id: str
    role: Literal["single", "production", "validation"] = "single"


class PipelineSettings(StrictModel):
    retrieval: bool = True
    static_validation: bool = True
    digital_twin: bool = True
    repair: bool = True
    regression_validation: bool = True
    fault_validation: bool = True
    xai: bool = True


class TranslationExperimentSettings(StrictModel):
    output_format: Literal["direct_flow", "intent_ir"] = "intent_ir"
    few_shot: bool = False
    state_grounding: bool = False
    dataset_path: Path = Path("experiments/e1/data/intents.jsonl")
    topology_path: Path = Path("experiments/e1/data/topology.json")


class RepairSettings(StrictModel):
    max_iterations: int = Field(default=3, ge=0, le=3)


class LoggingSettings(StrictModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    console: bool = True
    directory: Path = Path("logs/runs")


class SecretSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAFE_SDN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: AnyHttpUrl | None = None
    onos_user: str = "onos"
    onos_password: SecretStr = SecretStr("rocks")

    @model_validator(mode="after")
    def validate_llm_base_url(self) -> "SecretSettings":
        if self.llm_base_url is not None and self.llm_base_url.path.rstrip("/") not in {"", "/v1"}:
            raise ValueError("llm_base_url must be an origin URL or end with /v1")
        return self


class AppSettings(StrictModel):
    project: ProjectSettings
    llm: LLMSettings
    controller: ControllerSettings
    topology: TopologySettings
    pipeline: PipelineSettings
    translation_experiment: TranslationExperimentSettings = TranslationExperimentSettings()
    repair: RepairSettings
    logging: LoggingSettings
    secrets: SecretSettings

    @model_validator(mode="after")
    def validate_pipeline(self) -> "AppSettings":
        if self.pipeline.repair and self.repair.max_iterations == 0:
            raise ValueError("repair.max_iterations must be positive when repair is enabled")
        if not self.pipeline.repair and self.repair.max_iterations != 0:
            raise ValueError("repair.max_iterations must be 0 when repair is disabled")
        return self

    def public_snapshot(self) -> dict[str, Any]:
        """Return configuration safe to persist in run metadata."""
        snapshot = self.model_dump(mode="json", exclude={"secrets"})
        snapshot["secrets"] = {
            "llm_api_key": "**********",
            "llm_base_url": str(self.secrets.llm_base_url) if self.secrets.llm_base_url else None,
            "onos_user": self.secrets.onos_user,
            "onos_password": "**********",
        }
        return snapshot


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    """Load defaults, an optional experiment override, then environment secrets."""
    data = _read_toml(DEFAULT_CONFIG_PATH)
    selected_path = config_path or os.getenv("SAFE_SDN_CONFIG")
    if selected_path:
        override_path = Path(selected_path)
        if not override_path.is_absolute():
            override_path = PROJECT_ROOT / override_path
        data = _deep_merge(data, _read_toml(override_path))

    secrets = SecretSettings(_env_file=PROJECT_ROOT / ".env")
    return AppSettings.model_validate({**data, "secrets": secrets})
