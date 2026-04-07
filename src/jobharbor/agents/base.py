from __future__ import annotations

from typing import Protocol

from jobharbor.evaluation import EvaluationResult
from jobharbor.models import Application, Job


class EvaluationProvider(Protocol):
    provider_name: str

    def evaluate(
        self,
        *,
        job: Job,
        application: Application,
        cv_text: str = "",
        profile_text: str = "",
        prompt_text: str = "",
    ) -> EvaluationResult:
        ...
