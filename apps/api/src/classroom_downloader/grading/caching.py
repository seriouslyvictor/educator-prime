import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from ..content_extraction import extract_submission_content, ExtractedSubmissionContent
from ..grading_engine import GradingEngine, VisionExtractionRequest, VisionExtractionResult
from ..google_provider import GoogleProvider, SubmissionFile
from ..image_preprocessing import prepare_image_for_llm
from ..llm_errors import LlmCallError
from ..models import GradingAiAttempt, GradingFileCache, GradingJob, GradingScrubCache, GradingSubmission
from ..observability import get_logger, log_cache_hit, log_cache_miss, log_event
from ..privacy import PrivacyReport, ScrubbedSubmission, merge_reported_pii, scrub_submission
from ..settings import get_settings
from ._common import CachedScrubbedSubmission, default_cache_expiry, _identity_hash, _aware
from .attempts import _attempt_metadata, _record_attempt

logger = get_logger(__name__)


def cache_submission_file(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    file: SubmissionFile,
    provider: GoogleProvider,
    commit: bool = True,
) -> GradingFileCache:
    now = datetime.now(UTC)
    existing = session.exec(
        select(GradingFileCache)
        .where(GradingFileCache.job_id == job.id)
        .where(GradingFileCache.submission_id == submission.id)
        .where(GradingFileCache.source_file_id == file.source_file_id)
        .where(GradingFileCache.deleted_at.is_(None))
        .order_by(GradingFileCache.created_at.desc())
    ).first()
    if (
        existing
        and _aware(existing.expires_at) > now
        and Path(existing.cached_path).exists()
    ):
        log_cache_hit(
            logger,
            "grading.file",
            file.source_file_id,
            job_id=job.id,
            submission_id=submission.id,
            cache_id=existing.id,
            source_file_id=existing.source_file_id,
            source_name=existing.source_name,
            cached_path=existing.cached_path,
            byte_size=existing.byte_size,
            content_hash=existing.content_hash,
            expires_at=existing.expires_at,
        )
        existing._cache_hit = True
        return existing

    log_cache_miss(
        logger,
        "grading.file",
        file.source_file_id,
        job_id=job.id,
        submission_id=submission.id,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=file.mime_type,
    )
    content, media_type = provider.get_file_content(file.source_file_id)
    cache_root = Path(get_settings().grading_cache_path)
    job_dir = cache_root / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(content).hexdigest()
    suffix = Path(file.source_name).suffix or ".bin"
    cached_path = job_dir / f"{submission.id}-{digest[:12]}{suffix}"
    cached_path.write_bytes(content)
    row = GradingFileCache(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=media_type or file.mime_type,
        cached_path=str(cached_path),
        content_hash=digest,
        byte_size=len(content),
        expires_at=default_cache_expiry(),
    )
    session.add(row)
    job.cache_expires_at = row.expires_at
    session.add(job)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(row)
    log_event(
        logger,
        "grading.cache.write",
        job_id=job.id,
        submission_id=submission.id,
        cache_id=row.id,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        media_type=media_type,
        cached_path=str(cached_path),
        byte_size=len(content),
        content_hash=digest,
        expires_at=row.expires_at,
    )
    row._cache_hit = False
    return row


