from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jobharbor.models import PipelineItem
from jobharbor.pipeline_inbox import PipelineInboxService


@dataclass(frozen=True)
class BatchRunResult:
    processed: tuple[PipelineItem, ...]


class BatchProcessor:
    def __init__(self, *, pipeline_service: PipelineInboxService, reports_dir: Path) -> None:
        self._pipeline_service = pipeline_service
        self._reports_dir = reports_dir

    def run(self, *, limit: int | None = None, concurrency: int = 1) -> BatchRunResult:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than 0")
        if concurrency <= 0:
            raise ValueError("concurrency must be greater than 0")
        if concurrency != 1:
            raise ValueError("pipeline concurrency greater than 1 is not implemented yet")
        processed = self._pipeline_service.process_pending(reports_dir=self._reports_dir, limit=limit)
        return BatchRunResult(processed=tuple(processed))
