from pydantic import ValidationError

from jobharbor.config import Settings


ENV_KEYS = [
    "SCAN_INTERVAL_HOURS",
    "DATABASE_URL",
    "NOTIFICATION_PROVIDER",
    "NOTIFICATION_FALLBACK",
    "PUSHOVER_API_TOKEN",
    "PUSHOVER_USER_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "SMTP_TO",
]


def clear_env(monkeypatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_settings_defaults(monkeypatch) -> None:
    clear_env(monkeypatch)

    settings = Settings()

    assert settings.scan_interval_hours == 6
    assert settings.database_url == "sqlite:///./jobharbor.db"
    assert settings.notification_provider == "pushover"
    assert settings.notification_fallback == "email"


def test_env_override_mapping(monkeypatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("SCAN_INTERVAL_HOURS", "12")

    settings = Settings()

    assert settings.scan_interval_hours == 12


def test_invalid_notification_provider_raises_validation_error() -> None:
    try:
        Settings(notification_provider="sms")
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected validation error for unsupported notification_provider")


def test_blank_optional_values_normalize_to_none(monkeypatch) -> None:
    clear_env(monkeypatch)
    monkeypatch.setenv("PUSHOVER_API_TOKEN", "")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASS", "")
    monkeypatch.setenv("SMTP_TO", "")

    settings = Settings()

    assert settings.pushover_api_token is None
    assert settings.pushover_user_key is None
    assert settings.smtp_host is None
    assert settings.smtp_user is None
    assert settings.smtp_pass is None
    assert settings.smtp_to is None
