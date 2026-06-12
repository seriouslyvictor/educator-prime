"""Google API transient-error classification."""

from fastapi import HTTPException

from ..observability import get_logger, log_warning
from .errors import api_error

logger = get_logger(__name__)


def google_api_http_exception(error: Exception) -> HTTPException | None:
    try:
        from googleapiclient.errors import HttpError
    except Exception:
        return None

    status_code = getattr(getattr(error, "resp", None), "status", None)
    if not isinstance(error, HttpError):
        return None
    if status_code == 429:
        log_warning(logger, "google.api.rate_limited")
        return api_error(
            503,
            "google_rate_limited",
            "Google Classroom or Drive rate limited the request.",
        )
    if isinstance(status_code, int) and status_code >= 500:
        log_warning(logger, "google.api.unavailable", status_code=status_code)
        return api_error(
            503,
            "google_unavailable",
            "Google Classroom or Drive is temporarily unavailable.",
        )
    return None
