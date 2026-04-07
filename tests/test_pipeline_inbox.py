from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.models import Application, PipelineItem
from jobharbor.pipeline_inbox import PipelineInboxService, parse_pipeline_markdown


def test_parses_pending_and_processed_rows() -> None:
    rows = parse_pipeline_markdown(
        """\
# Pipeline

## Pending
- [ ] https://example.com/job | Acme | AI Engineer

## Processed
- [x] https://example.com/old | OldCo | Staff Engineer
"""
    )

    assert rows[0].url == "https://example.com/job"
    assert rows[0].company == "Acme"
    assert rows[0].title == "AI Engineer"
    assert rows[0].processed is False
    assert rows[1].processed is True


def test_imports_new_url_once(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "pipeline.md"
    path.write_text("- [ ] https://example.com/job | Acme | AI Engineer\n", encoding="utf-8")

    with Session(engine) as session:
        service = PipelineInboxService(session=session, path=path)
        service.import_markdown()
        service.import_markdown()
        items = session.exec(select(PipelineItem)).all()

    assert len(items) == 1
    assert items[0].status == "pending"


def test_process_pending_marks_processed_and_creates_application_report(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "pipeline.md"
    path.write_text("- [ ] https://example.com/job | Acme | AI Engineer\n", encoding="utf-8")

    with Session(engine) as session:
        service = PipelineInboxService(session=session, path=path)
        processed = service.process_pending(reports_dir=tmp_path / "reports")
        applications = session.exec(select(Application)).all()
        items = session.exec(select(PipelineItem)).all()

    assert len(processed) == 1
    assert len(applications) == 1
    assert items[0].status == "processed"
    assert items[0].application_id == applications[0].id
    assert "- [x] https://example.com/job | Acme | AI Engineer" in path.read_text(encoding="utf-8")


def test_limit_is_respected(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "pipeline.md"
    path.write_text(
        """\
- [ ] https://example.com/one | Acme | One
- [ ] https://example.com/two | Acme | Two
""",
        encoding="utf-8",
    )

    with Session(engine) as session:
        processed = PipelineInboxService(session=session, path=path).process_pending(
            reports_dir=tmp_path / "reports",
            limit=1,
        )
        items = session.exec(select(PipelineItem).order_by(PipelineItem.id)).all()

    assert len(processed) == 1
    assert items[0].status == "processed"
    assert items[1].status == "pending"
