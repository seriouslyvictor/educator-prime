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
    OutlierBatchRequest,
    OutlierFlag,
    OutlierSubmission,
    RubricInferenceRequest,
    VisionExtractionRequest,
    VisionExtractionResult,
)
from .llm_catalog import LlmModelEntry
from .llm_errors import LlmCallError, classify_llm_exception
from .observability import get_logger, log_event
from .settings import get_settings


logger = get_logger(__name__)
# Output budgets. Generous on purpose: the grading models in use are cheap and
# support ~64k output, so the real ceiling is model.max_output_tokens (applied
# via min() below). PDFs get the largest budget so multi-page transcriptions are
# not clipped — note the model still chooses how much to emit, so the vision
# prompt also forbids summarizing.
DEFAULT_MAX_OUTPUT_TOKENS = 4096
MAX_VISION_OUTPUT_TOKENS = 8192
MAX_PDF_OUTPUT_TOKENS = 32768


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
        self.max_vision_output_tokens = min(
            model.max_output_tokens or MAX_VISION_OUTPUT_TOKENS, MAX_VISION_OUTPUT_TOKENS
        )
        self.max_pdf_output_tokens = min(
            model.max_output_tokens or MAX_PDF_OUTPUT_TOKENS, MAX_PDF_OUTPUT_TOKENS
        )
        self.last_usage: dict[str, int] = {}
        self.last_latency_ms: int | None = None
        self.last_response: Any | None = None
        self.last_prompt_text: str | None = None
        self.last_response_text: str | None = None

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        messages = _build_messages(request)
        self.last_prompt_text = request.content
        self.last_response_text = None
        self.last_response = None
        self.last_usage = {}
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
        self.last_response_text = _response_content(response)
        result = parse_litellm_result(
            self.last_response_text,
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

    def review_outliers(self, request: OutlierBatchRequest) -> list[OutlierFlag]:
        settings = get_settings()
        chunks = chunk_outlier_submissions(
            request,
            model=self.model,
            max_input_tokens=self.catalog_model.max_input_tokens or 128000,
            context_fraction=settings.grading_outlier_context_fraction,
            max_submissions=settings.grading_outlier_batch_max_submissions,
        )
        flags: list[OutlierFlag] = []
        self.last_prompt_text = None
        self.last_response_text = None
        self.last_response = None
        self.last_usage = {}
        log_event(
            logger,
            "grading_engine.litellm.review_outliers.plan",
            job_id=request.job_id,
            model=self.model,
            submission_count=len(request.submissions),
            chunk_count=len(chunks),
        )
        for chunk in chunks:
            chunk_request = OutlierBatchRequest(
                job_id=request.job_id,
                activity_title=request.activity_title,
                submissions=chunk,
            )
            messages = build_outlier_messages(chunk_request)
            started = time.monotonic()
            response = litellm.completion(
                model=self.model,
                messages=messages,
                timeout=self.timeout_seconds,
                num_retries=self.max_retries,
                max_tokens=min(self.max_output_tokens, 2048),
                response_format=_outlier_response_format(self.catalog_model),
            )
            self.last_response = response
            self.last_latency_ms = int((time.monotonic() - started) * 1000)
            self.last_usage = _usage_dict(getattr(response, "usage", None))
            self.last_response_text = _response_content(response)
            self.last_prompt_text = _safe_messages_text(messages)
            parsed = parse_outlier_flags(self.last_response_text)
            valid_ids = {row.id for row in chunk}
            flags.extend(flag for flag in parsed if flag.id in valid_ids)
            log_event(
                logger,
                "grading_engine.litellm.review_outliers.response",
                job_id=request.job_id,
                model=self.model,
                chunk_size=len(chunk),
                flags_count=len(parsed),
                usage=self.last_usage,
                latency_ms=self.last_latency_ms,
            )
        return flags

    def extract_image(
        self, request: VisionExtractionRequest
    ) -> VisionExtractionResult:
        messages = _build_vision_messages(request)
        self.last_prompt_text = _safe_messages_text(messages)
        self.last_response_text = None
        self.last_response = None
        self.last_usage = {}
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
        is_pdf = request.image_mime_type.lower() == "application/pdf"
        vision_max_tokens = self.max_pdf_output_tokens if is_pdf else self.max_vision_output_tokens
        started = time.monotonic()
        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                timeout=self.timeout_seconds,
                num_retries=self.max_retries,
                max_tokens=vision_max_tokens,
                response_format=_vision_response_format(self.catalog_model),
            )
            self.last_response = response
            self.last_latency_ms = int((time.monotonic() - started) * 1000)
            self.last_usage = _usage_dict(getattr(response, "usage", None))
            self.last_response_text = _response_content(response)
            result = parse_vision_extraction_result(self.last_response_text)
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


