from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlmodel import Session, select

from .database import get_session, init_db
from .google_provider import GOOGLE_NATIVE_EXPORTS, GoogleProvider, get_google_provider
from .models import Activity, Course, ExportError, ExportFile, ExportJob, ExportStatus
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
    return AuthState(
        signed_in=True,
        identity_scopes=True,
        classroom_scopes=settings.google_provider == "mock",
        drive_scopes=settings.google_provider == "mock",
        email="teacher@example.edu" if settings.google_provider == "mock" else None,
        provider=settings.google_provider,
    )


@app.post("/api/auth/google/start", response_model=AuthStart)
def auth_start(scopes: list[str]) -> AuthStart:
    if settings.google_provider == "mock":
        return AuthStart(mock_connected=True, scopes=scopes)
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    raise HTTPException(
        status_code=501,
        detail="Real Google OAuth callback flow is reserved for credential configuration.",
    )


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
