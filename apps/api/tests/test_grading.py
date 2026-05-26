import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.database import engine
from classroom_downloader.content_extraction import extract_submission_content
from classroom_downloader.main import app
from classroom_downloader.grading_engine import GradingEngine, GradingEngineRequest, GradingEngineResult
from classroom_downloader.models import (
    GradingAiAttempt,
    GradingFileCache,
    GradingPseudonym,
    PrivacyAudit,
    PrivacyAuditRow,
)
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


def test_privacy_audit_endpoint_returns_safe_report_shape(tmp_path) -> None:
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
        response = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job["id"]
    assert body["total_files"] == 2
    assert body["passed_files"] + body["blocked_files"] == 2
    assert "rows" in body
    assert len(body["rows"]) == 2
    assert all(row["student_label"].startswith("student_") for row in body["rows"])
    assert all("@" not in row["student_label"] for row in body["rows"])
    assert all("student_email" not in row for row in body["rows"])
    assert all("student_name" not in row for row in body["rows"])
    assert {row["redacted_source_name"] for row in body["rows"]} == {
        "submission.gdoc",
        "submission.png",
    }
    assert all("diagram" not in row["redacted_source_name"] for row in body["rows"])


def test_privacy_audit_exports_safe_csv_and_json(tmp_path) -> None:
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
        audit = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit").json()
        csv_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit/export.csv")
        json_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit/export.json")

    assert csv_response.status_code == 200
    assert json_response.status_code == 200
    assert "ana.silva@example.edu" not in csv_response.text
    assert "Bruno Costa" not in csv_response.text
    assert "diagram.png" not in csv_response.text
    assert "submission.png" in csv_response.text
    exported = json_response.json()
    assert exported["id"] == audit["id"]
    assert "ana.silva@example.edu" not in json_response.text
    assert all("student_email" not in row for row in exported["rows"])


def test_safe_source_label_does_not_preserve_drive_id_suffix(tmp_path) -> None:
    drive_id = "drive.identifier.with.suffix"
    path = tmp_path / drive_id
    path.write_text("student work", encoding="utf-8")
    cache = GradingFileCache(
        id="cache-1",
        job_id="job-1",
        submission_id="submission-1",
        source_file_id=drive_id,
        source_name=drive_id,
        mime_type="text/plain",
        cached_path=str(path),
        content_hash="not-used",
        byte_size=path.stat().st_size,
        expires_at=datetime.now(UTC),
    )

    extracted = extract_submission_content(cache)

    assert extracted.safe_source_label == "submission"
    assert "identifier" not in extracted.safe_source_label
    assert "suffix" not in extracted.safe_source_label


def test_safe_source_label_does_not_preserve_identifier_like_suffixes(tmp_path) -> None:
    for source_name in ["Ana.Silva", "ana.silva@example.edu"]:
        path = tmp_path / source_name
        path.write_text("student work", encoding="utf-8")
        cache = GradingFileCache(
            id=f"cache-{source_name}",
            job_id="job-1",
            submission_id=f"submission-{source_name}",
            source_file_id=f"drive-{source_name}",
            source_name=source_name,
            mime_type="text/plain",
            cached_path=str(path),
            content_hash="not-used",
            byte_size=path.stat().st_size,
            expires_at=datetime.now(UTC),
        )

        extracted = extract_submission_content(cache)

        assert extracted.safe_source_label == "submission"
        assert "silva" not in extracted.safe_source_label.lower()
        assert "edu" not in extracted.safe_source_label.lower()


def test_draft_auto_runs_privacy_audit_when_missing(tmp_path) -> None:
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
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        audit_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit")

    assert drafted["total_submissions"] == 2
    assert audit_response.status_code == 200
    assert audit_response.json()["total_files"] == 2


def test_draft_blocks_when_latest_audit_has_high_risk_rows(tmp_path) -> None:
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
        audit = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit").json()

        with Session(engine) as session:
            row = session.get(PrivacyAuditRow, audit["rows"][0]["id"])
            assert row is not None
            row.privacy_status = "high_reidentification_risk"
            row.blocked_reason = "high_reidentification_risk"
            session.add(row)
            report = session.get(PrivacyAudit, audit["id"])
            assert report is not None
            report.high_risk_files = 1
            report.blocked_files = max(report.blocked_files, 1)
            session.add(report)
            session.commit()

        response = client.post(f"/api/grading/jobs/{job['id']}/draft")

    assert response.status_code == 409
    assert "Privacy audit" in response.json()["detail"]


