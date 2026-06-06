from datetime import UTC, datetime, timedelta
import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path
import random
import shutil
from uuid import uuid4
import json
import time

import litellm

from sqlmodel import Session, select

from .content_extraction import extract_submission_content
from .content_extraction import ExtractedSubmissionContent
from .grading_engine import (
    GradingEngine,
    GradingEngineRequest,
    RubricInferenceRequest,
    get_grading_engine,
)
from .google_provider import GoogleProvider, SubmissionFile
from .models import (
    GradingAiAttempt,
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingScrubCache,
    GradingStatus,
    GradingSubmission,
)
from .observability import (
    get_logger,
    log_cache_hit,
    log_cache_miss,
    log_debug,
    log_error,
    log_event,
    safe_fields,
    text_preview,
)
from .privacy import PrivacyReport, ScrubbedSubmission, scrub_submission
from .schemas import (
    GradingCriterionInput,
    GradingCriterionRead,
    GradingFileCacheRead,
    GradingJobRead,
    GradingSubmissionRead,
)
from .settings import get_settings

logger = get_logger(__name__)


DEFAULT_CRITERIA = [
    GradingCriterionInput(
        name="Understanding",
        weight=30,
        description="Shows command of the core concepts in the assignment.",
    ),
    GradingCriterionInput(
        name="Evidence",
        weight=25,
        description="Uses relevant details, sources, examples, or artifacts.",
    ),
    GradingCriterionInput(
        name="Reasoning",
        weight=30,
        description="Connects evidence to conclusions with clear logic.",
    ),
    GradingCriterionInput(
        name="Clarity",
        weight=15,
        description="Communicates in an organized, readable way.",
    ),
]


@dataclass(frozen=True)
class CachedScrubbedSubmission:
    extracted: ExtractedSubmissionContent
    scrubbed: ScrubbedSubmission
    cache_hit: bool


def default_cache_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(hours=settings.grading_cache_ttl_hours)


def ensure_default_criteria(
    session: Session,
    job_id: str,
    criteria: list[GradingCriterionInput] | None,
) -> None:
    rows = criteria or DEFAULT_CRITERIA
    for criterion in rows:
        session.add(
            GradingCriterion(
                id=str(uuid4()),
                job_id=job_id,
                name=criterion.name,
                weight=criterion.weight,
                description=criterion.description,
            )
        )


def _criteria_match_defaults(criteria: list[GradingCriterion]) -> bool:
    if len(criteria) != len(DEFAULT_CRITERIA):
        return False
    for row, default in zip(criteria, DEFAULT_CRITERIA, strict=True):
        if row.name != default.name or row.weight != default.weight or row.description != default.description:
            return False
    return True


