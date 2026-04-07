import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.batch import BatchProcessor
from jobharbor.models import PipelineItem
from jobharbor.pipeline_inbox import PipelineInboxService


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
        service = PipelineInboxService(session=session, path=path)
        result = BatchProcessor(pipeline_service=service, reports_dir=tmp_path / "reports").run(limit=1)
        items = session.exec(select(PipelineItem).order_by(PipelineItem.id)).all()

    assert len(result.processed) == 1
    assert items[0].status == "processed"
    assert items[1].status == "pending"


def test_processed_item_is_not_reprocessed(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "pipeline.md"
    path.write_text("- [x] https://example.com/done | Acme | Done\n", encoding="utf-8")

    with Session(engine) as session:
        service = PipelineInboxService(session=session, path=path)
        result = BatchProcessor(pipeline_service=service, reports_dir=tmp_path / "reports").run()
        items = session.exec(select(PipelineItem)).all()

    assert result.processed == ()
    assert len(items) == 1
    assert items[0].status == "processed"


def test_concurrency_setting_does_not_duplicate_work(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "pipeline.md"
    path.write_text("- [ ] https://example.com/one | Acme | One\n", encoding="utf-8")

    with Session(engine) as session:
        service = PipelineInboxService(session=session, path=path)
        with pytest.raises(ValueError, match="concurrency"):
            BatchProcessor(pipeline_service=service, reports_dir=tmp_path / "reports").run(concurrency=2)
        items = session.exec(select(PipelineItem)).all()

    assert items == []


def test_failed_item_remains_retryable_when_set_back_to_pending(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "pipeline.md"

    with Session(engine) as session:
        item = PipelineItem(url="https://example.com/fail", company="Acme", title="Fail", status="failed")
        session.add(item)
        session.commit()
        item.status = "pending"
        session.add(item)
        session.commit()

        service = PipelineInboxService(session=session, path=path)
        result = BatchProcessor(pipeline_service=service, reports_dir=tmp_path / "reports").run(limit=1)

    assert len(result.processed) == 1
    assert result.processed[0].status == "processed"
