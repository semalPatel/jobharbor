from jobharbor.main import health


def test_health() -> None:
    assert health() == {"ok": True}
