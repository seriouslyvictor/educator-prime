"""Google auth-error → HTTP translation.  Pure, no side effects."""
from dataclasses import dataclass

from fastapi import HTTPException

from ..observability import get_logger, log_warning
from .errors import api_error

logger = get_logger(__name__)


@dataclass(frozen=True)
class AuthFailure:
    http: HTTPException
    purge_token: bool = False


def _contains_invalid_grant(error: Exception) -> bool:
    haystack = " ".join(str(part) for part in getattr(error, "args", ()) if part)
    haystack = f"{haystack} {error}".lower()
    return "invalid_grant" in haystack


def _http_error_content(error: Exception) -> str:
    content = getattr(error, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="ignore").lower()
    return str(content).lower()


def _http_403_is_hard_auth_failure(error: Exception) -> bool:
    content = _http_error_content(error)
    hard_markers = (
        "invalid_grant",
        "invalid credentials",
        "autherror",
        "unauthorized_client",
    )
    return any(marker in content for marker in hard_markers)


def google_auth_http_exception(error: Exception) -> AuthFailure | None:
    if isinstance(error, FileNotFoundError):
        log_warning(logger, "google.auth.token_missing")
        return AuthFailure(
            api_error(
                401,
                "google_session_missing",
                "Google session missing. Please connect your Google account again.",
            ),
            purge_token=False,
        )
    try:
        from google.auth.exceptions import RefreshError
        from googleapiclient.errors import HttpError
    except Exception:
        return None

    if isinstance(error, RefreshError):
        purge_token = _contains_invalid_grant(error)
        log_warning(logger, "google.auth.refresh_failed", purge_token=purge_token)
        return AuthFailure(
            api_error(
                401,
                "google_session_expired",
                "Google session expired. Please connect your Google account again.",
            ),
            purge_token=purge_token,
        )
    status_code = getattr(getattr(error, "resp", None), "status", None)
    if isinstance(error, HttpError) and status_code in {401, 403}:
        purge_token = status_code == 403 and _http_403_is_hard_auth_failure(error)
        log_warning(
            logger,
            "google.auth.api_denied",
            status_code=status_code,
            purge_token=purge_token,
        )
        return AuthFailure(
            api_error(
                401,
                "google_auth_denied",
                "Google authorization failed. Please connect your Google account again.",
            ),
            purge_token=purge_token,
        )
    return None
