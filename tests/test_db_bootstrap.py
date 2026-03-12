import pytest

import jobharbor.db as db


def test_get_engine_reuses_same_url_and_separates_different_urls(monkeypatch) -> None:
    db._engine_for_url.cache_clear()

    calls: list[tuple[str, dict[str, object]]] = []
    listen_calls: list[tuple[object, str, object]] = []

    class FakeEngine:
        def __init__(self, url: str):
            self.url = url

    def fake_create_engine(url: str, **kwargs):
        calls.append((url, kwargs))
        return FakeEngine(url)

    def fake_listen(target: object, identifier: str, fn: object) -> None:
        listen_calls.append((target, identifier, fn))

    monkeypatch.setattr(db, "create_engine", fake_create_engine)
    monkeypatch.setattr(db.event, "listen", fake_listen)

    engine_one = db.get_engine("sqlite:///./one.db")
    engine_two = db.get_engine("sqlite:///./one.db")
    engine_three = db.get_engine("sqlite:///./two.db")

    assert engine_one is engine_two
    assert engine_three is not engine_one
    assert calls == [
        (
            "sqlite:///./one.db",
            {"connect_args": {"check_same_thread": False}},
        ),
        (
            "sqlite:///./two.db",
            {"connect_args": {"check_same_thread": False}},
        ),
    ]
    assert [identifier for _, identifier, _ in listen_calls] == ["connect", "connect"]


def test_get_engine_does_not_set_sqlite_connect_args_for_non_sqlite(monkeypatch) -> None:
    db._engine_for_url.cache_clear()

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_create_engine(url: str, **kwargs):
        calls.append((url, kwargs))
        return object()

    monkeypatch.setattr(db, "create_engine", fake_create_engine)

    db.get_engine("postgresql+psycopg://user:pass@localhost/jobharbor")

    assert calls == [("postgresql+psycopg://user:pass@localhost/jobharbor", {})]


def test_get_engine_uses_settings_database_url_when_not_provided(monkeypatch) -> None:
    db._engine_for_url.cache_clear()

    class FakeSettings:
        database_url = "sqlite:///./from-settings.db"

    captured_urls: list[str] = []

    def fake_engine_for_url(database_url: str):
        captured_urls.append(database_url)
        return object()

    monkeypatch.setattr(db, "Settings", lambda: FakeSettings())
    monkeypatch.setattr(db, "_engine_for_url", fake_engine_for_url)

    db.get_engine()

    assert captured_urls == ["sqlite:///./from-settings.db"]


def test_get_session_yields_and_closes_session(monkeypatch) -> None:
    engine = object()

    class FakeSession:
        def __init__(self, bound_engine: object):
            assert bound_engine is engine
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True

    monkeypatch.setattr(db, "get_engine", lambda: engine)
    monkeypatch.setattr(db, "Session", FakeSession)

    session_iter = db.get_session()
    session = next(session_iter)

    assert isinstance(session, FakeSession)
    assert session.closed is False

    with pytest.raises(StopIteration):
        next(session_iter)

    assert session.closed is True


def test_init_db_calls_create_all_with_engine(monkeypatch) -> None:
    engine = object()
    create_all_calls: list[object] = []

    def fake_create_all(bound_engine: object) -> None:
        create_all_calls.append(bound_engine)

    monkeypatch.setattr(db, "get_engine", lambda: engine)
    monkeypatch.setattr(db.SQLModel.metadata, "create_all", fake_create_all)

    db.init_db()

    assert create_all_calls == [engine]
