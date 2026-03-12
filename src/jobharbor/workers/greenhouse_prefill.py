from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from jobharbor.models import ApplicationStatus
from jobharbor.repositories.application_repo import ApplicationRepository

FINAL_SUBMIT_SELECTOR = "button[type='submit']"

PROFILE_TO_FORM_FIELD_MAP: dict[str, str] = {
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "phone": "phone",
    "location": "location",
    "linkedin_url": "linkedin",
    "website_url": "website",
}


@dataclass(frozen=True)
class PrefillOutcome:
    form_payload: dict[str, str]
    resume_upload_requested: bool
    final_status: ApplicationStatus


class GreenhousePrefillWorker:
    def __init__(self, *, application_repo: ApplicationRepository) -> None:
        self._application_repo = application_repo

    def build_form_payload(self, profile: Mapping[str, str]) -> dict[str, str]:
        payload: dict[str, str] = {}
        for profile_key, form_key in PROFILE_TO_FORM_FIELD_MAP.items():
            value = profile.get(profile_key)
            if value:
                payload[form_key] = value
        return payload

    def prepare_for_review(
        self,
        *,
        app_id: int,
        profile: Mapping[str, str],
        planned_actions: Sequence[Mapping[str, str]] = (),
    ) -> PrefillOutcome:
        self._assert_submit_boundary(planned_actions)
        payload = self.build_form_payload(profile)
        resume_upload_requested = bool(profile.get("resume_path"))

        application = self._application_repo.transition_status(
            app_id,
            ApplicationStatus.ready_for_review,
        )

        return PrefillOutcome(
            form_payload=payload,
            resume_upload_requested=resume_upload_requested,
            final_status=application.status,
        )

    def _assert_submit_boundary(
        self,
        planned_actions: Sequence[Mapping[str, str]],
    ) -> None:
        for action in planned_actions:
            if (
                action.get("action") == "click"
                and action.get("selector") == FINAL_SUBMIT_SELECTOR
            ):
                raise RuntimeError(
                    "submit boundary guard: final submit action is blocked"
                )
