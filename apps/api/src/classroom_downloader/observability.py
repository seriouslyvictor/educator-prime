from __future__ import annotations

import logging
from typing import Any

from .settings import get_settings


_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []
    if settings.log_rich:
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
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=level,
        format="%(message)s",
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


def log_warning(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.warning(_format_event(event, fields))


def log_error(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.exception(_format_event(event, fields))


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
        parts.append(f"{key}={_format_value(value)}")
    return " ".join(parts)


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return repr(value)
