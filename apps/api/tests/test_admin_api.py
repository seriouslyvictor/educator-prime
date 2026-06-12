from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.api.deps import get_current_session
from classroom_downloader.database import engine, init_db
from classroom_downloader.main import app
from classroom_downloader.models import (
    AppEvent,
    GradingAiAttempt,
    GradingAiAttemptPayload,
    UserSession,
)
from classroom_downloader.observability import purge_expired_observability_rows
from classroom_downloader.settings import get_settings


def _clear_rows() -> None:
    init_db()
    with Session(engine) as session:
        for model in (GradingAiAttemptPayload, GradingAiAttempt, AppEvent):
            for row in session.exec(select(model)).all():
                session.delete(row)
        session.commit()


def _session_for(email: str) -> UserSession:
    return UserSession(
        id=f"session-{email}",
        user_email=email,
        google_credentials_json="{}",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _seed_admin_rows() -> tuple[str, str]:
    with Session(engine) as session:
        old_event = AppEvent(
            id="event-old",
            created_at=datetime.now(UTC) - timedelta(hours=2),
            level="WARNING",
            event="auth.old",
            logger_name="test",
            user_email="teacher@example.edu",
            fields_json='{"message":"old"}',
        )
        new_event = AppEvent(
            id="event-new",
            created_at=datetime.now(UTC),
            level="ERROR",
            event="grading.failed",
            logger_name="test",
            user_email="admin@example.edu",
            fields_json='{"message":"needle"}',
        )
        attempt_one = GradingAiAttempt(
            id="attempt-1",
            job_id="job-1",
            submission_id="submission-1",
            stage="grading",
            engine="litellm",
            model="openai/gpt-5",
            status="failed",
            extraction_status="supported",
            privacy_status="clean",
            safe_error="api_unavailable",
            retryable=True,
            cost_cents=1.25,
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        attempt_two = GradingAiAttempt(
            id="attempt-2",
            job_id="job-2",
            submission_id="submission-2",
            stage="extraction",
            engine="litellm",
            model="openai/gpt-5",
            status="completed",
            extraction_status="supported",
            privacy_status="pending",
            created_at=datetime.now(UTC),
        )
        payload = GradingAiAttemptPayload(
            attempt_id="attempt-1",
            job_id="job-1",
            prompt_text="prompt",
            response_text="response",
        )
        session.add(old_event)
        session.add(new_event)
        session.add(attempt_one)
        session.add(attempt_two)
        session.add(payload)
        session.commit()
        return old_event.created_at.isoformat(), attempt_two.created_at.isoformat()


def test_non_admin_gets_403_on_admin_routes() -> None:
    _clear_rows()
    settings = get_settings()
    original_provider = settings.google_provider
    original_admins = settings.admin_emails
    settings.google_provider = "google"
    settings.admin_emails = "admin@example.edu"
    app.dependency_overrides[get_current_session] = lambda: _session_for("teacher@example.edu")
    try:
        with TestClient(app) as client:
            paths = [
                "/api/admin/events",
                "/api/admin/llm/attempts",
                "/api/admin/llm/attempts/missing/payload",
                "/api/admin/stats",
            ]
            assert [client.get(path).status_code for path in paths] == [403, 403, 403, 403]
    finally:
        app.dependency_overrides.pop(get_current_session, None)
        settings.google_provider = original_provider
        settings.admin_emails = original_admins


def test_admin_routes_allow_admin_and_filter_results() -> None:
    _clear_rows()
    before_event, before_attempt = _seed_admin_rows()
    settings = get_settings()
    original_provider = settings.google_provider
    original_admins = settings.admin_emails
    settings.google_provider = "google"
    settings.admin_emails = "admin@example.edu"
    app.dependency_overrides[get_current_session] = lambda: _session_for("admin@example.edu")
    try:
        with TestClient(app) as client:
            events = client.get(
                "/api/admin/events",
                params={"level": "ERROR", "event_prefix": "grading.", "q": "needle"},
            )
            attempts = client.get("/api/admin/llm/attempts", params={"job_id": "job-1"})
            older_attempts = client.get(
                "/api/admin/llm/attempts",
                params={"before": before_attempt},
            )
            older_events = client.get("/api/admin/events", params={"before": before_event})
            payload = client.get("/api/admin/llm/attempts/attempt-1/payload")
            stats = client.get("/api/admin/stats")

        assert events.status_code == 200
        assert [row["id"] for row in events.json()] == ["event-new"]
        assert attempts.status_code == 200
        assert attempts.json()[0]["id"] == "attempt-1"
        assert attempts.json()[0]["has_payload"] is True
        assert [row["id"] for row in older_attempts.json()] == ["attempt-1"]
        assert older_events.json() == []
        assert payload.json()["prompt_text"] == "prompt"
        assert stats.status_code == 200
        assert stats.json()["attempts_7d"] == 2
        assert stats.json()["failures_7d"] == 1
    finally:
        app.dependency_overrides.pop(get_current_session, None)
        settings.google_provider = original_provider
        settings.admin_emails = original_admins


def test_mock_provider_is_allowed_for_admin_api() -> None:
    _clear_rows()
    _seed_admin_rows()
    settings = get_settings()
    original_provider = settings.google_provider
    settings.google_provider = "mock"
    try:
        with TestClient(app) as client:
            response = client.get("/api/admin/stats")
        assert response.status_code == 200
    finally:
        settings.google_provider = original_provider


def test_payload_returns_404_after_purge() -> None:
    _clear_rows()
    _seed_admin_rows()
    settings = get_settings()
    original_retention = settings.llm_payload_retention_days
    settings.llm_payload_retention_days = 14
    try:
        with Session(engine) as session:
            payload = session.get(GradingAiAttemptPayload, "attempt-1")
            assert payload is not None
            payload.created_at = datetime.now(UTC) - timedelta(days=15)
            session.add(payload)
            session.commit()
            purge_expired_observability_rows(session)

        with TestClient(app) as client:
            response = client.get("/api/admin/llm/attempts/attempt-1/payload")

        assert response.status_code == 404
    finally:
        settings.llm_payload_retention_days = original_retention


def test_auth_me_reports_is_admin_from_allowlist() -> None:
    settings = get_settings()
    original_provider = settings.google_provider
    original_admins = settings.admin_emails
    settings.google_provider = "mock"
    settings.admin_emails = "teacher@example.edu"
    try:
        with TestClient(app) as client:
            admin_body = client.get("/api/auth/me").json()
        settings.admin_emails = "other@example.edu"
        with TestClient(app) as client:
            non_admin_body = client.get("/api/auth/me").json()

        assert admin_body["is_admin"] is True
        assert non_admin_body["is_admin"] is False
    finally:
        settings.google_provider = original_provider
        settings.admin_emails = original_admins
