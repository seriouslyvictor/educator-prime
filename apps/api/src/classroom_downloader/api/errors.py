"""Shared API error contract for user-facing flow gates."""

from fastapi import HTTPException

ERROR_CODES = (
    "not_signed_in",
    "session_expired",
    "google_session_missing",
    "google_session_expired",
    "google_auth_denied",
    "oauth_not_configured",
    "google_rate_limited",
    "google_unavailable",
    "llm_not_configured",
    "busy_retry",
)


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
