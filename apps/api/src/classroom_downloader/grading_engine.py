from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol


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
        return GradingEngineResult(
            score=score,
            confidence=confidence,
            feedback=feedback,
            flags=flags,
        )


DEFAULT_GRADING_ENGINE: GradingEngine = MockGradingEngine()
