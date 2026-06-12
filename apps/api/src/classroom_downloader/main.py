"""App assembly, compat re-exports, and static-file catch-all.

Compat surface for tests:
  from classroom_downloader.main import app           # TestClient target
  from classroom_downloader.main import settings      # conftest + test fixtures
  from classroom_downloader.main import provider_dependency  # dependency_overrides key
"""
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from sqlmodel import Session

from .database import engine, init_db
from .observability import (
    _SENSITIVE_FIELDS,
    configure_logging,
    current_request_id,
    current_user_email,
    get_logger,
    log_event,
    purge_expired_observability_rows,
)
from .settings import get_settings

# Compat re-exports — imported by tests via 'from classroom_downloader.main import …'
from .api.deps import provider_dependency  # noqa: F401 — re-exported for test compat
from .routers import health as _health_router
from .routers import auth as _auth_router
from .routers import courses as _courses_router
from .routers import exports as _exports_router
from .routers import grading as _grading_router

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


def _scrub_sentry_event(event: dict, hint: object) -> dict:
    def scrub(value: object, key: str | None = None) -> object:
        try:
            if key in _SENSITIVE_FIELDS:
                return "<redacted>"
            if isinstance(value, dict):
                return {
                    str(item_key): scrub(item_value, str(item_key))
                    for item_key, item_value in value.items()
                }
            if isinstance(value, list):
                return [scrub(item) for item in value]
            if isinstance(value, tuple):
                return [scrub(item) for item in value]
            return value
        except Exception:
            return value

    try:
        extra = event.get("extra")
        if isinstance(extra, dict):
            event["extra"] = scrub(extra)
        contexts = event.get("contexts")
        if isinstance(contexts, dict):
            event["contexts"] = scrub(contexts)
        breadcrumbs = event.get("breadcrumbs")
        if isinstance(breadcrumbs, dict):
            values = breadcrumbs.get("values")
            if isinstance(values, list):
                for breadcrumb in values:
                    if isinstance(breadcrumb, dict) and isinstance(
                        breadcrumb.get("data"), dict
                    ):
                        breadcrumb["data"] = scrub(breadcrumb["data"])
    except Exception:
        return event
    return event


if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
        before_send=_scrub_sentry_event,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with Session(engine) as session:
        purge_expired_observability_rows(session)
    log_event(
        logger,
        "app.startup",
        provider=settings.google_provider,
        database_url=settings.database_url,
        cache_path=settings.grading_cache_path,
        frontend_origin=settings.frontend_origin,
        log_level=settings.log_level,
        payload_previews=settings.log_payload_previews,
    )
    yield


app = FastAPI(title="Classroom Downloader API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request, call_next):
    request_token = current_request_id.set(uuid4().hex[:12])
    user_token = current_user_email.set(None)
    try:
        return await call_next(request)
    finally:
        current_user_email.reset(user_token)
        current_request_id.reset(request_token)

# --- API routers (order matters — registered before the static catch-all) ----

app.include_router(_health_router.router)
app.include_router(_auth_router.router)
app.include_router(_courses_router.router)
app.include_router(_exports_router.router)
app.include_router(_grading_router.router)


# --- Static frontend catch-all (MUST be last) --------------------------------


def _static_frontend_root() -> Path | None:
    if not settings.static_dir:
        return None
    root = Path(settings.static_dir)
    if not root.exists() or not root.is_dir():
        return None
    return root


@app.get("/{full_path:path}", include_in_schema=False)
def serve_static_frontend(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    root = _static_frontend_root()
    if root is None:
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = (root / full_path).resolve()
    root_resolved = root.resolve()
    if candidate.is_file() and candidate.is_relative_to(root_resolved):
        return FileResponse(candidate)
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
