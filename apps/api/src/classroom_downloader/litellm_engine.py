from __future__ import annotations

import json
import time
from base64 import b64encode
from typing import Any

import litellm

from xml.sax.saxutils import escape, quoteattr

from .grading_engine import (
    GradingEngineRequest,
    GradingEngineResult,
    RubricInferenceRequest,
    VisionExtractionRequest,
    VisionExtractionResult,
)
from .llm_catalog import LlmModelEntry
from .llm_errors import LlmCallError, classify_llm_exception
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
        self.max_vision_output_tokens = min(model.max_output_tokens or 2000, 2000)
        self.last_usage: dict[str, int] = {}
        self.last_latency_ms: int | None = None
        self.last_response: Any | None = None

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
        self.last_response = response
        self.last_latency_ms = int((time.monotonic() - started) * 1000)
        self.last_usage = _usage_dict(getattr(response, "usage", None))
        result = parse_litellm_result(
            _response_content(response),
            request_score=request.request_score,
        )

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

    def infer_rubric(
        self, request: RubricInferenceRequest
    ) -> list[dict[str, str | int | None]]:
        messages = _build_rubric_messages(request)
        log_event(
            logger,
            "grading_engine.litellm.infer_rubric.request",
            job_id=request.job_id,
            model=self.model,
            activity_title=request.activity_title,
            description_only=request.description_only,
            has_description=bool(request.activity_description),
            sample_count=len(request.samples),
        )
        started = time.monotonic()
        response = litellm.completion(
            model=self.model,
            messages=messages,
            timeout=self.timeout_seconds,
            num_retries=self.max_retries,
            max_tokens=self.max_output_tokens,
            response_format=_rubric_response_format(self.catalog_model),
        )
        self.last_response = response
        self.last_latency_ms = int((time.monotonic() - started) * 1000)
        self.last_usage = _usage_dict(getattr(response, "usage", None))
        criteria = parse_rubric_criteria(_response_content(response))
        log_event(
            logger,
            "grading_engine.litellm.infer_rubric.response",
            job_id=request.job_id,
            model=self.model,
            criteria_count=len(criteria),
            usage=self.last_usage,
            latency_ms=self.last_latency_ms,
        )
        return criteria

    def extract_image(
        self, request: VisionExtractionRequest
    ) -> VisionExtractionResult:
        messages = _build_vision_messages(request)
        log_event(
            logger,
            "grading_engine.litellm.extract_image.request",
            job_id=request.job_id,
            submission_id=request.submission_id,
            model=self.model,
            catalog_model=self.catalog_model.id,
            activity_title=request.activity_title,
            source_label=request.source_label,
            image_mime_type=request.image_mime_type,
            byte_size=len(request.image_data),
        )
        started = time.monotonic()
        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                timeout=self.timeout_seconds,
                num_retries=self.max_retries,
                max_tokens=self.max_vision_output_tokens,
                response_format=_vision_response_format(self.catalog_model),
            )
            self.last_response = response
            self.last_latency_ms = int((time.monotonic() - started) * 1000)
            self.last_usage = _usage_dict(getattr(response, "usage", None))
            result = parse_vision_extraction_result(_response_content(response))
        except LlmCallError:
            self.last_latency_ms = int((time.monotonic() - started) * 1000)
            raise
        except Exception as exc:
            self.last_latency_ms = int((time.monotonic() - started) * 1000)
            classified = classify_llm_exception(exc)
            if classified.code == "malformed_llm_response":
                raise LlmCallError("vision_malformed_response", True, classified.detail) from exc
            raise classified from exc

        log_event(
            logger,
            "grading_engine.litellm.extract_image.response",
            job_id=request.job_id,
            submission_id=request.submission_id,
            model=self.model,
            content_kind=result.content_kind,
            legibility=result.legibility,
            pii_observed=result.pii_observed,
            usage=self.last_usage,
            latency_ms=self.last_latency_ms,
        )
        return result


