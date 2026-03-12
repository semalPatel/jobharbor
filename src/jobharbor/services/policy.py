from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

ALLOW = "ALLOW"
REJECT_DAILY_PREP_CAP_REACHED = "REJECT_DAILY_PREP_CAP_REACHED"
REJECT_SOURCE_THROTTLED = "REJECT_SOURCE_THROTTLED"


@dataclass(frozen=True)
class PrepPolicy:
    max_preps_per_day: int
    source_throttle_interval: timedelta


@dataclass(frozen=True)
class PrepDecision:
    allowed: bool
    reason_code: str


def evaluate_prep_policy(
    *,
    source: str,
    now: datetime,
    daily_prep_timestamps: Sequence[datetime],
    source_last_prep_at: Mapping[str, datetime],
    policy: PrepPolicy,
) -> PrepDecision:
    _validate_policy(policy)

    prep_count_today = sum(1 for ts in daily_prep_timestamps if _is_same_day(ts, now))
    if prep_count_today >= policy.max_preps_per_day:
        return PrepDecision(allowed=False, reason_code=REJECT_DAILY_PREP_CAP_REACHED)

    last_source_prep = source_last_prep_at.get(source)
    if last_source_prep is not None:
        elapsed = now - last_source_prep
        if elapsed < policy.source_throttle_interval:
            return PrepDecision(allowed=False, reason_code=REJECT_SOURCE_THROTTLED)

    return PrepDecision(allowed=True, reason_code=ALLOW)


def _is_same_day(ts: datetime, now: datetime) -> bool:
    return ts.date() == now.date()


def _validate_policy(policy: PrepPolicy) -> None:
    if policy.max_preps_per_day <= 0:
        raise ValueError("max_preps_per_day must be greater than 0")
    if policy.source_throttle_interval.total_seconds() < 0:
        raise ValueError("source_throttle_interval must be non-negative")
