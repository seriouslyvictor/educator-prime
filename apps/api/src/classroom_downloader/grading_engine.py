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
    student_label: str
    source_label: str
    mime_type: str
    content: str


@dataclass(frozen=True)
class GradingEngineResult:
    score: float
    confidence: float
    feedback: str
    flags: list[str]


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
        score = float(62 + (int(seed[:4], 16) % 36))
        confidence = round(0.72 + ((int(seed[4:8], 16) % 24) / 100), 2)
        band = "strong" if score >= 85 else "developing" if score >= 72 else "emerging"
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
