"""Optional gated live-LLM test — grades one real corpus submission via Gemini.

Skips cleanly when GEMINI_TEST_KEY is not set so CI stays green and cost-free.
Set the env var to run the live check:

    GEMINI_TEST_KEY=... uv run pytest tests/test_litellm_live.py -v
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CD_GOOGLE_PROVIDER", "mock")

import pytest

from corpus import corpus_path

_GEMINI_TEST_KEY = os.environ.get("GEMINI_TEST_KEY")
_HAS_KEY = bool(_GEMINI_TEST_KEY)

pytestmark = pytest.mark.skipif(
    not _HAS_KEY,
    reason="GEMINI_TEST_KEY not set — skipping live Gemini grade test",
)


def _build_engine():
    """Construct a LiteLlmGradingEngine wired to Gemini 2.5 Flash."""
    from classroom_downloader.litellm_engine import LiteLlmGradingEngine
    from classroom_downloader.llm_catalog import LlmModelEntry

    model = LlmModelEntry(
        id="gemini/gemini-2.5-flash",
        provider="gemini",
        litellm_model="gemini/gemini-2.5-flash",
        enabled=True,
        display_name="Gemini 2.5 Flash (live test)",
        use_cases=["grading_draft"],
        input_cost_per_token=None,
        output_cost_per_token=None,
        max_input_tokens=None,
        max_output_tokens=4096,
        supports_response_schema=True,
        supports_vision=False,
        rpm_limit=None,
        tpm_limit=None,
        notes="Live integration test model.",
    )
    return LiteLlmGradingEngine(model=model, timeout_seconds=60, max_retries=1)


def _extract_docx_text() -> str:
    """Extract text from the real corpus docx for the grading request."""
    from classroom_downloader.content_extraction import extract_submission_content
    from classroom_downloader.models import GradingFileCache

    path = corpus_path("submissions-office-suite/PIM_I_FINAL_CORRIGIDO.docx")
    cache = GradingFileCache(
        id=str(uuid4()),
        job_id="live-test-job",
        submission_id=str(uuid4()),
        source_file_id="live-drive-docx",
        source_name=path.name,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        cached_path=str(path),
        content_hash="live-hash",
        byte_size=path.stat().st_size,
        expires_at=datetime.now(UTC),
    )
    result = extract_submission_content(cache)
    assert result.status in {"supported", "degraded"}, (
        f"Could not extract corpus docx: {result.status} / {result.error}"
    )
    return result.text


def test_live_gemini_grades_real_submission() -> None:
    """Grade one real docx submission via Gemini and assert sane bounds.

    This test is gated on GEMINI_TEST_KEY and will be skipped in CI.
    """
    # Expose the key under the standard env var LiteLLM reads.
    os.environ["GEMINI_API_KEY"] = _GEMINI_TEST_KEY  # type: ignore[arg-type]

    from classroom_downloader.grading_engine import GradingEngineRequest

    content = _extract_docx_text()
    assert len(content) > 100, "Extracted content too short for a meaningful grade"

    engine = _build_engine()
    request = GradingEngineRequest(
        job_id="live-test-job",
        submission_id=str(uuid4()),
        activity_title="Trabalho Final de Programação",
        rubric_mode="structured",
        teacher_loop="approve",
        rubric_text=None,
        criteria=[
            {"name": "Lógica", "weight": 70, "description": "Qualidade lógica do trabalho."},
            {"name": "Estilo", "weight": 30, "description": "Clareza e organização."},
        ],
        student_label="student_01",
        source_label="submission.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=content[:6000],  # stay well within token budget
    )

    result = engine.grade(request)

    assert result.score is not None, "Gemini returned no score"
    assert 0 <= result.score <= 100, f"Score out of [0,100]: {result.score}"
    assert result.confidence is not None
    assert 0.0 <= result.confidence <= 1.0, f"Confidence out of [0,1]: {result.confidence}"
    assert result.feedback, "Expected non-empty feedback"

    if result.criterion_scores:
        total = sum(c["earned"] for c in result.criterion_scores)
        # Allow a small tolerance for rounding in the model output.
        assert abs(total - result.score) < 5, (
            f"criterion_scores sum {total} too far from score {result.score}"
        )
