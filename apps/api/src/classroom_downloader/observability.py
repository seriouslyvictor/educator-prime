from __future__ import annotations

"""Logging helpers and event taxonomy.

Event names use <area>.<entity>.<action>. Cache events use the shared
cache.hit/cache.miss pair with cache="<name>" and key="<key>" fields. Preferred
actions are start, complete, failed, hit, miss, write, and skip.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
import json
import logging
from typing import Any

from .settings import get_settings


_CONFIGURED = False
_REDACTED = "<redacted>"
_SENSITIVE_FIELDS = {
    "access_token",
    "client_secret",
    "credentials",
    "credentials_json",
    "email",
    "picture",
    "raw_token",
    "refresh_token",
    "student_email",
    "student_name",
    "token",
}

class JsonEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []
    if settings.log_format == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonEventFormatter())
        handlers.append(handler)
    elif settings.log_rich:
        try:
            from rich.logging import RichHandler

            handlers.append(
                RichHandler(
                    rich_tracebacks=True,
                    show_path=False,
                    markup=False,
                )
            )
        except ModuleNotFoundError:
            handlers.append(logging.StreamHandler())
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        handlers.append(handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(_format_event(event, fields))


def log_debug(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.debug(_format_event(event, fields))


def log_warning(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.warning(_format_event(event, fields))


def log_error(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.exception(_format_event(event, fields))


def log_cache_hit(logger: logging.Logger, cache: str, key: str, **fields: Any) -> None:
    log_event(logger, "cache.hit", cache=cache, key=key, **fields)


def log_cache_miss(logger: logging.Logger, cache: str, key: str, **fields: Any) -> None:
    log_event(logger, "cache.miss", cache=cache, key=key, **fields)


def safe_fields(
    obj: Any,
    drop: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    redacted = _SENSITIVE_FIELDS | set(drop or set())
    if is_dataclass(obj) and not isinstance(obj, type):
        values = asdict(obj)
    elif isinstance(obj, Mapping):
        values = dict(obj)
    else:
        values = dict(getattr(obj, "__dict__", {}))
    return {
        str(key): _safe_value(value, key=str(key), redacted=redacted)
        for key, value in values.items()
    }


def text_preview(text: str | None) -> str:
    if not text:
        return ""
    settings = get_settings()
    if not settings.log_payload_previews:
        return "<preview disabled>"
    clean = text.replace("\r", "\\r").replace("\n", "\\n")
    limit = max(0, settings.log_preview_chars)
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit]}... <truncated {len(clean) - limit} chars>"


def byte_preview(content: bytes | None) -> str:
    if not content:
        return ""
    settings = get_settings()
    if not settings.log_payload_previews:
        return "<preview disabled>"
    limit = max(0, min(settings.log_preview_chars, 256))
    sample = content[:limit]
    try:
        decoded = sample.decode("utf-8")
    except UnicodeDecodeError:
        return sample.hex() + ("..." if len(content) > limit else "")
    return text_preview(decoded)


def _format_event(event: str, fields: dict[str, Any]) -> str:
    parts = [event]
    for key, value in fields.items():
        parts.append(f"{key}={_format_value(_safe_value(value, key=key))}")
    return " ".join(parts)


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return _bounded_repr(value)


def _safe_value(
    value: Any,
    *,
    key: str | None = None,
    redacted: set[str] | frozenset[str] = _SENSITIVE_FIELDS,
) -> Any:
    if key in redacted:
        return _REDACTED
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if is_dataclass(value) and not isinstance(value, type):
        return safe_fields(value, drop=set(redacted - _SENSITIVE_FIELDS))
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_value(item_value, key=str(item_key), redacted=redacted)
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_safe_value(item, redacted=redacted) for item in value]
    if isinstance(value, str):
        return _bounded_text(value)
    return value


def _bounded_text(value: str) -> str:
    settings = get_settings()
    limit = max(0, settings.log_preview_chars)
    if len(value) <= limit:
        return value
    return f"{value[:limit]}... <truncated {len(value) - limit} chars>"


def _bounded_repr(value: Any) -> str:
    rendered = repr(value)
    settings = get_settings()
    limit = max(0, settings.log_preview_chars)
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[:limit]}... <truncated {len(rendered) - limit} chars>"
