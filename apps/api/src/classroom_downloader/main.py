from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Queue
import shutil
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

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

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


def purge_cached_classroom_state_for_user(user_email: str, session: Session) -> None:
    clear_google_provider_caches()
    for row in session.exec(select(Activity).where(Activity.user_email == user_email)).all():
        session.delete(row)
    for row in session.exec(select(Course).where(Course.user_email == user_email)).all():
        session.delete(row)
    now = datetime.now(UTC)
    job_ids = [
        row.id
        for row in session.exec(
            select(GradingJob.id).where(GradingJob.user_email == user_email)
        ).all()
    ]
    if job_ids:
        for row in session.exec(
            select(GradingFileCache).where(GradingFileCache.job_id.in_(job_ids))
        ).all():
            row.deleted_at = row.deleted_at or now
            session.add(row)
        for row in session.exec(
            select(GradingScrubCache).where(GradingScrubCache.job_id.in_(job_ids))
        ).all():
            row.deleted_at = row.deleted_at or now
            session.add(row)
        for row in session.exec(
            select(ExportFile).where(ExportFile.job_id.in_(job_ids))
        ).all():
            row.cached_path = None
            row.content_hash = None
            row.byte_size = None
            row.cache_expires_at = None
            session.add(row)
        session.commit()
        for job_id in job_ids:
            shutil.rmtree(Path(settings.grading_cache_path) / job_id, ignore_errors=True)
            shutil.rmtree(Path(settings.export_cache_path) / job_id, ignore_errors=True)
    else:
        session.commit()


def get_current_session(
    request: Request,
    db: Session = Depends(get_session),
) -> UserSession:
    if settings.google_provider == "mock":
        return UserSession(
            id="mock-session",
            user_email="teacher@example.edu",
            google_credentials_json="{}",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    cookie_name = settings.session_cookie_name
    session_id = request.cookies.get(cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not signed in.")
    row = db.get(UserSession, session_id)
    if row is None or _as_utc(row.expires_at) < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    row.last_seen_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    return row


def get_current_user_email(
    current_session: UserSession = Depends(get_current_session),
) -> str:
    return current_session.user_email


def provider_dependency(
    current_session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_session),
) -> GoogleProvider:
    try:
        return make_google_provider(current_session.id, db)
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            purge_google_session_if_needed(auth_failure, current_session, db)
            raise auth_failure.http from error
        raise


_GRADING_ENGINE_ERRORS: dict[str, tuple[int, str]] = {
    "grading_provider_key_missing": (
        503,
        "AI grading is unavailable: the provider API key is missing. "
        "Set it in apps/api/.env and restart the API.",
    ),
    "grading_model_not_enabled": (
        503,
        "AI grading is unavailable: the selected model is not enabled in the "
        "catalog overlay (config/llm-model-overrides.json).",
    ),
    "unknown_grading_engine": (500, "AI grading engine is misconfigured."),
}


def resolve_grading_engine() -> GradingEngine:
    """Build the grading engine, translating config failures (missing key /
    disabled model) into a clear HTTP error before any work is done. Resolved via
    the grading module so test monkeypatches of grading.get_grading_engine apply."""
    try:
        return grading.get_grading_engine()
    except ValueError as error:
        status_code, detail = _GRADING_ENGINE_ERRORS.get(
            str(error), (500, "AI grading engine error.")
        )
        raise HTTPException(status_code=status_code, detail=detail) from error


def disconnected_auth_state() -> AuthState:
    return AuthState(
        signed_in=False,
        identity_scopes=False,
        classroom_scopes=False,
        drive_scopes=False,
        provider=settings.google_provider,
    )


@dataclass(frozen=True)
class AuthFailure:
    http: HTTPException
    purge_token: bool = False


def _contains_invalid_grant(error: Exception) -> bool:
    haystack = " ".join(str(part) for part in getattr(error, "args", ()) if part)
    haystack = f"{haystack} {error}".lower()
    return "invalid_grant" in haystack


def _http_error_content(error: Exception) -> str:
    content = getattr(error, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="ignore").lower()
    return str(content).lower()


def _http_403_is_hard_auth_failure(error: Exception) -> bool:
    content = _http_error_content(error)
    hard_markers = (
        "invalid_grant",
        "invalid credentials",
        "autherror",
        "unauthorized_client",
    )
    return any(marker in content for marker in hard_markers)


def google_auth_http_exception(error: Exception) -> AuthFailure | None:
    if isinstance(error, FileNotFoundError):
        log_warning(logger, "google.auth.token_missing")
        return AuthFailure(
            HTTPException(
                status_code=401,
                detail="Google session missing. Please connect your Google account again.",
            ),
            purge_token=False,
        )
    try:
        from google.auth.exceptions import RefreshError
        from googleapiclient.errors import HttpError
    except Exception:
        return None

    if isinstance(error, RefreshError):
        purge_token = _contains_invalid_grant(error)
        log_warning(logger, "google.auth.refresh_failed", purge_token=purge_token)
        return AuthFailure(
            HTTPException(
                status_code=401,
                detail="Google session expired. Please connect your Google account again.",
            ),
            purge_token=purge_token,
        )
    status_code = getattr(getattr(error, "resp", None), "status", None)
    if isinstance(error, HttpError) and status_code in {401, 403}:
        purge_token = status_code == 403 and _http_403_is_hard_auth_failure(error)
        log_warning(
            logger,
            "google.auth.api_denied",
            status_code=status_code,
            purge_token=purge_token,
        )
        return AuthFailure(
            HTTPException(
                status_code=401,
                detail="Google authorization failed. Please connect your Google account again.",
            ),
            purge_token=purge_token,
        )
    return None


def purge_google_session_if_needed(
    auth_failure: AuthFailure,
    current_session: UserSession,
    db: Session,
) -> None:
    if not auth_failure.purge_token:
        return
    row = db.get(UserSession, current_session.id)
    if row is not None:
        db.delete(row)
        db.commit()
    purge_cached_classroom_state_for_user(current_session.user_email, db)


def ensure_privacy_audit_allows_draft(
    job: GradingJob,
    session: Session,
    provider: GoogleProvider,
):
    audit = latest_privacy_audit(session, job.id)
    if audit is None or audit.status not in {"completed", "completed_with_blocks"}:
        audit = run_privacy_audit(session, job, provider)
    if audit.high_risk_files > 0:
        raise HTTPException(
            status_code=409,
            detail="Privacy audit found high-risk rows. Review the audit before drafting.",
        )
    return audit


def maybe_infer_job_criteria(
    job: GradingJob,
    session: Session,
    provider: GoogleProvider,
    grading_engine: GradingEngine,
    *,
    on_progress=None,
) -> None:
    """Run rubric inference once, before drafting, for infer-mode jobs whose
    criteria are still the placeholders. No-op otherwise (teacher-set or already
    inferred), so re-drafts don't re-bill the inference call."""
    if job.rubric_mode != "infer":
        return
    criteria = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job.id)
    ).all()
    if not _criteria_match_defaults(criteria):
        return
    infer_job_criteria(session, job, provider, grading_engine, on_progress=on_progress)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthState)
