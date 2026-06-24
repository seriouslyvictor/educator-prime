import json
import logging
import os
from datetime import UTC, datetime, timedelta

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.database import engine, init_db
from classroom_downloader.main import app, provider_dependency, settings
from classroom_downloader.models import Activity, Course, UserSession

_FAKE_CREDS_JSON = json.dumps({
    "token": "access-token",
    "refresh_token": "refresh-token",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "client-id",
    "client_secret": "client-secret",
    "scopes": [
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ],
})


def test_courses_exclude_archived() -> None:
    with TestClient(app) as client:
        response = client.get("/api/courses")

    assert response.status_code == 200
    course_ids = {course["id"] for course in response.json()}
    assert "course-1" in course_ids
    assert "course-archived" not in course_ids


def test_course_cache_logs_standard_hit_miss_pair(caplog) -> None:
    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            first = client.get("/api/courses?refresh=true")
            second = client.get("/api/courses")

    assert first.status_code == 200
    assert second.status_code == 200
    messages = [record.message for record in caplog.records]
    assert any("cache.miss cache='classroom.courses' key='active'" in message for message in messages)
    assert any("cache.hit cache='classroom.courses' key='active'" in message for message in messages)


def test_activities_include_classroom_grade_summary() -> None:
    with TestClient(app) as client:
        response = client.get("/api/courses/course-1/activities?refresh=true")

    assert response.status_code == 200
    rows = {activity["id"]: activity for activity in response.json()}
    assert rows["activity-1"]["total_submissions"] == 2
    assert rows["activity-1"]["graded_submissions"] == 1
    assert rows["activity-1"]["ungraded_submissions"] == 1
    assert rows["activity-1"]["concluded"] is False
    assert rows["activity-2"]["total_submissions"] == 1
    assert rows["activity-2"]["graded_submissions"] == 1
    assert rows["activity-2"]["ungraded_submissions"] == 0
    assert rows["activity-2"]["concluded"] is True



def test_export_creates_email_first_manifest_paths() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/exports",
            json={"course_id": "course-1", "activity_ids": ["activity-1"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["total_files"] == 2
    paths = {file["output_path"] for file in body["files"]}
    assert "Biology 101/Cell Diagram/ana.silva@example.edu--diagram.png" in paths
    assert "Biology 101/Cell Diagram/bruno.costa@example.edu--cell-diagram.pdf" in paths


def test_file_content_streams() -> None:
    with TestClient(app) as client:
        job = client.post(
            "/api/exports",
            json={"course_id": "course-1", "activity_ids": ["activity-1"]},
        ).json()
        file_id = job["files"][0]["id"]
        response = client.get(f"/api/exports/{job['id']}/files/{file_id}/content")

    assert response.status_code == 200
    assert response.content


def test_file_content_stream_uses_private_etag_cache() -> None:
    with TestClient(app) as client:
        job = client.post(
            "/api/exports",
            json={"course_id": "course-1", "activity_ids": ["activity-1"]},
        ).json()
        file_id = job["files"][0]["id"]
        first = client.get(f"/api/exports/{job['id']}/files/{file_id}/content")
        second = client.get(
            f"/api/exports/{job['id']}/files/{file_id}/content",
            headers={"If-None-Match": first.headers["etag"]},
        )

    assert first.status_code == 200
    assert first.headers["cache-control"].startswith("private")
    assert first.headers["etag"]
    assert second.status_code == 304


def test_auth_me_profile_failure_keeps_loadable_google_token_signed_in(
    monkeypatch,
) -> None:
    session_id = "test-session-auth-me-failure"
    monkeypatch.setattr(settings, "google_provider", "google")
    init_db()
    with Session(engine) as db:
        db.merge(UserSession(
            id=session_id,
            user_email="teacher@example.edu",
            google_credentials_json=_FAKE_CREDS_JSON,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ))
        db.commit()

    class FailingProvider:
        def account_profile(self):
            raise RuntimeError("stale token")

    monkeypatch.setattr(
        "classroom_downloader.api.deps.make_google_provider", lambda *_, **__: FailingProvider()
    )

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, session_id)
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["signed_in"] is True
    with Session(engine) as db:
        assert db.get(UserSession, session_id) is not None


def test_logout_deletes_google_token(monkeypatch) -> None:
    session_id = "test-session-logout"
    monkeypatch.setattr(settings, "google_provider", "google")
    init_db()
    with Session(engine) as db:
        db.merge(UserSession(
            id=session_id,
            user_email="teacher@example.edu",
            google_credentials_json=_FAKE_CREDS_JSON,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ))
        db.merge(Course(
            id="logout-course", name="Logout", course_state="ACTIVE",
            user_email="teacher@example.edu",
        ))
        db.merge(Activity(
            id="logout-activity", course_id="logout-course", title="Logout activity",
            user_email="teacher@example.edu",
        ))
        db.commit()

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, session_id)
        response = client.post("/api/auth/google/logout")

    assert response.status_code == 200
    assert response.json()["signed_in"] is False
    with Session(engine) as db:
        assert db.get(UserSession, session_id) is None
        assert db.exec(select(Course).where(Course.id == "logout-course")).first() is None
        assert db.exec(select(Activity).where(Activity.id == "logout-activity")).first() is None


