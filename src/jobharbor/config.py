from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    scan_interval_hours: int = Field(default=6, ge=6)
    database_url: str = "sqlite:///./jobharbor.db"
    notification_provider: str = "pushover"
    notification_fallback: str = "email"

    pushover_api_token: str | None = None
    pushover_user_key: str | None = None

    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_to: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
