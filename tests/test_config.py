from pydantic import ValidationError

from jobharbor.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.scan_interval_hours == 6
    assert settings.database_url == "sqlite:///./jobharbor.db"
    assert settings.notification_provider == "pushover"
    assert settings.notification_fallback == "email"


def test_scan_interval_has_minimum_of_six_hours() -> None:
    try:
        Settings(scan_interval_hours=5)
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected validation error when scan_interval_hours < 6")