def build_sample_xml(samples: list[dict[str, str]]) -> str:
    """Bundle scrubbed submissions into XML-delimited blocks for the prompt.
    XML tags separate the samples cleanly with minimal escaping."""
    blocks: list[str] = []
    for sample in samples:
        attrs = (
            f"label={quoteattr(str(sample.get('label', '')))} "
            f"source={quoteattr(str(sample.get('source_label', '')))} "
            f"mime={quoteattr(str(sample.get('mime_type', '')))}"
        )
        body = escape(str(sample.get("content", "")))
        blocks.append(f"<submission {attrs}>\n{body}\n</submission>")
    return "\n".join(blocks)


def _build_rubric_messages(request: RubricInferenceRequest) -> list[dict[str, str]]:
    sections = [
        f"Activity title: {request.activity_title}",
        f"Activity description: {request.activity_description or '(none provided)'}",
    ]


def _build_vision_messages(request: VisionExtractionRequest) -> list[dict[str, Any]]:
    context = {
        "activity_title": request.activity_title,
        "source_label": request.source_label,
    }
    image_url = "data:image/jpeg;base64," + b64encode(request.image_data).decode("ascii")
    return [
        {
            "role": "system",
            "content": (
                "You transcribe student work from images for a Brazilian teacher. "
                "Images may be photographed computer screens, handwritten assignments, "
                "code or terminal screenshots, frontend/UI screenshots, documents, "
                "spreadsheets, IDEs, or other computer work. Identify content_kind. "
                "Transcribe the student's work faithfully and completely in PT-BR. "
                "For visual work, describe layout, structure, colors, and visible output "
                "succinctly in PT-BR because the grader will only see this text. "
                "Replace any visible personal name, ID number, email, phone, or handle at "
                "the source with [student], [cpf], [email], [phone], or [social]; never "
                "copy it verbatim. Report the matching pii_observed category. Faces and "
                "ID documents are only reported in pii_observed and never described. "
                "Use legibility='full' when essentially everything is readable, 'partial' "
                "when meaningful chunks are not readable, and 'unreadable' when the work "
                "cannot be assessed. Respond with JSON only."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": json.dumps(context, ensure_ascii=True)},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]
    if request.rubric_text:
        sections.append(f"Teacher rubric notes: {request.rubric_text}")
    if not request.description_only and request.samples:
        sections.append(
            "Sample student submissions (XML-delimited, already redacted):\n"
            + build_sample_xml(request.samples)
        )
    user_content = "\n\n".join(sections)
    return [
        {
            "role": "system",
            "content": (
                "Design a grading rubric for this assignment. Infer the criteria a "
                "teacher would use to evaluate the work, favoring the activity "
                "description when it is informative and the sample submissions when it "
                "is thin. Respond with JSON only: an object with a 'criteria' array of "
                "{name, weight, description}, where weight is an integer percentage and "
                "all weights sum to 100. return a maximum of 6 criteria."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _rubric_response_format(model: LlmModelEntry) -> dict[str, Any]:
    settings = get_settings()
    if (
        settings.grading_structured_output == "auto"
        and model.supports_response_schema
    ):
        litellm.enable_json_schema_validation = True
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "rubric_criteria",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "criteria": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "weight": {"type": "integer", "minimum": 1, "maximum": 100},
                                    "description": {"type": ["string", "null"]},
                                },
                                "required": ["name", "weight", "description"],
                            },
                        },
                    },
                    "required": ["criteria"],
                },
            },
        }
    return {"type": "json_object"}


def _vision_response_format(model: LlmModelEntry) -> dict[str, Any]:
    settings = get_settings()
    if (
        settings.grading_structured_output == "auto"
        and model.supports_response_schema
    ):
        litellm.enable_json_schema_validation = True
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "vision_extraction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "transcription": {"type": "string"},
                        "visual_description": {"type": "string"},
                        "content_kind": {
                            "type": "string",
                            "enum": [
                                "handwriting",
                                "screen_photo",
                                "code_screenshot",
                                "app_screenshot",
                                "document_photo",
                                "other",
                            ],
                        },
                        "legibility": {
                            "type": "string",
                            "enum": ["full", "partial", "unreadable"],
                        },
                        "pii_observed": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "name_visible",
                                    "face",
                                    "id_document",
                                    "contact_info",
                                    "other_pii",
                                ],
                            },
                        },
                    },
                    "required": [
                        "transcription",
                        "visual_description",
                        "content_kind",
                        "legibility",
                        "pii_observed",
                    ],
                },
            },
        }
    return {"type": "json_object"}


