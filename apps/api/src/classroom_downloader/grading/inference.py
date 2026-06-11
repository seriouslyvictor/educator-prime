import random

from sqlmodel import Session, select

from ..grading_engine import GradingEngine, RubricInferenceRequest
from ..google_provider import GoogleProvider
from ..models import GradingCriterion, GradingJob
from ..observability import get_logger, log_error, log_event
from ..settings import get_settings
from .caching import cache_submission_file, scrub_submission_cached
from .criteria import (
    _is_substantial_description,
    _normalize_inferred_criteria,
    _normalize_weights_to_100,
    _replace_job_criteria,
)
from .submissions import _submission_for_file

logger = get_logger(__name__)


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
        if cached.scrubbed.report.status == "failed":
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
    from classroom_downloader import grading as _grading_pkg
    grading_engine = grading_engine or _grading_pkg.get_grading_engine()
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