def _normalize_inferred_criteria(
    rows: list[dict[str, str | int | None]] | None,
) -> list[GradingCriterionInput]:
    if not rows:
        return []
    criteria: list[GradingCriterionInput] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        try:
            weight = int(row.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0
        description_value = row.get("description")
        description = str(description_value).strip() if description_value else None
        if not name or weight <= 0:
            continue
        criteria.append(
            GradingCriterionInput(
                name=name,
                weight=weight,
                description=description,
            )
        )
    return criteria


def _replace_job_criteria(
    session: Session,
    job_id: str,
    criteria: list[GradingCriterionInput],
) -> list[GradingCriterion]:
    existing = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job_id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()
    created: list[GradingCriterion] = []
    for criterion in criteria:
        row = GradingCriterion(
            id=str(uuid4()),
            job_id=job_id,
            name=criterion.name,
            weight=criterion.weight,
            description=criterion.description,
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def _is_substantial_description(text: str | None) -> bool:
    settings = get_settings()
    if not text:
        return False
    normalized = " ".join(text.split())
    return (
        len(normalized) >= settings.rubric_description_min_chars
        and len(normalized.split()) >= settings.rubric_description_min_words
    )


def _normalize_weights_to_100(
    criteria: list[GradingCriterionInput],
) -> list[GradingCriterionInput]:
    total = sum(criterion.weight for criterion in criteria)
    if not criteria or total <= 0:
        return []
    scaled: list[GradingCriterionInput] = []
    running = 0
    for index, criterion in enumerate(criteria):
        if index == len(criteria) - 1:
            weight = max(1, 100 - running)
        else:
            weight = max(1, round(criterion.weight * 100 / total))
            running += weight
        scaled.append(
            GradingCriterionInput(
                name=criterion.name,
                weight=weight,
                description=criterion.description,
            )
        )
    return scaled


def _collect_inference_samples(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
    sample_size: int,
) -> list[dict[str, str]]:
    """Reuse the audit's cached + scrubbed content to build a privacy-safe sample.
    Only clean extractions are eligible; selection is randomized but seeded by the
    job id so a re-run is reproducible."""
    files = provider.list_submission_files(job.course_id, [job.activity_id])
    order = list(range(len(files)))
    random.Random(job.id).shuffle(order)
    samples: list[dict[str, str]] = []
    for position in order:
        if len(samples) >= sample_size:
            break
        file = files[position]
        submission = _submission_for_file(session, job, file)
        cache_file = cache_submission_file(
            session, job, submission, file, provider, commit=False
        )
        cached = scrub_submission_cached(
            session, job, submission, cache_file, commit=False
        )
        if cached.extracted.status in {"unsupported", "failed"}:
            continue
        if cached.scrubbed.report.status in {"failed", "high_reidentification_risk"}:
            continue
        content = cached.scrubbed.content.strip()
        if not content:
            continue
        samples.append(
            {
                "label": cached.scrubbed.student_label,
                "source_label": cached.scrubbed.source_label,
                "mime_type": cache_file.mime_type,
                "content": content,
            }
        )
    return samples


def infer_job_criteria(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
    grading_engine: GradingEngine | None = None,
    *,
    on_progress=None,
) -> list[GradingCriterion]:
    """Infer the rubric for an `infer`-mode job once, before drafting. Description
    first; otherwise a randomized sample of clean scrubbed submissions. Falls back
    to the existing (default) criteria whenever there is no usable signal or the
    engine returns nothing — never blocks grading."""
    grading_engine = grading_engine or get_grading_engine()
    settings = get_settings()

    def _existing() -> list[GradingCriterion]:
        return session.exec(
            select(GradingCriterion).where(GradingCriterion.job_id == job.id)
        ).all()

    if on_progress:
        on_progress(0, 1, "Lendo a descrição e as amostras")

    description_only = _is_substantial_description(job.activity_description)
    samples: list[dict[str, str]] = []
    if not description_only:
        samples = _collect_inference_samples(
            session, job, provider, settings.rubric_infer_sample_size
        )

    if not job.activity_description and not samples:
        log_event(
            logger,
            "grading.infer_criteria.no_signal",
            job_id=job.id,
            activity_id=job.activity_id,
        )
        if on_progress:
            on_progress(1, 1, "Sem sinal para inferir; mantendo critérios padrão")
        return _existing()

    request = RubricInferenceRequest(
        job_id=job.id,
        activity_title=job.activity_title,
        activity_description=job.activity_description,
        rubric_text=job.rubric_text,
        samples=samples,
        description_only=description_only or not samples,
    )
    log_event(
        logger,
        "grading.infer_criteria.request",
        job_id=job.id,
        engine=grading_engine.name,
        description_only=request.description_only,
        has_description=bool(job.activity_description),
        sample_count=len(samples),
    )
    try:
        raw = grading_engine.infer_rubric(request)
    except Exception:
        log_error(logger, "grading.infer_criteria.failed", job_id=job.id)
        raw = []

    normalized = _normalize_weights_to_100(_normalize_inferred_criteria(raw))
    if not normalized:
        log_event(logger, "grading.infer_criteria.empty_fallback", job_id=job.id)
        if on_progress:
            on_progress(1, 1, "Mantendo critérios padrão")
        return _existing()

    created = _replace_job_criteria(session, job.id, normalized)
    session.commit()
    log_event(
        logger,
        "grading.infer_criteria.complete",
        job_id=job.id,
        criteria_count=len(created),
        criteria=[{"name": row.name, "weight": row.weight} for row in created],
    )
    if on_progress:
        on_progress(1, 1, f"{len(created)} critérios definidos")
    return created


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
            _submission_read(row, latest_attempts.get(row.id))
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
    return _submission_read(submission, latest_attempt)


def draft_grading_job(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
    grading_engine: GradingEngine | None = None,
    on_progress=None,
    on_submission=None,
) -> GradingJob:
    grading_engine = grading_engine or get_grading_engine()
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

    files = provider.list_submission_files(job.course_id, [job.activity_id])
    log_event(logger, "grading.draft.files_loaded", job_id=job.id, count=len(files), files=[safe_fields(file) for file in files])
    file_cache_hits = 0
    file_cache_misses = 0
    scrub_cache_hits = 0
    scrub_cache_misses = 0
    total = len(files)
    for index, file in enumerate(files, start=1):
        submission = _submission_for_file(session, job, file)
        cache_file = cache_submission_file(session, job, submission, file, provider)
        if getattr(cache_file, "_cache_hit", False):
            file_cache_hits += 1
        else:
            file_cache_misses += 1
        cached_scrub = _draft_submission(session, job, submission, cache_file, grading_engine)
        if cached_scrub and cached_scrub.cache_hit:
            scrub_cache_hits += 1
        elif cached_scrub:
            scrub_cache_misses += 1
        if on_progress:
            on_progress(index, total, file.source_name)
        if on_submission:
            on_submission(index, total, file.source_name, grading_submission_snapshot(session, submission))

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
    job.submissions_graded = sum(1 for row in attempts if row.status == "completed")
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


def retry_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    provider: GoogleProvider,
    grading_engine: GradingEngine | None = None,
) -> GradingJob:
    grading_engine = grading_engine or get_grading_engine()
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
    file = SubmissionFile(
        id=submission.id,
        course_id=job.course_id,
        activity_id=job.activity_id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        mime_type=submission.mime_type,
    )
    cache_file = cache_submission_file(session, job, submission, file, provider)
    _draft_submission(session, job, submission, cache_file, grading_engine, reset_review=True)
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
    if existing and _aware(existing.expires_at) > now:
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
                flags=json.loads(existing.privacy_flags_json),
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
    extracted = extract_submission_content(cache_file)
    scrubbed = scrub_submission(session, job, submission, extracted)
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


def grading_csv(session: Session, job: GradingJob) -> str:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "student_name",
            "student_email",
            "ai_score",
            "final_score",
            "reviewed",
            "feedback",
            "confidence",
            "flag",
            "error",
        ],
    )
    writer.writeheader()
    for submission in submissions:
        writer.writerow(
            {
                "student_name": submission.student_name or "",
                "student_email": submission.student_email or "",
                "ai_score": submission.ai_score or "",
                "final_score": submission.final_score or "",
                "reviewed": submission.reviewed,
                "feedback": submission.feedback or "",
                "confidence": submission.confidence or "",
                "flag": submission.flag or "",
                "error": submission.error or "",
            }
        )
    return buffer.getvalue()


