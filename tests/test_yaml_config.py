from pathlib import Path

from jobharbor.config import load_yaml_config


def test_yaml_loader_reads_interval_and_keywords(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """\
scan_interval_hours: 3
include_domain_keywords:
  - android
  - kotlin
"""
    )

    config = load_yaml_config(path)

    assert config.scan_interval_hours == 3
    assert config.include_domain_keywords == ("android", "kotlin")
