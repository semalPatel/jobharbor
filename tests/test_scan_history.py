from datetime import UTC, datetime

from jobharbor.scan_history import SCAN_HISTORY_HEADER, ScanHistoryWriter


def test_scan_history_writer_appends_stable_tsv_rows(tmp_path) -> None:
    path = tmp_path / "data" / "scan-history.tsv"
    writer = ScanHistoryWriter(path, now=lambda: datetime(2026, 4, 7, 12, 0, tzinfo=UTC))

    row = writer.append(
        status="added",
        job={
            "url": "https://example.com/job",
            "source": "greenhouse",
            "title": "AI Engineer",
            "company": "Acme",
        },
    )

    assert row.status == "added"
    assert path.read_text(encoding="utf-8") == (
        SCAN_HISTORY_HEADER
        + "https://example.com/job\t2026-04-07T12:00:00+00:00\tgreenhouse\tAI Engineer\tAcme\tadded\t\n"
    )


def test_scan_history_writer_sanitizes_cells(tmp_path) -> None:
    path = tmp_path / "scan-history.tsv"
    writer = ScanHistoryWriter(path, now=lambda: datetime(2026, 4, 7, 12, 0, tzinfo=UTC))

    writer.append(status="skipped_capability", reason="missing\tsearch\ncapability")

    assert "missing search capability" in path.read_text(encoding="utf-8")
