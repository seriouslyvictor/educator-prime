import time
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..content_extraction import ExtractedSubmissionContent
from ..grading_engine import GradingEngine, GradingEngineRequest, OutlierBatchRequest, OutlierSubmission
from ..google_provider import GoogleProvider, SubmissionFile
from ..llm_errors import LlmCallError, classify_llm_exception
from ..models import (
    GradingAiAttempt,
    GradingAiAttemptPayload,
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingScrubCache,
    GradingStatus,
    GradingSubmission,
    GradingSubmissionFile,
)
from ..observability import get_logger, log_debug, log_error, log_event, safe_fields, text_preview
from ..privacy import ScrubbedSubmission
from ..settings import get_settings
from ._common import (
    _PRIVACY_STATUS_RANK,
    _EXTRACTION_STATUS_RANK,
    _worst_status,
    _sum_optional,
    _sum_float_optional,
    default_cache_expiry,
)
from .attempts import _record_attempt, _attempt_metadata
from .caching import cache_submission_file, scrub_submission_cached
from .criteria import _apply_criterion_notes
from .snapshots import grading_submission_snapshot
from .submission_scope import files_for_grading_scope
from .submissions import (
    _student_sort_key,
    _group_files,
    _submission_for_file,
    submission_files,
)

logger = get_logger(__name__)


def _combine_submission_content(
    parts: list[tuple[SubmissionFile, ExtractedSubmissionContent, ScrubbedSubmission]],
) -> str:
    """Join the scrubbed text of each attachment into one prompt body, labelled per
    file, so a multi-file submission is graded as a single set."""
    if len(parts) == 1:
        return parts[0][2].content
    # Generic per-file labels keep attachments distinguishable without leaking the
    # real filenames into the model prompt.
    sections = [
        f"=== Arquivo {index} ===\n{scrubbed.content.strip()}"
        for index, (_, _, scrubbed) in enumerate(parts, start=1)
    ]
    return "\n\n".join(sections)