def auth_me(
    request: Request,
    db: Session = Depends(get_session),
) -> AuthState:
    log_event(logger, "auth.me.start", provider=settings.google_provider)
    if settings.google_provider == "mock":
        from .google_provider import MockGoogleProvider
        profile = MockGoogleProvider().account_profile()
        log_event(logger, "auth.me.mock", name=profile.name, email=profile.email)
        return AuthState(
            signed_in=True,
            identity_scopes=True,
            classroom_scopes=True,
            drive_scopes=True,
            email=profile.email,
            name=profile.name,
            picture=profile.picture,
            provider="mock",
        )
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return disconnected_auth_state()
    row = db.get(UserSession, session_id)
    if row is None or _as_utc(row.expires_at) < datetime.now(UTC):
        return disconnected_auth_state()
    scopes: set[str] = set()
    name = None
    email = None
    picture = None
    try:
        store = DbTokenStore(session_id, db)
        credentials = store.load_credentials()
        scopes = set(credentials.scopes or [])
        provider = make_google_provider(session_id, db)
        profile = provider.account_profile()
        name = profile.name
        email = profile.email
        picture = profile.picture
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            log_warning(
                logger,
                "auth.me.profile_auth_failed",
                purge_token=auth_failure.purge_token,
            )
            purge_google_session_if_needed(auth_failure, row, db)
            if auth_failure.purge_token or not scopes:
                return disconnected_auth_state()
        else:
            log_error(logger, "auth.me.profile_failed")
            if not scopes:
                return disconnected_auth_state()
    log_event(
        logger,
        "auth.me.google",
        scope_count=len(scopes),
        scopes=sorted(scopes),
        name=name,
        email=email,
    )
    has_google_identity = {"openid", "email", "profile"}.issubset(scopes)
    has_classroom_identity = any("classroom.profile.emails" in scope for scope in scopes)
    return AuthState(
        signed_in=bool(scopes),
        identity_scopes=has_google_identity or has_classroom_identity,
        classroom_scopes=any(scope.startswith("classroom.") for scope in scopes)
        or any("classroom" in scope for scope in scopes),
        drive_scopes=any("drive.readonly" in scope for scope in scopes),
        email=email,
        name=name,
        picture=picture,
        provider=settings.google_provider,
    )


@app.post("/api/auth/google/logout")
def auth_logout(
    request: Request,
    db: Session = Depends(get_session),
) -> Response:
    log_event(logger, "auth.google.logout", provider=settings.google_provider)
    if settings.google_provider == "google":
        session_id = request.cookies.get(settings.session_cookie_name)
        if session_id:
            row = db.get(UserSession, session_id)
            if row is not None:
                purge_cached_classroom_state_for_user(row.user_email, db)
                db.delete(row)
                db.commit()
    response = JSONResponse(content=disconnected_auth_state().model_dump())
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return response


@app.post("/api/auth/google/start", response_model=AuthStart)
def auth_start(scopes: list[str], db: Session = Depends(get_session)) -> AuthStart:
    log_event(
        logger,
        "auth.google.start",
        provider=settings.google_provider,
        scope_count=len(scopes),
        scopes=scopes,
    )
    if settings.google_provider == "mock":
        return AuthStart(mock_connected=True, scopes=scopes)
    if not settings.google_client_id or not settings.google_client_secret:
        log_warning(logger, "auth.google.not_configured")
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    state = token_urlsafe(24)
    now = datetime.now(UTC)
    db.add(OAuthState(
        id=state,
        scopes_json=json.dumps(scopes),
        expires_at=now + timedelta(minutes=10),
    ))
    db.exec(delete(OAuthState).where(OAuthState.expires_at < now))
    db.commit()
    return AuthStart(
        authorization_url=build_oauth_authorization_url(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            scopes=scopes,
            state=state,
        ),
        scopes=scopes,
    )


def _email_from_credentials(creds) -> str | None:
    import base64 as _base64
    import json as _json

    id_token = getattr(creds, "id_token", None)
    if isinstance(id_token, dict):
        return id_token.get("email")
    if isinstance(id_token, str):
        try:
            payload = id_token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            return _json.loads(_base64.urlsafe_b64decode(payload)).get("email")
        except Exception:
            return None
    return None


