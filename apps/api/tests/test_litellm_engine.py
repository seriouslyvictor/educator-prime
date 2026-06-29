import json
import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

import pytest

from classroom_downloader.grading_engine import GradingEngineRequest, OutlierBatchRequest, OutlierSubmission, RubricInferenceRequest, VisionExtractionRequest
from classroom_downloader.litellm_engine import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    MAX_PDF_OUTPUT_TOKENS,
    MAX_VISION_OUTPUT_TOKENS,
    LiteLlmGradingEngine,
    _build_messages,
    build_outlier_messages,
    chunk_outlier_submissions,
    parse_outlier_flags,
    parse_vision_extraction_result,
    parse_litellm_result,
)
from classroom_downloader.llm_errors import LlmCallError
from classroom_downloader.llm_catalog import LlmModelEntry


def model_entry(
    supports_response_schema: bool = True,
    supports_vision: bool = False,
    max_output_tokens: int = 8192,
) -> LlmModelEntry:
    return LlmModelEntry(
        id="openai/gpt-5",
        provider="openai",
        litellm_model="openai/gpt-5",
        enabled=True,
        display_name="GPT-5",
        use_cases=["grading_draft"],
        input_cost_per_token=0.000001,
        output_cost_per_token=0.000004,
        max_input_tokens=128000,
        max_output_tokens=max_output_tokens,
        supports_response_schema=supports_response_schema,
        supports_vision=supports_vision,
        rpm_limit=None,
        tpm_limit=None,
        notes="",
        raw={},
    )

def _outlier_request() -> OutlierBatchRequest:
    return OutlierBatchRequest(
        job_id="job-outliers",
        activity_title="Lista de exercicios",
        submissions=[
            OutlierSubmission(
                id="sub-1",
                student_label="student_001",
                score=92,
                feedback="Bom trabalho.",
                content="Resposta coerente com <tags> & detalhes.",
            ),
            OutlierSubmission(
                id="sub-2",
                student_label="student_002",
                score=35,
                feedback="Nao respondeu ao enunciado.",
                content="wrong exercise entirely",
            ),
        ],
    )


def test_outlier_prompt_uses_xml_and_escapes_submission_content() -> None:
    messages = build_outlier_messages(_outlier_request())
    rendered = messages[1]["content"]

    assert '<submission id="sub-1"' in rendered
    assert "Resposta coerente com &lt;tags&gt; &amp; detalhes." in rendered
    assert "Return only genuine outliers" in messages[0]["content"]


def test_parse_outlier_flags_accepts_only_id_reason_rows() -> None:
    parsed = parse_outlier_flags(
        json.dumps(
            {
                "flags": [
                    {"id": "sub-2", "reason": "Entrega de outro exercicio."},
                    {"id": "", "reason": "sem id"},
                    {"id": "sub-3", "reason": "   "},
                ]
            }
        )
    )

    assert [(flag.id, flag.reason) for flag in parsed] == [("sub-2", "Entrega de outro exercicio.")]


def test_outlier_chunking_splits_when_context_budget_is_low(monkeypatch) -> None:
    request = OutlierBatchRequest(
        job_id="job-outliers",
        activity_title="Atividade",
        submissions=[
            OutlierSubmission(str(index), f"student_{index}", 80, "ok", "x" * 120)
            for index in range(4)
        ],
    )

    monkeypatch.setattr(
        "classroom_downloader.litellm_engine.litellm.token_counter",
        lambda model, messages: len(messages[1]["content"]),
    )

    chunks = chunk_outlier_submissions(
        request,
        model="openai/gpt-5",
        max_input_tokens=650,
        context_fraction=0.8,
        max_submissions=10,
    )

    assert len(chunks) > 1
    assert [row.id for chunk in chunks for row in chunk] == ["0", "1", "2", "3"]


