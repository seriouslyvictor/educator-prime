from datetime import UTC, datetime, timedelta
import sqlite3
import asyncio

from fastapi.testclient import TestClient
from sqlmodel import Session

from classroom_downloader.api.auth_errors import google_auth_http_exception
from classroom_downloader.api.errors import ERROR_CODES, api_error
from classroom_downloader.api.google_errors import google_api_http_exception
from classroom_downloader.database import engine, init_db
from classroom_downloader.llm_errors import classify_llm_exception
from classroom_downloader.main import app, settings, sqlite_operational_error_handler
from classroom_downloader.models import UserSession


def test_error_registry_has_unique_codes() -> None:
    assert len(ERROR_CODES) == len(set(ERROR_CODES))
    assert {
        "not_signed_in",
        "session_expired",
        "google_session_missing",
        "google_session_expired",
        "google_auth_denied",
        "google_permission_required",
        "oauth_not_configured",
        "google_rate_limited",
        "google_unavailable",
        "llm_not_configured",
        "busy_retry",
    }.issubset(ERROR_CODES)


def test_api_error_uses_structured_detail() -> None:
    error = api_error(503, "busy_retry", "Database is locked.")

    assert error.status_code == 503
    assert error.detail == {"code": "busy_retry", "message": "Database is locked."}


def test_api_error_accepts_metadata_fields() -> None:
    error = api_error(
        403,
        "google_permission_required",
        "Google permission is required for this action.",
        capability="drive_read",
        missing_scopes=["scope-a"],
    )

    assert error.detail == {
        "code": "google_permission_required",
        "message": "Google permission is required for this action.",
        "capability": "drive_read",
        "missing_scopes": ["scope-a"],
    }


def test_missing_session_returns_not_signed_in_code(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_provider", "google")

    with TestClient(app) as client:
        response = client.get("/api/grading/jobs")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_signed_in"


def test_expired_session_returns_session_expired_code(monkeypatch) -> None:
    session_id = "expired-session"
    monkeypatch.setattr(settings, "google_provider", "google")
    init_db()
    with Session(engine) as db:
        db.merge(
            UserSession(
                id=session_id,
                user_email="teacher@example.edu",
                google_credentials_json="{}",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db.commit()

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, session_id)
        response = client.get("/api/grading/jobs")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "session_expired"


def test_oauth_not_configured_returns_code(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_provider", "google")
    monkeypatch.setattr(settings, "google_client_id", "")
    monkeypatch.setattr(settings, "google_client_secret", "")

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/google/start",
            json={"capability": "identity", "reason": "Sign in"},
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "oauth_not_configured"


def test_google_auth_failures_return_codes() -> None:
    from google.auth.exceptions import RefreshError

    missing = google_auth_http_exception(FileNotFoundError("missing token"))
    expired = google_auth_http_exception(RefreshError("invalid_grant"))

    assert missing is not None
    assert missing.http.detail["code"] == "google_session_missing"
    assert expired is not None
    assert expired.http.detail["code"] == "google_session_expired"


def test_google_api_classifier_maps_rate_limit_and_unavailable() -> None:
    from googleapiclient.errors import HttpError

    class RateLimited:
        status = 429
        reason = "Too Many Requests"

    class ServerError:
        status = 503
        reason = "Unavailable"

    rate_limited = google_api_http_exception(HttpError(RateLimited(), b"{}"))
    unavailable = google_api_http_exception(HttpError(ServerError(), b"{}"))

    assert rate_limited is not None
    assert rate_limited.status_code == 503
    assert rate_limited.detail["code"] == "google_rate_limited"
    assert unavailable is not None
    assert unavailable.status_code == 503
    assert unavailable.detail["code"] == "google_unavailable"


def test_llm_budget_exhausted_is_non_retryable() -> None:
    from litellm import exceptions as litellm_exceptions

    error = classify_llm_exception(litellm_exceptions.BudgetExceededError(12.0, 10.0))

    assert error.code == "api_budget_exhausted"
    assert error.retryable is False


def test_database_locked_returns_busy_retry_code() -> None:
    response = asyncio.run(
        sqlite_operational_error_handler(
            None,
            sqlite3.OperationalError("database is locked"),
        )
    )

    assert response.status_code == 503
    assert response.body
    assert b'"code":"busy_retry"' in response.body


def test_responses_include_app_version_header() -> None:
    with TestClient(app) as client:
        response = client.get("/api/auth/me")

    assert response.headers["x-app-version"] == app.version
