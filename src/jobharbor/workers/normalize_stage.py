from __future__ import annotations

import re
from typing import Any


class NormalizeStageWorker:
    def run(self, context: dict[str, Any]) -> None:
        discovered = context.get("discovered_jobs")
        if not isinstance(discovered, list):
            context["normalized_jobs"] = []
            return

        normalized: list[dict[str, Any]] = []
        for raw in discovered:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item["title"] = _clean_text(item.get("title"))
            item["description"] = _clean_text(item.get("description"))
            item["location"] = _clean_text(item.get("location"))
            item["company"] = _clean_text(item.get("company"))
            item["url"] = _clean_text(item.get("url"))
            item["source"] = _clean_text(item.get("source"))
            item["external_id"] = _clean_text(item.get("external_id"))
            if not item.get("work_auth"):
                item["work_auth"] = _infer_work_auth(item.get("description", ""))
            normalized.append(item)

        context["normalized_jobs"] = normalized


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def _infer_work_auth(description: str) -> str:
    text = (description or "").lower()
    if "us authorized" in text or "authorized to work in the us" in text:
        return "us_authorized"
    if "sponsorship" in text and ("not" in text or "no" in text):
        return "us_authorized"
    if "sponsorship" in text:
        return "requires_sponsorship"
    return ""
