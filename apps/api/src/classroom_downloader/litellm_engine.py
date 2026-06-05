from __future__ import annotations

import json
import time
from typing import Any

import litellm

from .grading_engine import GradingEngineRequest, GradingEngineResult
from .llm_catalog import LlmModelEntry
from .observability import get_logger, log_event
from .settings import get_settings


logger = get_logger(__name__)
DEFAULT_MAX_OUTPUT_TOKENS = 1200


class LiteLlmGradingEngine:
    name = "litellm"

    def __init__(
        self,
        model: LlmModelEntry,
        timeout_seconds: int,
        max_retries: int,
    ) -> None:
        self.catalog_model = model
        self.model = model.litellm_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_output_tokens = min(
            model.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
            DEFAULT_MAX_OUTPUT_TOKENS,
        )
        self.last_usage: dict[str, int] = {}
        self.last_latency_ms: int | None = None

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        messages = _build_messages(request)
        log_event(
            logger,
            "grading_engine.litellm.request",
            job_id=request.job_id,
            submission_id=request.submission_id,
            model=self.model,
            catalog_model=self.catalog_model.id,
            activity_title=request.activity_title,
            rubric_mode=request.rubric_mode,
            teacher_loop=request.teacher_loop,
            student_label=request.student_label,
            source_label=request.source_label,
            mime_type=request.mime_type,
            content_chars=len(request.content),
        )
        log_event(
            logger,
            "litellm.grade.catalog_model",
            model_id=self.catalog_model.id,
            provider=self.catalog_model.provider,
            input_cost_per_token=self.catalog_model.input_cost_per_token,
            output_cost_per_token=self.catalog_model.output_cost_per_token,
            max_input_tokens=self.catalog_model.max_input_tokens,
            max_output_tokens=self.catalog_model.max_output_tokens,
            rpm_limit=self.catalog_model.rpm_limit,
            tpm_limit=self.catalog_model.tpm_limit,
        )

        started = time.monotonic()
        response = litellm.completion(
            model=self.model,
            messages=messages,
            timeout=self.timeout_seconds,
            num_retries=self.max_retries,
            max_tokens=self.max_output_tokens,
            response_format=_response_format(self.catalog_model),
        )
        self.last_latency_ms = int((time.monotonic() - started) * 1000)
        self.last_usage = _usage_dict(getattr(response, "usage", None))
        result = parse_litellm_result(_response_content(response))

        log_event(
            logger,
            "grading_engine.litellm.response",
            job_id=request.job_id,
            submission_id=request.submission_id,
            model=self.model,
            score=result.score,
            confidence=result.confidence,
            flags=result.flags,
            usage=self.last_usage,
            latency_ms=self.last_latency_ms,
        )
        return result


def parse_litellm_result(content: str) -> GradingEngineResult:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed_llm_response") from exc

    if not isinstance(payload, dict):
        raise ValueError("malformed_llm_response")

    score = _bounded_number(payload.get("score"), minimum=0, maximum=100)
    confidence = _bounded_number(payload.get("confidence"), minimum=0, maximum=1)
    feedback = payload.get("feedback")
    criterion_notes = payload.get("criterion_notes", [])
    flags = payload.get("flags", [])

    if confidence is None:
        raise ValueError("malformed_llm_response")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError("malformed_llm_response")
    if not isinstance(criterion_notes, list):
        raise ValueError("malformed_llm_response")
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ValueError("malformed_llm_response")

    return GradingEngineResult(
        score=score,
        confidence=confidence,
        feedback=feedback,
        flags=flags,
        criterion_notes=[
            note
            for note in criterion_notes
            if isinstance(note, dict)
            and isinstance(note.get("criterion"), str)
            and isinstance(note.get("note"), str)
        ],
    )


def _build_messages(request: GradingEngineRequest) -> list[dict[str, str]]:
    cowrite = request.teacher_loop == "cowrite"
    required_json_shape = {
        "score": "omit or null in cowrite mode; otherwise number from 0 to 100",
        "confidence": "number from 0 to 1",
        "feedback": "non-empty teacher-facing draft feedback",
        "criterion_notes": [{"criterion": "string", "note": "string"}],
        "flags": ["string"],
    }
    user_payload = {
        "activity_title": request.activity_title,
        "rubric_mode": request.rubric_mode,
        "teacher_loop": request.teacher_loop,
        "rubric_text": request.rubric_text,
        "criteria": request.criteria,
        "student_label": request.student_label,
        "source_label": request.source_label,
        "mime_type": request.mime_type,
        "submission_text": request.content,
        "required_json_shape": required_json_shape,
    }
    return [
        {
            "role": "system",
            "content": (
                "Draft grades for the teacher to review. Respond with JSON only. "
                "Use the rubric text and criteria when present. "
                "This is not a final grade; the teacher must review and approve it. "
                + (
                    "In cowrite mode, do not assign a numeric score; return reasoning "
                    "and criterion notes for the teacher to grade."
                    if cowrite
                    else "Return a numeric draft score."
                )
            ),
        },
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=True),
        },
    ]


def _response_format(model: LlmModelEntry) -> dict[str, Any]:
    settings = get_settings()
    if (
        settings.grading_structured_output == "auto"
        and model.supports_response_schema
    ):
        litellm.enable_json_schema_validation = True
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "grading_draft",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "feedback": {"type": "string", "minLength": 1},
                        "criterion_notes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "criterion": {"type": "string"},
                                    "note": {"type": "string"},
                                },
                                "required": ["criterion", "note"],
                            },
                        },
                        "flags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "score",
                        "confidence",
                        "feedback",
                        "criterion_notes",
                        "flags",
                    ],
                },
            },
        }
    return {"type": "json_object"}


def _response_content(response: Any) -> str:
    choices = _get_field(response, "choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("malformed_llm_response")

    message = _get_field(choices[0], "message")
    content = _get_field(message, "content")
    if not isinstance(content, str):
        raise ValueError("malformed_llm_response")
    return content


def _usage_dict(usage: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        value = _get_field(usage, key)
        if isinstance(value, int):
            result[key] = value
    return result


def _get_field(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _bounded_number(value: Any, *, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if minimum <= number <= maximum:
        return number
    return None
