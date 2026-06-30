"""Job-level grading orchestration.

Coordinates provider file listing, queue materialization, per-submission
drafting (submission_drafting.py), outlier review (outliers.py), cost rollup,
and final job state transitions.

Public API: draft_grading_job, retry_submission, _draft_submission (re-exported).
"""
import time
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..grading_engine import GradingEngine
from ..google_provider import GoogleProvider, SubmissionFile
from ..models import (
    GradingAiAttempt,
    GradingJob,
    GradingStatus,
    GradingSubmission,
)
from ..observability import get_logger, log_event, safe_fields
from ._common import (
    _sum_optional,
    _sum_float_optional,
    default_cache_expiry,
)
from .outliers import (
    review_outliers_for_job,
    _refresh_counts,
    _outlier_review_already_completed,  # compat re-export: tests import from drafting
)
from .snapshots import grading_submission_snapshot
from .submission_drafting import _draft_submission  # re-exported via __init__
from .submission_scope import files_for_grading_scope
from .submissions import (
    _student_sort_key,
    _group_files,
    _submission_for_file,
    submission_files,
)

logger = get_logger(__name__)


def _refresh_cost_rollup(
    session: Session,
    job: GradingJob,
    grading_engine: GradingEngine,
    started: float,
) -> None:
    attempts = session.exec(
        select(GradingAiAttempt).where(GradingAiAttempt.job_id == job.id)
    ).all()
    job.total_prompt_tokens = _sum_optional(row.prompt_tokens for row in attempts)
    job.total_completion_tokens = _sum_optional(row.completion_tokens for row in attempts)
    job.total_cached_tokens = _sum_optional(row.cached_prompt_tokens for row in attempts)
    job.total_cost_cents = _sum_float_optional(row.cost_cents for row in attempts)
    job.wall_clock_ms = int((time.monotonic() - started) * 1000)
    job.submissions_graded = sum(
        1 for row in attempts if row.stage == "grading" and row.status == "completed"
    )
    job.ai_engine = grading_engine.name
    job.ai_mode = job.batch_mode
    job.ai_model = getattr(grading_engine, "model", None)
    log_event(
        logger,
        "grading.job.cost.summary",
        job_id=job.id,
        total_prompt_tokens=job.total_prompt_tokens,
        total_completion_tokens=job.total_completion_tokens,
        total_cached_tokens=job.total_cached_tokens,
        total_cost_cents=job.total_cost_cents,
        wall_clock_ms=job.wall_clock_ms,
        submissions_graded=job.submissions_graded,
        engine=job.ai_engine,
        mode=job.ai_mode,
        model=job.ai_model,
    )


def draft_grading_job(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
    grading_engine: GradingEngine | None = None,
    on_progress=None,
    on_submission=None,
    on_queued=None,
    on_submission_start=None,
    on_outlier_progress=None,
) -> GradingJob:
    from classroom_downloader import grading as _grading_pkg
    grading_engine = grading_engine or _grading_pkg.get_grading_engine()
    started = time.monotonic()
    log_event(
        logger,
        "grading.draft.start",
        job_id=job.id,
        course_id=job.course_id,
        course_name=job.course_name,
        activity_id=job.activity_id,
        activity_title=job.activity_title,
        engine=grading_engine.name,
        model=getattr(grading_engine, "model", None),
    )
    now = datetime.now(UTC)
    job.status = GradingStatus.drafting
    job.updated_at = now
    job.cache_expires_at = job.cache_expires_at or default_cache_expiry()
    session.add(job)
    session.commit()

    files = files_for_grading_scope(
        provider,
        job,
        provider.list_submission_files(job.course_id, [job.activity_id]),
    )
    log_event(logger, "grading.draft.files_loaded", job_id=job.id, count=len(files), files=[safe_fields(file) for file in files])
    file_cache_hits = 0
    file_cache_misses = 0
    scrub_cache_hits = 0
    scrub_cache_misses = 0
    # Group a student's attachments into one submission so they're graded as a set,
    # in a stable alphabetical order so the queue is predictable (not cache-warmth order).
    groups = _group_files(files)
    groups.sort(key=_student_sort_key)
    total = len(groups)

    # Materialize every submission up front and publish the full queue, so the review
    # screen shows all students as "na fila" immediately instead of popping in as each
    # finishes. Each then transitions queued -> drafting -> done honestly.
    plan: list[tuple[GradingSubmission, list[SubmissionFile]]] = []
    for group_files in groups:
        submission = None
        for file in group_files:
            submission = _submission_for_file(session, job, file)
        assert submission is not None
        plan.append((submission, group_files))
    if on_queued:
        on_queued([grading_submission_snapshot(session, submission) for submission, _ in plan])

    for index, (submission, group_files) in enumerate(plan, start=1):
        if on_submission_start:
            on_submission_start(index - 1, total, submission.source_name, submission.id)
        hits = _draft_submission(session, job, submission, group_files, provider, grading_engine)
        file_cache_hits += hits[0]
        file_cache_misses += hits[1]
        scrub_cache_hits += hits[2]
        scrub_cache_misses += hits[3]
        if on_progress:
            on_progress(index, total, submission.source_name)
        if on_submission:
            on_submission(index, total, submission.source_name, grading_submission_snapshot(session, submission))

    if on_outlier_progress:
        on_outlier_progress(total, total, "Analisando exceções")
    outlier_flags = review_outliers_for_job(session, job, grading_engine)
    for flag in outlier_flags:
        submission = session.get(GradingSubmission, flag["id"])
        if submission is None:
            continue
        snapshot = grading_submission_snapshot(session, submission)
        if on_outlier_progress:
            on_outlier_progress(total, total, "Analisando exceções", snapshot)
        elif on_submission:
            on_submission(total, total, "Analisando exceções", snapshot)
    _refresh_counts(session, job)
    _refresh_cost_rollup(session, job, grading_engine, started)
    job.status = GradingStatus.completed if job.reviewed_submissions == job.total_submissions and job.total_submissions else GradingStatus.reviewing
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.draft.complete",
        job_id=job.id,
        status=job.status,
        total_submissions=job.total_submissions,
        reviewed_submissions=job.reviewed_submissions,
        flagged_submissions=job.flagged_submissions,
        file_cache_hits=file_cache_hits,
        file_cache_misses=file_cache_misses,
        scrub_cache_hits=scrub_cache_hits,
        scrub_cache_misses=scrub_cache_misses,
    )
    return job


def retry_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    provider: GoogleProvider,
    grading_engine: GradingEngine | None = None,
) -> GradingJob:
    from classroom_downloader import grading as _grading_pkg
    grading_engine = grading_engine or _grading_pkg.get_grading_engine()
    log_event(
        logger,
        "grading.retry.start",
        job_id=job.id,
        submission_id=submission.id,
        source_file_id=submission.source_file_id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        engine=grading_engine.name,
    )
    files = [
        SubmissionFile(
            id=row.id,
            course_id=job.course_id,
            activity_id=job.activity_id,
            student_email=submission.student_email,
            student_name=submission.student_name,
            source_file_id=row.source_file_id,
            source_name=row.source_name,
            mime_type=row.mime_type,
            classroom_submission_id=submission.group_key,
        )
        for row in submission_files(session, submission)
    ]
    _draft_submission(session, job, submission, files, provider, grading_engine, reset_review=True)
    _refresh_counts(session, job)
    job.status = GradingStatus.reviewing
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.retry.complete",
        job_id=job.id,
        submission_id=submission.id,
        status=job.status,
        flagged_submissions=job.flagged_submissions,
    )
    return job
