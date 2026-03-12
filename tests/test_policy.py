from datetime import UTC, datetime, timedelta, timezone

import pytest

from jobharbor.services.policy import (
    ALLOW,
    REJECT_DAILY_PREP_CAP_REACHED,
    REJECT_SOURCE_THROTTLED,
    PrepPolicy,
    evaluate_prep_policy,
)


def test_policy_allows_when_within_daily_cap_and_source_interval() -> None:
    now = datetime(2026, 3, 12, 15, 0, tzinfo=UTC)
    daily_preps = [
        datetime(2026, 3, 12, 8, 0, tzinfo=UTC),
        datetime(2026, 3, 12, 10, 30, tzinfo=UTC),
    ]
    source_preps = {
        "greenhouse": datetime(2026, 3, 12, 13, 0, tzinfo=UTC),
    }

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=daily_preps,
        source_last_prep_at=source_preps,
        policy=PrepPolicy(max_preps_per_day=3, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is True
    assert decision.reason_code == ALLOW


def test_policy_rejects_when_daily_prep_cap_is_reached() -> None:
    now = datetime(2026, 3, 12, 18, 0, tzinfo=UTC)
    daily_preps = [
        datetime(2026, 3, 12, 7, 0, tzinfo=UTC),
        datetime(2026, 3, 12, 11, 0, tzinfo=UTC),
    ]

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=daily_preps,
        source_last_prep_at={},
        policy=PrepPolicy(max_preps_per_day=2, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is False
    assert decision.reason_code == REJECT_DAILY_PREP_CAP_REACHED


def test_policy_rejects_when_source_interval_throttle_not_elapsed() -> None:
    now = datetime(2026, 3, 12, 14, 30, tzinfo=UTC)

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=[datetime(2026, 3, 12, 9, 0, tzinfo=UTC)],
        source_last_prep_at={"greenhouse": datetime(2026, 3, 12, 14, 0, tzinfo=UTC)},
        policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is False
    assert decision.reason_code == REJECT_SOURCE_THROTTLED


def test_policy_prioritizes_daily_cap_reason_over_source_throttle() -> None:
    now = datetime(2026, 3, 12, 15, 0, tzinfo=UTC)
    daily_preps = [
        datetime(2026, 3, 12, 9, 0, tzinfo=UTC),
        datetime(2026, 3, 12, 11, 0, tzinfo=UTC),
    ]

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=daily_preps,
        source_last_prep_at={"greenhouse": datetime(2026, 3, 12, 14, 45, tzinfo=UTC)},
        policy=PrepPolicy(max_preps_per_day=2, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is False
    assert decision.reason_code == REJECT_DAILY_PREP_CAP_REACHED


def test_policy_counts_day_boundary_using_utc_rollover() -> None:
    now = datetime(2026, 3, 13, 0, 5, tzinfo=UTC)
    daily_preps = [
        datetime(2026, 3, 12, 23, 59, tzinfo=UTC),
        datetime(2026, 3, 13, 0, 1, tzinfo=UTC),
    ]

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=daily_preps,
        source_last_prep_at={},
        policy=PrepPolicy(max_preps_per_day=1, source_throttle_interval=timedelta(minutes=15)),
    )

    assert decision.allowed is False
    assert decision.reason_code == REJECT_DAILY_PREP_CAP_REACHED


def test_policy_counts_mixed_timezone_offsets_by_same_utc_day() -> None:
    plus_14 = timezone(timedelta(hours=14))
    minus_7 = timezone(timedelta(hours=-7))
    now = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
    daily_preps = [
        datetime(2026, 3, 13, 1, 0, tzinfo=plus_14),  # 2026-03-12 11:00 UTC
        datetime(2026, 3, 12, 4, 0, tzinfo=minus_7),  # 2026-03-12 11:00 UTC
    ]

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=daily_preps,
        source_last_prep_at={},
        policy=PrepPolicy(max_preps_per_day=2, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is False
    assert decision.reason_code == REJECT_DAILY_PREP_CAP_REACHED


def test_policy_allows_when_throttle_elapsed_equals_interval_boundary() -> None:
    now = datetime(2026, 3, 12, 16, 0, tzinfo=UTC)

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=[],
        source_last_prep_at={"greenhouse": datetime(2026, 3, 12, 15, 0, tzinfo=UTC)},
        policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is True
    assert decision.reason_code == ALLOW


def test_policy_rejects_when_last_source_prep_is_in_future_clock_skew() -> None:
    now = datetime(2026, 3, 12, 15, 0, tzinfo=UTC)

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=now,
        daily_prep_timestamps=[],
        source_last_prep_at={"greenhouse": datetime(2026, 3, 12, 16, 0, tzinfo=UTC)},
        policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
    )

    assert decision.allowed is False
    assert decision.reason_code == REJECT_SOURCE_THROTTLED


def test_policy_rejects_naive_datetimes() -> None:
    now_naive = datetime(2026, 3, 12, 15, 0)
    aware_now = datetime(2026, 3, 12, 15, 0, tzinfo=UTC)
    aware_last = datetime(2026, 3, 12, 14, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_prep_policy(
            source="greenhouse",
            now=now_naive,
            daily_prep_timestamps=[],
            source_last_prep_at={},
            policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_prep_policy(
            source="greenhouse",
            now=aware_now,
            daily_prep_timestamps=[datetime(2026, 3, 12, 10, 0)],
            source_last_prep_at={},
            policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_prep_policy(
            source="greenhouse",
            now=aware_now,
            daily_prep_timestamps=[],
            source_last_prep_at={"greenhouse": datetime(2026, 3, 12, 14, 0)},
            policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
        )

    decision = evaluate_prep_policy(
        source="greenhouse",
        now=aware_now,
        daily_prep_timestamps=[],
        source_last_prep_at={"greenhouse": aware_last},
        policy=PrepPolicy(max_preps_per_day=5, source_throttle_interval=timedelta(hours=1)),
    )
    assert decision.allowed is True
