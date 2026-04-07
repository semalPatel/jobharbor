from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Any, Mapping

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jobharbor.config_schema import YamlConfig, load_yaml_config

CONFIG_ENV_VAR = "JOBHARBOR_CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path("config.yaml")


class Settings(BaseSettings):
    scan_interval_hours: int = 6
    database_url: str = "sqlite:///./jobharbor.db"
    jobharbor_home: Path = Path("./workspace")
    evaluation_provider: Literal["stub", "command", "codex"] = "stub"
    evaluation_command: str | None = None
    evaluation_timeout_seconds: int = 60
    notification_provider: Literal["pushover", "email"] = "pushover"
    notification_fallback: Literal["email"] = "email"

    pushover_api_token: str | None = None
    pushover_user_key: str | None = None

    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_to: str | None = None

    include_domain_keywords: tuple[str, ...] = ()
    exclude_domain_keywords: tuple[str, ...] = ()
    allowed_location_keywords: tuple[str, ...] = ()
    allowed_work_auth: tuple[str, ...] = ()
    connector_rollout: tuple[str, ...] = ()
    discovery_capabilities: tuple[str, ...] | str = Field(
        default=("http",),
        validation_alias=AliasChoices("JOBHARBOR_DISCOVERY_CAPABILITIES", "DISCOVERY_CAPABILITIES"),
    )

    @field_validator(
        "pushover_api_token",
        "pushover_user_key",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_pass",
        "smtp_to",
        "evaluation_command",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "include_domain_keywords",
        "exclude_domain_keywords",
        "allowed_location_keywords",
        "allowed_work_auth",
        "connector_rollout",
        "discovery_capabilities",
        mode="before",
    )
    @classmethod
    def split_csv_tuple(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ()
            if "," in text:
                return tuple(part.strip() for part in text.split(",") if part.strip())
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _apply_yaml_overrides(cls, values: Mapping[str, Any]) -> Mapping[str, Any]:
        overrides = cls._yaml_overrides()
        if not overrides:
            return dict(values)

        merged = dict(values)
        for name, candidate in overrides.items():
            if candidate is None or name in merged:
                continue
            merged[name] = candidate
        return merged

    @classmethod
    def _yaml_overrides(cls) -> dict[str, Any]:
        path = cls._resolve_yaml_path()
        if path is None:
            return {}
        config = load_yaml_config(path)
        return {
            "scan_interval_hours": config.scan_interval_hours,
            "include_domain_keywords": config.include_domain_keywords or (),
            "exclude_domain_keywords": config.exclude_domain_keywords or (),
            "allowed_location_keywords": config.allowed_location_keywords or (),
            "allowed_work_auth": config.allowed_work_auth or (),
            "connector_rollout": config.connector_rollout or (),
            "discovery_capabilities": config.discovery_capabilities or None,
        }

    @classmethod
    def _resolve_yaml_path(cls) -> Path | None:
        explicit = os.getenv(CONFIG_ENV_VAR)
        if explicit:
            path = Path(explicit)
            if not path.exists():
                raise FileNotFoundError(f"yaml config not found at {path}")
            return path
        if DEFAULT_CONFIG_PATH.exists():
            return DEFAULT_CONFIG_PATH
        return None


__all__ = ["Settings", "YamlConfig", "load_yaml_config"]