@app.get("/api/auth/google/callback")
def auth_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_session),
) -> RedirectResponse:
    log_event(logger, "auth.google.callback.start", state=state, has_code=bool(code))
    if not settings.google_client_id or not settings.google_client_secret:
        log_warning(logger, "auth.google.callback.not_configured")
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    oauth_state = db.get(OAuthState, state)
    if oauth_state is None or _as_utc(oauth_state.expires_at) < datetime.now(UTC):
        log_warning(logger, "auth.google.callback.invalid_state", received_state=state)
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    scopes = json.loads(oauth_state.scopes_json)
    db.delete(oauth_state)
    db.commit()

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=scopes,
        state=state,
    )
    flow.redirect_uri = settings.google_redirect_uri
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow.fetch_token(authorization_response=str(request.url), code=code)
    creds = flow.credentials
    user_email = _email_from_credentials(creds) or ""

    session_id = token_urlsafe(32)
    now = datetime.now(UTC)
    max_age = timedelta(hours=settings.session_max_age_hours)
    db.add(UserSession(
        id=session_id,
        user_email=user_email,
        google_credentials_json=creds.to_json(),
        created_at=now,
        expires_at=now + max_age,
    ))
    db.commit()

    log_event(
        logger,
        "auth.google.callback.complete",
        user_email=user_email,
        scopes=scopes,
    )
    is_prod = settings.frontend_origin.startswith("https://")
    redirect = RedirectResponse(f"{settings.frontend_origin}/?google=connected")
    redirect.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=int(max_age.total_seconds()),
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path="/",
    )
    return redirect


