from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Field, SQLModel

from jobharbor.db import get_engine, get_session, init_db


class BootstrapProbe(SQLModel, table=True):
    __tablename__ = "bootstrap_probe"

    id: int | None = Field(default=None, primary_key=True)
    value: str


def sqlite_url_for(path: Path) -> str:
    return f"sqlite:///{path}"


def test_get_engine_uses_settings_database_url(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "engine.db"
    monkeypatch.setenv("DATABASE_URL", sqlite_url_for(db_path))

    engine = get_engine()

    assert str(engine.url) == sqlite_url_for(db_path)


def test_get_session_returns_session_bound_to_engine(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "session.db"
    monkeypatch.setenv("DATABASE_URL", sqlite_url_for(db_path))

    session = get_session()
    try:
        bind = session.get_bind()
        assert bind is not None
        assert str(bind.url) == sqlite_url_for(db_path)
    finally:
        session.close()


def test_init_db_bootstraps_sqlmodel_metadata(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap.db"
    monkeypatch.setenv("DATABASE_URL", sqlite_url_for(db_path))

    init_db()

    engine = get_engine()
    inspector = inspect(engine)
    assert inspector.has_table("bootstrap_probe")
