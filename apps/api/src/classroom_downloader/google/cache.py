"""TTL cache helpers shared across Google provider implementations."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..observability import get_logger, log_event, log_cache_hit, log_cache_miss


logger = get_logger(__name__)


@dataclass
class _TtlCacheEntry:
    value: object
    expires_at: datetime


_PROFILE_CACHE: dict[str, _TtlCacheEntry] = {}
_ACCOUNT_PROFILE_CACHE: dict[str, _TtlCacheEntry] = {}
_DRIVE_METADATA_CACHE: dict[str, _TtlCacheEntry] = {}
_GRADE_SUMMARY_CACHE: dict[str, _TtlCacheEntry] = {}


def clear_google_provider_caches() -> None:
    _PROFILE_CACHE.clear()
    _ACCOUNT_PROFILE_CACHE.clear()
    _DRIVE_METADATA_CACHE.clear()
    _GRADE_SUMMARY_CACHE.clear()
    log_event(logger, "google.cache.clear")


def _ttl(minutes: int) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def _cache_hit(entry: _TtlCacheEntry | None) -> bool:
    return bool(entry and entry.expires_at > datetime.now(UTC))