@app.get("/api/courses", response_model=list[CourseRead])
def list_courses(
    refresh: bool = False,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session: UserSession = Depends(get_current_session),
) -> list[Course]:
    user_email = current_session.user_email
    log_event(logger, "classroom.courses.start")
    cached_rows = session.exec(
        select(Course)
        .where(Course.user_email == user_email)
        .where(Course.course_state != "ARCHIVED")
    ).all()
    if cached_rows and not refresh and all(_is_fresh(row.fetched_at, settings.classroom_cache_ttl_minutes) for row in cached_rows):
        log_cache_hit(logger, "classroom.courses", "active", stored_count=len(cached_rows))
        return cached_rows
    log_cache_miss(logger, "classroom.courses", "active", stored_count=len(cached_rows))
    try:
        active_courses = [
            course for course in provider.list_courses() if course.course_state != "ARCHIVED"
        ]
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            purge_google_session_if_needed(auth_failure, current_session, session)
            raise auth_failure.http from error
        if cached_rows:
            log_warning(logger, "classroom.courses.stale_fallback", stored_count=len(cached_rows))
            return cached_rows
        raise
    log_event(
        logger,
        "classroom.courses.complete",
        active_count=len(active_courses),
        courses=[safe_fields(course) for course in active_courses],
    )
    for course in active_courses:
        session.merge(
            Course(
                id=course.id,
                name=course.name,
                section=course.section,
                course_state=course.course_state,
                user_email=user_email,
                fetched_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    session.commit()
    rows = session.exec(
        select(Course)
        .where(Course.user_email == user_email)
        .where(Course.course_state != "ARCHIVED")
    ).all()
    log_event(logger, "classroom.courses.complete", stored_count=len(rows))
    return rows


@app.get("/api/courses/{course_id}/activities", response_model=list[ActivityRead])
def list_activities(
    course_id: str,
    refresh: bool = False,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session: UserSession = Depends(get_current_session),
) -> list[Activity]:
    user_email = current_session.user_email
    log_event(logger, "classroom.activities.start", course_id=course_id)
    cached_rows = session.exec(
        select(Activity)
        .where(Activity.course_id == course_id)
        .where(Activity.user_email == user_email)
    ).all()
    if cached_rows and not refresh and all(_is_fresh(row.fetched_at, settings.classroom_cache_ttl_minutes) for row in cached_rows):
        log_cache_hit(logger, "classroom.activities", course_id, course_id=course_id, stored_count=len(cached_rows))
        return cached_rows
    log_cache_miss(logger, "classroom.activities", course_id, course_id=course_id, stored_count=len(cached_rows))
    try:
        activities = provider.list_activities(course_id)
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            purge_google_session_if_needed(auth_failure, current_session, session)
            raise auth_failure.http from error
        if cached_rows:
            log_warning(logger, "classroom.activities.stale_fallback", course_id=course_id, stored_count=len(cached_rows))
            return cached_rows
        raise
    log_event(
        logger,
        "classroom.activities.complete",
        course_id=course_id,
        count=len(activities),
        activities=[safe_fields(activity) for activity in activities],
    )
    if not activities:
        raise HTTPException(status_code=404, detail="Course not found or has no activities.")
    for activity in activities:
        session.merge(
            Activity(
                id=activity.id,
                course_id=activity.course_id,
                title=activity.title,
                work_type=activity.work_type,
                state=activity.state,
                due_label=activity.due_label,
                description=activity.description,
                user_email=user_email,
                fetched_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    session.commit()
    rows = session.exec(
        select(Activity)
        .where(Activity.course_id == course_id)
        .where(Activity.user_email == user_email)
    ).all()
    log_event(logger, "classroom.activities.complete", course_id=course_id, stored_count=len(rows))
    return rows


@app.post("/api/exports", response_model=ExportJobRead)
def create_export(
    payload: ExportCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> ExportJobRead:
    log_event(
        logger,
        "export.create.start",
        course_id=payload.course_id,
        activity_ids=payload.activity_ids,
    )
    course = next(
        (course for course in provider.list_courses() if course.id == payload.course_id),
        None,
    )
    if course is None or course.course_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Active course not found.")

    activities = {activity.id: activity for activity in provider.list_activities(course.id)}
    files = provider.list_submission_files(course.id, payload.activity_ids)
    log_event(
        logger,
        "export.create.submissions_loaded",
        course_id=course.id,
        activity_ids=payload.activity_ids,
        file_count=len(files),
        files=[safe_fields(file) for file in files],
    )
    used_paths: set[str] = set()
    job = ExportJob(
        id=str(uuid4()),
        course_id=course.id,
        course_name=course.name,
        user_email=user_email,
        status=ExportStatus.running,
        total_files=len(files),
        completed_files=0,
    )
    session.add(job)
    session.commit()

    completed = 0
    for submission_file in files:
        activity = activities.get(submission_file.activity_id)
        if activity is None:
            error = ExportError(
                id=str(uuid4()),
                job_id=job.id,
                file_id=submission_file.id,
                message="Activity metadata was not found for submission file.",
            )
            session.add(error)
            log_warning(
                logger,
                "export.create.missing_activity",
                job_id=job.id,
                file=safe_fields(submission_file),
            )
            continue

        source_name = submission_file.source_name
        export_mime_type = None
        google_export = GOOGLE_NATIVE_EXPORTS.get(submission_file.mime_type)
        if google_export:
            export_mime_type, extension = google_export
            source_name = f"{source_name.rsplit('.', 1)[0]}{extension}"

        output_path = build_output_path(
            course.name,
            activity.title,
            source_name,
            submission_file.student_email,
            submission_file.student_name,
            submission_file.id,
            used_paths,
        )
        session.add(
            ExportFile(
                id=str(uuid4()),
                job_id=job.id,
                course_id=course.id,
                activity_id=activity.id,
                activity_name=activity.title,
                student_email=submission_file.student_email,
                student_name=submission_file.student_name,
                source_file_id=submission_file.source_file_id,
                source_name=source_name,
                mime_type=submission_file.mime_type,
                export_mime_type=export_mime_type,
                output_path=output_path,
            )
        )
        completed += 1
        log_event(
            logger,
            "export.create.file_registered",
            job_id=job.id,
            source_file_id=submission_file.source_file_id,
            source_name=source_name,
            output_path=output_path,
            student_email=submission_file.student_email,
            student_name=submission_file.student_name,
            mime_type=submission_file.mime_type,
        )

    job.status = ExportStatus.completed
    job.completed_files = completed
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "export.create.complete",
        job_id=job.id,
        completed_files=job.completed_files,
        total_files=job.total_files,
    )
    return _build_export_read(job.id, session)


def _build_export_read(job_id: str, session: Session) -> ExportJobRead:
    job = session.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found.")
    files = session.exec(select(ExportFile).where(ExportFile.job_id == job_id)).all()
    errors = session.exec(select(ExportError).where(ExportError.job_id == job_id)).all()
    return ExportJobRead(
        id=job.id,
        course_id=job.course_id,
        course_name=job.course_name,
        status=job.status,
        total_files=job.total_files,
        completed_files=job.completed_files,
        files=[ExportFileRead.model_validate(file, from_attributes=True) for file in files],
        errors=[
            ExportErrorRead.model_validate(error, from_attributes=True) for error in errors
        ],
    )


@app.get("/api/exports/{job_id}", response_model=ExportJobRead)
def read_export(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> ExportJobRead:
    job = session.get(ExportJob, job_id)
    if job is None or job.user_email != user_email:
        raise HTTPException(status_code=404, detail="Export job not found.")
    return _build_export_read(job_id, session)


@app.get("/api/exports/{job_id}/files/{file_id}/content")
def stream_export_file(
    job_id: str,
    file_id: str,
    request: Request,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> Response:
    log_event(logger, "export.file.stream.start", job_id=job_id, file_id=file_id)
    job = session.get(ExportJob, job_id)
    if job is None or job.user_email != user_email:
        raise HTTPException(status_code=404, detail="Export file not found.")
    file = session.get(ExportFile, file_id)
    if file is None or file.job_id != job_id:
        raise HTTPException(status_code=404, detail="Export file not found.")
    cached_response = _export_file_cache_response(request, file)
    if cached_response is not None:
        return cached_response
    log_cache_miss(logger, "export.file.stream", file.id, file_id=file.id)
    try:
        content, media_type = provider.get_file_content(file.source_file_id)
    except KeyError as error:
        log_warning(
            logger,
            "export.file.stream.not_found",
            job_id=job_id,
            file_id=file_id,
            source_file_id=file.source_file_id,
        )
        raise HTTPException(status_code=404, detail="Drive file not found.") from error
    log_event(
        logger,
        "export.file.stream.complete",
        job_id=job_id,
        file_id=file_id,
        source_file_id=file.source_file_id,
        media_type=media_type,
        byte_size=len(content),
    )
    return _store_and_stream_export_file(session, job_id, file, content, media_type, request)


@app.get("/api/grading/health", response_model=GradingHealthRead)
def grading_health(probe: bool = False) -> GradingHealthRead:
    readiness = inspect_grading_readiness(probe=probe)
    log_event(
        logger,
        "grading.health",
        engine=readiness.engine,
        ready=readiness.ready,
        status=readiness.status,
        model=readiness.model,
        provider=readiness.provider,
        missing_keys=readiness.missing_keys,
        probed=readiness.probed,
        probe_ok=readiness.probe_ok,
    )
    return GradingHealthRead(
        engine=readiness.engine,
        ready=readiness.ready,
        status=readiness.status,
        model=readiness.model,
        provider=readiness.provider,
        missing_keys=readiness.missing_keys,
        detail=readiness.detail,
        probed=readiness.probed,
        probe_ok=readiness.probe_ok,
    )


@app.get("/api/grading/queue", response_model=list[GradingQueueItem])
def grading_queue(
    course_id: str | None = None,
    activity_id: str | None = None,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> list[GradingQueueItem]:
    log_event(logger, "grading.queue.start", course_id=course_id, activity_id=activity_id)
    if not course_id or not activity_id:
        raise HTTPException(
            status_code=400,
            detail="Grading queue requires course_id and activity_id; global scans are disabled.",
        )

    try:
        course = provider.get_course(course_id)
        activity = provider.get_activity(course_id, activity_id)
        files = provider.list_submission_files(course_id, [activity_id])
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Course or activity not found.") from error

    latest_job = session.exec(
        select(GradingJob)
        .where(GradingJob.course_id == course.id)
        .where(GradingJob.activity_id == activity.id)
        .where(GradingJob.user_email == user_email)
        .order_by(GradingJob.created_at.desc())
    ).first()
    item = GradingQueueItem(
        course_id=course.id,
        course_name=course.name,
        activity_id=activity.id,
        activity_title=activity.title,
        due_label=activity.due_label,
        submission_count=len(files),
        status=latest_job.status.value if latest_job else "ready",
        latest_job_id=latest_job.id if latest_job else None,
        reviewed_submissions=latest_job.reviewed_submissions if latest_job else 0,
        total_submissions=latest_job.total_submissions if latest_job else len(files),
    )
    log_event(logger, "grading.queue.complete", item=item.model_dump())
    return [item]


@app.get("/api/grading/jobs", response_model=list[GradingQueueItem])
def list_grading_jobs(
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> list[GradingQueueItem]:
    """List grading jobs so the teacher can resume in-progress work. Pure DB read:
    every label needed (course/activity names, counts, status) already lives on the
    GradingJob row, so this never calls the Google provider. Collapses to the newest
    job per (course_id, activity_id) and returns them most-recently-updated first."""
    log_event(logger, "grading.jobs.list.start")
    jobs = session.exec(
        select(GradingJob)
        .where(GradingJob.user_email == user_email)
        .order_by(GradingJob.updated_at.desc())
    ).all()
    newest_by_activity: dict[tuple[str, str], GradingJob] = {}
    for job in jobs:
        newest_by_activity.setdefault((job.course_id, job.activity_id), job)

    due_labels: dict[str, str | None] = {}
    activity_ids = {job.activity_id for job in newest_by_activity.values()}
    if activity_ids:
        for activity in session.exec(
            select(Activity)
            .where(Activity.id.in_(activity_ids))
            .where(Activity.user_email == user_email)
        ).all():
            due_labels[activity.id] = activity.due_label

    items = [
        GradingQueueItem(
            course_id=job.course_id,
            course_name=job.course_name,
            activity_id=job.activity_id,
            activity_title=job.activity_title,
            due_label=due_labels.get(job.activity_id),
            submission_count=job.total_submissions,
            status=job.status.value,
            latest_job_id=job.id,
            reviewed_submissions=job.reviewed_submissions,
            total_submissions=job.total_submissions,
        )
        for job in newest_by_activity.values()
    ]
    log_event(logger, "grading.jobs.list.complete", count=len(items))
    return items


VALID_RUBRIC_MODES = {"infer", "brief", "structured", "saved", "calibrate"}


@app.post("/api/grading/jobs", response_model=GradingJobRead)
def create_grading_job(
    payload: GradingJobCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    rubric_mode = (payload.rubric_mode or "").strip().lower()
    log_event(
        logger,
        "grading.job.create.start",
        course_id=payload.course_id,
        activity_id=payload.activity_id,
        rubric_mode=rubric_mode,
        teacher_loop=payload.teacher_loop,
        criteria_count=len(payload.criteria or []),
    )
    if rubric_mode not in VALID_RUBRIC_MODES:
        raise HTTPException(status_code=422, detail="Unknown rubric mode.")
    try:
        course = provider.get_course(payload.course_id)
        activity = provider.get_activity(payload.course_id, payload.activity_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Course or activity not found.") from error
    if course.course_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Active course not found.")
    session.merge(
        Course(
            id=course.id,
            name=course.name,
            section=course.section,
            course_state=course.course_state,
            user_email=user_email,
        )
    )
    session.merge(
        Activity(
            id=activity.id,
            course_id=activity.course_id,
            title=activity.title,
            work_type=activity.work_type,
            state=activity.state,
            due_label=activity.due_label,
            description=activity.description,
            user_email=user_email,
        )
    )

    job = GradingJob(
        id=str(uuid4()),
        course_id=course.id,
        course_name=course.name,
        activity_id=activity.id,
        activity_title=activity.title,
        activity_description=activity.description,
        rubric_mode=rubric_mode,
        teacher_loop=payload.teacher_loop,
        rubric_text=payload.rubric_text,
        batch_mode=settings.grading_batch_mode,
        status=GradingStatus.ready,
        cache_expires_at=default_cache_expiry(),
        user_email=user_email,
    )
    session.add(job)
    ensure_default_criteria(session, job.id, payload.criteria)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.job.create.complete",
        job_id=job.id,
        course_id=job.course_id,
        course_name=job.course_name,
        activity_id=job.activity_id,
        activity_title=job.activity_title,
        rubric_mode=job.rubric_mode,
        teacher_loop=job.teacher_loop,
        rubric_text=job.rubric_text,
        batch_mode=job.batch_mode,
        cache_expires_at=job.cache_expires_at,
    )
    return grading_job_snapshot(session, job)


def _get_owned_job(job_id: str, user_email: str, session: Session) -> GradingJob:
    job = session.get(GradingJob, job_id)
    if job is None or job.user_email != user_email:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    return job


@app.get("/api/grading/jobs/{job_id}", response_model=GradingJobRead)
def read_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    job = _get_owned_job(job_id, user_email, session)
    return grading_job_snapshot(session, job)


@app.patch("/api/grading/jobs/{job_id}/criteria", response_model=GradingJobRead)
def update_grading_criteria(
    job_id: str,
    payload: GradingCriteriaUpdate,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    """Replace a job's criteria before drafting. Lets the teacher edit the
    inferred (or structured) rubric; once saved, the criteria no longer match the
    placeholders, so inference won't overwrite them on a later prepare."""
    log_event(
        logger,
        "grading.criteria.update.start",
        job_id=job_id,
        criteria_count=len(payload.criteria),
    )
    job = _get_owned_job(job_id, user_email, session)
    if job.status != GradingStatus.ready:
        raise HTTPException(
            status_code=409, detail="Criteria can only be edited before drafting."
        )
    cleaned = [
        criterion
        for criterion in payload.criteria
        if criterion.name.strip() and criterion.weight > 0
    ]
    if not cleaned:
        raise HTTPException(
            status_code=422, detail="At least one weighted criterion is required."
        )
    _replace_job_criteria(session, job.id, cleaned)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.criteria.update.complete",
        job_id=job.id,
        criteria_count=len(cleaned),
    )
    return grading_job_snapshot(session, job)


@app.post("/api/grading/jobs/{job_id}/classroom-links", response_model=GradingJobRead)
def prepare_classroom_links(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session: UserSession = Depends(get_current_session),
) -> GradingJobRead:
    log_event(logger, "grading.classroom_links.start", job_id=job_id)
    job = _get_owned_job(job_id, current_session.user_email, session)
    try:
        links = provider.list_submission_links(job.course_id, job.activity_id)
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            log_warning(
                logger,
                "grading.classroom_links.auth_failed",
                job_id=job.id,
                purge_token=auth_failure.purge_token,
            )
            purge_google_session_if_needed(auth_failure, current_session, session)
        else:
            log_warning(logger, "grading.classroom_links.failed", job_id=job.id)
        return grading_job_snapshot(session, job)

    links_by_file_id = {link.source_file_id: link for link in links}
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    updated_count = 0
    for submission in submissions:
        link = links_by_file_id.get(submission.source_file_id)
        if link is None:
            continue
        submission.classroom_submission_id = link.classroom_submission_id
        submission.alternate_link = link.alternate_link
        submission.updated_at = datetime.now(UTC)
        session.add(submission)
        updated_count += 1
    if updated_count:
        job.updated_at = datetime.now(UTC)
        session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.classroom_links.complete",
        job_id=job.id,
        link_count=len(links),
        updated_count=updated_count,
    )
    return grading_job_snapshot(session, job)


@app.post("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
def run_grading_privacy_audit(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> PrivacyAuditRead:
    log_event(logger, "grading.privacy_audit.endpoint.start", job_id=job_id)
    job = _get_owned_job(job_id, user_email, session)
    audit = run_privacy_audit(session, job, provider)
    log_event(
        logger,
        "grading.privacy_audit.endpoint.complete",
        job_id=job_id,
        audit_id=audit.id,
        status=audit.status,
        total_files=audit.total_files,
        passed=audit.passed_files,
        redacted=audit.redacted_files,
        blocked=audit.blocked_files,
        high_risk=audit.high_risk_files,
    )
    return privacy_audit_snapshot(session, audit)


@app.get("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
def read_grading_privacy_audit(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> PrivacyAuditRead:
    job = _get_owned_job(job_id, user_email, session)
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    return privacy_audit_snapshot(session, audit)


@app.get("/api/grading/jobs/{job_id}/privacy-audit/stream")
def stream_grading_privacy_audit(
    job_id: str,
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> StreamingResponse:
    events: Queue[dict] = Queue()

    def worker() -> None:
        try:
            with Session(engine) as stream_session:
                job = stream_session.get(GradingJob, job_id)
                if job is None or job.user_email != user_email:
                    events.put({"phase": "audit", "error": "Grading job not found."})
                    return

                def on_progress(processed: int, total: int, label: str) -> None:
                    events.put(
                        {
                            "phase": "audit",
                            "processed": processed,
                            "total": total,
                            "current": label,
                        }
                    )

                audit = run_privacy_audit(stream_session, job, provider, on_progress=on_progress)
                events.put(
                    {
                        "phase": "audit",
                        "done": True,
                        "summary": privacy_audit_snapshot(stream_session, audit).model_dump(mode="json"),
                    }
                )
        except Exception:
            log_error(logger, "grading.privacy_audit.stream.failed", job_id=job_id)
            events.put({"phase": "audit", "error": "Privacy audit failed."})

    def event_stream():
        thread = Thread(target=worker, daemon=True)
        thread.start()
        while True:
            payload = events.get()
            yield _sse_event(payload)
            if payload.get("done") or payload.get("error"):
                break
        thread.join(timeout=1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/grading/jobs/{job_id}/criteria/stream")
def stream_grading_criteria(
    job_id: str,
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> StreamingResponse:
    events: Queue[dict] = Queue()

    def worker() -> None:
        try:
            with Session(engine) as stream_session:
                job = stream_session.get(GradingJob, job_id)
                if job is None or job.user_email != user_email:
                    events.put({"phase": "criteria", "error": "Grading job not found."})
                    return
                grading_engine = resolve_grading_engine()

                def on_progress(processed: int, total: int, label: str) -> None:
                    events.put(
                        {
                            "phase": "criteria",
                            "processed": processed,
                            "total": total,
                            "current": label,
                        }
                    )

                maybe_infer_job_criteria(
                    job,
                    stream_session,
                    provider,
                    grading_engine,
                    on_progress=on_progress,
                )
                events.put(
                    {
                        "phase": "criteria",
                        "done": True,
                        "job": grading_job_snapshot(stream_session, job).model_dump(mode="json"),
                    }
                )
        except Exception:
            log_error(logger, "grading.criteria.stream.failed", job_id=job_id)
            events.put({"phase": "criteria", "error": "Criteria inference failed."})

    def event_stream():
        thread = Thread(target=worker, daemon=True)
        thread.start()
        while True:
            payload = events.get()
            yield _sse_event(payload)
            if payload.get("done") or payload.get("error"):
                break
        thread.join(timeout=1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/grading/jobs/{job_id}/privacy-audit/export.csv")
def export_privacy_audit_csv(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> Response:
    job = _get_owned_job(job_id, user_email, session)
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    safe_name = "".join(char if char.isalnum() else "-" for char in job.activity_title)
    return _conditional_response(
        request=request,
        content=privacy_audit_csv(session, audit),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}-privacy-audit.csv"'
        },
    )


@app.get("/api/grading/jobs/{job_id}/privacy-audit/export.json", response_model=PrivacyAuditRead)
def export_privacy_audit_json(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> Response:
    job = _get_owned_job(job_id, user_email, session)
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    payload = privacy_audit_snapshot(session, audit).model_dump_json()
    return _conditional_response(
        request=request,
        content=payload,
        media_type="application/json",
    )


@app.post("/api/grading/jobs/{job_id}/draft", response_model=GradingJobRead)
def draft_job(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    log_event(logger, "grading.draft.endpoint.start", job_id=job_id)
    job = _get_owned_job(job_id, user_email, session)
    grading_engine = resolve_grading_engine()
    ensure_privacy_audit_allows_draft(job, session, provider)
    job = draft_grading_job(session, job, provider, grading_engine)
    log_event(
        logger,
        "grading.draft.endpoint.complete",
        job_id=job.id,
        status=job.status,
        total_submissions=job.total_submissions,
        reviewed_submissions=job.reviewed_submissions,
        flagged_submissions=job.flagged_submissions,
    )
    return grading_job_snapshot(session, job)


@app.get("/api/grading/jobs/{job_id}/draft/stream")
def stream_draft_job(
    job_id: str,
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> StreamingResponse:
    events: Queue[dict] = Queue()

    def worker() -> None:
        try:
            with Session(engine) as stream_session:
                job = stream_session.get(GradingJob, job_id)
                if job is None or job.user_email != user_email:
                    events.put({"phase": "draft", "error": "Grading job not found."})
                    return
                grading_engine = resolve_grading_engine()
                ensure_privacy_audit_allows_draft(job, stream_session, provider)

                def on_progress(processed: int, total: int, label: str) -> None:
                    events.put(
                        {
                            "phase": "draft",
                            "processed": processed,
                            "total": total,
                            "current": label,
                        }
                    )

                def on_submission(processed: int, total: int, label: str, submission) -> None:
                    events.put(
                        {
                            "phase": "draft",
                            "processed": processed,
                            "total": total,
                            "current": label,
                            "submission": submission.model_dump(mode="json"),
                        }
                    )

                def on_queued(submissions) -> None:
                    events.put(
                        {
                            "phase": "draft",
                            "processed": 0,
                            "total": len(submissions),
                            "current": "Na fila",
                            "queued": [row.model_dump(mode="json") for row in submissions],
                        }
                    )

                def on_submission_start(processed: int, total: int, label: str, submission_id: str) -> None:
                    events.put(
                        {
                            "phase": "draft",
                            "processed": processed,
                            "total": total,
                            "current": label,
                            "drafting_id": submission_id,
                        }
                    )

                drafted = draft_grading_job(
                    stream_session,
                    job,
                    provider,
                    grading_engine,
                    on_progress=on_progress,
                    on_submission=on_submission,
                    on_queued=on_queued,
                    on_submission_start=on_submission_start,
                )
                events.put(
                    {
                        "phase": "draft",
                        "done": True,
                        "job": grading_job_snapshot(stream_session, drafted).model_dump(mode="json"),
                    }
                )
        except Exception:
            log_error(logger, "grading.draft.stream.failed", job_id=job_id)
            events.put({"phase": "draft", "error": "Drafting failed."})

    def event_stream():
        thread = Thread(target=worker, daemon=True)
        thread.start()
        while True:
            payload = events.get()
            yield _sse_event(payload)
            if payload.get("done") or payload.get("error"):
                break
        thread.join(timeout=1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post(
    "/api/grading/jobs/{job_id}/submissions/{submission_id}/review",
    response_model=GradingJobRead,
)
def review_submission(
    job_id: str,
    submission_id: str,
    payload: GradingReviewUpdate,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    log_event(
        logger,
        "grading.review.start",
        job_id=job_id,
        submission_id=submission_id,
        final_score=payload.final_score,
        reviewed=payload.reviewed,
        feedback=payload.feedback,
    )
    job = _get_owned_job(job_id, user_email, session)
    submission = session.get(GradingSubmission, submission_id)
    if submission is None or submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")
    submission.final_score = payload.final_score
    submission.feedback = payload.feedback
    submission.reviewed = payload.reviewed
    submission.updated_at = datetime.now(UTC)
    session.add(submission)
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    job.reviewed_submissions = sum(1 for row in submissions if row.reviewed)
    job.flagged_submissions = sum(1 for row in submissions if row.flag or row.error)
    job.total_submissions = len(submissions)
    if job.total_submissions and job.reviewed_submissions == job.total_submissions:
        job.status = GradingStatus.completed
    else:
        job.status = GradingStatus.reviewing
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.review.complete",
        job_id=job.id,
        submission_id=submission_id,
        status=job.status,
        reviewed_submissions=job.reviewed_submissions,
        total_submissions=job.total_submissions,
    )
    return grading_job_snapshot(session, job)


@app.post(
    "/api/grading/jobs/{job_id}/submissions/{submission_id}/posted",
    response_model=GradingJobRead,
)
def mark_submission_posted(
    job_id: str,
    submission_id: str,
    payload: GradingPostedUpdate,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    log_event(
        logger,
        "grading.posted.start",
        job_id=job_id,
        submission_id=submission_id,
        posted=payload.posted,
    )
    job = _get_owned_job(job_id, user_email, session)
    submission = session.get(GradingSubmission, submission_id)
    if submission is None or submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")
    submission.posted_to_classroom = payload.posted
    submission.posted_at = datetime.now(UTC) if payload.posted else None
    submission.updated_at = datetime.now(UTC)
    job.updated_at = datetime.now(UTC)
    session.add(submission)
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        logger,
        "grading.posted.complete",
        job_id=job.id,
        submission_id=submission_id,
        posted=submission.posted_to_classroom,
    )
    return grading_job_snapshot(session, job)


@app.post(
    "/api/grading/jobs/{job_id}/submissions/{submission_id}/retry",
    response_model=GradingJobRead,
)
def retry_grading_submission(
    job_id: str,
    submission_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    log_event(logger, "grading.retry.endpoint.start", job_id=job_id, submission_id=submission_id)
    job = _get_owned_job(job_id, user_email, session)
    submission = session.get(GradingSubmission, submission_id)
    if submission is None or submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")
    grading_engine = resolve_grading_engine()
    job = retry_submission(session, job, submission, provider, grading_engine)
    log_event(
        logger,
        "grading.retry.endpoint.complete",
        job_id=job.id,
        submission_id=submission_id,
        status=job.status,
        flagged_submissions=job.flagged_submissions,
    )
    return grading_job_snapshot(session, job)


# Student-uploaded files are served back to the teacher. Only render types that
# cannot execute script on the app origin inline; everything else (HTML, SVG,
# Office docs, unknown binaries) is forced to download. Paired with nosniff so the
# browser cannot re-interpret a "safe" type as active content.
SAFE_INLINE_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
    }
)
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


def _preview_response_mode(mime_type: str, source_name: str, content: bytes) -> tuple[bool, str]:
    if mime_type in SAFE_INLINE_MIME_TYPES:
        return True, mime_type
    if mime_type.startswith("text/") or mime_type in SAFE_TEXT_MIME_TYPES:
        return True, "text/plain; charset=utf-8"
    if mime_type == "application/octet-stream" and Path(source_name).suffix.lower() in SAFE_TEXT_EXTENSIONS:
        if _is_utf8_text(content):
            return True, "text/plain; charset=utf-8"
    return False, mime_type or "application/octet-stream"


@app.get("/api/grading/jobs/{job_id}/submissions/{submission_id}/preview")
def preview_grading_submission(
    job_id: str,
    submission_id: str,
    request: Request,
    file_id: str | None = None,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> Response:
    """Stream the teacher's own copy of a submission so they can read the real work
    next to the AI draft. This serves the *original* cached file (not the LLM-scrubbed
    text): the teacher already has read access to these submissions, and only the
    redacted text is ever sent to the model. Served from the per-job cache, so it
    disappears when the cache TTL lapses or the teacher clears the cache.
    `file_id` selects one attachment of a multi-file submission (defaults to the primary)."""
    job = _get_owned_job(job_id, user_email, session)
    submission = session.get(GradingSubmission, submission_id)
    if submission is None or submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")
    selected_file_id = file_id or submission.source_file_id
    cache = session.exec(
        select(GradingFileCache)
        .where(GradingFileCache.job_id == job.id)
        .where(GradingFileCache.submission_id == submission.id)
        .where(GradingFileCache.source_file_id == selected_file_id)
        .where(GradingFileCache.deleted_at.is_(None))
        .order_by(GradingFileCache.created_at.desc())
    ).first()
    if cache is None:
        raise HTTPException(
            status_code=404,
            detail="Submission preview is not available (cache cleared or not drafted yet).",
        )
    path = Path(cache.cached_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Cached submission file is no longer available.",
        )
    normalized_mime = (cache.mime_type or submission.mime_type or "").split(";")[0].strip().lower()
    content = path.read_bytes()
    inline_ok, response_media_type = _preview_response_mode(
        normalized_mime,
        cache.source_name or submission.source_name,
        content,
    )
    log_event(
        logger,
        "grading.submission.preview",
        job_id=job_id,
        submission_id=submission_id,
        cache_id=cache.id,
        mime_type=normalized_mime,
        inline=inline_ok,
        byte_size=cache.byte_size,
    )
    return _conditional_response(
        request=request,
        content=content,
        media_type=response_media_type,
        headers={
            "Content-Disposition": "inline" if inline_ok else 'attachment; filename="submission"',
            # Prevent MIME sniffing turning an allowlisted type into active content.
            "X-Content-Type-Options": "nosniff",
        },
        max_age_seconds=300,
    )


@app.delete("/api/grading/jobs/{job_id}/cache", response_model=GradingJobRead)
def delete_grading_cache(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    log_event(logger, "grading.cache.delete.endpoint.start", job_id=job_id)
    job = _get_owned_job(job_id, user_email, session)
    job = delete_job_cache(session, job)
    log_event(logger, "grading.cache.delete.endpoint.complete", job_id=job_id)
    return grading_job_snapshot(session, job)


@app.get("/api/grading/jobs/{job_id}/export.csv")
def export_grading_csv(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> Response:
    job = _get_owned_job(job_id, user_email, session)
    body = grading_csv(session, job)
    safe_name = "".join(char if char.isalnum() else "-" for char in job.activity_title)
    return _conditional_response(
        request=request,
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}-grading-drafts.csv"'
        },
    )


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


def _export_file_cache_response(request: Request, file: ExportFile) -> Response | None:
    if not file.cached_path or not file.content_hash or not file.cache_expires_at:
        return None
    if not _is_future(file.cache_expires_at):
        return None
    path = Path(file.cached_path)
    if not path.exists() or not path.is_file():
        return None
    etag = f'"{file.content_hash}"'
    headers = _cache_headers(etag, settings.export_cache_ttl_hours * 3600)
    if etag in _if_none_match(request):
        log_debug(logger, "export.file.stream.not_modified", file_id=file.id)
        return Response(status_code=304, headers=headers)
    content = path.read_bytes()
    log_cache_hit(
        logger,
        "export.file.stream",
        file.id,
        file_id=file.id,
        cached_path=file.cached_path,
        byte_size=len(content),
    )
    return Response(content=content, media_type=file.export_mime_type or file.mime_type, headers=headers)


def _store_and_stream_export_file(
    session: Session,
    job_id: str,
    file: ExportFile,
    content: bytes,
    media_type: str,
    request: Request,
) -> Response:
    digest = sha256(content).hexdigest()
    cache_dir = Path(settings.export_cache_path) / job_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.output_path).suffix or ".bin"
    cache_path = cache_dir / f"{file.id}-{digest[:12]}{suffix}"
    cache_path.write_bytes(content)
    file.cached_path = str(cache_path)
    file.content_hash = digest
    file.byte_size = len(content)
    file.cache_expires_at = datetime.now(UTC) + timedelta(hours=settings.export_cache_ttl_hours)
    session.add(file)
    session.commit()
    session.refresh(file)
    return _conditional_response(
        request=request,
        content=content,
        media_type=media_type,
        max_age_seconds=settings.export_cache_ttl_hours * 3600,
    )


def _is_future(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value > datetime.now(UTC)


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
