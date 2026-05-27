import json
import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

import pytest

from classroom_downloader.grading_engine import GradingEngineRequest
from classroom_downloader.litellm_engine import LiteLlmGradingEngine, parse_litellm_result
from classroom_downloader.llm_catalog import LlmModelEntry


def model_entry() -> LlmModelEntry:
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
        max_output_tokens=8192,
        supports_response_schema=True,
        supports_vision=False,
        rpm_limit=None,
        tpm_limit=None,
        notes="",
        raw={},
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


def test_engine_calls_litellm_with_scrubbed_payload(monkeypatch) -> None:
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

    result = engine.grade(
        GradingEngineRequest(
            job_id="job-1",
            submission_id="submission-1",
            activity_title="Essay Draft",
            rubric_mode="brief",
            teacher_loop="approve",
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
    rendered = json.dumps(captured["messages"])
    assert "student_001" in rendered
    assert "This is scrubbed work" in rendered
    assert "Ana Silva" not in rendered
