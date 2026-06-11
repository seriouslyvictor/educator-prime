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
    request_score: bool = True


@dataclass(frozen=True)
class GradingEngineResult:
    score: float | None
    confidence: float
    feedback: str
    flags: list[str]
    criterion_notes: list[dict[str, str]] | None = None
    inferred_criteria: list[dict[str, str | int | None]] | None = None


@dataclass(frozen=True)
class RubricInferenceRequest:
    job_id: str
    activity_title: str
    activity_description: str | None
    rubric_text: str | None
    samples: list[dict[str, str]]
    description_only: bool = False


@dataclass(frozen=True)
class VisionExtractionRequest:
    job_id: str
    submission_id: str
    activity_title: str
    source_label: str
    image_data: bytes
    image_mime_type: str


@dataclass(frozen=True)
class VisionExtractionResult:
    transcription: str
    visual_description: str
    content_kind: str
    legibility: str
    pii_observed: list[str]


class GradingEngine(Protocol):
    name: str
    model: str | None

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        ...

    def infer_rubric(
        self, request: RubricInferenceRequest
    ) -> list[dict[str, str | int | None]]:
        ...

    def extract_image(
        self, request: VisionExtractionRequest
    ) -> VisionExtractionResult:
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

    def infer_rubric(
        self, request: "RubricInferenceRequest"
    ) -> list[dict[str, str | int | None]]:
        log_event(
            logger,
            "grading_engine.mock.infer_rubric",
            job_id=request.job_id,
            activity_title=request.activity_title,
            description_only=request.description_only,
            has_description=bool(request.activity_description),
            sample_count=len(request.samples),
        )
        # Deterministic rubric whose weights sum to 100; stable for tests.
        return [
            {"name": "Thesis", "weight": 30, "description": "States a clear, arguable claim."},
            {"name": "Evidence", "weight": 30, "description": "Supports the claim with relevant evidence."},
            {"name": "Reasoning", "weight": 25, "description": "Explains how evidence backs the claim."},
            {"name": "Mechanics", "weight": 15, "description": "Organized, readable, and correct."},
        ]

    def extract_image(
        self, request: VisionExtractionRequest
    ) -> VisionExtractionResult:
        log_event(
            logger,
            "grading_engine.mock.extract_image",
            job_id=request.job_id,
            submission_id=request.submission_id,
            activity_title=request.activity_title,
            source_label=request.source_label,
            image_mime_type=request.image_mime_type,
            byte_size=len(request.image_data),
        )
        seed = sha256(f"{request.job_id}|{request.submission_id}".encode("utf-8")).hexdigest()
        return VisionExtractionResult(
            transcription=f"Transcricao visual mock {seed[:8]} assinada por [student].",
            visual_description="Folha fotografada com resposta manuscrita legivel.",
            content_kind="handwriting",
            legibility="full",
            pii_observed=["name_visible"],
        )


DEFAULT_GRADING_ENGINE: GradingEngine = MockGradingEngine()


# Provider -> conventional env var for an explicit (live) key probe. LiteLLM
# reads these itself for the actual call; we only need the var name to resolve a
# key for `check_valid_key`. The offline readiness check below does not need it.
_PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


@dataclass(frozen=True)
class GradingReadiness:
    engine: str
    ready: bool
    status: str  # ok | mock | model_not_enabled | provider_key_missing | unknown_engine
    model: str | None
    provider: str | None
    missing_keys: list[str]
    detail: str
    probed: bool = False
    probe_ok: bool | None = None


def _missing_provider_keys(litellm_model: str) -> list[str]:
    """Offline check via litellm.validate_environment: which provider env vars
    the selected model needs but the process environment is missing."""
    import litellm

    try:
        result = litellm.validate_environment(litellm_model)
    except Exception:  # litellm could not introspect the model; do not block.
        return []
    if not isinstance(result, dict) or result.get("keys_in_environment"):
        return []
    return [key for key in (result.get("missing_keys") or []) if isinstance(key, str)]


def _probe_valid_key(litellm_model: str) -> tuple[bool | None, str]:
    """Live check via litellm.check_valid_key. Returns (ok, detail); ok is None
    when the provider key cannot be resolved for a probe (offline result stands)."""
    import os

    import litellm

    provider = litellm_model.split("/", 1)[0] if "/" in litellm_model else ""
    env_var = _PROVIDER_KEY_ENV.get(provider)
    api_key = os.environ.get(env_var) if env_var else None
    if not api_key:
        return None, "Live key probe is not supported for this provider; offline check only."
    try:
        ok = bool(litellm.check_valid_key(model=litellm_model, api_key=api_key))
    except Exception:
        return False, "Live key probe could not reach the provider."
    if ok:
        return True, f"Live key probe succeeded for {litellm_model}."
    return False, f"Live key probe rejected the credential for {litellm_model}."


def inspect_grading_readiness(settings=None, *, probe: bool = False) -> GradingReadiness:
    """Non-raising readiness report for the configured grading engine. Used by
    the health endpoint and (the offline part) by get_grading_engine."""
    from .settings import get_settings

    settings = settings or get_settings()
    engine = settings.grading_engine
    if engine == "mock":
        return GradingReadiness(
            engine="mock",
            ready=True,
            status="mock",
            model=None,
            provider=None,
            missing_keys=[],
            detail="Using the deterministic mock grader; no provider key required.",
        )
    if engine != "litellm":
        return GradingReadiness(
            engine=engine,
            ready=False,
            status="unknown_engine",
            model=None,
            provider=None,
            missing_keys=[],
            detail=f"Unknown grading engine '{engine}'.",
        )

    from .llm_catalog import load_llm_catalog

    catalog = load_llm_catalog(settings)
    model = catalog.models.get(settings.litellm_model)
    if model is None or not model.enabled:
        return GradingReadiness(
            engine="litellm",
            ready=False,
            status="model_not_enabled",
            model=settings.litellm_model,
            provider=model.provider if model else None,
            missing_keys=[],
            detail=(
                f"Model '{settings.litellm_model}' is not enabled in the catalog overlay "
                "(config/llm-model-overrides.json)."
            ),
        )

    missing = _missing_provider_keys(model.litellm_model)
    if missing:
        return GradingReadiness(
            engine="litellm",
            ready=False,
            status="provider_key_missing",
            model=model.litellm_model,
            provider=model.provider,
            missing_keys=missing,
            detail=f"Missing provider credential(s): {', '.join(missing)}.",
        )

    detail = f"{model.litellm_model} is configured and its provider key is present."
    probed = False
    probe_ok: bool | None = None
    if probe:
        probed = True
        probe_ok, detail = _probe_valid_key(model.litellm_model)
    return GradingReadiness(
        engine="litellm",
        ready=True,
        status="ok",
        model=model.litellm_model,
        provider=model.provider,
        missing_keys=[],
        detail=detail,
        probed=probed,
        probe_ok=probe_ok,
    )


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
        missing = _missing_provider_keys(model.litellm_model)
        if missing:
            log_event(
                logger,
                "grading.engine.provider_key_missing",
                model=model.litellm_model,
                provider=model.provider,
                missing_keys=missing,
            )
            raise ValueError("grading_provider_key_missing")
        return LiteLlmGradingEngine(
            model=model,
            timeout_seconds=settings.litellm_timeout_seconds,
            max_retries=settings.litellm_max_retries,
        )
    raise ValueError("unknown_grading_engine")
