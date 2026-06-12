"""FastAPI dependencies: session, user, provider, grading engine."""
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from ..database import get_session
from .. import grading
from ..google_provider import GoogleProvider, make_google_provider
from ..grading_engine import GradingEngine
from ..models import UserSession
from ..observability import current_user_email, get_logger
from ..settings import get_settings
from .auth_errors import google_auth_http_exception
from .session_cleanup import purge_google_session_if_needed

settings = get_settings()
logger = get_logger(__name__)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


_GRADING_ENGINE_ERRORS: dict[str, tuple[int, str]] = {
    "grading_provider_key_missing": (
        503,
        "AI grading is unavailable: the provider API key is missing. "
        "Set it in apps/api/.env and restart the API.",
    ),
    "grading_model_not_enabled": (
        503,
        "AI grading is unavailable: the selected model is not enabled in the "
        "catalog overlay (config/llm-model-overrides.json).",
    ),
    "unknown_grading_engine": (500, "AI grading engine is misconfigured."),
}


def get_current_session(
    request: Request,
    db: Session = Depends(get_session),
) -> UserSession:
    if settings.google_provider == "mock":
        row = UserSession(
            id="mock-session",
            user_email="teacher@example.edu",
            google_credentials_json="{}",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        current_user_email.set(row.user_email)
        return row
    cookie_name = settings.session_cookie_name
    session_id = request.cookies.get(cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not signed in.")
    row = db.get(UserSession, session_id)
    if row is None or _as_utc(row.expires_at) < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    row.last_seen_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    current_user_email.set(row.user_email)
    return row


def get_current_user_email(
    current_session: UserSession = Depends(get_current_session),
) -> str:
    return current_session.user_email


def provider_dependency(
    current_session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_session),
) -> GoogleProvider:
    try:
        return make_google_provider(current_session.id, db)
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            purge_google_session_if_needed(auth_failure, current_session, db)
            raise auth_failure.http from error
        raise


def resolve_grading_engine() -> GradingEngine:
    """Build the grading engine, translating config failures (missing key /
    disabled model) into a clear HTTP error before any work is done. Resolved via
    the grading module so test monkeypatches of grading.get_grading_engine apply."""
    try:
        return grading.get_grading_engine()
    except ValueError as error:
        status_code, detail = _GRADING_ENGINE_ERRORS.get(
            str(error), (500, "AI grading engine error.")
        )
        raise HTTPException(status_code=status_code, detail=detail) from error
