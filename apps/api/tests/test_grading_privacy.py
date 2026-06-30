"""Privacy, pseudonymisation, and audit-gate tests for the grading pipeline.

Tests privacy-audit endpoint shape, redaction of PII in logs and engine payloads,
scrub-cache reuse, audit-gate blocks, and pseudonym stability.
"""

import os
import logging
import json
from datetime import UTC, datetime

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from classroom_downloader.database import engine
from classroom_downloader.content_extraction import extract_submission_content
from classroom_downloader.main import app
from classroom_downloader.grading_engine import (
    GradingEngine,
    GradingEngineRequest,
    GradingEngineResult,
)
from classroom_downloader.models import (
    GradingAiAttempt,
    GradingFileCache,
    GradingJob,
    GradingPseudonym,
    GradingScrubCache,
    PrivacyAudit,
    PrivacyAuditRow,
)
from classroom_downloader.settings import get_settings

from grading_helpers import _sse_payloads


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


def test_privacy_audit_marks_visual_rows_pending_with_consent_and_does_not_cache(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
                "include_visual_submissions": True,
            },
        ).json()
        response = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit")

    assert response.status_code == 200
    body = response.json()
    image_row = next(row for row in body["rows"] if row["mime_type"].startswith("image/"))
    assert image_row["extraction_status"] == "pending_vision"
    assert image_row["extraction_error"] is None
    assert image_row["audit_pass"] is True
    assert image_row["blocked_reason"] is None
    assert body["blocked_files"] == 0

    with Session(engine) as session:
        image_cache = session.exec(
            select(GradingFileCache)
            .where(GradingFileCache.job_id == job["id"])
            .where(GradingFileCache.mime_type == "image/png")
        ).one()
        scrub_rows = session.exec(
            select(GradingScrubCache)
            .where(GradingScrubCache.job_id == job["id"])
            .where(GradingScrubCache.content_hash == image_cache.content_hash)
        ).all()

    assert scrub_rows == []


def test_submission_file_logs_do_not_expose_student_identity(tmp_path, caplog) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with caplog.at_level(logging.INFO):
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
    submission_file_messages = [
        record.message
        for record in caplog.records
        if "submission_files" in record.message or "files_loaded" in record.message
    ]
    assert submission_file_messages
    rendered = "\n".join(submission_file_messages)
    assert "ana.silva@example.edu" not in rendered
    assert "Ana Silva" not in rendered
    assert "'student_email': '<redacted>'" in rendered


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


def test_privacy_audit_stream_emits_progress_and_terminal_event(tmp_path) -> None:
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
        with client.stream("GET", f"/api/grading/jobs/{job['id']}/privacy-audit/stream") as response:
            assert response.status_code == 200
            payloads = _sse_payloads(response)

    progress = [payload for payload in payloads if payload.get("processed")]
    terminal = payloads[-1]
    assert progress
    assert terminal["phase"] == "audit"
    assert terminal["done"] is True
    assert terminal["summary"]["job_id"] == job["id"]
    assert terminal["summary"]["total_files"] == progress[-1]["total"]


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


def test_draft_reuses_privacy_audit_scrub_cache(tmp_path) -> None:
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
        assert audit["total_files"] == 2

        with Session(engine) as session:
            before = session.exec(
                select(GradingScrubCache).where(GradingScrubCache.job_id == job["id"])
            ).all()

        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()

    with Session(engine) as session:
        after = session.exec(
            select(GradingScrubCache).where(GradingScrubCache.job_id == job["id"])
        ).all()

    assert drafted["total_submissions"] == 2
    assert len(before) == 2
    assert len(after) == len(before)


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


def test_grading_engine_only_receives_pseudonymized_payload(
    monkeypatch,
    tmp_path,
) -> None:
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
                "rubric_text": "Focus on evidence quality.",
            },
        ).json()
        from classroom_downloader import grading

        monkeypatch.setattr(
            grading,
            "get_grading_engine",
            lambda: CapturingEngine(),
        )
        client.post(f"/api/grading/jobs/{job['id']}/draft")

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
    assert all(request.rubric_text == "Focus on evidence quality." for request in captured)


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


def test_docx_submission_grades_and_filename_redacted(tmp_path: Path) -> None:
    """Docx vai para extração de texto; filename não aparece no payload ao engine."""
    get_settings().grading_cache_path = str(tmp_path / "grading")
    captured: list[GradingEngineRequest] = []

    class CapturingEngine(GradingEngine):
        name = "capture"
        model = None

        def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
            captured.append(request)
            return GradingEngineResult(
                score=88,
                confidence=0.85,
                feedback="Bom trabalho.",
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
        from classroom_downloader import grading as _grading_module
        import unittest.mock as _mock
        with _mock.patch.object(_grading_module, "get_grading_engine", return_value=CapturingEngine()):
            body = client.post(f"/api/grading/jobs/{job['id']}/draft").json()

    assert captured, "Nenhuma requisição ao engine — a extração falhou para todos os arquivos"
    # Verifica que filenames e dados pessoais não vazam no payload
    payload_text = "\n".join(
        f"{r.student_label}\n{r.source_label}\n{r.content}" for r in captured
    )
    assert "essay draft.docx" not in payload_text
    assert "notas.xlsx" not in payload_text
    assert "apresentacao.pptx" not in payload_text
    assert "diego.lima@example.edu" not in payload_text
    assert "Diego Lima" not in payload_text
    # Todos os student_labels devem ser pseudônimos
    assert all(r.student_label.startswith("student_") for r in captured)
