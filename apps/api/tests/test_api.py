import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from classroom_downloader.main import app


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
