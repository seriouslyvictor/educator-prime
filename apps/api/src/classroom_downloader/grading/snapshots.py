import json

from sqlmodel import Session, select

from ..models import (
    GradingAiAttempt,
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingSubmission,
    GradingSubmissionFile,
)
from ..observability import get_logger
from ..schemas import (
    GradingCriterionRead,
    GradingFileCacheRead,
    GradingJobRead,
    GradingSubmissionFileRead,
    GradingSubmissionRead,
)
from ._common import _iso
from .submissions import submission_files

logger = get_logger(__name__)


def _submission_read(
    submission: GradingSubmission,
    attempt: GradingAiAttempt | None,
    files: list[GradingSubmissionFile] | None = None,
) -> GradingSubmissionRead:
    file_rows = files if files is not None else [
        GradingSubmissionFile(
            id=submission.id,
            job_id=submission.job_id,
            submission_id=submission.id,
            source_file_id=submission.source_file_id,
            source_name=submission.source_name,
            mime_type=submission.mime_type,
        )
    ]
    return GradingSubmissionRead(
        id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        mime_type=submission.mime_type,
        files=[
            GradingSubmissionFileRead(
                source_file_id=row.source_file_id,
                source_name=row.source_name,
                mime_type=row.mime_type,
            )
            for row in file_rows
        ],
        ai_score=submission.ai_score,
        confidence=submission.confidence,
        final_score=submission.final_score,
        feedback=submission.feedback,
        reviewed=submission.reviewed,
        flag=submission.flag,
        error=submission.error,
        classroom_submission_id=submission.classroom_submission_id,
        alternate_link=submission.alternate_link,
        posted_to_classroom=submission.posted_to_classroom,
        posted_at=_iso(submission.posted_at),
        privacy_status=attempt.privacy_status if attempt else None,
        extraction_status=attempt.extraction_status if attempt else None,
        ai_attempt_status=attempt.status if attempt else None,
        error_retryable=attempt.retryable if attempt else False,
        ai_engine=attempt.engine if attempt else None,
        ai_model=attempt.model if attempt else None,
        ai_safe_error=attempt.safe_error if attempt else None,
        ai_flags=json.loads(attempt.flags_json) if attempt else [],
        privacy_flags=(
            json.loads(attempt.privacy_flags_json)
            if attempt and attempt.privacy_flags_json
            else []
        ),
        ai_prompt_tokens=attempt.prompt_tokens if attempt else None,
        ai_completion_tokens=attempt.completion_tokens if attempt else None,
        ai_token_count=attempt.token_count if attempt else None,
        ai_cached_prompt_tokens=attempt.cached_prompt_tokens if attempt else None,
        ai_cache_write_tokens=attempt.cache_write_tokens if attempt else None,
        ai_cost_cents=attempt.cost_cents if attempt else None,
        ai_latency_ms=attempt.latency_ms if attempt else None,
    )


def grading_job_snapshot(session: Session, job: GradingJob) -> GradingJobRead:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    criteria = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job.id)
    ).all()
    cache_files = session.exec(
        select(GradingFileCache).where(GradingFileCache.job_id == job.id)
    ).all()
    attempts = session.exec(
        select(GradingAiAttempt)
        .where(GradingAiAttempt.job_id == job.id)
        .order_by(GradingAiAttempt.created_at.desc())
    ).all()
    latest_attempts: dict[str, GradingAiAttempt] = {}
    for attempt in attempts:
        latest_attempts.setdefault(attempt.submission_id, attempt)
    file_rows = session.exec(
        select(GradingSubmissionFile)
        .where(GradingSubmissionFile.job_id == job.id)
        .order_by(GradingSubmissionFile.created_at)
    ).all()
    files_by_submission: dict[str, list[GradingSubmissionFile]] = {}
    for row in file_rows:
        files_by_submission.setdefault(row.submission_id, []).append(row)
    return GradingJobRead(
        id=job.id,
        course_id=job.course_id,
        course_name=job.course_name,
        activity_id=job.activity_id,
        activity_title=job.activity_title,
        rubric_mode=job.rubric_mode,
        teacher_loop=job.teacher_loop,
        rubric_text=job.rubric_text,
        batch_mode=job.batch_mode,
        include_visual_submissions=job.include_visual_submissions,
        queue_state=job.queue_state,
        status=job.status,
        total_submissions=job.total_submissions,
        reviewed_submissions=job.reviewed_submissions,
        flagged_submissions=job.flagged_submissions,
        total_prompt_tokens=job.total_prompt_tokens,
        total_completion_tokens=job.total_completion_tokens,
        total_cached_tokens=job.total_cached_tokens,
        total_cost_cents=job.total_cost_cents,
        wall_clock_ms=job.wall_clock_ms,
        submissions_graded=job.submissions_graded,
        ai_engine=job.ai_engine,
        ai_mode=job.ai_mode,
        ai_model=job.ai_model,
        cache_expires_at=_iso(job.cache_expires_at),
        criteria=[
            GradingCriterionRead.model_validate(row, from_attributes=True)
            for row in criteria
        ],
        submissions=[
            _submission_read(
                row,
                latest_attempts.get(row.id),
                files_by_submission.get(row.id),
            )
            for row in submissions
        ],
        cache_files=[
            GradingFileCacheRead(
                id=row.id,
                submission_id=row.submission_id,
                source_file_id=row.source_file_id,
                source_name=row.source_name,
                mime_type=row.mime_type,
                content_hash=row.content_hash,
                byte_size=row.byte_size,
                expires_at=_iso(row.expires_at) or "",
                deleted_at=_iso(row.deleted_at),
            )
            for row in cache_files
        ],
    )


def grading_submission_snapshot(
    session: Session,
    submission: GradingSubmission,
) -> GradingSubmissionRead:
    latest_attempt = session.exec(
        select(GradingAiAttempt)
        .where(GradingAiAttempt.submission_id == submission.id)
        .order_by(GradingAiAttempt.created_at.desc())
    ).first()
    return _submission_read(submission, latest_attempt, submission_files(session, submission))