def build_outlier_messages(request: OutlierBatchRequest) -> list[dict[str, str]]:
    blocks: list[str] = []
    for submission in request.submissions:
        attrs = (
            f'id={quoteattr(submission.id)} '
            f'label={quoteattr(submission.student_label)} '
            f'score={quoteattr("" if submission.score is None else str(submission.score))}'
        )
        body = escape(
            "Draft feedback:\n"
            + submission.feedback
            + "\n\nScrubbed submission:\n"
            + submission.content
        )
        blocks.append(f"<submission {attrs}>\n{body}\n</submission>")
    return [
        {
            "role": "system",
            "content": (
                "Review the whole class after draft grading. Return only genuine outliers: "
                "wrong exercise, delivery far outside the class norm, or a student in clear difficulty. "
                "Do not restate ordinary rubric feedback. Respond with JSON only as "
                "{\"flags\":[{\"id\":string,\"reason\":string}]}. Return an empty flags array when there are no true exceptions. "
                "Write reasons in Brazilian Portuguese."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Activity title: {request.activity_title}\n\n"
                "Submissions are XML-delimited and already privacy-scrubbed.\n"
                + "\n".join(blocks)
            ),
        },
    ]


def parse_outlier_flags(content: str) -> list[OutlierFlag]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed_llm_response") from exc
    rows = payload.get("flags") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("malformed_llm_response")
    flags: list[OutlierFlag] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        flag_id = row.get("id")
        reason = row.get("reason")
        if isinstance(flag_id, str) and flag_id.strip() and isinstance(reason, str) and reason.strip():
            flags.append(OutlierFlag(id=flag_id.strip(), reason=reason.strip()))
    return flags


def chunk_outlier_submissions(
    request: OutlierBatchRequest,
    *,
    model: str,
    max_input_tokens: int,
    context_fraction: float,
    max_submissions: int,
) -> list[list[OutlierSubmission]]:
    if not request.submissions:
        return []
    max_submissions = max(1, max_submissions)
    budget = max(1, int(max_input_tokens * context_fraction))
    chunks: list[list[OutlierSubmission]] = []
    current: list[OutlierSubmission] = []
    for submission in request.submissions:
        candidate = [*current, submission]
        candidate_request = OutlierBatchRequest(request.job_id, request.activity_title, candidate)
        token_count = _message_token_count(model, build_outlier_messages(candidate_request))
        reserve = 128 * len(candidate)
        if current and (len(candidate) > max_submissions or token_count + reserve > budget):
            chunks.append(current)
            current = [submission]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _message_token_count(model: str, messages: list[dict[str, str]]) -> int:
    try:
        count = litellm.token_counter(model=model, messages=messages)
    except Exception:
        count = len(json.dumps(messages, ensure_ascii=True)) // 4
    try:
        return int(count)
    except (TypeError, ValueError):
        return len(json.dumps(messages, ensure_ascii=True)) // 4


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
                "all weights sum to 100. Return a maximum of 6 criteria. "
                "Always write criterion names and descriptions in Brazilian Portuguese, "
                "regardless of the assignment language, rubric notes, or sample submissions."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _build_vision_messages(request: VisionExtractionRequest) -> list[dict[str, Any]]:
    context = {
        "activity_title": request.activity_title,
        "source_label": request.source_label,
    }
    mime = request.image_mime_type.lower()
    if mime == "application/pdf":
        file_data = "data:application/pdf;base64," + b64encode(request.image_data).decode("ascii")
        media_part: dict[str, Any] = {"type": "file", "file": {"file_data": file_data}}
    else:
        image_url = f"data:{mime};base64," + b64encode(request.image_data).decode("ascii")
        media_part = {"type": "image_url", "image_url": {"url": image_url}}
    return [
        {
            "role": "system",
            "content": (
                "You transcribe student work from images or PDF documents for a Brazilian teacher. "
                "Images may be photographed computer screens, handwritten assignments, "
                "code or terminal screenshots, frontend/UI screenshots, documents, "
                "spreadsheets, IDEs, or other computer work. PDF documents may be "
                "typed or scanned documents, exported Google Docs, spreadsheets, or "
                "presentations. Identify content_kind. "
                "Transcribe the student's work faithfully and in full: reproduce every "
                "page and section verbatim, in reading order, preserving the original "
                "wording. Do not summarize, abbreviate, paraphrase, or skip any part — "
                "even for long multi-page documents, transcribe the whole thing. "
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
                media_part,
            ],
        },
    ]