def scrub_submission_cached(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    cache_file: GradingFileCache,
    commit: bool = True,
    vision_extractor: GradingEngine | None = None,
) -> CachedScrubbedSubmission:
    now = datetime.now(UTC)
    identity_hash = _identity_hash(submission)
    existing = session.exec(
        select(GradingScrubCache)
        .where(GradingScrubCache.job_id == job.id)
        .where(GradingScrubCache.submission_id == submission.id)
        .where(GradingScrubCache.content_hash == cache_file.content_hash)
        .where(GradingScrubCache.identity_hash == identity_hash)
        .where(GradingScrubCache.deleted_at.is_(None))
        .order_by(GradingScrubCache.created_at.desc())
    ).first()
    if (
        existing
        and _aware(existing.expires_at) > now
        and not _bypass_visual_scrub_cache(job, cache_file, existing)
    ):
        extracted = ExtractedSubmissionContent(
            status=existing.extraction_status,
            text="",
            safe_source_label=existing.safe_source_label,
            error=existing.extraction_error,
        )
        scrubbed = ScrubbedSubmission(
            student_label=existing.student_label,
            source_label=existing.source_label,
            content=existing.scrubbed_content,
            report=PrivacyReport(
                status=existing.privacy_status,
                counts=json.loads(existing.redaction_counts_json),
            ),
        )
        log_cache_hit(
            logger,
            "grading.scrub",
            cache_file.content_hash,
            job_id=job.id,
            submission_id=submission.id,
            cache_id=existing.id,
            content_hash=cache_file.content_hash,
            privacy_status=scrubbed.report.status,
            extraction_status=extracted.status,
        )
        return CachedScrubbedSubmission(extracted, scrubbed, cache_hit=True)

    log_cache_miss(
        logger,
        "grading.scrub",
        cache_file.content_hash,
        job_id=job.id,
        submission_id=submission.id,
        content_hash=cache_file.content_hash,
    )
    extracted = extract_submission_content(
        cache_file,
        allow_visual_pending=job.include_visual_submissions,
    )
    if extracted.status == "pending_vision" and vision_extractor is not None:
        extracted = _extract_visual_submission(
            session,
            job,
            submission,
            cache_file,
            extracted,
            vision_extractor,
        )
    scrubbed = scrub_submission(session, job, submission, extracted)
    if extracted.pii_observed:
        scrubbed = ScrubbedSubmission(
            student_label=scrubbed.student_label,
            source_label=scrubbed.source_label,
            content=scrubbed.content,
            report=merge_reported_pii(scrubbed.report, extracted.pii_observed),
        )
    if extracted.status == "pending_vision":
        log_event(
            logger,
            "grading.scrub_cache.skip_pending_vision",
            job_id=job.id,
            submission_id=submission.id,
            content_hash=cache_file.content_hash,
        )
        return CachedScrubbedSubmission(extracted, scrubbed, cache_hit=False)
    if (
        extracted.error
        and extracted.retryable
        and cache_file.mime_type.lower().startswith("image/")
    ):
        return CachedScrubbedSubmission(extracted, scrubbed, cache_hit=False)
    row = GradingScrubCache(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        content_hash=cache_file.content_hash,
        identity_hash=identity_hash,
        student_label=scrubbed.student_label,
        source_label=scrubbed.source_label,
        safe_source_label=extracted.safe_source_label,
        scrubbed_content=scrubbed.content,
        extraction_status=extracted.status,
        extraction_error=extracted.error,
        privacy_status=scrubbed.report.status,
        privacy_flags_json=json.dumps(scrubbed.report.flags),
        redaction_counts_json=json.dumps(scrubbed.report.counts),
        byte_size=cache_file.byte_size,
        expires_at=min(_aware(cache_file.expires_at), default_cache_expiry()),
    )
    session.add(row)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(row)
    log_event(
        logger,
        "grading.scrub_cache.write",
        job_id=job.id,
        submission_id=submission.id,
        cache_id=row.id,
        content_hash=cache_file.content_hash,
        privacy_status=scrubbed.report.status,
        extraction_status=extracted.status,
    )
    return CachedScrubbedSubmission(extracted, scrubbed, cache_hit=False)


