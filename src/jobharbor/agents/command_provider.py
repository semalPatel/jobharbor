from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any

from jobharbor.evaluation import EvaluationDimension, EvaluationResult
from jobharbor.models import Application, Job


class CommandEvaluationProvider:
    provider_name = "command"

    def __init__(self, *, command: str, timeout_seconds: int) -> None:
        if not command.strip():
            raise ValueError("evaluation command is required for command provider")
        if timeout_seconds <= 0:
            raise ValueError("evaluation timeout must be greater than 0")
        self._command = command
        self._timeout_seconds = timeout_seconds

    def evaluate(
        self,
        *,
        job: Job,
        application: Application,
        cv_text: str = "",
        profile_text: str = "",
        prompt_text: str = "",
    ) -> EvaluationResult:
        payload = {
            "job": {
                "id": job.id,
                "source": job.source,
                "external_id": job.external_id,
                "title": job.title,
                "company": job.company,
                "url": job.url,
                "location": job.location,
                "posted_at": job.posted_at,
                "description": job.description,
            },
            "application": {
                "id": application.id,
                "job_id": application.job_id,
                "status": application.status.value,
            },
            "cv_text": cv_text,
            "profile_text": profile_text,
            "prompt_text": prompt_text,
        }
        try:
            completed = subprocess.run(
                shlex.split(self._command),
                input=json.dumps(payload, sort_keys=True),
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("evaluation command timed out") from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(f"evaluation command failed: {message}") from exc

        try:
            output = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("evaluation command returned malformed JSON") from exc
        if not isinstance(output, dict):
            raise ValueError("evaluation command output must be a JSON object")
        return _result_from_payload(output)


def _result_from_payload(payload: dict[str, Any]) -> EvaluationResult:
    dimensions = payload.get("dimensions", [])
    if not isinstance(dimensions, list):
        raise ValueError("evaluation dimensions must be a list")
    return EvaluationResult(
        application_id=_required_int(payload, "application_id"),
        job_id=_required_int(payload, "job_id"),
        company=_required_str(payload, "company"),
        role=_required_str(payload, "role"),
        score=_required_float(payload, "score"),
        recommendation=_required_str(payload, "recommendation"),
        summary=_required_str(payload, "summary"),
        dimensions=tuple(_dimension_from_payload(row) for row in dimensions),
        gaps=_text_tuple(payload.get("gaps", []), "gaps"),
        risks=_text_tuple(payload.get("risks", []), "risks"),
        next_actions=_text_tuple(payload.get("next_actions", []), "next_actions"),
        draft_answers=_text_tuple(payload.get("draft_answers", []), "draft_answers"),
    )


def _dimension_from_payload(value: object) -> EvaluationDimension:
    if not isinstance(value, dict):
        raise ValueError("evaluation dimension entries must be objects")
    return EvaluationDimension(
        name=_required_str(value, "name"),
        score=_required_float(value, "score"),
        rationale=_required_str(value, "rationale"),
    )


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"evaluation field {key} must be an integer")
    return value


def _required_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"evaluation field {key} must be numeric")
    return float(value)


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"evaluation field {key} must be a non-empty string")
    return value.strip()


def _text_tuple(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"evaluation field {key} must be a list")
    return tuple(str(item).strip() for item in value if str(item).strip())
