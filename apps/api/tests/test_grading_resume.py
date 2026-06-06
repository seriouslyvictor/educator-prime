"""Coverage for the resume/preview additions: the global grading-jobs list and
the per-submission preview stream. Written order-independently (assert on the
created job, not global emptiness) to match the shared in-memory DB used by the
rest of the grading suite."""

import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from classroom_downloader.main import app


def _create_job(client, course_id="course-1", activity_id="activity-1"):
    return client.post(
        "/api/grading/jobs",
        json={
            "course_id": course_id,
            "activity_id": activity_id,
            "rubric_mode": "infer",
            "teacher_loop": "approve",
        },
    ).json()


def test_jobs_list_surfaces_created_job() -> None:
    with TestClient(app) as client:
        job = _create_job(client)
        listing = client.get("/api/grading/jobs").json()

    match = [item for item in listing if item["latest_job_id"] == job["id"]]
    assert len(match) == 1
    assert match[0]["course_name"] == "Biology 101"
    assert match[0]["activity_title"] == "Cell Diagram"
    assert match[0]["activity_id"] == "activity-1"


def test_jobs_list_collapses_to_newest_per_activity() -> None:
    with TestClient(app) as client:
        first = _create_job(client, activity_id="activity-2")
        second = _create_job(client, activity_id="activity-2")
        listing = client.get("/api/grading/jobs").json()

    rows = [item for item in listing if item["activity_id"] == "activity-2"]
    assert len(rows) == 1
    assert rows[0]["latest_job_id"] == second["id"]
    assert second["id"] != first["id"]


def test_submission_preview_streams_image_inline() -> None:
    with TestClient(app) as client:
        job = _create_job(client)  # activity-1's first submission is an image/png
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission = drafted["submissions"][0]
        ok = client.get(
            f"/api/grading/jobs/{job['id']}/submissions/{submission['id']}/preview"
        )
        missing = client.get(
            f"/api/grading/jobs/{job['id']}/submissions/missing/preview"
        )

    assert ok.status_code == 200
    assert ok.content  # cached submission bytes streamed back to the teacher
    assert ok.headers["content-type"].startswith("image/png")
    assert ok.headers["content-disposition"] == "inline"
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert missing.status_code == 404


def test_submission_preview_forces_download_for_unsafe_type() -> None:
    # course-2/activity-3 is a .docx — not on the inline allowlist, so it must be
    # served as an attachment (never rendered as active content on the app origin).
    with TestClient(app) as client:
        job = _create_job(client, course_id="course-2", activity_id="activity-3")
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission = drafted["submissions"][0]
        response = client.get(
            f"/api/grading/jobs/{job['id']}/submissions/{submission['id']}/preview"
        )

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_submission_preview_unknown_job_is_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/grading/jobs/missing/submissions/missing/preview")

    assert response.status_code == 404
