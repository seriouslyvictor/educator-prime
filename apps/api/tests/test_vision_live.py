import os
from pathlib import Path

import pytest

from classroom_downloader.grading_engine import VisionExtractionRequest, get_grading_engine
from classroom_downloader.image_preprocessing import prepare_image_for_llm


pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_LLM_TESTS") != "1",
    reason="set LIVE_LLM_TESTS=1 to run live LLM vision tests",
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "images"


@pytest.mark.parametrize(
    ("filename", "expected_kinds", "expect_pii"),
    [
        ("screen-photo.jpg", {"screen_photo"}, False),
        ("handwriting-photo-with-name.jpg", {"handwriting", "document_photo"}, True),
        ("code-screenshot.png", {"code_screenshot"}, False),
        ("app-screenshot.png", {"app_screenshot"}, False),
    ],
)
def test_live_vision_extracts_fixture_structure(
    filename: str,
    expected_kinds: set[str],
    expect_pii: bool,
) -> None:
    path = FIXTURE_DIR / filename
    if not path.exists():
        pytest.skip(f"fixture missing: {path}")

    engine = get_grading_engine()
    if engine.name != "litellm":
        pytest.skip("live vision tests require CD_GRADING_ENGINE=litellm")
    catalog_model = getattr(engine, "catalog_model", None)
    if not getattr(catalog_model, "supports_vision", False):
        pytest.skip("configured model does not advertise supports_vision")

    prepared = prepare_image_for_llm(path)
    result = engine.extract_image(
        VisionExtractionRequest(
            job_id="live-vision-test",
            submission_id=filename,
            activity_title="Teste de extracao visual",
            source_label=path.name,
            image_data=prepared.data,
            image_mime_type=prepared.mime_type,
        )
    )

    assert result.content_kind in expected_kinds
    assert result.legibility in {"full", "partial", "unreadable"}
    assert result.transcription.strip() or result.visual_description.strip() or result.legibility == "unreadable"
    if expect_pii:
        assert result.pii_observed
