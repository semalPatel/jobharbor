from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorClassification:
    category: str
    retryable: bool


class PrefillWorkerError(Exception):
    classification = ErrorClassification(category="unknown", retryable=False)

    @classmethod
    def from_error(cls, error: BaseException) -> PrefillWorkerError:
        message = str(error).strip() or cls.classification.category
        instance = cls(message)
        instance.__cause__ = error
        return instance


class TransientPrefillError(PrefillWorkerError):
    classification = ErrorClassification(category="transient", retryable=True)


class AuthExpiredPrefillError(PrefillWorkerError):
    classification = ErrorClassification(category="auth_expired", retryable=False)


class FormChangedPrefillError(PrefillWorkerError):
    classification = ErrorClassification(category="form_changed", retryable=False)


class CaptchaDetectedPrefillError(PrefillWorkerError):
    classification = ErrorClassification(category="captcha_detected", retryable=False)


class ValidationFailedPrefillError(PrefillWorkerError):
    classification = ErrorClassification(category="validation_failed", retryable=False)


def classify_prefill_error(error: BaseException) -> PrefillWorkerError:
    if isinstance(error, PrefillWorkerError):
        return error

    message = str(error).lower()

    if isinstance(error, (TimeoutError, ConnectionError)) or _contains_any(
        message,
        ("timeout", "temporar", "try again", "connection reset", "network"),
    ):
        return TransientPrefillError.from_error(error)

    if _contains_any(
        message,
        ("auth", "unauthor", "forbidden", "session expired", "login required"),
    ):
        return AuthExpiredPrefillError.from_error(error)

    if _contains_any(message, ("captcha", "recaptcha", "hcaptcha")):
        return CaptchaDetectedPrefillError.from_error(error)

    if _contains_any(
        message,
        (
            "selector",
            "strict mode violation",
            "detached",
            "element not found",
            "no node found",
        ),
    ):
        return FormChangedPrefillError.from_error(error)

    if isinstance(error, ValueError) or _contains_any(
        message,
        ("validation", "invalid", "required field", "must be"),
    ):
        return ValidationFailedPrefillError.from_error(error)

    return TransientPrefillError.from_error(error)


def is_retryable_prefill_error(error: BaseException) -> bool:
    return classify_prefill_error(error).classification.retryable


def _contains_any(message: str, terms: tuple[str, ...]) -> bool:
    return any(term in message for term in terms)
