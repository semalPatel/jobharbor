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
        payload: Sequence[dict[str, Any]],
    ) -> None:
        self._name = name
        self._call_log = call_log
        self._payload = list(payload)

    def fetch_jobs(self) -> Sequence[dict[str, Any]]:
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
    assert run.to_run_log_payload() == {
        "source": "discovery",
        "status": RunStatus.partial_failure,
        "message": "discovered 2 jobs with 1 connector failures",
    }