def _outlier_response_format(model: LlmModelEntry) -> dict[str, Any]:
    settings = get_settings()
    if settings.grading_structured_output == "auto" and model.supports_response_schema:
        litellm.enable_json_schema_validation = True
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "outlier_flags",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "flags": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "id": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["id", "reason"],
                            },
                        },
                    },
                    "required": ["flags"],
                },
            },
        }
    return {"type": "json_object"}


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
                                "pdf_document",
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
    criterion_scores_raw = payload.get("criterion_scores", [])
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

    # Parse per-criterion scores; degrade gracefully when absent or malformed.
    # Gate: only materialise when the model returned a non-empty valid list.
    criterion_scores: list[dict[str, str | float]] | None = None
    if isinstance(criterion_scores_raw, list) and criterion_scores_raw:
        valid: list[dict[str, str | float]] = []
        for row in criterion_scores_raw:
            if not isinstance(row, dict):
                continue
            name = row.get("criterion")
            earned = row.get("earned")
            if not isinstance(name, str) or name.strip() == "":
                continue
            try:
                earned_f = float(earned)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if earned_f < 0:
                earned_f = 0.0
            valid.append({"criterion": name.strip(), "earned": round(earned_f, 2)})
        if valid:
            criterion_scores = valid

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
        criterion_scores=criterion_scores,
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
        "pdf_document",
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
        "criterion_scores": (
            [{"criterion": "string (criterion name)", "earned": "number 0..weight"}]
            if request.criteria
            else []
        ),
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


def _safe_messages_text(messages: list[dict[str, Any]]) -> str:
    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            if "image_url" in value:
                image_url = value.get("image_url")
                if isinstance(image_url, dict):
                    url = str(image_url.get("url", ""))
                    return {
                        "type": value.get("type", "image_url"),
                        "image_url": "<image bytes>" if url else "<image>",
                    }
                return {"type": value.get("type", "image_url"), "image_url": "<image>"}
            if value.get("type") == "file" and "file" in value:
                file_obj = value.get("file")
                if isinstance(file_obj, dict) and file_obj.get("file_data"):
                    return {"type": "file", "file": "<pdf bytes>"}
                return {"type": "file", "file": "<pdf>"}
            return {key: scrub(item) for key, item in value.items()}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return json.dumps(scrub(messages), ensure_ascii=True)


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
                        "criterion_scores": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "criterion": {"type": "string"},
                                    "earned": {"type": "number", "minimum": 0},
                                },
                                "required": ["criterion", "earned"],
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
                        "criterion_scores",
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
