from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, select

from classroom_downloader.database import engine, init_db
from classroom_downloader.grading.attempts import _record_attempt
from classroom_downloader.models import (
    GradingAiAttempt,
    GradingAiAttemptPayload,
    GradingJob,
    GradingSubmission,
)
from classroom_downloader.observability import purge_expired_observability_rows
from classroom_downloader.settings import get_settings


class DummyEngine:
    name = "litellm"
    model = "openai/gpt-5"


def _clear_rows() -> None:
    init_db()
    with Session(engine) as session:
        for row in session.exec(select(GradingAiAttemptPayload)).all():
            session.delete(row)
        for row in session.exec(select(GradingAiAttempt)).all():
            session.delete(row)
        for row in session.exec(select(GradingSubmission)).all():
            session.delete(row)
        for row in session.exec(select(GradingJob)).all():
            session.delete(row)
        session.commit()


def _seed_job_submission(session: Session) -> tuple[GradingJob, GradingSubmission]:
    suffix = uuid4().hex
    job = GradingJob(
        id=f"job-{suffix}",
        course_id="course-1",
        course_name="Course",
        activity_id="activity-1",
        activity_title="Activity",
        rubric_mode="brief",
        teacher_loop="approve",
    )
    submission = GradingSubmission(
        id=f"submission-{suffix}",
        job_id=job.id,
        source_file_id="file-1",
        source_name="submission.txt",
        mime_type="text/plain",
    )
    session.add(job)
    session.add(submission)
    session.commit()
    session.refresh(job)
    session.refresh(submission)
    return job, submission


def test_attempt_payload_logging_on_writes_payload_row() -> None:
    _clear_rows()
    settings = get_settings()
    original = settings.llm_payload_logging
    settings.llm_payload_logging = True
    try:
        with Session(engine) as session:
            job, submission = _seed_job_submission(session)
            attempt = _record_attempt(
                session=session,
                job=job,
                submission=submission,
                engine=DummyEngine(),
                status="completed",
                extraction_status="supported",
                privacy_status="clean",
                flags=[],
                retry_count=0,
                prompt_text="student_1 escreveu texto scrubbed",
                response_text='{"feedback":"ok"}',
            )
            payload = session.get(GradingAiAttemptPayload, attempt.id)

        assert payload is not None
        assert payload.prompt_text == "student_1 escreveu texto scrubbed"
        assert payload.response_text == '{"feedback":"ok"}'
    finally:
        settings.llm_payload_logging = original


def test_attempt_payload_logging_off_skips_payload_row() -> None:
    _clear_rows()
    settings = get_settings()
    original = settings.llm_payload_logging
    settings.llm_payload_logging = False
    try:
        with Session(engine) as session:
            job, submission = _seed_job_submission(session)
            attempt = _record_attempt(
                session=session,
                job=job,
                submission=submission,
                engine=DummyEngine(),
                status="completed",
                extraction_status="supported",
                privacy_status="clean",
                flags=[],
                retry_count=0,
                prompt_text="prompt",
                response_text="response",
            )
            payload = session.get(GradingAiAttemptPayload, attempt.id)

        assert payload is None
    finally:
        settings.llm_payload_logging = original


def test_transport_failure_payload_keeps_prompt_with_null_response() -> None:
    _clear_rows()
    settings = get_settings()
    original = settings.llm_payload_logging
    settings.llm_payload_logging = True
    try:
        with Session(engine) as session:
            job, submission = _seed_job_submission(session)
            attempt = _record_attempt(
                session=session,
                job=job,
                submission=submission,
                engine=DummyEngine(),
                status="failed",
                extraction_status="supported",
                privacy_status="clean",
                flags=[],
                retry_count=0,
                safe_error="api_unavailable",
                retryable=True,
                prompt_text="prompt that failed",
                response_text=None,
            )
            payload = session.get(GradingAiAttemptPayload, attempt.id)

        assert payload is not None
        assert payload.prompt_text == "prompt that failed"
        assert payload.response_text is None
    finally:
        settings.llm_payload_logging = original


def test_purge_removes_expired_payload_but_keeps_attempt() -> None:
    _clear_rows()
    settings = get_settings()
    original_logging = settings.llm_payload_logging
    original_retention = settings.llm_payload_retention_days
    settings.llm_payload_logging = True
    settings.llm_payload_retention_days = 14
    try:
        with Session(engine) as session:
            job, submission = _seed_job_submission(session)
            attempt = _record_attempt(
                session=session,
                job=job,
                submission=submission,
                engine=DummyEngine(),
                status="completed",
                extraction_status="supported",
                privacy_status="clean",
                flags=[],
                retry_count=0,
                prompt_text="old prompt",
                response_text="old response",
            )
            payload = session.get(GradingAiAttemptPayload, attempt.id)
            assert payload is not None
            payload.created_at = datetime.now(UTC) - timedelta(days=15)
            session.add(payload)
            session.commit()

            purge_expired_observability_rows(session)

            assert session.get(GradingAiAttemptPayload, attempt.id) is None
            assert session.get(GradingAiAttempt, attempt.id) is not None
    finally:
        settings.llm_payload_logging = original_logging
        settings.llm_payload_retention_days = original_retention
