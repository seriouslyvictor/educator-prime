from dataclasses import dataclass

from litellm import exceptions as litellm_exceptions


@dataclass(frozen=True)
class LlmCallError(Exception):
    code: str
    retryable: bool
    detail: str | None = None

    def __str__(self) -> str:
        return self.code


def classify_llm_exception(exc: Exception) -> LlmCallError:
    if isinstance(exc, LlmCallError):
        return exc
    if isinstance(
        exc,
        (
            litellm_exceptions.ServiceUnavailableError,
            litellm_exceptions.InternalServerError,
        ),
    ):
        return LlmCallError("api_unavailable", True, _detail(exc))
    if isinstance(exc, litellm_exceptions.RateLimitError):
        return LlmCallError("api_rate_limited", True, _detail(exc))
    if isinstance(exc, litellm_exceptions.Timeout):
        return LlmCallError("api_timeout", True, _detail(exc))
    if isinstance(exc, litellm_exceptions.APIConnectionError):
        return LlmCallError("api_connection", True, _detail(exc))
    if isinstance(
        exc,
        (
            litellm_exceptions.AuthenticationError,
            litellm_exceptions.PermissionDeniedError,
        ),
    ):
        return LlmCallError("api_auth_failed", False, _detail(exc))
    if isinstance(exc, litellm_exceptions.ContextWindowExceededError):
        return LlmCallError("context_window_exceeded", False, _detail(exc))
    if isinstance(exc, litellm_exceptions.ContentPolicyViolationError):
        return LlmCallError("content_blocked", False, _detail(exc))
    if isinstance(exc, litellm_exceptions.BadRequestError):
        detail = _detail(exc)
        if _looks_like_safety_block(detail):
            return LlmCallError("content_blocked", False, detail)
        return LlmCallError("api_bad_request", False, detail)
    if isinstance(exc, ValueError) and str(exc) == "malformed_llm_response":
        return LlmCallError("malformed_llm_response", True, _detail(exc))
    return LlmCallError("llm_call_failed", False, _detail(exc))


def _detail(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _looks_like_safety_block(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "safety",
            "blocked",
            "block_reason",
            "content policy",
            "policy violation",
        )
    )