def test_courses_reports_expired_google_session_as_unauthorized() -> None:
    from google.auth.exceptions import RefreshError

    class ExpiredProvider:
        def list_courses(self):
            raise RefreshError("expired")

    app.dependency_overrides[provider_dependency] = lambda: ExpiredProvider()
    try:
        with TestClient(app) as client:
            response = client.get("/api/courses?refresh=true")
    finally:
        app.dependency_overrides.pop(provider_dependency, None)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "google_session_expired"
    assert "connect your Google account again" in response.json()["detail"]["message"]


def test_grading_queue_missing_token_returns_401(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_provider", "google")

    with TestClient(app) as client:
        response = client.get(
            "/api/grading/queue",
            params={"course_id": "course-1", "activity_id": "activity-1"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_signed_in"
    assert "Not signed in" in response.json()["detail"]["message"]


def test_transient_403_keeps_token(monkeypatch, tmp_path) -> None:
    from googleapiclient.errors import HttpError

    token_path = tmp_path / "google-user.json"
    token_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "google_provider", "google")
    monkeypatch.setattr(settings, "google_token_path", str(token_path))

    class Response:
        status = 403
        reason = "Forbidden"

    class ForbiddenProvider:
        def list_courses(self):
            raise HttpError(resp=Response(), content=b'{"error":"rateLimitExceeded"}')

    app.dependency_overrides[provider_dependency] = lambda: ForbiddenProvider()
    try:
        with TestClient(app) as client:
            response = client.get("/api/courses?refresh=true")
    finally:
        app.dependency_overrides.pop(provider_dependency, None)

    assert response.status_code == 401
    assert token_path.exists()


def test_static_frontend_serves_index_and_keeps_api_404(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        '<div id="root">Classroom Downloader app shell</div>',
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "static_dir", str(static_dir))

    with TestClient(app) as client:
        root = client.get("/")
        nested = client.get("/grader/final")
        api_missing = client.get("/api/not-a-real-route")

    assert root.status_code == 200
    assert "Classroom Downloader app shell" in root.text
    assert nested.status_code == 200
    assert "Classroom Downloader app shell" in nested.text
    assert api_missing.status_code == 404
    assert api_missing.headers["content-type"].startswith("application/json")


def test_invalid_grant_deletes_token(monkeypatch) -> None:
    from google.auth.exceptions import RefreshError

    session_id = "test-session-invalid-grant"
    monkeypatch.setattr(settings, "google_provider", "google")
    init_db()
    with Session(engine) as db:
        db.merge(UserSession(
            id=session_id,
            user_email="teacher@example.edu",
            google_credentials_json=_FAKE_CREDS_JSON,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ))
        db.commit()

    class InvalidGrantProvider:
        def list_courses(self):
            raise RefreshError("invalid_grant: token revoked")

    app.dependency_overrides[provider_dependency] = lambda: InvalidGrantProvider()
    try:
        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, session_id)
            response = client.get("/api/courses?refresh=true")
    finally:
        app.dependency_overrides.pop(provider_dependency, None)

    assert response.status_code == 401
    with Session(engine) as db:
        assert db.get(UserSession, session_id) is None