def _draft_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    cache_file: GradingFileCache,
    grading_engine: GradingEngine,
    reset_review: bool = False,
) -> CachedScrubbedSubmission:
    log_debug(
        logger,
        "grading.submission.draft.start",
        job_id=job.id,
        submission_id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        cache_file_id=cache_file.id,
        engine=grading_engine.name,
        reset_review=reset_review,
    )
    cached_scrub = scrub_submission_cached(session, job, submission, cache_file)
    extracted = cached_scrub.extracted
    scrubbed = cached_scrub.scrubbed
    settings = get_settings()
    criteria = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job.id)
    ).all()
    retry_count = len(
        session.exec(
            select(GradingAiAttempt).where(GradingAiAttempt.submission_id == submission.id)
        ).all()
    )

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
        return cached_scrub

    if scrubbed.report.status in {"failed", "high_reidentification_risk"}:
        log_event(
            logger,
            "grading.submission.blocked_before_engine",
            job_id=job.id,
            submission_id=submission.id,
            extraction_status=extracted.status,
            extraction_error=extracted.error,
            privacy_status=scrubbed.report.status,
            privacy_flags=scrubbed.report.flags,
            scrubbed_preview=text_preview(scrubbed.content),
        )
        attempt = _record_attempt(
            session=session,
            job=job,
            submission=submission,
            engine=grading_engine,
            status="blocked",
            extraction_status=extracted.status,
            privacy_status=scrubbed.report.status,
            flags=scrubbed.report.flags,
            retry_count=retry_count,
            safe_error=extracted.error or scrubbed.report.status,
        )
        submission.flag = attempt.safe_error
        submission.error = attempt.safe_error
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
        return cached_scrub

    try:
        log_debug(
            logger,
            "grading.submission.engine_call.start",
            job_id=job.id,
            submission_id=submission.id,
            engine=grading_engine.name,
            model=getattr(grading_engine, "model", None),
            student_label=scrubbed.student_label,
            source_label=scrubbed.source_label,
            mime_type=submission.mime_type,
            content_chars=len(scrubbed.content),
            content_preview=text_preview(scrubbed.content),
        )
        result = grading_engine.grade(
            GradingEngineRequest(
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
                student_label=scrubbed.student_label,
                source_label=scrubbed.source_label,
                mime_type=submission.mime_type,
                content=scrubbed.content,
            )
        )
    except Exception:
        log_error(
            logger,
            "grading.submission.engine_call.failed",
            job_id=job.id,
            submission_id=submission.id,
            engine=grading_engine.name,
        )
        attempt = _record_attempt(
            session=session,
            job=job,
            submission=submission,
            engine=grading_engine,
            status="failed",
            extraction_status=extracted.status,
            privacy_status=scrubbed.report.status,
            flags=scrubbed.report.flags,
            retry_count=retry_count,
            safe_error="grading_engine_failed",
        )
        submission.flag = attempt.safe_error
        submission.error = attempt.safe_error
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
        return cached_scrub

    flags = sorted(set([*scrubbed.report.flags, *result.flags]))
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
        combined_flags=flags,
    )
    _record_attempt(
        session=session,
        job=job,
        submission=submission,
        engine=grading_engine,
        status="completed",
        extraction_status=extracted.status,
        privacy_status=scrubbed.report.status,
        flags=flags,
        retry_count=retry_count,
        prompt_tokens=attempt_metadata["prompt_tokens"],
        completion_tokens=attempt_metadata["completion_tokens"],
        token_count=attempt_metadata["token_count"],
        cached_prompt_tokens=attempt_metadata["cached_prompt_tokens"],
        cache_write_tokens=attempt_metadata["cache_write_tokens"],
        cost_cents=attempt_metadata["cost_cents"],
        latency_ms=attempt_metadata["latency_ms"],
    )
    _apply_criterion_notes(session, criteria, result.criterion_notes or [])
    cowrite = job.teacher_loop == "cowrite"
    auto_accept = (
        job.teacher_loop == "auto"
        and result.confidence >= settings.grading_auto_accept_confidence
        and not result.flags
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
    submission.flag = None if auto_accept else flags[0] if flags else None
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
    return cached_scrub


def _apply_criterion_notes(
    session: Session,
    criteria: list[GradingCriterion],
    criterion_notes: list[dict[str, str]],
) -> None:
    notes_by_name = {
        note["criterion"].strip().lower(): note["note"].strip()
        for note in criterion_notes
        if note.get("criterion") and note.get("note")
    }
    if not notes_by_name:
        return
    for criterion in criteria:
        note = notes_by_name.get(criterion.name.strip().lower())
        if note:
            criterion.latest_ai_note = note
            session.add(criterion)


def _record_attempt(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    engine: GradingEngine,
    status: str,
    extraction_status: str,
    privacy_status: str,
    flags: list[str],
    retry_count: int,
    safe_error: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    token_count: int | None = None,
    cached_prompt_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    cost_cents: float | None = None,
    latency_ms: int | None = None,
) -> GradingAiAttempt:
    attempt = GradingAiAttempt(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        engine=engine.name,
        model=getattr(engine, "model", None),
        status=status,
        extraction_status=extraction_status,
        privacy_status=privacy_status,
        safe_error=safe_error,
        flags_json=json.dumps(flags),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        token_count=token_count,
        cached_prompt_tokens=cached_prompt_tokens,
        cache_write_tokens=cache_write_tokens,
        cost_cents=cost_cents,
        latency_ms=latency_ms,
        retry_count=retry_count,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    log_event(
        logger,
        "grading.attempt.record",
        attempt_id=attempt.id,
        job_id=job.id,
        submission_id=submission.id,
        engine=attempt.engine,
        model=attempt.model,
        status=attempt.status,
        extraction_status=attempt.extraction_status,
        privacy_status=attempt.privacy_status,
        safe_error=attempt.safe_error,
        flags=flags,
        prompt_tokens=attempt.prompt_tokens,
        completion_tokens=attempt.completion_tokens,
        token_count=attempt.token_count,
        cached_prompt_tokens=attempt.cached_prompt_tokens,
        cache_write_tokens=attempt.cache_write_tokens,
        cost_cents=attempt.cost_cents,
        latency_ms=attempt.latency_ms,
        retry_count=attempt.retry_count,
    )
    return attempt


def _attempt_metadata(grading_engine: GradingEngine) -> dict[str, int | float | None]:
    usage = getattr(grading_engine, "last_usage", {}) or {}
    prompt_tokens = _int_or_none(usage.get("prompt_tokens"))
    completion_tokens = _int_or_none(usage.get("completion_tokens"))
    token_count = _int_or_none(usage.get("total_tokens"))
    cached_prompt_tokens = _int_or_none(usage.get("cache_read_input_tokens"))
    cache_write_tokens = _int_or_none(usage.get("cache_creation_input_tokens"))
    latency_ms = _int_or_none(getattr(grading_engine, "last_latency_ms", None))
    cost_cents: float | None = None

    if (
        grading_engine.name == "litellm"
        and prompt_tokens is not None
        and completion_tokens is not None
    ):
        cost_cents = _completion_cost_cents(grading_engine)
        if cost_cents is None:
            from .llm_catalog import estimate_cost_cents, load_llm_catalog

            catalog_model = getattr(grading_engine, "catalog_model", None)
            if catalog_model is None:
                model_id = getattr(grading_engine, "model", None)
                catalog_model = load_llm_catalog().models.get(model_id)
            if catalog_model is not None:
                cost_cents = estimate_cost_cents(
                    catalog_model,
                    prompt_tokens,
                    completion_tokens,
                )

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "token_count": token_count,
        "cached_prompt_tokens": cached_prompt_tokens,
        "cache_write_tokens": cache_write_tokens,
        "cost_cents": cost_cents,
        "latency_ms": latency_ms,
    }


def _completion_cost_cents(grading_engine: GradingEngine) -> float | None:
    response = getattr(grading_engine, "last_response", None)
    if response is None:
        return None
    try:
        cost_usd = litellm.completion_cost(completion_response=response)
    except Exception:
        return None
    try:
        return round(float(cost_usd) * 100, 4)
    except (TypeError, ValueError):
        return None


def _sum_optional(values) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _sum_float_optional(values) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present), 4)


