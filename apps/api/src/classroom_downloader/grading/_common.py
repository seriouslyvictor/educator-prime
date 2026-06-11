from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from ..content_extraction import ExtractedSubmissionContent
from ..models import GradingSubmission
from ..observability import get_logger
from ..privacy import ScrubbedSubmission
from ..settings import get_settings

logger = get_logger(__name__)


@dataclass(frozen=True)
class CachedScrubbedSubmission:
    extracted: ExtractedSubmissionContent
    scrubbed: ScrubbedSubmission
    cache_hit: bool


def default_cache_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(hours=settings.grading_cache_ttl_hours)


_PRIVACY_STATUS_RANK = {
    "clean": 0,
    "partial_redaction": 1,
    "redacted": 2,
    "high_reidentification_risk": 3,
    "failed": 4,
}
_EXTRACTION_STATUS_RANK = {
    "supported": 0,
    "degraded": 1,
    "pending_vision": 1,
    "unsupported": 2,
    "failed": 3,
}


def _worst_status(statuses: list[str], ranks: dict[str, int], default: str) -> str:
    present = [status for status in statuses if status]
    if not present:
        return default
    return max(present, key=lambda status: ranks.get(status, 0))


def _sum_optional(values) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _sum_float_optional(values) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present), 4)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _identity_hash(submission: GradingSubmission) -> str:
    payload = "\0".join(
        [
            submission.student_name or "",
            submission.student_email or "",
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
