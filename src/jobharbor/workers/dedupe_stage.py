from __future__ import annotations

from typing import Any

from jobharbor.services.dedupe import dedupe_fingerprint


class DedupeStageWorker:
    def run(self, context: dict[str, Any]) -> None:
        normalized = context.get("normalized_jobs")
        if not isinstance(normalized, list):
            context["deduped_jobs"] = []
            return

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in normalized:
            if not isinstance(item, dict):
                continue
            fingerprint = dedupe_fingerprint(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            deduped.append(item)

        context["deduped_jobs"] = deduped
