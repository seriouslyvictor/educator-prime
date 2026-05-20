import re
import unicodedata
from pathlib import PurePosixPath

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_segment(value: str | None, fallback: str = "untitled") -> str:
    normalized = unicodedata.normalize("NFKD", value or "").strip()
    normalized = normalized.replace('"', "").replace("'", "")
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip(" .-")
    if not normalized:
        normalized = fallback
    if normalized.upper() in WINDOWS_RESERVED_NAMES:
        normalized = f"{normalized}-item"
    return normalized[:120]


def build_output_path(
    course_name: str,
    activity_name: str,
    source_name: str,
    student_email: str | None,
    student_name: str | None,
    stable_id: str,
    used_paths: set[str],
) -> str:
    course = sanitize_segment(course_name, "course")
    activity = sanitize_segment(activity_name, "activity")
    identity = sanitize_segment(student_email or student_name or stable_id, "student")
    filename = sanitize_segment(source_name, "submission")
    candidate = str(PurePosixPath(course, activity, f"{identity}--{filename}"))
    if candidate not in used_paths:
        used_paths.add(candidate)
        return candidate

    suffix = 2
    stem, dot, extension = filename.rpartition(".")
    while True:
        if dot:
            deduped = f"{identity}--{stem}-{suffix}.{extension}"
        else:
            deduped = f"{identity}--{filename}-{suffix}"
        candidate = str(PurePosixPath(course, activity, deduped))
        if candidate not in used_paths:
            used_paths.add(candidate)
            return candidate
        suffix += 1
