import json
from uuid import uuid4

import litellm

from sqlmodel import Session

from ..grading_engine import GradingEngine
from ..models import GradingAiAttempt, GradingJob, GradingSubmission
from ..observability import get_logger, log_event
from ._common import _int_or_none, _sum_optional, _sum_float_optional

logger = get_logger(__name__)


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
    privacy_flags: list[str] | None = None,
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
        privacy_flags_json=json.dumps(privacy_flags or []),
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
            from ..llm_catalog import estimate_cost_cents, load_llm_catalog

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