def _extract_visual_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    cache_file: GradingFileCache,
    pending: ExtractedSubmissionContent,
    vision_extractor: GradingEngine,
) -> ExtractedSubmissionContent:
    retry_count = len(
        session.exec(
            select(GradingAiAttempt).where(GradingAiAttempt.submission_id == submission.id)
        ).all()
    )
    try:
        prepared = prepare_image_for_llm(Path(cache_file.cached_path))
    except LlmCallError as exc:
        status = "unsupported" if exc.code == "local_unsupported_image_format" else "failed"
        return ExtractedSubmissionContent(
            status=status,
            text="",
            safe_source_label=pending.safe_source_label,
            error=exc.code,
            retryable=exc.retryable,
        )

    try:
        result = vision_extractor.extract_image(
            VisionExtractionRequest(
                job_id=job.id,
                submission_id=submission.id,
                activity_title=job.activity_title,
                source_label=pending.safe_source_label,
                image_data=prepared.data,
                image_mime_type=prepared.mime_type,
            )
        )
    except LlmCallError as exc:
        safe_error = _vision_safe_error(exc.code)
        metadata = _attempt_metadata(vision_extractor)
        _record_attempt(
            session=session,
            job=job,
            submission=submission,
            engine=vision_extractor,
            stage="extraction",
            status="failed",
            extraction_status="failed",
            privacy_status="failed",
            flags=[],
            privacy_flags=[],
            retry_count=retry_count,
            safe_error=safe_error,
            retryable=exc.retryable,
            prompt_tokens=metadata["prompt_tokens"],
            completion_tokens=metadata["completion_tokens"],
            token_count=metadata["token_count"],
            cached_prompt_tokens=metadata["cached_prompt_tokens"],
            cache_write_tokens=metadata["cache_write_tokens"],
            cost_cents=metadata["cost_cents"],
            latency_ms=metadata["latency_ms"],
        )
        return ExtractedSubmissionContent(
            status="failed",
            text="",
            safe_source_label=pending.safe_source_label,
            error=safe_error,
            retryable=exc.retryable,
        )

    extracted = _extracted_from_vision_result(pending, result)
    metadata = _attempt_metadata(vision_extractor)
    _record_attempt(
        session=session,
        job=job,
        submission=submission,
        engine=vision_extractor,
        stage="extraction",
        status="failed" if extracted.status == "failed" else "completed",
        extraction_status=extracted.status,
        privacy_status="pending",
        flags=[],
        privacy_flags=[],
        retry_count=retry_count,
        safe_error=extracted.error,
        retryable=extracted.retryable,
        prompt_tokens=metadata["prompt_tokens"],
        completion_tokens=metadata["completion_tokens"],
        token_count=metadata["token_count"],
        cached_prompt_tokens=metadata["cached_prompt_tokens"],
        cache_write_tokens=metadata["cache_write_tokens"],
        cost_cents=metadata["cost_cents"],
        latency_ms=metadata["latency_ms"],
    )
    return extracted


def _extracted_from_vision_result(
    pending: ExtractedSubmissionContent,
    result: VisionExtractionResult,
) -> ExtractedSubmissionContent:
    blocks = [result.transcription.strip()]
    if result.visual_description.strip():
        blocks.append("[descricao visual]\n" + result.visual_description.strip())
    text = "\n\n".join(block for block in blocks if block)
    if result.legibility == "unreadable":
        return ExtractedSubmissionContent(
            status="failed",
            text="",
            safe_source_label=pending.safe_source_label,
            error="vision_unreadable",
            retryable=False,
            pii_observed=result.pii_observed,
            content_kind=result.content_kind,
        )
    return ExtractedSubmissionContent(
        status="degraded" if result.legibility == "partial" else "supported",
        text=text,
        safe_source_label=pending.safe_source_label,
        pii_observed=result.pii_observed,
        content_kind=result.content_kind,
    )


def _vision_safe_error(code: str) -> str:
    if code.startswith("vision_") or code.startswith("local_"):
        return code
    return f"vision_{code}"


def _bypass_visual_scrub_cache(
    job: GradingJob,
    cache_file: GradingFileCache,
    existing: GradingScrubCache,
) -> bool:
    if not job.include_visual_submissions or not cache_file.mime_type.lower().startswith("image/"):
        return False
    return existing.extraction_status == "pending_vision" or (
        existing.extraction_status == "unsupported"
        and existing.extraction_error == "unsupported_visual_submission"
    )


def delete_job_cache(session: Session, job: GradingJob) -> GradingJob:
    now = datetime.now(UTC)
    rows = session.exec(
        select(GradingFileCache).where(GradingFileCache.job_id == job.id)
    ).all()
    for row in rows:
        path = Path(row.cached_path)
        if path.exists() and path.is_file():
            path.unlink()
            log_event(logger, "grading.cache.file_deleted", job_id=job.id, cache_id=row.id, cached_path=row.cached_path)
        row.deleted_at = row.deleted_at or now
        session.add(row)
    scrub_rows = session.exec(
        select(GradingScrubCache).where(GradingScrubCache.job_id == job.id)
    ).all()
    for row in scrub_rows:
        row.deleted_at = row.deleted_at or now
        session.add(row)
    job.cache_expires_at = None
    job.updated_at = now
    session.add(job)
    session.commit()
    shutil.rmtree(Path(get_settings().grading_cache_path) / job.id, ignore_errors=True)
    session.refresh(job)
    log_event(
        logger,
        "grading.cache.delete.complete",
        job_id=job.id,
        cache_count=len(rows),
        scrub_cache_count=len(scrub_rows),
    )
    return job