def _submission_read(
    submission: GradingSubmission,
    attempt: GradingAiAttempt | None,
) -> GradingSubmissionRead:
    return GradingSubmissionRead(
        id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        mime_type=submission.mime_type,
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
        ai_engine=attempt.engine if attempt else None,
        ai_model=attempt.model if attempt else None,
        ai_safe_error=attempt.safe_error if attempt else None,
        ai_flags=json.loads(attempt.flags_json) if attempt else [],
        ai_prompt_tokens=attempt.prompt_tokens if attempt else None,
        ai_completion_tokens=attempt.completion_tokens if attempt else None,
        ai_token_count=attempt.token_count if attempt else None,
        ai_cached_prompt_tokens=attempt.cached_prompt_tokens if attempt else None,
        ai_cache_write_tokens=attempt.cache_write_tokens if attempt else None,
        ai_cost_cents=attempt.cost_cents if attempt else None,
        ai_latency_ms=attempt.latency_ms if attempt else None,
    )


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _submission_for_file(
    session: Session,
    job: GradingJob,
    file: SubmissionFile,
) -> GradingSubmission:
    existing = session.exec(
        select(GradingSubmission)
        .where(GradingSubmission.job_id == job.id)
        .where(GradingSubmission.source_file_id == file.source_file_id)
    ).first()
    if existing:
        log_event(
            logger,
            "grading.submission.hit",
            job_id=job.id,
            submission_id=existing.id,
            source_file_id=file.source_file_id,
            student_email=existing.student_email,
            student_name=existing.student_name,
        )
        return existing
    row = GradingSubmission(
        id=str(uuid4()),
        job_id=job.id,
        student_email=file.student_email,
        student_name=file.student_name,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=file.mime_type,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log_event(
        logger,
        "grading.submission.create",
        job_id=job.id,
        submission_id=row.id,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        student_email=file.student_email,
        student_name=file.student_name,
        mime_type=file.mime_type,
    )
    return row


def _identity_hash(submission: GradingSubmission) -> str:
    payload = "\0".join(
        [
            submission.student_name or "",
            submission.student_email or "",
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _refresh_counts(session: Session, job: GradingJob) -> None:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    job.total_submissions = len(submissions)
    job.reviewed_submissions = sum(1 for row in submissions if row.reviewed)
    job.flagged_submissions = sum(1 for row in submissions if row.flag or row.error)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