def parse_rubric_criteria(content: str) -> list[dict[str, str | int | None]]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed_llm_response") from exc
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("criteria", [])
    else:
        raise ValueError("malformed_llm_response")
    if not isinstance(rows, list):
        raise ValueError("malformed_llm_response")
    criteria: list[dict[str, str | int | None]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        weight = row.get("weight")
        if not isinstance(name, str) or not isinstance(weight, int):
            continue
        description = row.get("description")
        criteria.append(
            {
                "name": name,
                "weight": weight,
                "description": description if isinstance(description, str) else None,
            }
        )
    return criteria


def parse_litellm_result(
    content: str,
    request_score: bool = True,
) -> GradingEngineResult:
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
    inferred_criteria = payload.get("inferred_criteria", [])
    flags = payload.get("flags", [])

    if request_score:
        # Scored levels (approve/auto) must return a calibrated 0-100 score; a
        # missing, null, or out-of-range value is a malformed draft, not a
        # silent scoreless row.
        if score is None:
            raise ValueError("malformed_llm_response")
    else:
        # Cowrite withholds the numeric grade: ignore any score the model emits.
        score = None
    if confidence is None:
        raise ValueError("malformed_llm_response")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError("malformed_llm_response")
    if not isinstance(criterion_notes, list):
        raise ValueError("malformed_llm_response")
    if not isinstance(inferred_criteria, list):
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
        inferred_criteria=[
            criterion
            for criterion in inferred_criteria
            if isinstance(criterion, dict)
            and isinstance(criterion.get("name"), str)
            and isinstance(criterion.get("weight"), int)
        ],
    )


def parse_vision_extraction_result(content: str) -> VisionExtractionResult:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LlmCallError("vision_malformed_response", True, str(exc)) from exc
    if not isinstance(payload, dict):
        raise LlmCallError("vision_malformed_response", True, "payload_not_object")

    transcription = payload.get("transcription")
    visual_description = payload.get("visual_description")
    content_kind = payload.get("content_kind")
    legibility = payload.get("legibility")
    pii_observed = payload.get("pii_observed")
    if not isinstance(transcription, str) or not isinstance(visual_description, str):
        raise LlmCallError("vision_malformed_response", True, "missing_text_fields")
    if content_kind not in {
        "handwriting",
        "screen_photo",
        "code_screenshot",
        "app_screenshot",
        "document_photo",
        "other",
    }:
        raise LlmCallError("vision_malformed_response", True, "invalid_content_kind")
    if legibility not in {"full", "partial", "unreadable"}:
        raise LlmCallError("vision_malformed_response", True, "invalid_legibility")
    if not isinstance(pii_observed, list) or not all(
        item in {"name_visible", "face", "id_document", "contact_info", "other_pii"}
        for item in pii_observed
    ):
        raise LlmCallError("vision_malformed_response", True, "invalid_pii_observed")
    if (
        not transcription.strip()
        and not visual_description.strip()
        and legibility != "unreadable"
    ):
        raise LlmCallError("vision_malformed_response", True, "empty_readable_image")
    return VisionExtractionResult(
        transcription=transcription.strip(),
        visual_description=visual_description.strip(),
        content_kind=content_kind,
        legibility=legibility,
        pii_observed=pii_observed,
    )


def _build_messages(request: GradingEngineRequest) -> list[dict[str, str]]:
    cowrite = not request.request_score
    required_json_shape = {
        "score": "omit or null in cowrite mode; otherwise number from 0 to 100",
        "confidence": "number from 0 to 1",
        "feedback": "Teacher facing feedback, this feedback must be objective, direct and concise, pointing out only what is missing",
        "inferred_criteria": (
            [{"name": "string", "weight": "integer percentage", "description": "string or null"}]
            if request.rubric_mode == "infer"
            else []
        ),
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
                "Your response must always be in PT-BR"
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
                        "inferred_criteria": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "weight": {"type": "integer", "minimum": 1, "maximum": 100},
                                    "description": {"type": ["string", "null"]},
                                },
                                "required": ["name", "weight", "description"],
                            },
                        },
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
                        "inferred_criteria",
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
