from __future__ import annotations

from typing import Any


class ReviewStageWorker:
    def run(self, context: dict[str, Any]) -> None:
        queued_items = context.get("queued_items")
        if isinstance(queued_items, list):
            context["review_count"] = len(queued_items)
        else:
            context["review_count"] = 0
