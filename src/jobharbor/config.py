from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    scan_interval_hours: int = 6
    database_url: str = "sqlite:///./jobharbor.db"
    notification_provider: Literal["pushover", "email"] = "pushover"
    notification_fallback: Literal["email"] = "email"

    pushover_api_token: str | None = None
    pushover_user_key: str | None = None

    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_to: str | None = None

    @field_validator(
        "pushover_api_token",
        "pushover_user_key",
        "smtp_host",
        "smtp_user",
        "smtp_pass",
        "smtp_to",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