def _draft_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    files: list[SubmissionFile],
    provider: GoogleProvider,
    grading_engine: GradingEngine,
    reset_review: bool = False,
) -> tuple[int, int, int, int]:
    """Draft one submission (a student's whole Classroom submission). Caches and
    scrubs every attachment, then sends their combined scrubbed text to the engine in
    a single grade call. Returns (file_hits, file_misses, scrub_hits, scrub_misses)."""
    log_debug(
        logger,
        "grading.submission.draft.start",
        job_id=job.id,
        submission_id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        file_count=len(files),
        source_names=[file.source_name for file in files],
        engine=grading_engine.name,
        reset_review=reset_review,
    )
    settings = get_settings()
    criteria = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job.id)
    ).all()
    retry_count = len(
        session.exec(
            select(GradingAiAttempt).where(GradingAiAttempt.submission_id == submission.id)
        ).all()
    )

    file_cache_hits = file_cache_misses = scrub_cache_hits = scrub_cache_misses = 0
    parts: list[tuple[SubmissionFile, ExtractedSubmissionContent, ScrubbedSubmission]] = []
    vision_extractor = _vision_extractor_for_job(job, grading_engine)
    for file in files:
        cache_file = cache_submission_file(session, job, submission, file, provider)
        if getattr(cache_file, "_cache_hit", False):
            file_cache_hits += 1
        else:
            file_cache_misses += 1
        cached = scrub_submission_cached(
            session,
            job,
            submission,
            cache_file,
            vision_extractor=vision_extractor,
        )
        if cached.cache_hit:
            scrub_cache_hits += 1
        else:
            scrub_cache_misses += 1
        parts.append((file, cached.extracted, cached.scrubbed))

    stats = (file_cache_hits, file_cache_misses, scrub_cache_hits, scrub_cache_misses)

    if job.teacher_loop == "off":
        log_event(
            logger,
            "grading.submission.engine_call.skipped",
            job_id=job.id,
            submission_id=submission.id,
            teacher_loop=job.teacher_loop,
        )
        submission.ai_score = None
        submission.confidence = None
        submission.final_score = None if reset_review else submission.final_score
        submission.feedback = None if reset_review else submission.feedback
        submission.reviewed = False if reset_review else submission.reviewed
        submission.flag = None
        submission.error = None
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
        return stats

    # Only files we could read and safely scrub are sent to the model.
    usable = [
        (file, extracted, scrubbed)
        for (file, extracted, scrubbed) in parts
        if extracted.status not in {"unsupported", "failed"}
        and scrubbed.report.status != "failed"
        and scrubbed.content.strip()
    ]

    if not usable:
        privacy_flags = sorted({flag for _, _, scrubbed in parts for flag in scrubbed.report.flags})
        privacy_status = _worst_status(
            [scrubbed.report.status for _, _, scrubbed in parts], _PRIVACY_STATUS_RANK, "failed"
        )
        extraction_status = _worst_status(
            [extracted.status for _, extracted, _ in parts], _EXTRACTION_STATUS_RANK, "failed"
        )
        first_error = next((extracted.error for _, extracted, _ in parts if extracted.error), None)
        error_retryable = any(
            extracted.error == first_error and extracted.retryable
            for _, extracted, _ in parts
        )
        safe_error = first_error or (privacy_status if privacy_status == "failed" else None) or "unsupported_file_type"
        log_event(
            logger,
            "grading.submission.blocked_before_engine",
            job_id=job.id,
            submission_id=submission.id,
            extraction_status=extraction_status,
            privacy_status=privacy_status,
            privacy_flags=privacy_flags,
            file_count=len(parts),
        )
        attempt = _record_attempt(
            session=session,
            job=job,
            submission=submission,
            engine=grading_engine,
            status="blocked",
            extraction_status=extraction_status,
            privacy_status=privacy_status,
            flags=[],
            privacy_flags=privacy_flags,
            retry_count=retry_count,
            safe_error=safe_error,
            retryable=error_retryable,
        )
        submission.flag = attempt.safe_error
        submission.error = attempt.safe_error
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
        return stats

    privacy_flags = sorted({flag for _, _, scrubbed in usable for flag in scrubbed.report.flags})
    privacy_status = _worst_status(
        [scrubbed.report.status for _, _, scrubbed in usable], _PRIVACY_STATUS_RANK, "clean"
    )
    extraction_status = _worst_status(
        [extracted.status for _, extracted, _ in usable], _EXTRACTION_STATUS_RANK, "supported"
    )
    student_label = usable[0][2].student_label
    source_label = usable[0][2].source_label
    combined_content = _combine_submission_content(usable)
    mime_type = usable[0][0].mime_type if len(usable) == 1 else "multipart/mixed"

    try:
        log_debug(
            logger,
            "grading.submission.engine_call.start",
            job_id=job.id,
            submission_id=submission.id,
            engine=grading_engine.name,
            model=getattr(grading_engine, "model", None),
            student_label=student_label,
            source_label=source_label,
            file_count=len(usable),
            content_chars=len(combined_content),
            content_preview=text_preview(combined_content),
        )
        request = GradingEngineRequest(
            job_id=job.id,
            submission_id=submission.id,
            activity_title=job.activity_title,
            rubric_mode=job.rubric_mode,
            teacher_loop=job.teacher_loop,
            request_score=job.teacher_loop != "cowrite",
            rubric_text=job.rubric_text,
            criteria=[
                {
                    "name": criterion.name,
                    "weight": criterion.weight,
                    "description": criterion.description,
                }
                for criterion in criteria
            ],
            student_label=student_label,
            source_label=source_label,
            mime_type=mime_type,
            content=combined_content,
        )
        try:
            result = grading_engine.grade(request)
        except LlmCallError:
            raise
        except Exception as exc:
            raise classify_llm_exception(exc) from exc
    except LlmCallError as exc:
        log_error(
            logger,
            "grading.submission.engine_call.failed",
            job_id=job.id,
            submission_id=submission.id,
            engine=grading_engine.name,
            safe_error=exc.code,
            retryable=exc.retryable,
            prompt_text=combined_content,
            response_text=getattr(grading_engine, "last_response_text", None),
        )
        attempt = _record_attempt(
            session=session,
            job=job,
            submission=submission,
            engine=grading_engine,
            status="failed",
            extraction_status=extraction_status,
            privacy_status=privacy_status,
            flags=[],
            privacy_flags=privacy_flags,
            retry_count=retry_count,
            safe_error=exc.code,
            retryable=exc.retryable,
        )
        submission.flag = attempt.safe_error
        submission.error = attempt.safe_error
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
        return stats

    grading_flags = sorted(set(result.flags))
    attempt_metadata = _attempt_metadata(grading_engine)
    log_event(
        logger,
        "grading.submission.engine_call.complete",
        job_id=job.id,
        submission_id=submission.id,
        engine=grading_engine.name,
        model=getattr(grading_engine, "model", None),
        score=result.score,
        confidence=result.confidence,
        feedback=result.feedback,
        result_flags=result.flags,
        privacy_flags=privacy_flags,
    )
    _record_attempt(
        session=session,
        job=job,
        submission=submission,
        engine=grading_engine,
        status="completed",
        extraction_status=extraction_status,
        privacy_status=privacy_status,
        flags=grading_flags,
        privacy_flags=privacy_flags,
        retry_count=retry_count,
        prompt_tokens=attempt_metadata["prompt_tokens"],
        completion_tokens=attempt_metadata["completion_tokens"],
        token_count=attempt_metadata["token_count"],
        cached_prompt_tokens=attempt_metadata["cached_prompt_tokens"],
        cache_write_tokens=attempt_metadata["cache_write_tokens"],
        cost_cents=attempt_metadata["cost_cents"],
        latency_ms=attempt_metadata["latency_ms"],
        prompt_text=combined_content,
        response_text=getattr(grading_engine, "last_response_text", None),
    )
    _apply_criterion_notes(session, criteria, result.criterion_notes or [])
    cowrite = job.teacher_loop == "cowrite"
    auto_accept = (
        job.teacher_loop == "auto"
        and result.confidence >= settings.grading_auto_accept_confidence
        and not privacy_flags
        and result.score is not None
    )
    submission.ai_score = None if cowrite else result.score
    submission.confidence = result.confidence
    if cowrite:
        submission.final_score = None if reset_review else submission.final_score
    else:
        submission.final_score = result.score if reset_review else submission.final_score or result.score
    submission.feedback = result.feedback if reset_review else submission.feedback or result.feedback
    submission.reviewed = auto_accept if reset_review else submission.reviewed or auto_accept
    # Pass-1 keeps only mechanical privacy/extraction signals in the badge.
    # Whole-class outliers are reviewed after all drafts complete.
    badge_flags = privacy_flags
    submission.flag = None if auto_accept else badge_flags[0] if badge_flags else None
    submission.error = None
    submission.updated_at = datetime.now(UTC)
    session.add(submission)
    log_event(
        logger,
        "grading.submission.draft.complete",
        job_id=job.id,
        submission_id=submission.id,
        ai_score=submission.ai_score,
        confidence=submission.confidence,
        final_score=submission.final_score,
        feedback=submission.feedback,
        reviewed=submission.reviewed,
        flag=submission.flag,
        error=submission.error,
    )
    return stats


