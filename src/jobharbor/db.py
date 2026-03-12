from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, Session, create_engine

from jobharbor.config import Settings


@lru_cache
def get_engine() -> Engine:
    settings = Settings()
    if settings.database_url.startswith("sqlite"):
        return create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
        )
    return create_engine(settings.database_url)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())
