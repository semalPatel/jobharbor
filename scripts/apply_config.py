#!/usr/bin/env python3
"""Validate a YAML config and remind operators to point JOBHARBOR_CONFIG_PATH at it."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Iterable

from jobharbor.config_schema import load_yaml_config, YamlConfig

REQUIRED_FIELDS = {
    "scan_interval_hours": "Scan cadence in hours",
    "include_domain_keywords": "At least one include keyword",
}


def _parse_args() -> Path:
    parser = ArgumentParser(
        description="Validate a jobharbor YAML config and show how to wire it into the runtime."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="config.yaml",
        help="Path to the YAML config to validate (default: config.yaml)",
    )
    return Path(parser.parse_args().config)


def _missing_fields(config: YamlConfig) -> list[str]:
    missing: list[str] = []
    if config.scan_interval_hours is None:
        missing.append("scan_interval_hours")
    if not config.include_domain_keywords:
        missing.append("include_domain_keywords")
    return missing


def _format_instructions(path: Path) -> Iterable[str]:
    resolved = path.resolve()
    yield "Config valid."
    yield (
        f"Set JOBHARBOR_CONFIG_PATH={resolved} in your environment "
        f"(or add JOBHARBOR_CONFIG_PATH={resolved} to `.env`) before starting the container."
    )
    yield "If you leave the file named config.yaml in the repo root, the service will detect it automatically."


def main() -> None:
    config_path = _parse_args()
    if not config_path.exists():
        raise SystemExit(f"config file not found: {config_path}")

    config = load_yaml_config(config_path)
    missing = _missing_fields(config)
    if missing:
        names = ", ".join(f"{name} ({REQUIRED_FIELDS.get(name, 'required')})" for name in missing)
        raise SystemExit(f"Config {config_path} is missing required entries: {names}")

    for message in _format_instructions(config_path):
        print(message)


if __name__ == "__main__":
    main()
