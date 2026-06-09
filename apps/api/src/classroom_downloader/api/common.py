"""SSE + generic HTTP-cache primitives.  No domain dependencies."""
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import Request
from fastapi.responses import Response


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _is_fresh(value: datetime | None, ttl_minutes: int) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value > datetime.now(UTC) - timedelta(minutes=ttl_minutes)


def _etag(content: bytes | str) -> str:
    body = content.encode("utf-8") if isinstance(content, str) else content
    return f'"{sha256(body).hexdigest()}"'


def _cache_headers(etag: str, max_age_seconds: int) -> dict[str, str]:
    return {
        "Cache-Control": f"private, max-age={max_age_seconds}",
        "ETag": etag,
    }


def _if_none_match(request: Request) -> set[str]:
    header = request.headers.get("if-none-match", "")
    return {part.strip() for part in header.split(",") if part.strip()}


def _conditional_response(
    request: Request,
    content: bytes | str,
    media_type: str,
    headers: dict[str, str] | None = None,
    max_age_seconds: int = 300,
) -> Response:
    etag = _etag(content)
    response_headers = {
        **(headers or {}),
        **_cache_headers(etag, max_age_seconds),
    }
    if etag in _if_none_match(request):
        return Response(status_code=304, headers=response_headers)
    return Response(content=content, media_type=media_type, headers=response_headers)


def _is_future(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value > datetime.now(UTC)
