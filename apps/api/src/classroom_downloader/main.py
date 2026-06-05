from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select

from .database import get_session, init_db
from .grading import (
    default_cache_expiry,
    delete_job_cache,
    draft_grading_job,
    ensure_default_criteria,
    grading_csv,
    grading_job_snapshot,
    retry_submission,
)
from .google_provider import (
    GOOGLE_NATIVE_EXPORTS,
    GoogleProvider,
    TokenStore,
    build_oauth_authorization_url,
    clear_google_provider_caches,
    get_google_provider,
)
from .models import (
    Activity,
    Course,
    ExportError,
    ExportFile,
    ExportJob,
    ExportStatus,
    GradingJob,
    GradingStatus,
    GradingSubmission,
    GradingFileCache,
    GradingScrubCache,
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
    GradingJobCreate,
    GradingJobRead,
    GradingQueueItem,
    GradingReviewUpdate,
    PrivacyAuditRead,
)
from .settings import get_settings

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


def purge_cached_classroom_state(session: Session) -> None:
    clear_google_provider_caches()
    for row in session.exec(select(Activity)).all():
        session.delete(row)
    for row in session.exec(select(Course)).all():
        session.delete(row)
    now = datetime.now(UTC)
    for row in session.exec(select(GradingFileCache)).all():
        row.deleted_at = row.deleted_at or now
        session.add(row)
    for row in session.exec(select(GradingScrubCache)).all():
        row.deleted_at = row.deleted_at or now
        session.add(row)
    for row in session.exec(select(ExportFile)).all():
        row.cached_path = None
        row.content_hash = None
        row.byte_size = None
        row.cache_expires_at = None
        session.add(row)
    session.commit()
    shutil.rmtree(Path(settings.grading_cache_path), ignore_errors=True)
    shutil.rmtree(Path(settings.export_cache_path), ignore_errors=True)


def provider_dependency(session: Session = Depends(get_session)) -> GoogleProvider:
    try:
        return get_google_provider()
    except Exception as error:
        auth_error = google_auth_http_exception(error)
        if auth_error:
            TokenStore(settings.google_token_path).delete()
            purge_cached_classroom_state(session)
            raise auth_error from error
        raise


def disconnected_auth_state() -> AuthState:
    return AuthState(
        signed_in=False,
        identity_scopes=False,
        classroom_scopes=False,
        drive_scopes=False,
        provider=settings.google_provider,
    )


def google_auth_http_exception(error: Exception) -> HTTPException | None:
    try:
        from google.auth.exceptions import RefreshError
        from googleapiclient.errors import HttpError
    except Exception:
        return None

    if isinstance(error, RefreshError):
        log_warning(logger, "google.auth.refresh_failed")
        return HTTPException(
            status_code=401,
            detail="Google session expired. Logout and connect your Google account again.",
        )
    status_code = getattr(getattr(error, "resp", None), "status", None)
    if isinstance(error, HttpError) and status_code in {401, 403}:
        log_warning(logger, "google.auth.api_denied", status_code=status_code)
        return HTTPException(
            status_code=401,
            detail="Google authorization failed. Logout and connect your Google account again.",
        )
    return None


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthState)
def auth_me(session: Session = Depends(get_session)) -> AuthState:
    log_event(logger, "auth.me.start", provider=settings.google_provider)
    if settings.google_provider == "google":
        token_store = TokenStore(settings.google_token_path)
        scopes: set[str] = set()
        name = None
        email = None
        picture = None
        if token_store.exists():
            try:
                credentials = token_store.load_credentials()
                scopes = set(credentials.scopes or [])
                profile = get_google_provider().account_profile()
                name = profile.name
                email = profile.email
                picture = profile.picture
            except Exception:
                log_error(logger, "auth.me.profile_failed")
                TokenStore(settings.google_token_path).delete()
                purge_cached_classroom_state(session)
                return disconnected_auth_state()
        log_event(
            logger,
            "auth.me.google",
            token_exists=token_store.exists(),
            scope_count=len(scopes),
            scopes=sorted(scopes),
            name=name,
            email=email,
            picture=picture,
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
    profile = get_google_provider().account_profile()
    log_event(
        logger,
        "auth.me.mock",
        name=profile.name,
        email=profile.email,
        picture=profile.picture,
    )
    return AuthState(
        signed_in=True,
        identity_scopes=True,
        classroom_scopes=settings.google_provider == "mock",
        drive_scopes=settings.google_provider == "mock",
        email=profile.email,
        name=profile.name,
        picture=profile.picture,
        provider=settings.google_provider,
    )


@app.post("/api/auth/google/logout", response_model=AuthState)
def auth_logout(session: Session = Depends(get_session)) -> AuthState:
    log_event(logger, "auth.google.logout", provider=settings.google_provider)
    if settings.google_provider == "google":
        TokenStore(settings.google_token_path).delete()
        purge_cached_classroom_state(session)
    return disconnected_auth_state()


@app.post("/api/auth/google/start", response_model=AuthStart)
def auth_start(scopes: list[str]) -> AuthStart:
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
    state_path = Path(settings.google_oauth_state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"state": state, "scopes": scopes}),
        encoding="utf-8",
    )
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


