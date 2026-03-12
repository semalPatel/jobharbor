from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
    now_utc = _as_utc_aware(now, field_name="now")

    prep_count_today = sum(
        1
        for idx, ts in enumerate(daily_prep_timestamps)
        if _is_same_day_utc(ts, now_utc, field_name=f"daily_prep_timestamps[{idx}]")
    )
    if prep_count_today >= policy.max_preps_per_day:
        return PrepDecision(allowed=False, reason_code=REJECT_DAILY_PREP_CAP_REACHED)

    last_source_prep = source_last_prep_at.get(source)
    if last_source_prep is not None:
        last_source_prep_utc = _as_utc_aware(
            last_source_prep,
            field_name=f"source_last_prep_at[{source!r}]",
        )
        elapsed = now_utc - last_source_prep_utc
        if elapsed < policy.source_throttle_interval:
            return PrepDecision(allowed=False, reason_code=REJECT_SOURCE_THROTTLED)

    return PrepDecision(allowed=True, reason_code=ALLOW)


def _is_same_day_utc(ts: datetime, now_utc: datetime, *, field_name: str) -> bool:
    ts_utc = _as_utc_aware(ts, field_name=field_name)
    return ts_utc.date() == now_utc.date()


def _as_utc_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _validate_policy(policy: PrepPolicy) -> None:
    if policy.max_preps_per_day <= 0:
        raise ValueError("max_preps_per_day must be greater than 0")
    if policy.source_throttle_interval.total_seconds() < 0:
        raise ValueError("source_throttle_interval must be non-negative")
