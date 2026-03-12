from sqlmodel import SQLModel, Session, create_engine

from jobharbor.config import Settings


def get_engine():
    settings = Settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


def get_session() -> Session:
    return Session(get_engine())


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())