def test_engine_review_outliers_calls_litellm_with_schema(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {"content": json.dumps({"flags": [{"id": "sub-2", "reason": "Fora do padrao da turma."}]})}

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    engine = LiteLlmGradingEngine(model=model_entry(), timeout_seconds=30, max_retries=1)

    flags = engine.review_outliers(_outlier_request())

    assert [(flag.id, flag.reason) for flag in flags] == [("sub-2", "Fora do padrao da turma.")]
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["name"] == "outlier_flags"
    assert '<submission id="sub-2"' in captured["messages"][1]["content"]



def test_infer_rubric_prompt_requires_brazilian_portuguese(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "criteria": [
                            {
                                "name": "Clareza",
                                "weight": 100,
                                "description": "Comunica as ideias com organiza\u00e7\u00e3o.",
                            }
                        ]
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    engine = LiteLlmGradingEngine(model=model_entry(), timeout_seconds=30, max_retries=1)

    engine.infer_rubric(
        RubricInferenceRequest(
            job_id="job-criteria",
            activity_title="Essay Draft",
            activity_description="Write an argumentative essay.",
            rubric_text=None,
            samples=[],
            description_only=True,
        )
    )

    system_prompt = captured["messages"][0]["content"]
    assert "criterion names and descriptions" in system_prompt
    assert "Brazilian Portuguese" in system_prompt



def _request(
    *,
    request_score: bool = True,
    rubric_text: str | None = None,
    criteria: list[dict[str, object]] | None = None,
) -> GradingEngineRequest:
    return GradingEngineRequest(
        job_id="job-1",
        submission_id="submission-1",
        activity_title="Essay Draft",
        rubric_mode="brief",
        teacher_loop="approve" if request_score else "cowrite",
        request_score=request_score,
        rubric_text=rubric_text,
        criteria=list(criteria or []),
        student_label="student_001",
        source_label="submission_001",
        mime_type="text/plain",
        content="This is scrubbed work.",
    )


def test_parse_litellm_result_requires_structured_shape() -> None:
    parsed = parse_litellm_result(
        json.dumps(
            {
                "score": 87,
                "confidence": 0.82,
                "feedback": "Good evidence, but revise the conclusion.",
                "criterion_notes": [{"criterion": "Evidence", "note": "Uses examples."}],
                "flags": ["check_reasoning"],
            }
        )
    )

    assert parsed.score == 87
    assert parsed.confidence == 0.82
    assert parsed.feedback.startswith("Good evidence")
    assert parsed.flags == ["check_reasoning"]


def test_parse_litellm_result_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="malformed_llm_response"):
        parse_litellm_result("not json")


def _scored_payload(criterion_scores: list[dict], score: int = 80) -> str:
    return json.dumps(
        {
            "score": score,
            "confidence": 0.8,
            "feedback": "ok",
            "criterion_notes": [],
            "criterion_scores": criterion_scores,
            "flags": [],
        }
    )


def test_parse_litellm_result_normalizes_criterion_scores_to_score() -> None:
    # Model's parts don't sum to its own score (50+40=90 != 80); they must be
    # scaled so the bars reconcile with the authoritative overall score.
    parsed = parse_litellm_result(
        _scored_payload(
            [
                {"criterion": "Lógica", "earned": 50},
                {"criterion": "Estilo", "earned": 40},
            ],
            score=80,
        )
    )
    assert parsed.criterion_scores is not None
    earned = [c["earned"] for c in parsed.criterion_scores]
    assert round(sum(earned), 1) == 80.0
    # Relative split is preserved (Lógica still larger than Estilo).
    assert earned[0] > earned[1]


def test_parse_litellm_result_drops_criterion_scores_when_parts_are_zero() -> None:
    # All-zero parts but a positive score: there is no honest split, so the bars
    # are dropped rather than shown contradicting the score.
    parsed = parse_litellm_result(
        _scored_payload(
            [
                {"criterion": "Lógica", "earned": 0},
                {"criterion": "Estilo", "earned": 0},
            ],
            score=80,
        )
    )
    assert parsed.criterion_scores is None


def test_parse_vision_extraction_result_requires_structured_shape() -> None:
    parsed = parse_vision_extraction_result(
        json.dumps(
            {
                "transcription": "Resposta manuscrita.",
                "visual_description": "Folha com duas secoes.",
                "content_kind": "handwriting",
                "legibility": "partial",
                "pii_observed": ["name_visible"],
            }
        )
    )

    assert parsed.transcription == "Resposta manuscrita."
    assert parsed.visual_description == "Folha com duas secoes."
    assert parsed.content_kind == "handwriting"
    assert parsed.legibility == "partial"
    assert parsed.pii_observed == ["name_visible"]


def test_parse_vision_extraction_result_rejects_empty_readable_response() -> None:
    with pytest.raises(LlmCallError) as error:
        parse_vision_extraction_result(
            json.dumps(
                {
                    "transcription": "",
                    "visual_description": "",
                    "content_kind": "other",
                    "legibility": "full",
                    "pii_observed": [],
                }
            )
        )

    assert error.value.code == "vision_malformed_response"
    assert error.value.retryable is True


def test_parse_litellm_result_requires_score_when_requested() -> None:
    with pytest.raises(ValueError, match="malformed_llm_response"):
        parse_litellm_result(
            json.dumps(
                {
                    "confidence": 0.8,
                    "feedback": "No score returned.",
                    "criterion_notes": [],
                    "flags": [],
                }
            )
        )


def test_parse_litellm_result_rejects_out_of_range_score_when_requested() -> None:
    with pytest.raises(ValueError, match="malformed_llm_response"):
        parse_litellm_result(
            json.dumps(
                {
                    "score": 150,
                    "confidence": 0.8,
                    "feedback": "Score is out of bounds.",
                    "criterion_notes": [],
                    "flags": [],
                }
            )
        )


def test_parse_litellm_result_allows_null_score_in_cowrite() -> None:
    parsed = parse_litellm_result(
        json.dumps(
            {
                "confidence": 0.8,
                "feedback": "Reasoning only for the teacher to grade.",
                "criterion_notes": [{"criterion": "Evidence", "note": "Uses sources."}],
                "flags": [],
            }
        ),
        request_score=False,
    )

    assert parsed.score is None
    assert parsed.confidence == 0.8
    assert parsed.criterion_notes == [{"criterion": "Evidence", "note": "Uses sources."}]


def test_parse_litellm_result_drops_score_in_cowrite() -> None:
    parsed = parse_litellm_result(
        json.dumps(
            {
                "score": 88,
                "confidence": 0.8,
                "feedback": "Reasoning only.",
                "criterion_notes": [],
                "flags": [],
            }
        ),
        request_score=False,
    )

    assert parsed.score is None


def test_build_messages_cowrite_forbids_numeric_grade() -> None:
    cowrite = _build_messages(_request(request_score=False))
    scored = _build_messages(_request(request_score=True))

    assert cowrite[0]["role"] == "system"
    assert "do not assign a numeric score" in cowrite[0]["content"].lower()
    assert "numeric" in scored[0]["content"].lower()
    assert "do not assign a numeric score" not in scored[0]["content"].lower()


def test_build_messages_renders_rubric_and_criteria_after_static_prefix() -> None:
    messages = _build_messages(
        _request(
            request_score=True,
            rubric_text="Focus on evidence quality.",
            criteria=[
                {"name": "Evidence", "weight": 100, "description": "Uses sources."}
            ],
        )
    )

    # Static instruction block must lead (cache-prefix ordering).
    assert messages[0]["role"] == "system"
    rendered = json.dumps(messages)
    assert "Focus on evidence quality." in rendered
    assert "Evidence" in rendered


def test_engine_falls_back_to_json_object_when_schema_unsupported(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "score": 80,
                        "confidence": 0.8,
                        "feedback": "Solid draft.",
                        "criterion_notes": [],
                        "flags": [],
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        return Response()

    monkeypatch.setattr(
        "classroom_downloader.litellm_engine.litellm.completion", fake_completion
    )
    engine = LiteLlmGradingEngine(
        model=model_entry(supports_response_schema=False),
        timeout_seconds=30,
        max_retries=1,
    )

    engine.grade(_request(request_score=True))

    assert captured["response_format"] == {"type": "json_object"}


def test_engine_calls_litellm_with_scrubbed_payload(monkeypatch) -> None:
    captured = {}
    events = []

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "score": 91,
                        "confidence": 0.9,
                        "feedback": "Strong work.",
                        "criterion_notes": [],
                        "flags": [],
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}

        return Response()

    def fake_log_event(logger, event_name, **kwargs):
        events.append((event_name, kwargs))

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    monkeypatch.setattr("classroom_downloader.litellm_engine.log_event", fake_log_event)
    engine = LiteLlmGradingEngine(model=model_entry(), timeout_seconds=30, max_retries=1)

    result = engine.grade(
        GradingEngineRequest(
            job_id="job-1",
            submission_id="submission-1",
            activity_title="Essay Draft",
            rubric_mode="brief",
            teacher_loop="approve",
            rubric_text="Focus on evidence quality.",
            criteria=[
                {
                    "name": "Evidence",
                    "weight": 100,
                    "description": "Uses relevant examples.",
                }
            ],
            student_label="student_001",
            source_label="submission_001",
            mime_type="text/plain",
            content="This is scrubbed work by [student].",
        )
    )

    assert result.score == 91
    assert result.confidence == 0.9
    assert result.feedback == "Strong work."
    assert captured["model"] == "openai/gpt-5"
    assert captured["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS
    rendered = json.dumps(captured["messages"])
    assert "student_001" in rendered
    assert "This is scrubbed work" in rendered
    assert "Ana Silva" not in rendered
    assert events
    for _, event_kwargs in events:
        assert "content_preview" not in event_kwargs
        assert "raw_content" not in event_kwargs
        assert "feedback_preview" not in event_kwargs

    request_event = dict(events)["grading_engine.litellm.request"]
    assert request_event["content_chars"] == len("This is scrubbed work by [student].")

    catalog_event = dict(events)["litellm.grade.catalog_model"]
    assert catalog_event["model_id"] == "openai/gpt-5"
    assert catalog_event["provider"] == "openai"
    assert catalog_event["input_cost_per_token"] == 0.000001
    assert catalog_event["output_cost_per_token"] == 0.000004
    assert catalog_event["max_input_tokens"] == 128000
    assert catalog_event["max_output_tokens"] == 8192
    assert catalog_event["rpm_limit"] is None
    assert catalog_event["tpm_limit"] is None

    response_event = dict(events)["grading_engine.litellm.response"]
    assert response_event["score"] == 91
    assert response_event["confidence"] == 0.9
    assert response_event["usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_tokens": 140,
    }


def test_engine_uses_json_schema_response_format_when_supported(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "score": 91,
                        "confidence": 0.9,
                        "feedback": "Strong work.",
                        "criterion_notes": [],
                        "flags": [],
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    engine = LiteLlmGradingEngine(model=model_entry(), timeout_seconds=30, max_retries=1)

    engine.grade(
        GradingEngineRequest(
            job_id="job-1",
            submission_id="submission-1",
            activity_title="Essay Draft",
            rubric_mode="brief",
            teacher_loop="approve",
            rubric_text=None,
            criteria=[],
            student_label="student_001",
            source_label="submission_001",
            mime_type="text/plain",
            content="This is scrubbed work.",
        )
    )

    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert "score" in response_format["json_schema"]["schema"]["properties"]


def test_extract_image_calls_litellm_with_multimodal_payload(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "transcription": "Codigo exibido na tela.",
                        "visual_description": "Terminal com saida de teste.",
                        "content_kind": "code_screenshot",
                        "legibility": "full",
                        "pii_observed": ["name_visible"],
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    engine = LiteLlmGradingEngine(
        model=model_entry(supports_vision=True),
        timeout_seconds=30,
        max_retries=1,
    )

    result = engine.extract_image(
        VisionExtractionRequest(
            job_id="job-1",
            submission_id="submission-1",
            activity_title="Projeto",
            source_label="submission.png",
            image_data=b"jpeg-bytes",
            image_mime_type="image/jpeg",
        )
    )

    assert result.content_kind == "code_screenshot"
    assert result.pii_observed == ["name_visible"]
    assert captured["model"] == "openai/gpt-5"
    assert captured["max_tokens"] == MAX_VISION_OUTPUT_TOKENS
    assert captured["response_format"]["type"] == "json_schema"
    user_content = captured["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert "Projeto" in user_content[0]["text"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_extract_image_pdf_uses_file_part_and_larger_budget(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)

        class Choice:
            message = {
                "content": json.dumps(
                    {
                        "transcription": "Relatório completo do aluno.",
                        "visual_description": "Documento PDF de várias páginas.",
                        "content_kind": "pdf_document",
                        "legibility": "full",
                        "pii_observed": [],
                    }
                )
            }

        class Response:
            choices = [Choice()]
            usage = {"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700}

        return Response()

    monkeypatch.setattr("classroom_downloader.litellm_engine.litellm.completion", fake_completion)
    # A model whose own ceiling (65536) exceeds both budgets, so the PDF budget
    # is set by MAX_PDF_OUTPUT_TOKENS and is visibly larger than the image one.
    engine = LiteLlmGradingEngine(
        model=model_entry(supports_vision=True, max_output_tokens=65536),
        timeout_seconds=30,
        max_retries=1,
    )

    result = engine.extract_image(
        VisionExtractionRequest(
            job_id="job-1",
            submission_id="submission-1",
            activity_title="Projeto",
            source_label="submission.pdf",
            image_data=b"%PDF-1.4 fake",
            image_mime_type="application/pdf",
        )
    )

    assert result.content_kind == "pdf_document"
    # PDFs get the generous transcription budget, larger than images.
    assert captured["max_tokens"] == MAX_PDF_OUTPUT_TOKENS
    assert MAX_PDF_OUTPUT_TOKENS > MAX_VISION_OUTPUT_TOKENS
    user_content = captured["messages"][1]["content"]
    assert user_content[1]["type"] == "file"
    assert user_content[1]["file"]["file_data"].startswith("data:application/pdf;base64,")
