from datetime import UTC, datetime, timedelta

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
