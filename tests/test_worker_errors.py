import pytest

from jobharbor.workers.greenhouse_prefill import (
    classify_prefill_exception,
    should_retry_prefill_exception,
)
from jobharbor.workers.errors import (
    AuthExpiredPrefillError,
    CaptchaDetectedPrefillError,
    FormChangedPrefillError,
    TransientPrefillError,
    ValidationFailedPrefillError,
    classify_prefill_error,
    is_retryable_prefill_error,
)


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (TimeoutError("navigation timed out"), TransientPrefillError),
        (RuntimeError("session expired please log in"), AuthExpiredPrefillError),
        (RuntimeError("selector not found for required field"), FormChangedPrefillError),
        (RuntimeError("captcha challenge detected"), CaptchaDetectedPrefillError),
        (ValueError("validation failed: required email"), ValidationFailedPrefillError),
    ],
)
def test_classify_prefill_error_maps_known_exception_patterns(
    error: Exception,
    expected_type: type[Exception],
) -> None:
    classified = classify_prefill_error(error)

    assert isinstance(classified, expected_type)
    assert classified.__cause__ is error


def test_retryability_only_for_transient_errors() -> None:
    transient = classify_prefill_error(TimeoutError("temporary network issue"))
    auth_expired = classify_prefill_error(RuntimeError("auth token expired"))

    assert is_retryable_prefill_error(transient) is True
    assert is_retryable_prefill_error(auth_expired) is False


def test_greenhouse_prefill_error_helpers_delegate_to_taxonomy() -> None:
    err = classify_prefill_exception(RuntimeError("captcha required"))

    assert isinstance(err, CaptchaDetectedPrefillError)
    assert should_retry_prefill_exception(err) is False
    assert should_retry_prefill_exception(TimeoutError("try again")) is True
