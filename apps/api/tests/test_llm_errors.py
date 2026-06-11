import httpx
from litellm import exceptions as litellm_exceptions

from classroom_downloader.llm_errors import LlmCallError, classify_llm_exception


def _response(status_code: int = 400) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", "https://example.test"))


def test_classifies_litellm_exceptions() -> None:
    cases = [
        (
            litellm_exceptions.ServiceUnavailableError("down", "openai", "gpt"),
            "api_unavailable",
            True,
        ),
        (
            litellm_exceptions.InternalServerError("down", "openai", "gpt"),
            "api_unavailable",
            True,
        ),
        (
            litellm_exceptions.RateLimitError("limit", "openai", "gpt"),
            "api_rate_limited",
            True,
        ),
        (
            litellm_exceptions.Timeout("timeout", model="gpt", llm_provider="openai"),
            "api_timeout",
            True,
        ),
        (
            litellm_exceptions.APIConnectionError("conn", "openai", "gpt"),
            "api_connection",
            True,
        ),
        (
            litellm_exceptions.AuthenticationError("auth", "openai", "gpt"),
            "api_auth_failed",
            False,
        ),
        (
            litellm_exceptions.PermissionDeniedError("denied", "openai", "gpt", _response(403)),
            "api_auth_failed",
            False,
        ),
        (
            litellm_exceptions.ContextWindowExceededError("too large", "gpt", "openai"),
            "context_window_exceeded",
            False,
        ),
        (
            litellm_exceptions.ContentPolicyViolationError("blocked", "gpt", "openai"),
            "content_blocked",
            False,
        ),
        (
            litellm_exceptions.BadRequestError("bad", "gpt", "openai"),
            "api_bad_request",
            False,
        ),
        (ValueError("malformed_llm_response"), "malformed_llm_response", True),
        (RuntimeError("boom"), "llm_call_failed", False),
    ]

    for exc, code, retryable in cases:
        classified = classify_llm_exception(exc)
        assert classified.code == code
        assert classified.retryable is retryable


def test_classifies_gemini_safety_bad_request_as_content_blocked() -> None:
    exc = litellm_exceptions.BadRequestError(
        "Gemini response blocked by safety settings",
        "gemini/gemini-2.5-flash",
        "gemini",
    )

    classified = classify_llm_exception(exc)

    assert classified.code == "content_blocked"
    assert classified.retryable is False


def test_existing_llm_call_error_passes_through() -> None:
    exc = LlmCallError("api_timeout", True, "detail")

    assert classify_llm_exception(exc) is exc
