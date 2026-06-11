from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.database import engine
from classroom_downloader.main import app, settings
from classroom_downloader.models import (
    GradingAiAttempt,
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingPseudonym,
    GradingScrubCache,
    GradingStatus,
    GradingSubmission,
    GradingSubmissionFile,
    PrivacyAudit,
    PrivacyAuditRow,
)


def _create_job(
    client: TestClient,
    *,
    course_id: str = "course-1",
    activity_id: str = "activity-1",
) -> dict:
    return client.post(
        "/api/grading/jobs",
        json={
            "course_id": course_id,
            "activity_id": activity_id,
            "rubric_mode": "infer",
            "teacher_loop": "approve",
        },
    ).json()


def _seed_other_user_job(session: Session) -> GradingJob:
    job = GradingJob(
        id=f"job-{uuid4()}",
        course_id="course-other",
        course_name="Other Course",
        activity_id=f"activity-{uuid4()}",
        activity_title="Other Activity",
        rubric_mode="infer",
        teacher_loop="approve",
        status=GradingStatus.ready,
        user_email="other@example.edu",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _seed_job_children(session: Session, job_id: str, tmp_path) -> None:
    submission = GradingSubmission(
        id=f"submission-{uuid4()}",
        job_id=job_id,
        source_file_id="source-1",
        source_name="submission.txt",
        mime_type="text/plain",
    )
    cache_file = tmp_path / "grading" / job_id / "submission.txt"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("cached", encoding="utf-8")
    audit = PrivacyAudit(
        id=f"audit-{uuid4()}",
        job_id=job_id,
        status="completed",
    )
    session.add_all(
        [
            submission,
            GradingCriterion(
                id=f"criterion-{uuid4()}",
                job_id=job_id,
                name="Content",
                weight=100,
            ),
            GradingSubmissionFile(
                id=f"file-{uuid4()}",
                job_id=job_id,
                submission_id=submission.id,
                source_file_id="source-1",
                source_name="submission.txt",
                mime_type="text/plain",
            ),
            GradingFileCache(
                id=f"cache-{uuid4()}",
                job_id=job_id,
                submission_id=submission.id,
                source_file_id="source-1",
                source_name="submission.txt",
                mime_type="text/plain",
                cached_path=str(cache_file),
                content_hash="hash",
                byte_size=6,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
            GradingPseudonym(
                id=f"pseudonym-{uuid4()}",
                job_id=job_id,
                submission_id=submission.id,
                student_label="Student 1",
                source_label="Real Student",
            ),
            GradingAiAttempt(
                id=f"attempt-{uuid4()}",
                job_id=job_id,
                submission_id=submission.id,
                engine="mock",
                status="completed",
                extraction_status="supported",
                privacy_status="safe",
            ),
            GradingScrubCache(
                id=f"scrub-{uuid4()}",
                job_id=job_id,
                submission_id=submission.id,
                content_hash="hash",
                identity_hash="identity",
                student_label="Student 1",
                source_label="Real Student",
                safe_source_label="Student 1",
                scrubbed_content="cached",
                extraction_status="supported",
                privacy_status="safe",
                byte_size=6,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
            audit,
            PrivacyAuditRow(
                id=f"audit-row-{uuid4()}",
                audit_id=audit.id,
                job_id=job_id,
                submission_id=submission.id,
                student_label="Student 1",
                redacted_source_name="submission.txt",
                mime_type="text/plain",
                byte_size=6,
                extraction_status="supported",
                privacy_status="safe",
            ),
        ]
    )
    session.commit()


def test_queue_management_routes_are_owner_guarded() -> None:
    with TestClient(app) as client:
        with Session(engine) as session:
            job = _seed_other_user_job(session)
        responses = [
            client.delete(f"/api/grading/jobs/{job.id}"),
            client.post(f"/api/grading/jobs/{job.id}/archive"),
            client.post(f"/api/grading/jobs/{job.id}/hide"),
            client.post(f"/api/grading/jobs/{job.id}/restore"),
        ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404]


def test_delete_grading_job_removes_all_children_and_cache_dir(tmp_path) -> None:
    settings.grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = _create_job(client)
        with Session(engine) as session:
            _seed_job_children(session, job["id"], tmp_path)

        response = client.delete(f"/api/grading/jobs/{job['id']}")

    assert response.status_code == 204
    assert not (tmp_path / "grading" / job["id"]).exists()

    child_tables = [
        GradingCriterion,
        GradingSubmission,
        GradingSubmissionFile,
        GradingFileCache,
        GradingPseudonym,
        GradingAiAttempt,
        GradingScrubCache,
        PrivacyAudit,
        PrivacyAuditRow,
    ]
    with Session(engine) as session:
        assert session.get(GradingJob, job["id"]) is None
        for table in child_tables:
            assert session.exec(select(table).where(table.job_id == job["id"])).all() == []


def test_archive_hide_restore_and_state_filters() -> None:
    with TestClient(app) as client:
        active = _create_job(client, course_id="course-1", activity_id="activity-1")
        archived = _create_job(client, course_id="course-1", activity_id="activity-2")
        hidden = _create_job(client, course_id="course-2", activity_id="activity-3")

        archive_response = client.post(f"/api/grading/jobs/{archived['id']}/archive")
        hide_response = client.post(f"/api/grading/jobs/{hidden['id']}/hide")
        active_listing = client.get("/api/grading/jobs").json()
        archived_listing = client.get("/api/grading/jobs?state=archived").json()
        hidden_listing = client.get("/api/grading/jobs?state=hidden").json()
        all_listing = client.get("/api/grading/jobs?state=all").json()
        unknown_state = client.get("/api/grading/jobs?state=deleted")
        restore_response = client.post(f"/api/grading/jobs/{archived['id']}/restore")
        restored_listing = client.get("/api/grading/jobs").json()

    assert archive_response.status_code == 200
    assert archive_response.json()["queue_state"] == "archived"
    assert hide_response.status_code == 200
    assert hide_response.json()["queue_state"] == "hidden"

    assert active["id"] in {item["latest_job_id"] for item in active_listing}
    assert archived["id"] not in {item["latest_job_id"] for item in active_listing}
    assert hidden["id"] not in {item["latest_job_id"] for item in active_listing}
    assert {item["latest_job_id"] for item in archived_listing} == {archived["id"]}
    assert {item["latest_job_id"] for item in hidden_listing} == {hidden["id"]}
    assert {active["id"], archived["id"], hidden["id"]}.issubset(
        {item["latest_job_id"] for item in all_listing}
    )
    assert unknown_state.status_code == 422
    assert restore_response.status_code == 200
    assert restore_response.json()["queue_state"] == "active"
    assert archived["id"] in {item["latest_job_id"] for item in restored_listing}


def test_queue_state_is_present_in_jobs_and_queue_payloads() -> None:
    with TestClient(app) as client:
        job = _create_job(client, course_id="course-1", activity_id="activity-1")
        jobs_payload = client.get("/api/grading/jobs").json()
        queue_payload = client.get(
            "/api/grading/queue?course_id=course-1&activity_id=activity-1"
        ).json()

    jobs_match = [item for item in jobs_payload if item["latest_job_id"] == job["id"]]
    assert jobs_match[0]["queue_state"] == "active"
    assert queue_payload[0]["queue_state"] == "active"
