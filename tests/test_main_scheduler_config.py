from pathlib import Path
from typing import Iterable

from pytest import MonkeyPatch

from jobharbor.config import Settings, CONFIG_ENV_VAR


def _write_config(path: Path, *, interval: int, keywords: Iterable[str]) -> None:
    path.write_text(
        "scan_interval_hours: %d\ninclude_domain_keywords:\n%s\n"
        % (
            interval,
            "".join(f"  - {keyword}\n" for keyword in keywords),
        )
    )


def test_settings_applies_yaml_scan_interval(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_file = tmp_path / "yaml_config.yaml"
    _write_config(config_file, interval=3, keywords=["android", "kotlin"])
    monkeypatch.setenv(CONFIG_ENV_VAR, str(config_file))

    settings = Settings()

    assert settings.scan_interval_hours == 3
    assert settings.include_domain_keywords == ("android", "kotlin")


def test_environment_path_precedence_over_default(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    default_config = tmp_path / "config.yaml"
    _write_config(default_config, interval=5, keywords=["default"])
    explicit_config = tmp_path / "override.yaml"
    _write_config(explicit_config, interval=7, keywords=["override"])

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(CONFIG_ENV_VAR, str(explicit_config))

    settings = Settings()

    assert settings.scan_interval_hours == 7
    assert settings.include_domain_keywords == ("override",)


def test_default_config_path_used_when_env_unset(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_file = tmp_path / "config.yaml"
    _write_config(config_file, interval=4, keywords=["default"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)

    settings = Settings()

    assert settings.scan_interval_hours == 4
    assert settings.include_domain_keywords == ("default",)