def test_draft_reruns_incomplete_latest_privacy_audit(tmp_path) -> None:
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

        with Session(engine) as session:
            incomplete = PrivacyAudit(
                id="incomplete-audit",
                job_id=job["id"],
                status="running",
                total_files=0,
                passed_files=0,
                blocked_files=0,
                high_risk_files=0,
            )
            session.add(incomplete)
            session.commit()

        response = client.post(f"/api/grading/jobs/{job['id']}/draft")
        audit_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit")

    assert response.status_code == 200
    latest = audit_response.json()
    assert latest["id"] != "incomplete-audit"
    assert latest["status"] in {"completed", "completed_with_blocks"}
    assert latest["total_files"] == 2


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


def test_draft_job_records_privacy_attempt_metadata(tmp_path) -> None:
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
        body = client.post(f"/api/grading/jobs/{job['id']}/draft").json()

    assert all("privacy_status" in row for row in body["submissions"])
    assert all("extraction_status" in row for row in body["submissions"])
    assert all("ai_attempt_status" in row for row in body["submissions"])

    with Session(engine) as session:
        attempts = session.exec(
            select(GradingAiAttempt).where(GradingAiAttempt.job_id == job["id"])
        ).all()

    assert len(attempts) == body["total_submissions"]
    assert {attempt.engine for attempt in attempts} == {"mock"}
    assert {attempt.status for attempt in attempts} <= {"completed", "blocked"}
    assert all(attempt.privacy_status for attempt in attempts)
    assert all(attempt.extraction_status for attempt in attempts)


def test_grading_engine_only_receives_pseudonymized_payload(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    captured: list[GradingEngineRequest] = []

    class CapturingEngine(GradingEngine):
        name = "capture"

        def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
            captured.append(request)
            return GradingEngineResult(
                score=91,
                confidence=0.88,
                feedback="Pseudonymized draft feedback.",
                flags=[],
            )

    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-2",
                "activity_id": "activity-3",
                "rubric_mode": "brief",
                "teacher_loop": "approve",
            },
        ).json()
        from classroom_downloader import grading

        original = grading.DEFAULT_GRADING_ENGINE
        grading.DEFAULT_GRADING_ENGINE = CapturingEngine()
        try:
            client.post(f"/api/grading/jobs/{job['id']}/draft")
        finally:
            grading.DEFAULT_GRADING_ENGINE = original

    assert captured
    payload = "\n".join(
        "\n".join(
            [
                request.student_label,
                request.source_label,
                request.content,
                request.activity_title,
            ]
        )
        for request in captured
    )
    assert "Diego Lima" not in payload
    assert "diego.lima@example.edu" not in payload
    assert "essay draft.docx" not in payload
    assert all(request.student_label.startswith("student_") for request in captured)


def test_pseudonym_mapping_is_local_and_stable_across_retry(tmp_path) -> None:
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
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission = drafted["submissions"][0]

        with Session(engine) as session:
            pseudonym = session.exec(
                select(GradingPseudonym)
                .where(GradingPseudonym.job_id == job["id"])
                .where(GradingPseudonym.submission_id == submission["id"])
            ).one()
            first_label = pseudonym.student_label

        client.post(f"/api/grading/jobs/{job['id']}/submissions/{submission['id']}/retry")

    with Session(engine) as session:
        pseudonyms = session.exec(
            select(GradingPseudonym)
            .where(GradingPseudonym.job_id == job["id"])
            .where(GradingPseudonym.submission_id == submission["id"])
        ).all()

    assert len(pseudonyms) == 1
    assert pseudonyms[0].student_label == first_label
    assert submission["student_email"] not in first_label
    assert submission["source_file_id"] not in first_label


def test_unsupported_submission_blocks_normal_ai_draft(tmp_path) -> None:
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
        body = client.post(f"/api/grading/jobs/{job['id']}/draft").json()

    visual_submission = next(row for row in body["submissions"] if row["mime_type"].startswith("image/"))
    assert visual_submission["ai_attempt_status"] == "blocked"
    assert visual_submission["privacy_status"] == "failed"
    assert visual_submission["extraction_status"] == "unsupported"
    assert visual_submission["ai_score"] is None
    assert visual_submission["error"] == "unsupported_visual_submission"


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