def _json_list(value: str | None) -> list[str]:
    import json

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
    if not callable(reviewer):
        flags = []
    else:
        flags = reviewer(
            OutlierBatchRequest(
                job_id=job.id,
                activity_title=job.activity_title,
                submissions=candidates,
            )
        ) or []
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
            status="completed",
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


def _vision_extractor_for_job(
    job: GradingJob,
    grading_engine: GradingEngine,
) -> GradingEngine | None:
    if not job.include_visual_submissions:
        return None
    if grading_engine.name == "mock":
        return grading_engine
    catalog_model = getattr(grading_engine, "catalog_model", None)
    if getattr(catalog_model, "supports_vision", False):
        return grading_engine
    return None


def _refresh_counts(session: Session, job: GradingJob) -> None:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    job.total_submissions = len(submissions)
    job.reviewed_submissions = sum(1 for row in submissions if row.reviewed)
    job.flagged_submissions = sum(1 for row in submissions if row.flag or row.error)


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
        on_outlier_progress(total, total, "Analisando exce\u00e7\u00f5es")
    outlier_flags = review_outliers_for_job(session, job, grading_engine)
    for flag in outlier_flags:
        submission = session.get(GradingSubmission, flag["id"])
        if submission is None:
            continue
        snapshot = grading_submission_snapshot(session, submission)
        if on_outlier_progress:
            on_outlier_progress(total, total, "Analisando exce\u00e7\u00f5es", snapshot)
        elif on_submission:
            on_submission(total, total, "Analisando exce\u00e7\u00f5es", snapshot)
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
