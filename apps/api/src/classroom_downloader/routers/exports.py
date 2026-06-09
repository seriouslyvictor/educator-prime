"""Exports router: /api/exports/*"""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlmodel import Session, select

from ..api.common import (
    _cache_headers,
    _conditional_response,
    _if_none_match,
    _is_future,
)
from ..api.deps import get_current_user_email, provider_dependency
from ..database import get_session
from ..google_provider import GOOGLE_NATIVE_EXPORTS, GoogleProvider
from ..models import ExportError, ExportFile, ExportJob, ExportStatus
from ..naming import build_output_path
from ..observability import get_logger, log_cache_hit, log_cache_miss, log_debug, log_event, log_warning, safe_fields
from ..schemas import ExportCreate, ExportErrorRead, ExportFileRead, ExportJobRead
from ..settings import get_settings

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()


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


@router.post("/api/exports", response_model=ExportJobRead)
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


@router.get("/api/exports/{job_id}", response_model=ExportJobRead)
def read_export(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> ExportJobRead:
    job = session.get(ExportJob, job_id)
    if job is None or job.user_email != user_email:
        raise HTTPException(status_code=404, detail="Export job not found.")
    return _build_export_read(job_id, session)


@router.get("/api/exports/{job_id}/files/{file_id}/content")
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
