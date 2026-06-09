from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Queue
from secrets import token_urlsafe
from threading import Thread
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlmodel import Session, delete, select

from .database import engine, get_session, init_db
from . import grading
from .grading import (
    _criteria_match_defaults,
    _replace_job_criteria,
    default_cache_expiry,
    delete_job_cache,
    draft_grading_job,
    ensure_default_criteria,
    grading_csv,
    grading_job_snapshot,
    infer_job_criteria,
    retry_submission,
)
from .google_provider import (
    GOOGLE_NATIVE_EXPORTS,
    DbTokenStore,
    GoogleProvider,
    TokenStore,
    build_oauth_authorization_url,
    clear_google_provider_caches,
    make_google_provider,
)
from .grading_engine import GradingEngine, inspect_grading_readiness
from .models import (
    Activity,
    Course,
    ExportError,
    ExportFile,
    ExportJob,
    ExportStatus,
    GradingCriterion,
    GradingJob,
    GradingStatus,
    GradingSubmission,
    GradingFileCache,
    GradingScrubCache,
    OAuthState,
    UserSession,
)
from .naming import build_output_path
from .observability import (
    configure_logging,
    get_logger,
    log_cache_hit,
    log_cache_miss,
    log_debug,
    log_error,
    log_event,
    log_warning,
    safe_fields,
)
from .privacy_audit import (
    latest_privacy_audit,
    privacy_audit_csv,
    privacy_audit_snapshot,
    run_privacy_audit,
)
from .schemas import (
    ActivityRead,
    AuthStart,
    AuthState,
    CourseRead,
    ExportCreate,
    ExportErrorRead,
    ExportFileRead,
    ExportJobRead,
    GradingHealthRead,
    GradingCriteriaUpdate,
    GradingJobCreate,
    GradingJobRead,
    GradingPostedUpdate,
    GradingQueueItem,
    GradingReviewUpdate,
    PrivacyAuditRead,
)
from .settings import get_settings
from .api.common import (
    _sse_event,
    _as_utc,
    _is_fresh,
    _etag,
    _cache_headers,
    _if_none_match,
    _conditional_response,
    _is_future,
)
from .api.auth_errors import (
    AuthFailure,
    _contains_invalid_grant,
    _http_error_content,
    _http_403_is_hard_auth_failure,
    google_auth_http_exception,
)
from .api.session_cleanup import (
    purge_cached_classroom_state_for_user,
    purge_google_session_if_needed,
)
from .api.deps import (
    get_current_session,
    get_current_user_email,
    provider_dependency,
    resolve_grading_engine,
)
from .routers import health as _health_router
from .routers import auth as _auth_router
from .routers import courses as _courses_router
from .routers import exports as _exports_router
from .routers import grading as _grading_router

settings = get_settings()
configure_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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


def _static_frontend_root() -> Path | None:
    if not settings.static_dir:
        return None
    root = Path(settings.static_dir)
    if not root.exists() or not root.is_dir():
        return None
    return root


app.include_router(_health_router.router)
app.include_router(_auth_router.router)
app.include_router(_courses_router.router)
app.include_router(_exports_router.router)
app.include_router(_grading_router.router)


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
