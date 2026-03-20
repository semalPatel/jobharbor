from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from sqlmodel import Session

from jobharbor.models import ApplicationStatus, RunLog, RunStatus
from jobharbor.repositories.application_repo import ApplicationRepository
from jobharbor.workers.greenhouse_prefill import GreenhousePrefillWorker


class PrefillStageWorker:
    def __init__(self, *, session: Session, profile_path: Path | str = Path("profile.yaml")) -> None:
        self._session = session
        self._profile_path = Path(profile_path)

    def run(self, context: dict[str, Any]) -> None:
        queued_items = context.get("queued_items")
        if not isinstance(queued_items, list):
            return

        profile = _load_profile(self._profile_path)
        repo = ApplicationRepository(self._session)
        greenhouse = GreenhousePrefillWorker(application_repo=repo)

        for item in queued_items:
            if not isinstance(item, dict):
                continue
            app_id = item.get("app_id")
            job = item.get("job")
            if not isinstance(app_id, int) or not isinstance(job, dict):
                continue

            source = str(job.get("source", "")).strip().lower()
            apply_url = str(job.get("url", "")).strip()
            planned_actions = [{"action": "fill", "selector": "#first_name"}]
            if source == "greenhouse":
                outcome = greenhouse.prepare_for_review(
                    app_id=app_id,
                    profile=profile,
                    planned_actions=planned_actions,
                )
                payload = dict(outcome.form_payload)
            else:
                repo.transition_status(app_id, to_status=ApplicationStatus.ready_for_review)
                payload = _generic_prefill_payload(profile)

            if apply_url:
                payload["apply_url"] = apply_url

            self._session.add(
                RunLog(
                    source=f"prefill:application:{app_id}",
                    status=RunStatus.success,
                    message=json.dumps(payload, sort_keys=True),
                )
            )
            self._session.commit()


def _load_profile(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"profile file not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    if not isinstance(content, dict):
        raise TypeError("profile file must be a mapping")
    return content


def _generic_prefill_payload(profile: dict[str, object]) -> dict[str, str]:
    fields = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "location",
        "linkedin_url",
        "website_url",
        "resume_path",
    )
    payload: dict[str, str] = {}
    for field in fields:
        value = profile.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            payload[field] = text
    return payload
