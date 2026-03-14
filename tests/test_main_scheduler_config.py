from pathlib import Path

from pytest import MonkeyPatch

from jobharbor.config import Settings, CONFIG_ENV_VAR


def test_settings_applies_yaml_scan_interval(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_file = tmp_path / "yaml_config.yaml"
    config_file.write_text("scan_interval_hours: 3\ninclude_domain_keywords: [android, kotlin]\n")
    monkeypatch.setenv(CONFIG_ENV_VAR, str(config_file))

    settings = Settings()

    assert settings.scan_interval_hours == 3
    assert settings.include_domain_keywords == ("android", "kotlin")
