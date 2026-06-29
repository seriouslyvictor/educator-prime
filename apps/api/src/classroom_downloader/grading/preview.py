"""Preview response policy for submission files served to the teacher.

Student-uploaded files are served back to the teacher so they can read the
real work next to the AI draft. Only render types that cannot execute script
on the app origin inline; everything else (HTML, SVG, Office docs, unknown
binaries) is forced to download. Paired with nosniff so the browser cannot
re-interpret a "safe" type as active content.
"""

from pathlib import Path

# MIME types that are safe to serve with Content-Disposition: inline.
SAFE_INLINE_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
    }
)

# MIME types that should be served as text/plain (safe to render, not as-declared).
SAFE_TEXT_MIME_TYPES = frozenset(
    {
        "text/plain",
        "application/json",
        "application/ld+json",
        "application/xml",
        "application/xhtml+xml",
        "application/javascript",
        "application/typescript",
        "application/x-yaml",
        "application/yaml",
        "text/csv",
        "text/markdown",
        "text/x-python",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++",
        "text/x-csharp",
        "text/x-go",
        "text/x-rust",
        "text/x-php",
        "text/x-ruby",
        "text/x-sql",
    }
)

# File extensions that should be served as text/plain when the MIME type is
# application/octet-stream (generic binary), if the content is valid UTF-8.
SAFE_TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".xml",
        ".yaml",
        ".yml",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".scss",
        ".html",
        ".htm",
        ".java",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".sql",
        ".sh",
        ".ps1",
        ".bat",
        ".ini",
        ".toml",
        ".lock",
    }
)


def _is_utf8_text(content: bytes) -> bool:
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def preview_response_mode(mime_type: str, source_name: str, content: bytes) -> tuple[bool, str]:
    """Return (inline_ok, effective_media_type) for a cached submission file.

    inline_ok=True  → serve with Content-Disposition: inline
    inline_ok=False → serve with Content-Disposition: attachment (force download)
    """
    if mime_type in SAFE_INLINE_MIME_TYPES:
        return True, mime_type
    if mime_type.startswith("text/") or mime_type in SAFE_TEXT_MIME_TYPES:
        return True, "text/plain; charset=utf-8"
    if mime_type == "application/octet-stream" and Path(source_name).suffix.lower() in SAFE_TEXT_EXTENSIONS:
        if _is_utf8_text(content):
            return True, "text/plain; charset=utf-8"
    return False, mime_type or "application/octet-stream"
