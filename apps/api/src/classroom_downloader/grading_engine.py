from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from .observability import get_logger, log_event, text_preview


logger = get_logger(__name__)


@dataclass(frozen=True)
class GradingEngineRequest:
    job_id: str
    submission_id: str
    activity_title: str
    rubric_mode: str
    teacher_loop: str
    rubric_text: str | None
    criteria: list[dict[str, str | int | None]]
    student_label: str
    source_label: str
    mime_type: str
    content: str


@dataclass(frozen=True)
class GradingEngineResult:
    score: float | None
    confidence: float
    feedback: str
    flags: list[str]
    criterion_notes: list[dict[str, str]] | None = None


class GradingEngine(Protocol):
    name: str
    model: str | None

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        ...


class MockGradingEngine:
    name = "mock"
    model = None

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        log_event(
            logger,
            "grading_engine.mock.request",
            job_id=request.job_id,
            submission_id=request.submission_id,
            activity_title=request.activity_title,
            rubric_mode=request.rubric_mode,
            teacher_loop=request.teacher_loop,
            rubric_text=bool(request.rubric_text),
            criteria_count=len(request.criteria),
            student_label=request.student_label,
            source_label=request.source_label,
            mime_type=request.mime_type,
            content_chars=len(request.content),
            content_preview=text_preview(request.content),
        )
        seed = sha256(
            f"{request.job_id}|{request.submission_id}|{request.student_label}|{request.source_label}".encode(
                "utf-8"
            )
        ).hexdigest()
        score = None if request.teacher_loop == "cowrite" else float(62 + (int(seed[:4], 16) % 36))
        confidence = round(0.72 + ((int(seed[4:8], 16) % 24) / 100), 2)
        band_score = score or 0
        band = "strong" if band_score >= 85 else "developing" if band_score >= 72 else "emerging"
        flags: list[str] = []
        if request.mime_type.startswith("image/"):
            flags.append("visual_submission")
            confidence = min(confidence, 0.78)
        feedback = (
            f"{request.student_label} has an {band} draft for {request.activity_title}. "
            "The teacher should confirm evidence quality before finalizing."
        )
        feedback += f" Confidence: {int(confidence * 100)}%."
        result = GradingEngineResult(
            score=score,
            confidence=confidence,
            feedback=feedback,
            flags=flags,
            criterion_notes=[],
        )
        log_event(
            logger,
            "grading_engine.mock.response",
            job_id=request.job_id,
            submission_id=request.submission_id,
            score=result.score,
            confidence=result.confidence,
            flags=result.flags,
            feedback=result.feedback,
        )
        return result


DEFAULT_GRADING_ENGINE: GradingEngine = MockGradingEngine()


def get_grading_engine() -> GradingEngine:
    from .settings import get_settings

    settings = get_settings()
    if settings.grading_engine == "mock":
        return DEFAULT_GRADING_ENGINE
    if settings.grading_engine == "litellm":
        from .litellm_engine import LiteLlmGradingEngine
        from .llm_catalog import load_llm_catalog

        catalog = load_llm_catalog(settings)
        model = catalog.models.get(settings.litellm_model)
        if model is None or not model.enabled:
            raise ValueError("grading_model_not_enabled")
        return LiteLlmGradingEngine(
            model=model,
            timeout_seconds=settings.litellm_timeout_seconds,
            max_retries=settings.litellm_max_retries,
        )
    raise ValueError("unknown_grading_engine")
