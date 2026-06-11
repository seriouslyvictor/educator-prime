"""Safe inspection and selective extraction of zip submissions.

A zip is never extracted to disk. The central directory is inspected first
(no decompression) and the whole archive is rejected if it looks hostile:
encrypted entries, too many files, declared sizes too large, or a
compression ratio typical of zip bombs. Entries that survive the gate are
filtered by an extension allowlist and read fully in memory with hard byte
caps, so lying size headers cannot exhaust the host.
"""

import re
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .observability import get_logger, log_event


logger = get_logger(__name__)


ZIP_MIME_TYPES = {
    "application/zip",
    "application/x-zip",
    "application/x-zip-compressed",
    "application/zip-compressed",
    "multipart/x-zip",
}

# Structural gate: any violation rejects the whole archive.
MAX_ENTRY_COUNT = 200
MAX_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
COMPRESSION_RATIO_LIMIT = 100
# Ratio is only meaningful above this size; tiny archives of repetitive
# text legitimately compress very well.
RATIO_CHECK_FLOOR_BYTES = 1024 * 1024

# Per-entry extraction caps. Reads are chunked and stop at the cap even if
# the declared size in the header is smaller (headers can lie).
MAX_ENTRY_TEXT_BYTES = 200_000
MAX_TOTAL_TEXT_BYTES = 500_000
READ_CHUNK_BYTES = 65_536

# Only text-decodable formats can be graded from inside an archive; images
# and PDFs inside zips are skipped (the vision pipeline operates on cached
# files, not archive entries).
GRADEABLE_ZIP_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".h",
    ".hpp",
    ".htm",
    ".html",
    ".ipynb",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".php",
    ".py",
    ".rb",
    ".sql",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

NESTED_ARCHIVE_EXTENSIONS = {".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip"}

# Tooling/OS noise: silently dropped, does not degrade the submission.
EXCLUDED_DIR_SEGMENTS = {
    ".git",
    ".gradle",
    ".idea",
    ".next",
    ".venv",
    ".vscode",
    "__macosx",
    "__pycache__",
    "bin",
    "build",
    "dist",
    "env",
    "node_modules",
    "obj",
    "target",
    "vendor",
    "venv",
}
EXCLUDED_FILE_NAMES = {".ds_store", "desktop.ini", "thumbs.db"}

_MANIFEST_SKIPPED_LIMIT = 20
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class ZipEntryText:
    name: str
    text: str


@dataclass(frozen=True)
class SkippedZipEntry:
    name: str
    reason: str


@dataclass(frozen=True)
class ZipExtractionResult:
    entries: list[ZipEntryText] = field(default_factory=list)
    skipped: list[SkippedZipEntry] = field(default_factory=list)
    noise_count: int = 0
    truncated: bool = False
    error: str | None = None


