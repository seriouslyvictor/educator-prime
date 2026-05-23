import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.database import engine
from classroom_downloader.main import app
from classroom_downloader.models import GradingFileCache
from classroom_downloader.settings import get_settings


def test_grading_queue_lists_ready_assignments() -> None:
    with TestClient(app) as client:
        response = client.get("/api/grading/queue")

    assert response.status_code == 200
    items = response.json()
    assert {item["activity_id"] for item in items} >= {"activity-1", "activity-2"}
    cell_diagram = next(item for item in items if item["activity_id"] == "activity-1")
    assert cell_diagram["submission_count"] == 2
    assert cell_diagram["status"] in {"ready", "reviewing", "completed"}


def test_draft_job_creates_submissions_criteria_and_cache(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        response = client.post(f"/api/grading/jobs/{job['id']}/draft")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reviewing"
    assert body["total_submissions"] == 2
    assert len(body["criteria"]) == 4
    assert len(body["cache_files"]) == 2
    assert all(Path(row["content_hash"]).name for row in body["cache_files"])
    assert all(Path(tmp_path / "grading" / body["id"]).exists() for _ in body["cache_files"])


def test_retry_reuses_cache_before_expiry_and_refetches_after(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "brief",
                "teacher_loop": "approve",
            },
        ).json()
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission_id = drafted["submissions"][0]["id"]
        before = len(drafted["cache_files"])

        reused = client.post(
            f"/api/grading/jobs/{job['id']}/submissions/{submission_id}/retry"
        ).json()
        assert len(reused["cache_files"]) == before

        with Session(engine) as session:
            cache = session.exec(
                select(GradingFileCache)
                .where(GradingFileCache.job_id == job["id"])
                .where(GradingFileCache.submission_id == submission_id)
            ).first()
            assert cache is not None
            cache.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            session.add(cache)
            session.commit()

        refetched = client.post(
            f"/api/grading/jobs/{job['id']}/submissions/{submission_id}/retry"
        ).json()

    assert len(refetched["cache_files"]) == before + 1


def test_delete_cache_preserves_results_and_marks_metadata(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "structured",
                "teacher_loop": "approve",
            },
        ).json()
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        cache_path = tmp_path / "grading" / job["id"]
        assert cache_path.exists()

        deleted = client.delete(f"/api/grading/jobs/{job['id']}/cache").json()

    assert len(deleted["submissions"]) == len(drafted["submissions"])
    assert deleted["cache_expires_at"] is None
    assert all(row["deleted_at"] for row in deleted["cache_files"])
    assert not cache_path.exists()


def test_grading_csv_includes_teacher_edits(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "saved",
                "teacher_loop": "approve",
            },
        ).json()
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission_id = drafted["submissions"][0]["id"]
        client.post(
            f"/api/grading/jobs/{job['id']}/submissions/{submission_id}/review",
            json={
                "final_score": 88,
                "feedback": "Teacher-edited feedback",
                "reviewed": True,
            },
        )
        response = client.get(f"/api/grading/jobs/{job['id']}/export.csv")

    assert response.status_code == 200
    assert "Teacher-edited feedback" in response.text
    assert "88" in response.text
