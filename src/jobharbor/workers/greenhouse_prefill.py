from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from jobharbor.models import ApplicationStatus
from jobharbor.repositories.application_repo import ApplicationRepository
from jobharbor.workers.errors import (
    PrefillWorkerError,
    classify_prefill_error,
    is_retryable_prefill_error,
)

FINAL_SUBMIT_SELECTOR = "button[type='submit']"
SUBMIT_SELECTOR_VARIANTS: tuple[str, ...] = (
    "button[type='submit']",
    'button[type="submit"]',
    "input[type='submit']",
    'input[type="submit"]',
)

EXPLICIT_SUBMIT_ACTIONS: set[str] = {
    "submit",
    "form_submit",
    "press_enter",
}

UPLOAD_ACTION_TYPES: set[str] = {
    "upload",
    "upload_file",
    "attach_file",
}

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

    def build_form_payload(self, profile: Mapping[str, object]) -> dict[str, str]:
        payload: dict[str, str] = {}
        for profile_key, form_key in PROFILE_TO_FORM_FIELD_MAP.items():
            cleaned = _clean_string(profile.get(profile_key))
            if cleaned:
                payload[form_key] = cleaned
        return payload

    def prepare_for_review(
        self,
        *,
        app_id: int,
        profile: Mapping[str, object],
        planned_actions: Sequence[Mapping[str, object]] = (),
    ) -> PrefillOutcome:
        self._assert_submit_boundary(planned_actions)

        upload_action_present = _has_upload_action(planned_actions)
        resume_path = _clean_string(profile.get("resume_path"))
        if upload_action_present and not resume_path:
            raise ValueError("resume_path is required when upload action is planned")

        payload = self.build_form_payload(profile)

        application = self._application_repo.transition_status(
            app_id,
            ApplicationStatus.ready_for_review,
        )

        return PrefillOutcome(
            form_payload=payload,
            resume_upload_requested=upload_action_present and bool(resume_path),
            final_status=application.status,
        )

    def _assert_submit_boundary(
        self,
        planned_actions: Sequence[Mapping[str, object]],
    ) -> None:
        for action in planned_actions:
            action_name = _normalized_action_name(action)
            selector = _clean_string(action.get("selector")) or ""

            if _has_explicit_submit_intent(action, action_name):
                raise RuntimeError(
                    "submit boundary guard: final submit action is blocked"
                )

            if action_name == "click" and _selector_looks_like_submit(selector):
                raise RuntimeError(
                    "submit boundary guard: final submit action is blocked"
                )


def _normalized_action_name(action: Mapping[str, object]) -> str:
    action_name = _clean_string(action.get("action"))
    if action_name:
        return action_name.lower()

    action_type = _clean_string(action.get("type"))
    if action_type:
        return action_type.lower()

    return ""


def _has_explicit_submit_intent(action: Mapping[str, object], action_name: str) -> bool:
    if action_name in EXPLICIT_SUBMIT_ACTIONS:
        return True
    if "submit" in action_name:
        return True

    intent = (_clean_string(action.get("intent")) or "").lower()
    if "submit" in intent:
        return True

    return _is_truthy(action.get("submit_intent"))


def _selector_looks_like_submit(selector: str) -> bool:
    normalized = selector.lower().replace(" ", "")
    if "submit" in normalized:
        return True
    return normalized in {variant.replace(" ", "") for variant in SUBMIT_SELECTOR_VARIANTS}


def _has_upload_action(planned_actions: Sequence[Mapping[str, object]]) -> bool:
    for action in planned_actions:
        action_name = _normalized_action_name(action)
        if action_name in UPLOAD_ACTION_TYPES:
            return True
        if "upload" in action_name:
            return True
    return False


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "yes", "y", "on"}
    return False


def classify_prefill_exception(error: BaseException) -> PrefillWorkerError:
    return classify_prefill_error(error)


def should_retry_prefill_exception(error: BaseException) -> bool:
    return is_retryable_prefill_error(error)
