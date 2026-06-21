"""Google API transient-error classification."""
import json

from fastapi import HTTPException

from ..observability import get_logger, log_warning
from .errors import api_error

logger = get_logger(__name__)


def _http_error_reason(error: Exception) -> str:
    content = getattr(error, "content", b"")
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="ignore")
    if not isinstance(content, str):
        return ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content.lower()
    reasons: list[str] = []
    for item in payload.get("error", {}).get("errors", []):
        if isinstance(item, dict):
            for key in ("reason", "message"):
                value = item.get(key)
                if isinstance(value, str):
                    reasons.append(value)
    message = payload.get("error", {}).get("message")
    if isinstance(message, str):
        reasons.append(message)
    return " ".join(reasons).lower()


def google_api_http_exception(error: Exception) -> HTTPException | None:
    try:
        from googleapiclient.errors import HttpError
    except Exception:
        return None

    status_code = getattr(getattr(error, "resp", None), "status", None)
    if not isinstance(error, HttpError):
        return None
    if status_code == 403:
        reason = _http_error_reason(error)
        classroom_unavailable_markers = (
            "classroom api has not been used",
            "classroom is not enabled",
            "classroom disabled",
            "not eligible to use classroom",
            "access to classroom is denied",
            "classroomnotavailable",
        )
        if any(marker in reason for marker in classroom_unavailable_markers):
            log_warning(logger, "google.api.classroom_not_available")
            return api_error(
                403,
                "classroom_not_available",
                "This Google account cannot access Classroom.",
            )
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
