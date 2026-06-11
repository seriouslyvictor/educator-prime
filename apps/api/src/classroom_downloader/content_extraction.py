from dataclasses import dataclass
from pathlib import Path

from .models import GradingFileCache
from .observability import get_logger, log_event, text_preview
from .zip_extraction import (
    ZIP_MIME_TYPES,
    extract_zip_submission,
    render_zip_submission_text,
)


logger = get_logger(__name__)


TEXT_MIME_PREFIXES = ("text/",)
TEXT_MIME_TYPES = {
    "application/json",
    "application/javascript",
    "application/x-python-code",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
}
DEGRADED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SAFE_SOURCE_EXTENSIONS = {
    ".csv",
    ".docx",
    ".gdoc",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".pdf",
    ".png",
    ".py",
    ".txt",
    ".webp",
    ".zip",
}


@dataclass(frozen=True)
class ExtractedSubmissionContent:
    status: str
    text: str
    safe_source_label: str
    error: str | None = None
    retryable: bool = False
    pii_observed: list[str] | None = None
    content_kind: str | None = None


def extract_submission_content(
    cache_file: GradingFileCache,
    *,
    allow_visual_pending: bool = False,
) -> ExtractedSubmissionContent:
    mime_type = cache_file.mime_type.lower()
    safe_source_label = _safe_source_label(cache_file)
    log_event(
        logger,
        "content.extract.start",
        cache_file_id=cache_file.id,
        submission_id=cache_file.submission_id,
        source_file_id=cache_file.source_file_id,
        source_name=cache_file.source_name,
        cached_path=cache_file.cached_path,
        mime_type=cache_file.mime_type,
        byte_size=cache_file.byte_size,
        safe_source_label=safe_source_label,
    )
    if mime_type.startswith("image/"):
        if allow_visual_pending:
            log_event(
                logger,
                "content.extract.pending_visual",
                cache_file_id=cache_file.id,
                mime_type=cache_file.mime_type,
            )
            return ExtractedSubmissionContent(
                status="pending_vision",
                text="",
                safe_source_label=safe_source_label,
            )
        log_event(
            logger,
            "content.extract.unsupported_visual",
            cache_file_id=cache_file.id,
            mime_type=cache_file.mime_type,
        )
        return ExtractedSubmissionContent(
            status="unsupported",
            text="",
            safe_source_label=safe_source_label,
            error="unsupported_visual_submission",
        )

    path = Path(cache_file.cached_path)
    if not path.exists():
        log_event(
            logger,
            "content.extract.cached_file_missing",
            cache_file_id=cache_file.id,
            cached_path=cache_file.cached_path,
        )
        return ExtractedSubmissionContent(
            status="failed",
            text="",
            safe_source_label=safe_source_label,
            error="cached_file_missing",
        )

    if _is_zip_submission(cache_file, mime_type):
        return _extract_zip_content(cache_file, path, safe_source_label)

    content = path.read_bytes()
    text = _decode_text(content)
    if text is None:
        log_event(
            logger,
            "content.extract.unsupported_binary",
            cache_file_id=cache_file.id,
            byte_size=len(content),
        )
        return ExtractedSubmissionContent(
            status="unsupported",
            text="",
            safe_source_label=safe_source_label,
            error="unsupported_binary_submission",
        )

    if mime_type.startswith(TEXT_MIME_PREFIXES) or mime_type in TEXT_MIME_TYPES:
        log_event(
            logger,
            "content.extract.supported",
            cache_file_id=cache_file.id,
            char_count=len(text),
            text_preview=text_preview(text),
        )
        return ExtractedSubmissionContent(
            status="supported",
            text=text,
            safe_source_label=safe_source_label,
        )

    if mime_type in DEGRADED_MIME_TYPES:
        log_event(
            logger,
            "content.extract.degraded",
            cache_file_id=cache_file.id,
            mime_type=mime_type,
            char_count=len(text),
            text_preview=text_preview(text),
        )
        return ExtractedSubmissionContent(
            status="degraded",
            text=text,
            safe_source_label=safe_source_label,
        )

    log_event(
        logger,
        "content.extract.unsupported_type",
        cache_file_id=cache_file.id,
        mime_type=mime_type,
    )
    return ExtractedSubmissionContent(
        status="unsupported",
        text="",
        safe_source_label=safe_source_label,
        error="unsupported_file_type",
    )


def _is_zip_submission(cache_file: GradingFileCache, mime_type: str) -> bool:
    if mime_type in ZIP_MIME_TYPES:
        return True
    return Path(cache_file.source_name).suffix.lower() == ".zip"


def _extract_zip_content(
    cache_file: GradingFileCache,
    path: Path,
    safe_source_label: str,
) -> ExtractedSubmissionContent:
    result = extract_zip_submission(path)
    if result.error:
        log_event(
            logger,
            "content.extract.zip_rejected",
            cache_file_id=cache_file.id,
            error=result.error,
        )
        return ExtractedSubmissionContent(
            status="unsupported",
            text="",
            safe_source_label=safe_source_label,
            error=result.error,
        )
    if not result.entries:
        log_event(
            logger,
            "content.extract.zip_no_gradeable_entries",
            cache_file_id=cache_file.id,
            skipped_count=len(result.skipped),
            noise_count=result.noise_count,
        )
        return ExtractedSubmissionContent(
            status="unsupported",
            text="",
            safe_source_label=safe_source_label,
            error="zip_no_gradeable_entries",
        )
    text = render_zip_submission_text(result)
    status = "supported" if not result.skipped and not result.truncated else "degraded"
    log_event(
        logger,
        "content.extract.zip",
        cache_file_id=cache_file.id,
        status=status,
        entry_count=len(result.entries),
        skipped_count=len(result.skipped),
        noise_count=result.noise_count,
        truncated=result.truncated,
        char_count=len(text),
        text_preview=text_preview(text),
    )
    return ExtractedSubmissionContent(
        status=status,
        text=text,
        safe_source_label=safe_source_label,
    )


def _decode_text(content: bytes) -> str | None:
    for encoding in ("utf-8", "utf-16"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return None


def _safe_source_label(cache_file: GradingFileCache) -> str:
    if cache_file.source_name == cache_file.source_file_id:
        return "submission"
    suffix = Path(cache_file.source_name).suffix.lower()
    if suffix in SAFE_SOURCE_EXTENSIONS:
        return f"submission{suffix}"
    return "submission"
