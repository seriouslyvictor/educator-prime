import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.database import engine
from classroom_downloader.main import app, provider_dependency, settings
from classroom_downloader.models import Activity, Course


def test_courses_exclude_archived() -> None:
    with TestClient(app) as client:
        response = client.get("/api/courses")

    assert response.status_code == 200
    course_ids = {course["id"] for course in response.json()}
    assert "course-1" in course_ids
    assert "course-archived" not in course_ids


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


def test_auth_me_does_not_treat_stale_google_token_as_signed_in(
    monkeypatch, tmp_path
) -> None:
    token_path = tmp_path / "google-user.json"
    token_path.write_text(
        """
        {
          "token": "access-token",
          "refresh_token": "refresh-token",
          "client_id": "client-id",
          "client_secret": "client-secret",
          "scopes": [
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "google_provider", "google")
    monkeypatch.setattr(settings, "google_token_path", str(token_path))
    with Session(engine) as session:
        session.merge(Course(id="stale-course", name="Stale", course_state="ACTIVE"))
        session.merge(
            Activity(
                id="stale-activity",
                course_id="stale-course",
                title="Stale activity",
            )
        )
        session.commit()

    class FailingProvider:
        def account_profile(self):
            raise RuntimeError("stale token")

    monkeypatch.setattr(
        "classroom_downloader.main.get_google_provider", lambda: FailingProvider()
    )

    with TestClient(app) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["signed_in"] is False
    assert not token_path.exists()
    with Session(engine) as session:
        assert session.exec(select(Course).where(Course.id == "stale-course")).first() is None
        assert (
            session.exec(select(Activity).where(Activity.id == "stale-activity")).first()
            is None
        )


def test_logout_deletes_google_token(monkeypatch, tmp_path) -> None:
    token_path = tmp_path / "google-user.json"
    token_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "google_provider", "google")
    monkeypatch.setattr(settings, "google_token_path", str(token_path))
    with Session(engine) as session:
        session.merge(Course(id="logout-course", name="Logout", course_state="ACTIVE"))
        session.merge(
            Activity(
                id="logout-activity",
                course_id="logout-course",
                title="Logout activity",
            )
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/auth/google/logout")

    assert response.status_code == 200
    assert response.json()["signed_in"] is False
    assert not token_path.exists()
    with Session(engine) as session:
        assert session.exec(select(Course).where(Course.id == "logout-course")).first() is None
        assert (
            session.exec(select(Activity).where(Activity.id == "logout-activity")).first()
            is None
        )


def test_courses_reports_expired_google_session_as_unauthorized() -> None:
    from google.auth.exceptions import RefreshError

    class ExpiredProvider:
        def list_courses(self):
            raise RefreshError("expired")

    app.dependency_overrides[provider_dependency] = lambda: ExpiredProvider()
    try:
        with TestClient(app) as client:
            response = client.get("/api/courses")
    finally:
        app.dependency_overrides.pop(provider_dependency, None)

    assert response.status_code == 401
    assert "connect your Google account again" in response.json()["detail"]
