from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence, Tuple

import yaml


@dataclass(frozen=True)
class YamlConfig:
    scan_interval_hours: int | None = None
    include_domain_keywords: Tuple[str, ...] = field(default_factory=tuple)
    exclude_domain_keywords: Tuple[str, ...] = field(default_factory=tuple)
    allowed_location_keywords: Tuple[str, ...] = field(default_factory=tuple)
    allowed_work_auth: Tuple[str, ...] = field(default_factory=tuple)
    connector_rollout: Tuple[str, ...] = field(default_factory=tuple)
    discovery_capabilities: Tuple[str, ...] = field(default_factory=tuple)


def load_yaml_config(path: Path) -> YamlConfig:
    payload = _read_yaml(path)
    return YamlConfig(
        scan_interval_hours=payload.get("scan_interval_hours"),
        include_domain_keywords=_normalize_list(payload.get("include_domain_keywords")),
        exclude_domain_keywords=_normalize_list(payload.get("exclude_domain_keywords")),
        allowed_location_keywords=_normalize_list(payload.get("allowed_location_keywords")),
        allowed_work_auth=_normalize_list(payload.get("allowed_work_auth")),
        connector_rollout=_normalize_list(payload.get("connector_rollout")),
        discovery_capabilities=_normalize_list(payload.get("discovery_capabilities")),
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise TypeError("yaml config must define a mapping")
    return content


def _normalize_list(candidate: Any) -> Tuple[str, ...]:
    if candidate is None:
        return tuple()
    if isinstance(candidate, str):
        return (candidate.strip(),)
    if isinstance(candidate, Iterable):
        return tuple(str(item).strip() for item in candidate if str(item).strip())
    return tuple()


__all__ = ["YamlConfig", "load_yaml_config"]