@app.get("/api/auth/google/callback")
def auth_callback(request: Request, code: str, state: str) -> RedirectResponse:
    log_event(logger, "auth.google.callback.start", state=state, has_code=bool(code))
    if not settings.google_client_id or not settings.google_client_secret:
        log_warning(logger, "auth.google.callback.not_configured")
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    state_path = Path(settings.google_oauth_state_path)
    state_payload = (
        json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    )
    expected_state = state_payload.get("state")
    if not expected_state or state != expected_state:
        log_warning(
            logger,
            "auth.google.callback.invalid_state",
            expected_state=expected_state,
            received_state=state,
        )
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

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
        scopes=state_payload.get("scopes", []),
        state=state,
    )
    flow.redirect_uri = settings.google_redirect_uri
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow.fetch_token(authorization_response=str(request.url), code=code)
    TokenStore(settings.google_token_path).save(flow.credentials.to_json())
    state_path.unlink(missing_ok=True)
    log_event(
        logger,
        "auth.google.callback.complete",
        token_path=settings.google_token_path,
        scopes=state_payload.get("scopes", []),
    )
    return RedirectResponse(f"{settings.frontend_origin}/?google=connected")


@app.get("/api/courses", response_model=list[CourseRead])
def list_courses(
    refresh: bool = False,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> list[Course]:
    log_event(logger, "classroom.courses.start")
    cached_rows = session.exec(select(Course).where(Course.course_state != "ARCHIVED")).all()
    if cached_rows and not refresh and all(_is_fresh(row.fetched_at, settings.classroom_cache_ttl_minutes) for row in cached_rows):
        log_cache_hit(logger, "classroom.courses", "active", stored_count=len(cached_rows))
        return cached_rows
    log_cache_miss(logger, "classroom.courses", "active", stored_count=len(cached_rows))
    try:
        active_courses = [
            course for course in provider.list_courses() if course.course_state != "ARCHIVED"
        ]
    except Exception as error:
        auth_error = google_auth_http_exception(error)
        if auth_error:
            TokenStore(settings.google_token_path).delete()
            purge_cached_classroom_state(session)
            raise auth_error from error
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
                fetched_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    session.commit()
    rows = session.exec(select(Course).where(Course.course_state != "ARCHIVED")).all()
    log_event(logger, "classroom.courses.complete", stored_count=len(rows))
    return rows


@app.get("/api/courses/{course_id}/activities", response_model=list[ActivityRead])
def list_activities(
    course_id: str,
    refresh: bool = False,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> list[Activity]:
    log_event(logger, "classroom.activities.start", course_id=course_id)
    cached_rows = session.exec(select(Activity).where(Activity.course_id == course_id)).all()
    if cached_rows and not refresh and all(_is_fresh(row.fetched_at, settings.classroom_cache_ttl_minutes) for row in cached_rows):
        log_cache_hit(logger, "classroom.activities", course_id, course_id=course_id, stored_count=len(cached_rows))
        return cached_rows
    log_cache_miss(logger, "classroom.activities", course_id, course_id=course_id, stored_count=len(cached_rows))
    try:
        activities = provider.list_activities(course_id)
    except Exception as error:
        auth_error = google_auth_http_exception(error)
        if auth_error:
            TokenStore(settings.google_token_path).delete()
            purge_cached_classroom_state(session)
            raise auth_error from error
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
                fetched_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    session.commit()
    rows = session.exec(select(Activity).where(Activity.course_id == course_id)).all()
    log_event(logger, "classroom.activities.complete", course_id=course_id, stored_count=len(rows))
    return rows


@app.post("/api/exports", response_model=ExportJobRead)
def create_export(
    payload: ExportCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
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
    return read_export(job.id, session)


@app.get("/api/exports/{job_id}", response_model=ExportJobRead)
def read_export(job_id: str, session: Session = Depends(get_session)) -> ExportJobRead:
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


@app.get("/api/exports/{job_id}/files/{file_id}/content")
def stream_export_file(
    job_id: str,
    file_id: str,
    request: Request,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> Response:
    log_event(logger, "export.file.stream.start", job_id=job_id, file_id=file_id)
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


@app.get("/api/grading/queue", response_model=list[GradingQueueItem])
def grading_queue(
    course_id: str | None = None,
    activity_id: str | None = None,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
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


@app.post("/api/grading/jobs", response_model=GradingJobRead)
def create_grading_job(
    payload: GradingJobCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> GradingJobRead:
    log_event(
        logger,
        "grading.job.create.start",
        course_id=payload.course_id,
        activity_id=payload.activity_id,
        rubric_mode=payload.rubric_mode,
        teacher_loop=payload.teacher_loop,
        criteria_count=len(payload.criteria or []),
    )
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
        )
    )

    job = GradingJob(
        id=str(uuid4()),
        course_id=course.id,
        course_name=course.name,
        activity_id=activity.id,
        activity_title=activity.title,
        rubric_mode=payload.rubric_mode,
        teacher_loop=payload.teacher_loop,
        rubric_text=payload.rubric_text,
        status=GradingStatus.ready,
        cache_expires_at=default_cache_expiry(),
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
        cache_expires_at=job.cache_expires_at,
    )
    return grading_job_snapshot(session, job)


@app.get("/api/grading/jobs/{job_id}", response_model=GradingJobRead)
def read_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
) -> GradingJobRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    return grading_job_snapshot(session, job)


@app.post("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
def run_grading_privacy_audit(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> PrivacyAuditRead:
    log_event(logger, "grading.privacy_audit.endpoint.start", job_id=job_id)
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
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
) -> PrivacyAuditRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    return privacy_audit_snapshot(session, audit)


@app.get("/api/grading/jobs/{job_id}/privacy-audit/export.csv")
def export_privacy_audit_csv(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
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
) -> Response:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
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
) -> GradingJobRead:
    log_event(logger, "grading.draft.endpoint.start", job_id=job_id)
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    ensure_privacy_audit_allows_draft(job, session, provider)
    job = draft_grading_job(session, job, provider)
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


@app.post(
    "/api/grading/jobs/{job_id}/submissions/{submission_id}/review",
    response_model=GradingJobRead,
)
def review_submission(
    job_id: str,
    submission_id: str,
    payload: GradingReviewUpdate,
    session: Session = Depends(get_session),
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
    job = session.get(GradingJob, job_id)
    submission = session.get(GradingSubmission, submission_id)
    if job is None or submission is None or submission.job_id != job.id:
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
    "/api/grading/jobs/{job_id}/submissions/{submission_id}/retry",
    response_model=GradingJobRead,
)
def retry_grading_submission(
    job_id: str,
    submission_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> GradingJobRead:
    log_event(logger, "grading.retry.endpoint.start", job_id=job_id, submission_id=submission_id)
    job = session.get(GradingJob, job_id)
    submission = session.get(GradingSubmission, submission_id)
    if job is None or submission is None or submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")
    job = retry_submission(session, job, submission, provider)
    log_event(
        logger,
        "grading.retry.endpoint.complete",
        job_id=job.id,
        submission_id=submission_id,
        status=job.status,
        flagged_submissions=job.flagged_submissions,
    )
    return grading_job_snapshot(session, job)


@app.delete("/api/grading/jobs/{job_id}/cache", response_model=GradingJobRead)
def delete_grading_cache(
    job_id: str,
    session: Session = Depends(get_session),
) -> GradingJobRead:
    log_event(logger, "grading.cache.delete.endpoint.start", job_id=job_id)
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    job = delete_job_cache(session, job)
    log_event(logger, "grading.cache.delete.endpoint.complete", job_id=job_id)
    return grading_job_snapshot(session, job)


@app.get("/api/grading/jobs/{job_id}/export.csv")
def export_grading_csv(
    job_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
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
