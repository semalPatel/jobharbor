from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from sqlmodel import Session, select

from jobharbor.models import PipelineItem
from jobharbor.reports import EvaluationReportStageWorker
from jobharbor.workers.queue_stage import QueueStageWorker

PIPELINE_STATUSES = {"pending", "processing", "processed", "failed", "skipped"}


@dataclass(frozen=True)
class PipelineInboxRow:
    url: str
    company: str = ""
    title: str = ""
    processed: bool = False


def parse_pipeline_markdown(text: str) -> list[PipelineInboxRow]:
    rows: list[PipelineInboxRow] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            processed = True
            payload = stripped[5:].strip()
        elif stripped.startswith("- [ ]"):
            processed = False
            payload = stripped[5:].strip()
        else:
            continue
        parts = [part.strip() for part in payload.split("|")]
        if not parts or not parts[0]:
            continue
        rows.append(
            PipelineInboxRow(
                url=parts[0],
                company=parts[1] if len(parts) > 1 else "",
                title=parts[2] if len(parts) > 2 else "",
                processed=processed,
            )
        )
    return rows


class PipelineInboxService:
    def __init__(self, *, session: Session, path: Path) -> None:
        self._session = session
        self._path = path

    def import_markdown(self) -> list[PipelineItem]:
        if not self._path.exists():
            return []
        rows = parse_pipeline_markdown(self._path.read_text(encoding="utf-8"))
        imported: list[PipelineItem] = []
        for row in rows:
            existing = self._by_url(row.url)
            if existing is not None:
                if not existing.company and row.company:
                    existing.company = row.company
                if not existing.title and row.title:
                    existing.title = row.title
                self._session.add(existing)
                imported.append(existing)
                continue
            item = PipelineItem(
                url=row.url,
                company=row.company or None,
                title=row.title or None,
                status="processed" if row.processed else "pending",
                source="manual",
            )
            self._session.add(item)
            imported.append(item)
        self._session.commit()
        for item in imported:
            self._session.refresh(item)
        return imported

    def export_markdown(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        items = list(self._session.exec(select(PipelineItem).order_by(PipelineItem.id)).all())
        self._path.write_text(render_pipeline_markdown(items), encoding="utf-8")

    def process_pending(self, *, reports_dir: Path, limit: int | None = None) -> list[PipelineItem]:
        self.import_markdown()
        stmt = select(PipelineItem).where(PipelineItem.status == "pending").order_by(PipelineItem.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        pending = list(self._session.exec(stmt).all())
        processed: list[PipelineItem] = []
        for item in pending:
            item.status = "processing"
            self._session.add(item)
            self._session.commit()
            try:
                context = {"eligible_jobs": [_job_dict(item)]}
                QueueStageWorker(session=self._session).run(context)
                queued_items = context.get("queued_items")
                if not isinstance(queued_items, list) or not queued_items:
                    item.status = "skipped"
                else:
                    item.application_id = queued_items[0]["app_id"]
                    EvaluationReportStageWorker(session=self._session, reports_dir=reports_dir).run(context)
                    item.status = "processed"
                self._session.add(item)
                self._session.commit()
            except Exception:
                self._session.rollback()
                item.status = "failed"
                self._session.add(item)
                self._session.commit()
            self._session.refresh(item)
            processed.append(item)
        self.export_markdown()
        return processed

    def _by_url(self, url: str) -> PipelineItem | None:
        stmt = select(PipelineItem).where(PipelineItem.url == url).limit(1)
        return self._session.exec(stmt).first()


def render_pipeline_markdown(items: list[PipelineItem]) -> str:
    pending = [item for item in items if item.status in {"pending", "processing", "failed"}]
    processed = [item for item in items if item.status in {"processed", "skipped"}]
    lines = ["# Pipeline", "", "## Pending", ""]
    lines.extend(_render_item(item, checked=False) for item in pending)
    lines.extend(["", "## Processed", ""])
    lines.extend(_render_item(item, checked=True) for item in processed)
    return "\n".join(lines) + "\n"


def _render_item(item: PipelineItem, *, checked: bool) -> str:
    marker = "x" if checked else " "
    return f"- [{marker}] {item.url} | {item.company or ''} | {item.title or ''}".rstrip()


def _job_dict(item: PipelineItem) -> dict[str, str]:
    return {
        "source": "pipeline",
        "external_id": hashlib.sha256(item.url.encode("utf-8")).hexdigest(),
        "title": item.title or "",
        "company": item.company or "",
        "url": item.url,
        "location": "",
        "posted_at": "",
        "description": "manual pipeline inbox",
        "provider": "pipeline",
        "source_url": item.url,
    }
