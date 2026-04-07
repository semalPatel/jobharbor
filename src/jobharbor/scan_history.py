from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


SCAN_HISTORY_HEADER = "url\tfirst_seen\tsource\ttitle\tcompany\tstatus\treason\n"
ALLOWED_SCAN_HISTORY_STATUSES = {
    "added",
    "skipped_title",
    "skipped_dup",
    "skipped_capability",
    "failed_fetch",
    "failed_parse",
}


@dataclass(frozen=True)
class ScanHistoryRow:
    url: str
    first_seen: str
    source: str
    title: str
    company: str
    status: str
    reason: str


class ScanHistoryWriter:
    def __init__(
        self,
        path: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._path = path
        self._now = now or (lambda: datetime.now(tz=UTC))

    def append(
        self,
        *,
        status: str,
        reason: str = "",
        job: Mapping[str, object] | None = None,
        url: str | None = None,
        source: str | None = None,
        title: str | None = None,
        company: str | None = None,
    ) -> ScanHistoryRow:
        if status not in ALLOWED_SCAN_HISTORY_STATUSES:
            raise ValueError(f"unsupported scan history status: {status}")
        job = job or {}
        row = ScanHistoryRow(
            url=_clean(url if url is not None else job.get("url")),
            first_seen=self._now().replace(microsecond=0).isoformat(),
            source=_clean(source if source is not None else job.get("source")),
            title=_clean(title if title is not None else job.get("title")),
            company=_clean(company if company is not None else job.get("company")),
            status=status,
            reason=_clean(reason),
        )
        self._append_row(row)
        return row

    def _append_row(self, row: ScanHistoryRow) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists() or not self._path.read_text(encoding="utf-8").strip():
            self._path.write_text(SCAN_HISTORY_HEADER, encoding="utf-8")
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\t".join(
                    (
                        _tsv_cell(row.url),
                        _tsv_cell(row.first_seen),
                        _tsv_cell(row.source),
                        _tsv_cell(row.title),
                        _tsv_cell(row.company),
                        _tsv_cell(row.status),
                        _tsv_cell(row.reason),
                    )
                )
                + "\n"
            )


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tsv_cell(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
