"""Real-file corpus tests for content_extraction.py.

Each test loads a file from test_files/ via corpus_path(), wraps it in a
GradingFileCache pointed at the real bytes on disk, and asserts on the
extraction lane / status without relying on exact char counts.

These are self-contained (no provider, no network, no LLM).
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CD_GOOGLE_PROVIDER", "mock")

import pytest

from corpus import corpus_path
from classroom_downloader.content_extraction import extract_submission_content
from classroom_downloader.models import GradingFileCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"


def _cache_for(path: Path, mime_type: str) -> GradingFileCache:
    """Build a minimal GradingFileCache pointing at a real file on disk."""
    return GradingFileCache(
        id=str(uuid4()),
        job_id="corpus-job",
        submission_id=str(uuid4()),
        source_file_id="corpus-drive",
        source_name=path.name,
        mime_type=mime_type,
        cached_path=str(path),
        content_hash="corpus-hash",
        byte_size=path.stat().st_size,
        expires_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# DOCX — office text lane
# ---------------------------------------------------------------------------

def test_real_docx_extraction_returns_supported_with_text() -> None:
    path = corpus_path("submissions-office-suite/PIM_I_FINAL_CORRIGIDO.docx")
    cache = _cache_for(path, DOCX_MIME)
    result = extract_submission_content(cache)

    assert result.status in {"supported", "degraded"}, (
        f"Expected supported or degraded, got {result.status!r}: {result.error}"
    )
    assert result.error is None or result.status == "degraded"
    # The file is a real PIM report — should contain substantial text
    assert len(result.text) > 50, "Expected more than 50 chars of extracted text"


# ---------------------------------------------------------------------------
# XLSX — office spreadsheet lane
# ---------------------------------------------------------------------------

def test_real_xlsx_extraction_returns_supported_with_text() -> None:
    path = corpus_path("submissions-office-suite/05 - FÓRMULAS E FUNÇÕES.xlsx")
    cache = _cache_for(path, XLSX_MIME)
    result = extract_submission_content(cache)

    assert result.status in {"supported", "degraded"}, (
        f"Expected supported or degraded, got {result.status!r}: {result.error}"
    )
    assert len(result.text) > 0, "Expected non-empty text from xlsx"


# ---------------------------------------------------------------------------
# ZIP — zip extraction lane
# ---------------------------------------------------------------------------

def test_real_zip_extraction_returns_supported_with_tree() -> None:
    path = corpus_path("submissions-code/greenfit.zip")
    cache = _cache_for(path, "application/zip")
    result = extract_submission_content(cache)

    assert result.status in {"supported", "degraded"}, (
        f"Expected supported or degraded, got {result.status!r}: {result.error}"
    )
    assert len(result.text) > 0, "Expected non-empty rendered text from zip"


# ---------------------------------------------------------------------------
# HTML + JS — text lane (html and js files in tcc_golpe_zero/)
# ---------------------------------------------------------------------------

def test_real_html_extraction_returns_supported() -> None:
    path = corpus_path("submissions-code/tcc_golpe_zero/index.html")
    cache = _cache_for(path, "text/html")
    result = extract_submission_content(cache)

    assert result.status in {"supported", "degraded"}, (
        f"Expected supported or degraded, got {result.status!r}: {result.error}"
    )
    assert len(result.text) > 0


def test_real_js_extraction_returns_supported() -> None:
    path = corpus_path("submissions-code/tcc_golpe_zero/script.js")
    cache = _cache_for(path, "application/javascript")
    result = extract_submission_content(cache)

    assert result.status in {"supported", "degraded"}, (
        f"Expected supported or degraded, got {result.status!r}: {result.error}"
    )
    assert len(result.text) > 0


# ---------------------------------------------------------------------------
# PDF — vision lane
# ---------------------------------------------------------------------------

def test_real_pdf_with_visual_flag_returns_pending_vision() -> None:
    path = corpus_path("submissions-office-suite/PIM I - FINAL.pdf")
    cache = _cache_for(path, PDF_MIME)
    result = extract_submission_content(cache, allow_visual_pending=True)

    assert result.status == "pending_vision", (
        f"Expected pending_vision, got {result.status!r}: {result.error}"
    )
    assert result.error is None


def test_real_pdf_without_visual_flag_returns_unsupported() -> None:
    path = corpus_path("submissions-office-suite/PIM I - FINAL.pdf")
    cache = _cache_for(path, PDF_MIME)
    result = extract_submission_content(cache, allow_visual_pending=False)

    assert result.status == "unsupported", (
        f"Expected unsupported, got {result.status!r}: {result.error}"
    )
    assert result.error == "unsupported_visual_submission"
