from __future__ import annotations

from typing import Any

from jobharbor.services.filters import HardFilterPolicy, evaluate_hard_filters


class ScoreStageWorker:
    def __init__(self, *, settings) -> None:
        self._settings = settings
        rollout = tuple(getattr(settings, "connector_rollout", ()) or ())
        if rollout:
            self._allowed_sources = {source.strip().lower() for source in rollout if source.strip()}
        else:
            self._allowed_sources = {"greenhouse", "ashby", "lever", "ycombinator"}

    def run(self, context: dict[str, Any]) -> None:
        candidates = context.get("deduped_jobs")
        if not isinstance(candidates, list):
            context["eligible_jobs"] = []
            return

        base_policy = HardFilterPolicy(
            include_domain_keywords=set(self._settings.include_domain_keywords),
            exclude_domain_keywords=set(self._settings.exclude_domain_keywords),
            allowed_location_keywords=set(self._settings.allowed_location_keywords),
            allowed_work_auth=set(self._settings.allowed_work_auth),
        )

        eligible: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip().lower()
            if source not in self._allowed_sources:
                continue

            # Policy decision: missing work auth is treated as unknown-but-allowed.
            policy = base_policy
            if base_policy.allowed_work_auth and not str(item.get("work_auth", "")).strip():
                policy = HardFilterPolicy(
                    include_domain_keywords=base_policy.include_domain_keywords,
                    exclude_domain_keywords=base_policy.exclude_domain_keywords,
                    company_blacklist=base_policy.company_blacklist,
                    title_blacklist=base_policy.title_blacklist,
                    allowed_location_keywords=base_policy.allowed_location_keywords,
                    allowed_work_auth=set(),
                )

            decision = evaluate_hard_filters(item, policy=policy)
            if decision.passed:
                eligible.append(item)

        context["eligible_jobs"] = eligible
