"""Outlier review service for the grading pipeline.

Provides review_outliers_for_job and its supporting helpers. The outlier pass
is advisory and failure-isolated: engine or parser failures are caught, logged,
and recorded as failed without blocking the drafting pipeline from reaching a
reviewable state.
"""
import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..grading_engine import GradingEngine, OutlierBatchRequest, OutlierSubmission
from ..models import (
    GradingAiAttempt,
    GradingAiAttemptPayload,
    GradingFileCache,
    GradingJob,
    GradingScrubCache,
    GradingSubmission,
    GradingSubmissionFile,
)
from ..observability import get_logger, log_error, log_event
from ..settings import get_settings
from .attempts import _record_attempt, _attempt_metadata

logger = get_logger(__name__)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []


def _latest_grading_attempts(session: Session, job_id: str) -> dict[str, GradingAiAttempt]:
    attempts = session.exec(
        select(GradingAiAttempt)
        .where(GradingAiAttempt.job_id == job_id)
        .where(GradingAiAttempt.stage == "grading")
        .order_by(GradingAiAttempt.created_at.desc())
    ).all()
    latest: dict[str, GradingAiAttempt] = {}
    for attempt in attempts:
        latest.setdefault(attempt.submission_id, attempt)
    return latest


def _outlier_review_already_completed(session: Session, job_id: str) -> bool:
    return (
        session.exec(
            select(GradingAiAttempt)
            .where(GradingAiAttempt.job_id == job_id)
            .where(GradingAiAttempt.stage == "outlier_review")
            .where(GradingAiAttempt.status == "completed")
        ).first()
        is not None
    )


def _mechanical_flag_for_attempt(attempt: GradingAiAttempt | None) -> str | None:
    if attempt is None:
        return None
    privacy_flags = _json_list(attempt.privacy_flags_json)
    if privacy_flags:
        return privacy_flags[0]
    if attempt.extraction_status not in {"supported", "ok", "clean"}:
        return attempt.extraction_status
    if attempt.privacy_status not in {"clean", "redacted"}:
        return attempt.privacy_status
    return None


def _scrubbed_content_for_outlier_review(session: Session, submission: GradingSubmission) -> str | None:
    files = session.exec(
        select(GradingSubmissionFile).where(GradingSubmissionFile.submission_id == submission.id)
    ).all()
    sections: list[str] = []
    for index, file in enumerate(files, start=1):
        cache_file = session.exec(
            select(GradingFileCache)
            .where(GradingFileCache.job_id == submission.job_id)
            .where(GradingFileCache.submission_id == submission.id)
            .where(GradingFileCache.source_file_id == file.source_file_id)
            .where(GradingFileCache.deleted_at.is_(None))
            .order_by(GradingFileCache.created_at.desc())
        ).first()
        if cache_file is None:
            continue
        scrub_cache = session.exec(
            select(GradingScrubCache)
            .where(GradingScrubCache.job_id == submission.job_id)
            .where(GradingScrubCache.submission_id == submission.id)
            .where(GradingScrubCache.content_hash == cache_file.content_hash)
            .order_by(GradingScrubCache.created_at.desc())
        ).first()
        if scrub_cache is None or scrub_cache.privacy_status == "failed" or not scrub_cache.scrubbed_content.strip():
            continue
        content = scrub_cache.scrubbed_content.strip()
        if len(files) > 1:
            sections.append(f"=== Arquivo {index} ===\n{content}")
        else:
            sections.append(content)
    return "\n\n".join(sections) if sections else None


def _outlier_candidates(
    session: Session,
    job: GradingJob,
) -> tuple[list[OutlierSubmission], dict[str, GradingAiAttempt]]:
    attempts_by_submission = _latest_grading_attempts(session, job.id)
    candidates: list[OutlierSubmission] = []
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    for submission in submissions:
        attempt = attempts_by_submission.get(submission.id)
        if attempt is None or attempt.status != "completed" or submission.error:
            continue
        content = _scrubbed_content_for_outlier_review(session, submission)
        if content is None:
            payload = session.get(GradingAiAttemptPayload, attempt.id)
            content = payload.prompt_text if payload is not None and payload.prompt_text else None
        if not content:
            continue
        candidates.append(
            OutlierSubmission(
                id=submission.id,
                student_label=submission.student_name or submission.student_email or submission.source_name,
                score=submission.ai_score,
                feedback=submission.feedback or "",
                content=content,
            )
        )
    return candidates, attempts_by_submission


def _refresh_counts(session: Session, job: GradingJob) -> None:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    job.total_submissions = len(submissions)
    job.reviewed_submissions = sum(1 for row in submissions if row.reviewed)
    job.flagged_submissions = sum(1 for row in submissions if row.flag or row.error)


def review_outliers_for_job(
    session: Session,
    job: GradingJob,
    grading_engine: GradingEngine,
) -> list[dict[str, str]]:
    settings = get_settings()
    if settings.grading_outlier_review != "on":
        attempts_by_submission = _latest_grading_attempts(session, job.id)
        for submission in session.exec(select(GradingSubmission).where(GradingSubmission.job_id == job.id)).all():
            if not submission.error:
                submission.flag = _mechanical_flag_for_attempt(attempts_by_submission.get(submission.id))
                submission.updated_at = datetime.now(UTC)
                session.add(submission)
        _refresh_counts(session, job)
        session.commit()
        return []
    if _outlier_review_already_completed(session, job.id):
        return []
    candidates, attempts_by_submission = _outlier_candidates(session, job)
    if not candidates:
        return []
    reviewer = getattr(grading_engine, "review_outliers", None)
    review_failed = False
    if not callable(reviewer):
        flags = []
    else:
        try:
            flags = reviewer(
                OutlierBatchRequest(
                    job_id=job.id,
                    activity_title=job.activity_title,
                    submissions=candidates,
                )
            ) or []
        except Exception:
            review_failed = True
            flags = []
            log_error(logger, "grading.outlier_review.failed", job_id=job.id)
    flag_reasons = {flag.id: flag.reason for flag in flags}
    candidate_ids = {candidate.id for candidate in candidates}
    for submission in session.exec(select(GradingSubmission).where(GradingSubmission.job_id == job.id)).all():
        if submission.id not in candidate_ids or submission.error:
            continue
        submission.flag = flag_reasons.get(submission.id) or _mechanical_flag_for_attempt(attempts_by_submission.get(submission.id))
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
    marker_submission = session.get(GradingSubmission, candidates[0].id)
    if marker_submission is not None:
        metadata = _attempt_metadata(grading_engine)
        _record_attempt(
            session=session,
            job=job,
            submission=marker_submission,
            engine=grading_engine,
            status="failed" if review_failed else "completed",
            extraction_status="supported",
            privacy_status="clean",
            flags=[flag.reason for flag in flags],
            privacy_flags=[],
            retry_count=0,
            stage="outlier_review",
            prompt_tokens=metadata["prompt_tokens"],
            completion_tokens=metadata["completion_tokens"],
            token_count=metadata["token_count"],
            cached_prompt_tokens=metadata["cached_prompt_tokens"],
            cache_write_tokens=metadata["cache_write_tokens"],
            cost_cents=metadata["cost_cents"],
            latency_ms=metadata["latency_ms"],
        )
    _refresh_counts(session, job)
    session.commit()
    log_event(
        logger,
        "grading.outlier_review.complete",
        job_id=job.id,
        candidates=len(candidates),
        flags=len(flags),
    )
    return [{"id": flag.id, "reason": flag.reason} for flag in flags]
