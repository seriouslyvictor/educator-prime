"""Per-submission drafting for the grading pipeline.

Provides _draft_submission, which caches and scrubs every attachment for a
single student submission, then sends their combined scrubbed text to the
grading engine in one grade call.
"""
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..content_extraction import ExtractedSubmissionContent
from ..grading_engine import GradingEngine, GradingEngineRequest
from ..google_provider import GoogleProvider, SubmissionFile
from ..llm_errors import LlmCallError, classify_llm_exception
from ..models import (
    GradingAiAttempt,
    GradingCriterion,
    GradingJob,
    GradingSubmission,
)
from ..observability import get_logger, log_debug, log_error, log_event, text_preview
from ..privacy import ScrubbedSubmission
from ..settings import get_settings
from ._common import (
    _PRIVACY_STATUS_RANK,
    _EXTRACTION_STATUS_RANK,
    _worst_status,
)
from .attempts import _record_attempt, _attempt_metadata
from .caching import cache_submission_file, scrub_submission_cached
from .criteria import _apply_criterion_notes
from .scoring import _apply_criterion_scores

logger = get_logger(__name__)


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
    derived_score = _apply_criterion_scores(session, submission, criteria, result.criterion_scores or [])
    cowrite = job.teacher_loop == "cowrite"
    # Per-criterion points are the source of truth: when the engine returned a
    # matched breakdown, the overall score is their sum, not the model's separate
    # (and sometimes contradictory) holistic number. Brief mode and responses with
    # no matched criteria fall back to the holistic score.
    overall_score = result.score if derived_score is None else derived_score
    auto_accept = (
        job.teacher_loop == "auto"
        and result.confidence >= settings.grading_auto_accept_confidence
        and not privacy_flags
        and overall_score is not None
    )
    submission.ai_score = None if cowrite else overall_score
    submission.confidence = result.confidence
    if cowrite:
        submission.final_score = None if reset_review else submission.final_score
    else:
        submission.final_score = overall_score if reset_review else submission.final_score or overall_score
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
