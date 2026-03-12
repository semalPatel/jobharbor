from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, Session, create_engine

from jobharbor.config import Settings


@lru_cache
def _engine_for_url(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _set_sqlite_foreign_keys_pragma)
        return engine
    return create_engine(database_url)


def _set_sqlite_foreign_keys_pragma(dbapi_connection, connection_record) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def get_engine(database_url: str | None = None) -> Engine:
    resolved_url = database_url or Settings().database_url
    return _engine_for_url(resolved_url)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())
