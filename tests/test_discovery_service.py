from collections.abc import Sequence
from typing import Any

from jobharbor.models import RunStatus
from jobharbor.services.discovery_service import DiscoveryService


class RecordingConnector:
    def __init__(
        self,
        *,
        name: str,
        call_log: list[str],
        payload: Sequence[dict[str, Any]] | Sequence[Any],
    ) -> None:
        self._name = name
        self._call_log = call_log
        self._payload = list(payload)

    def fetch_jobs(self) -> Sequence[dict[str, Any]] | Sequence[Any]:
        self._call_log.append(self._name)
        return list(self._payload)


class FailingConnector:
    def __init__(self, *, name: str, call_log: list[str]) -> None:
        self._name = name
        self._call_log = call_log

    def fetch_jobs(self) -> Sequence[dict[str, Any]]:
        self._call_log.append(self._name)
        raise RuntimeError("upstream timeout")


def test_discovery_service_executes_connectors_in_configured_order() -> None:
    call_log: list[str] = []

    service = DiscoveryService(
        connectors=[
            (
                "greenhouse",
                RecordingConnector(
                    name="greenhouse",
                    call_log=call_log,
                    payload=[
                        {
                            "external_id": "2",
                            "title": "B",
                            "company": "Acme",
                            "location": "Remote",
                            "url": "https://example.test/2",
                            "posted_at": "2026-03-10",
                        },
                        {
                            "external_id": "1",
                            "title": "A",
                            "company": "Acme",
                            "location": "Remote",
                            "url": "https://example.test/1",
                            "posted_at": "2026-03-11",
                        },
                    ],
                ),
            ),
            (
                "ashby",
                RecordingConnector(
                    name="ashby",
                    call_log=call_log,
                    payload=[
                        {
                            "external_id": "20",
                            "title": "C",
                            "company": "Globex",
                            "location": "New York, NY",
                            "url": "https://example.test/20",
                            "posted_at": "2026-03-09",
                        }
                    ],
                ),
            ),
        ]
    )

    jobs, run = service.discover()

    assert call_log == ["greenhouse", "ashby"]
    assert [job["source"] for job in jobs] == ["greenhouse", "greenhouse", "ashby"]
    assert [job["external_id"] for job in jobs] == ["1", "2", "20"]
    assert run.status is RunStatus.success
    assert run.total_jobs == 3
    assert run.failure_details == []
    assert run.to_run_log_payload() == {
        "source": "discovery",
        "status": RunStatus.success,
        "message": "discovered 3 jobs from 2 connectors",
    }


def test_discovery_service_returns_partial_failure_outcome_and_continues() -> None:
    call_log: list[str] = []

    service = DiscoveryService(
        connectors=[
            (
                "greenhouse",
                RecordingConnector(
                    name="greenhouse",
                    call_log=call_log,
                    payload=[
                        {
                            "external_id": "1",
                            "title": "A",
                            "company": "Acme",
                            "location": "Remote",
                            "url": "https://example.test/1",
                            "posted_at": "2026-03-11",
                        }
                    ],
                ),
            ),
            ("ashby", FailingConnector(name="ashby", call_log=call_log)),
            (
                "lever",
                RecordingConnector(
                    name="lever",
                    call_log=call_log,
                    payload=[
                        {
                            "external_id": "9",
                            "title": "SRE",
                            "company": "Initech",
                            "location": "Austin, TX",
                            "url": "https://example.test/9",
                            "posted_at": "2026-03-08",
                        }
                    ],
                ),
            ),
        ]
    )

    jobs, run = service.discover()

    assert call_log == ["greenhouse", "ashby", "lever"]
    assert [job["source"] for job in jobs] == ["greenhouse", "lever"]
    assert run.status is RunStatus.partial_failure
    assert run.total_jobs == 2
    assert run.failure_details == [
        {
            "source": "ashby",
            "error_type": "RuntimeError",
            "message": "upstream timeout",
        }
    ]
    assert run.to_run_log_payload() == {
        "source": "discovery",
        "status": RunStatus.partial_failure,
        "message": "discovered 2 jobs with 1 connector failures",
    }


def test_discovery_service_all_connectors_fail_returns_failed() -> None:
    call_log: list[str] = []

    service = DiscoveryService(
        connectors=[
            ("greenhouse", FailingConnector(name="greenhouse", call_log=call_log)),
            ("ashby", FailingConnector(name="ashby", call_log=call_log)),
        ]
    )

    jobs, run = service.discover()

    assert jobs == []
    assert call_log == ["greenhouse", "ashby"]
    assert run.status is RunStatus.failed
    assert run.connectors_total == 2
    assert run.connectors_failed == 2
    assert [detail["source"] for detail in run.failure_details] == ["greenhouse", "ashby"]


def test_discovery_service_with_no_connectors_is_success_with_zero_jobs() -> None:
    service = DiscoveryService(connectors=[])

    jobs, run = service.discover()

    assert jobs == []
    assert run.status is RunStatus.success
    assert run.total_jobs == 0
    assert run.connectors_total == 0
    assert run.connectors_failed == 0
    assert run.failure_details == []


def test_discovery_service_payload_validation_failure_increments_failure_and_continues() -> None:
    call_log: list[str] = []

    service = DiscoveryService(
        connectors=[
            (
                "greenhouse",
                RecordingConnector(
                    name="greenhouse",
                    call_log=call_log,
                    payload=["not-a-mapping"],
                ),
            ),
            (
                "lever",
                RecordingConnector(
                    name="lever",
                    call_log=call_log,
                    payload=[
                        {
                            "external_id": "9",
                            "title": "SRE",
                            "company": "Initech",
                            "location": "Austin, TX",
                            "url": "https://example.test/9",
                            "posted_at": "2026-03-08",
                        }
                    ],
                ),
            ),
        ]
    )

    jobs, run = service.discover()

    assert call_log == ["greenhouse", "lever"]
    assert [job["source"] for job in jobs] == ["lever"]
    assert run.status is RunStatus.partial_failure
    assert run.connectors_failed == 1
    assert run.failure_details == [
        {
            "source": "greenhouse",
            "error_type": "TypeError",
            "message": "connector payload entries must be mappings",
        }
    ]


def test_discovery_service_unsupported_key_types_use_stable_empty_string() -> None:
    call_log: list[str] = []

    service = DiscoveryService(
        connectors=[
            (
                "greenhouse",
                RecordingConnector(
                    name="greenhouse",
                    call_log=call_log,
                    payload=[
                        {
                            "external_id": "same-id",
                            "posted_at": {"year": 2026},
                            "title": "zzz",
                            "company": "Acme",
                            "location": ["unsupported-location"],
                            "url": "https://example.test/b",
                        },
                        {
                            "external_id": "same-id",
                            "posted_at": "2026-03-10",
                            "title": ["list-is-unsupported"],
                            "company": "Acme",
                            "location": "Remote",
                            "url": "https://example.test/a",
                        },
                    ],
                ),
            )
        ]
    )

    jobs, run = service.discover()

    assert run.status is RunStatus.success
    assert [job["url"] for job in jobs] == ["https://example.test/b", "https://example.test/a"]
