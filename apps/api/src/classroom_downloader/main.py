from contextlib import asynccontextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
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
)
from .naming import build_output_path
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
)
from .settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Classroom Downloader API", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def provider_dependency() -> GoogleProvider:
    return get_google_provider()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthState)
def auth_me() -> AuthState:
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
                scopes = set()
                name = None
                email = None
                picture = None
        has_google_identity = {"openid", "email", "profile"}.issubset(scopes)
        has_classroom_identity = any("classroom.profile.emails" in scope for scope in scopes)
        return AuthState(
            signed_in=token_store.exists(),
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


@app.post("/api/auth/google/start", response_model=AuthStart)
def auth_start(scopes: list[str]) -> AuthStart:
    if settings.google_provider == "mock":
        return AuthStart(mock_connected=True, scopes=scopes)
    if not settings.google_client_id or not settings.google_client_secret:
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
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    state_path = Path(settings.google_oauth_state_path)
    state_payload = (
        json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    )
    expected_state = state_payload.get("state")
    if not expected_state or state != expected_state:
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
    return RedirectResponse(f"{settings.frontend_origin}/?google=connected")


@app.get("/api/courses", response_model=list[CourseRead])
def list_courses(
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> list[Course]:
    active_courses = [
        course for course in provider.list_courses() if course.course_state != "ARCHIVED"
    ]
    for course in active_courses:
        session.merge(
            Course(
                id=course.id,
                name=course.name,
                section=course.section,
                course_state=course.course_state,
            )
        )
    session.commit()
    return session.exec(select(Course).where(Course.course_state != "ARCHIVED")).all()


@app.get("/api/courses/{course_id}/activities", response_model=list[ActivityRead])
def list_activities(
    course_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> list[Activity]:
    activities = provider.list_activities(course_id)
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
            )
        )
    session.commit()
    return session.exec(select(Activity).where(Activity.course_id == course_id)).all()


@app.post("/api/exports", response_model=ExportJobRead)
def create_export(
    payload: ExportCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> ExportJobRead:
    course = next(
        (course for course in provider.list_courses() if course.id == payload.course_id),
        None,
    )
    if course is None or course.course_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Active course not found.")

    activities = {activity.id: activity for activity in provider.list_activities(course.id)}
    files = provider.list_submission_files(course.id, payload.activity_ids)
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

    job.status = ExportStatus.completed
    job.completed_files = completed
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
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
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> Response:
    file = session.get(ExportFile, file_id)
    if file is None or file.job_id != job_id:
        raise HTTPException(status_code=404, detail="Export file not found.")
    try:
        content, media_type = provider.get_file_content(file.source_file_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Drive file not found.") from error
    return Response(content=content, media_type=media_type)


@app.get("/api/grading/queue", response_model=list[GradingQueueItem])
def grading_queue(
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> list[GradingQueueItem]:
    items: list[GradingQueueItem] = []
    active_courses = [
        course for course in provider.list_courses() if course.course_state != "ARCHIVED"
    ]
    for course in active_courses:
        for activity in provider.list_activities(course.id):
            files = provider.list_submission_files(course.id, [activity.id])
            latest_job = session.exec(
                select(GradingJob)
                .where(GradingJob.course_id == course.id)
                .where(GradingJob.activity_id == activity.id)
                .order_by(GradingJob.created_at.desc())
            ).first()
            status = "ready"
            if latest_job:
                status = latest_job.status.value
            items.append(
                GradingQueueItem(
                    course_id=course.id,
                    course_name=course.name,
                    activity_id=activity.id,
                    activity_title=activity.title,
                    due_label=activity.due_label,
                    submission_count=len(files),
                    status=status,
                    latest_job_id=latest_job.id if latest_job else None,
                    reviewed_submissions=latest_job.reviewed_submissions
                    if latest_job
                    else 0,
                    total_submissions=latest_job.total_submissions if latest_job else len(files),
                )
            )
    return items


@app.post("/api/grading/jobs", response_model=GradingJobRead)
def create_grading_job(
    payload: GradingJobCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> GradingJobRead:
    course = next(
        (course for course in provider.list_courses() if course.id == payload.course_id),
        None,
    )
    if course is None or course.course_state == "ARCHIVED":
        raise HTTPException(status_code=404, detail="Active course not found.")
    activity = next(
        (
            activity
            for activity in provider.list_activities(course.id)
            if activity.id == payload.activity_id
        ),
        None,
    )
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found.")

    job = GradingJob(
        id=str(uuid4()),
        course_id=course.id,
        course_name=course.name,
        activity_id=activity.id,
        activity_title=activity.title,
        rubric_mode=payload.rubric_mode,
        teacher_loop=payload.teacher_loop,
        status=GradingStatus.ready,
        cache_expires_at=default_cache_expiry(),
    )
    session.add(job)
    ensure_default_criteria(session, job.id, payload.criteria)
    session.commit()
    session.refresh(job)
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


@app.post("/api/grading/jobs/{job_id}/draft", response_model=GradingJobRead)
def draft_job(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> GradingJobRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    job = draft_grading_job(session, job, provider)
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
    job = session.get(GradingJob, job_id)
    submission = session.get(GradingSubmission, submission_id)
    if job is None or submission is None or submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")
    job = retry_submission(session, job, submission, provider)
    return grading_job_snapshot(session, job)


@app.delete("/api/grading/jobs/{job_id}/cache", response_model=GradingJobRead)
def delete_grading_cache(
    job_id: str,
    session: Session = Depends(get_session),
) -> GradingJobRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    job = delete_job_cache(session, job)
    return grading_job_snapshot(session, job)


@app.get("/api/grading/jobs/{job_id}/export.csv")
def export_grading_csv(
    job_id: str,
    session: Session = Depends(get_session),
) -> Response:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    body = grading_csv(session, job)
    safe_name = "".join(char if char.isalnum() else "-" for char in job.activity_title)
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}-grading-drafts.csv"'
        },
    )