def extract_zip_submission(path: Path) -> ZipExtractionResult:
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return _rejected(path, "zip_invalid")
    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > MAX_ENTRY_COUNT:
            return _rejected(path, "zip_too_many_files", entry_count=len(infos))
        if any(info.flag_bits & 0x1 for info in infos):
            return _rejected(path, "zip_encrypted")
        total_uncompressed = sum(info.file_size for info in infos)
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            return _rejected(path, "zip_too_large", total_uncompressed=total_uncompressed)
        total_compressed = sum(info.compress_size for info in infos)
        if (
            total_uncompressed > RATIO_CHECK_FLOOR_BYTES
            and total_uncompressed > COMPRESSION_RATIO_LIMIT * max(total_compressed, 1)
        ):
            return _rejected(
                path,
                "zip_suspicious_compression",
                total_uncompressed=total_uncompressed,
                total_compressed=total_compressed,
            )

        entries: list[ZipEntryText] = []
        skipped: list[SkippedZipEntry] = []
        noise_count = 0
        included_bytes = 0
        truncated = False
        for info in infos:
            name = info.filename.replace("\\", "/")
            display = _display_name(name)
            if _is_noise(name):
                noise_count += 1
                continue
            if not _is_safe_entry_name(name):
                skipped.append(SkippedZipEntry(display, "nome de arquivo inválido"))
                continue
            if _is_symlink(info):
                skipped.append(SkippedZipEntry(display, "link simbólico"))
                continue
            suffix = PurePosixPath(name).suffix.lower()
            if suffix in NESTED_ARCHIVE_EXTENSIONS:
                skipped.append(SkippedZipEntry(display, "arquivo compactado aninhado"))
                continue
            if suffix not in GRADEABLE_ZIP_EXTENSIONS:
                skipped.append(SkippedZipEntry(display, "extensão não permitida"))
                continue
            if info.file_size > MAX_ENTRY_TEXT_BYTES:
                skipped.append(SkippedZipEntry(display, "arquivo grande demais"))
                continue
            if included_bytes + info.file_size > MAX_TOTAL_TEXT_BYTES:
                truncated = True
                skipped.append(SkippedZipEntry(display, "limite total de leitura atingido"))
                continue
            raw, read_error = _read_capped(archive, info)
            if raw is None:
                skipped.append(SkippedZipEntry(display, read_error or "arquivo corrompido"))
                continue
            text = _decode_entry(raw)
            if text is None:
                skipped.append(SkippedZipEntry(display, "conteúdo binário"))
                continue
            included_bytes += len(raw)
            entries.append(ZipEntryText(display, text))

    log_event(
        logger,
        "zip.extract.complete",
        path=str(path),
        entry_count=len(entries),
        skipped_count=len(skipped),
        noise_count=noise_count,
        included_bytes=included_bytes,
        truncated=truncated,
    )
    return ZipExtractionResult(
        entries=entries,
        skipped=skipped,
        noise_count=noise_count,
        truncated=truncated,
    )


def render_zip_submission_text(result: ZipExtractionResult) -> str:
    blocks = [
        f"[arquivo: {entry.name}]\n{entry.text}".rstrip() for entry in result.entries
    ]
    notes = [
        f"- {entry.name} ({entry.reason})"
        for entry in result.skipped[:_MANIFEST_SKIPPED_LIMIT]
    ]
    overflow = len(result.skipped) - _MANIFEST_SKIPPED_LIMIT
    if overflow > 0:
        notes.append(f"- ... e mais {overflow} arquivos ignorados")
    if result.noise_count:
        notes.append(
            f"- {result.noise_count} arquivos de sistema ou pastas de ferramentas"
            " ignorados (ex.: node_modules, __MACOSX)"
        )
    if notes:
        blocks.append("[arquivos ignorados]\n" + "\n".join(notes))
    return "\n\n".join(blocks)


def _rejected(path: Path, error: str, **details: object) -> ZipExtractionResult:
    log_event(logger, "zip.extract.rejected", path=str(path), error=error, **details)
    return ZipExtractionResult(error=error)


def _read_capped(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo
) -> tuple[bytes | None, str | None]:
    data = bytearray()
    try:
        with archive.open(info) as handle:
            while True:
                chunk = handle.read(READ_CHUNK_BYTES)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_ENTRY_TEXT_BYTES:
                    return None, "arquivo grande demais"
    except (zipfile.BadZipFile, zlib.error, OSError, RuntimeError, NotImplementedError):
        return None, "arquivo corrompido"
    return bytes(data), None


def _decode_entry(content: bytes) -> str | None:
    for encoding in ("utf-8", "utf-16"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return None


def _is_safe_entry_name(name: str) -> bool:
    if name.startswith("/") or _WINDOWS_DRIVE_RE.match(name):
        return False
    if any(ord(char) < 32 for char in name):
        return False
    return ".." not in name.split("/")


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _is_noise(name: str) -> bool:
    parts = [part.lower() for part in name.split("/") if part]
    if not parts:
        return True
    if any(part in EXCLUDED_DIR_SEGMENTS for part in parts[:-1]):
        return True
    basename = parts[-1]
    return basename in EXCLUDED_FILE_NAMES or basename.startswith("._")


def _display_name(name: str) -> str:
    cleaned = "".join(char for char in name if ord(char) >= 32)
    if len(cleaned) > 120:
        return cleaned[:117] + "..."
    return cleaned or "(sem nome)"
