"""Grading router: /api/grading/* — jobs, criteria, privacy-audit, draft, submissions, preview."""
from datetime import UTC, datetime
from pathlib import Path
from queue import Queue
from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlmodel import Session, select

from ..api.auth_errors import google_auth_http_exception
from ..api.common import _conditional_response, _sse_event
from ..api.google_errors import google_api_http_exception
from ..api.permissions import require_google_capability
from ..api.deps import (
    get_current_session,
    get_current_user_email,
    provider_dependency,
    resolve_grading_engine,
)
from ..api.session_cleanup import purge_google_session_if_needed
from ..database import engine, get_session
from ..grading import (
    _criteria_match_defaults,
    _replace_job_criteria,
    default_cache_expiry,
    delete_job,
    delete_job_cache,
    draft_grading_job,
    ensure_default_criteria,
    grading_csv,
    grading_job_snapshot,
    grading_submission_snapshot,
    infer_job_criteria,
    retry_submission,
)
from ..google_provider import GoogleProvider
from ..grading_engine import GradingEngine
from ..models import (
    Activity,
    Course,
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingStatus,
    GradingSubmission,
)
from ..observability import get_logger, log_error, log_event, log_warning
from ..privacy_audit import (
    latest_privacy_audit,
    privacy_audit_csv,
    privacy_audit_snapshot,
    run_privacy_audit,
)
from ..schemas import (
    GradingCriteriaUpdate,
    GradingHealthRead,
    GradingJobCreate,
    GradingJobRead,
    GradingPostedUpdate,
    GradingQueueItem,
    GradingReviewUpdate,
    PrivacyAuditRead,
)
from ..settings import get_settings
from ..grading_engine import inspect_grading_readiness

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()

# --- Module constants --------------------------------------------------------

VALID_RUBRIC_MODES = {"infer", "brief", "structured", "saved", "calibrate"}

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

# --- Helpers -----------------------------------------------------------------


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


def _get_owned_job(job_id: str, user_email: str, session: Session) -> GradingJob:
    job = session.get(GradingJob, job_id)
    if job is None or job.user_email != user_email:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    return job


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


# --- Routes ------------------------------------------------------------------


@router.get("/api/grading/health", response_model=GradingHealthRead)
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


@router.get("/api/grading/queue", response_model=list[GradingQueueItem])
def grading_queue(
    course_id: str | None = None,
    activity_id: str | None = None,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> list[GradingQueueItem]:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
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
        queue_state=latest_job.queue_state if latest_job else "active",
        reviewed_submissions=latest_job.reviewed_submissions if latest_job else 0,
        total_submissions=latest_job.total_submissions if latest_job else len(files),
    )
    log_event(logger, "grading.queue.complete", item=item.model_dump())
    return [item]


@router.get("/api/grading/jobs", response_model=list[GradingQueueItem])
def list_grading_jobs(
    state: str = "active",
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> list[GradingQueueItem]:
    """List grading jobs so the teacher can resume in-progress work. Pure DB read:
    every label needed (course/activity names, counts, status) already lives on the
    GradingJob row, so this never calls the Google provider. Collapses to the newest
    job per (course_id, activity_id) and returns them most-recently-updated first."""
    valid_states = {"active", "archived", "hidden", "all"}
    if state not in valid_states:
        raise HTTPException(status_code=422, detail="Unknown queue state.")
    log_event(logger, "grading.jobs.list.start", state=state)
    statement = (
        select(GradingJob)
        .where(GradingJob.user_email == user_email)
        .order_by(GradingJob.updated_at.desc())
    )
    if state != "all":
        statement = statement.where(GradingJob.queue_state == state)
    jobs = session.exec(statement).all()
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
            queue_state=job.queue_state,
            reviewed_submissions=job.reviewed_submissions,
            total_submissions=job.total_submissions,
        )
        for job in newest_by_activity.values()
    ]
    log_event(logger, "grading.jobs.list.complete", count=len(items))
    return items


@router.post("/api/grading/jobs", response_model=GradingJobRead)
def create_grading_job(
    payload: GradingJobCreate,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> GradingJobRead:
    require_google_capability(current_session, "classroom_read")
    user_email = current_session.user_email
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
        include_visual_submissions=payload.include_visual_submissions,
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
        include_visual_submissions=job.include_visual_submissions,
        cache_expires_at=job.cache_expires_at,
    )
    return grading_job_snapshot(session, job)


@router.delete("/api/grading/jobs/{job_id}", status_code=204)
def delete_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> Response:
    log_event(logger, "grading.job.delete.endpoint.start", job_id=job_id)
    job = _get_owned_job(job_id, user_email, session)
    delete_job(session, job)
    log_event(logger, "grading.job.delete.endpoint.complete", job_id=job_id)
    return Response(status_code=204)


def _set_queue_state(
    job_id: str,
    queue_state: str,
    session: Session,
    user_email: str,
) -> GradingJobRead:
    log_event(logger, "grading.job.queue_state.start", job_id=job_id, queue_state=queue_state)
    job = _get_owned_job(job_id, user_email, session)
    job.queue_state = queue_state
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(logger, "grading.job.queue_state.complete", job_id=job_id, queue_state=queue_state)
    return grading_job_snapshot(session, job)


@router.post("/api/grading/jobs/{job_id}/archive", response_model=GradingJobRead)
def archive_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    return _set_queue_state(job_id, "archived", session, user_email)


@router.post("/api/grading/jobs/{job_id}/hide", response_model=GradingJobRead)
def hide_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    return _set_queue_state(job_id, "hidden", session, user_email)


@router.post("/api/grading/jobs/{job_id}/restore", response_model=GradingJobRead)
def restore_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    return _set_queue_state(job_id, "active", session, user_email)


@router.get("/api/grading/jobs/{job_id}", response_model=GradingJobRead)
def read_grading_job(
    job_id: str,
    session: Session = Depends(get_session),
    user_email: str = Depends(get_current_user_email),
) -> GradingJobRead:
    job = _get_owned_job(job_id, user_email, session)
    return grading_job_snapshot(session, job)


@router.patch("/api/grading/jobs/{job_id}/criteria", response_model=GradingJobRead)
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


@router.post("/api/grading/jobs/{job_id}/classroom-links", response_model=GradingJobRead)
def prepare_classroom_links(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> GradingJobRead:
    require_google_capability(current_session, "submissions_read")
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
        elif google_api_http_exception(error):
            log_warning(logger, "grading.classroom_links.google_unavailable", job_id=job.id)
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


@router.post("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
def run_grading_privacy_audit(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> PrivacyAuditRead:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
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


@router.get("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
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


@router.get("/api/grading/jobs/{job_id}/privacy-audit/stream")
def stream_grading_privacy_audit(
    job_id: str,
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> StreamingResponse:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
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


@router.get("/api/grading/jobs/{job_id}/criteria/stream")
def stream_grading_criteria(
    job_id: str,
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> StreamingResponse:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
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


@router.get("/api/grading/jobs/{job_id}/privacy-audit/export.csv")
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


@router.get("/api/grading/jobs/{job_id}/privacy-audit/export.json", response_model=PrivacyAuditRead)
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


@router.post("/api/grading/jobs/{job_id}/draft", response_model=GradingJobRead)
def draft_job(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> GradingJobRead:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
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


@router.get("/api/grading/jobs/{job_id}/draft/stream")
def stream_draft_job(
    job_id: str,
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> StreamingResponse:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
    events: Queue[dict] = Queue()

    def worker() -> None:
        try:
            with Session(engine) as stream_session:
                job = stream_session.get(GradingJob, job_id)
                if job is None or job.user_email != user_email:
                    events.put({"phase": "draft", "error": "Grading job not found."})
                    return
                # Seed the queue from submissions the privacy audit already materialized:
                # the Google file listing below takes seconds, and the review screen
                # should show every student "na fila" before that round-trip, not after.
                existing = list(
                    stream_session.exec(
                        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
                    ).all()
                )
                if existing:
                    existing.sort(
                        key=lambda row: (row.student_name or row.student_email or "~").casefold()
                    )
                    events.put(
                        {
                            "phase": "draft",
                            "processed": 0,
                            "total": len(existing),
                            "current": "Na fila",
                            "queued": [
                                grading_submission_snapshot(stream_session, row).model_dump(mode="json")
                                for row in existing
                            ],
                        }
                    )
                else:
                    events.put(
                        {
                            "phase": "draft",
                            "processed": 0,
                            "total": 0,
                            "current": "Preparando a lista de alunos...",
                        }
                    )
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


@router.post(
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


@router.post(
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


@router.post(
    "/api/grading/jobs/{job_id}/submissions/{submission_id}/retry",
    response_model=GradingJobRead,
)
def retry_grading_submission(
    job_id: str,
    submission_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session=Depends(get_current_session),
) -> GradingJobRead:
    require_google_capability(current_session, "submissions_read")
    require_google_capability(current_session, "drive_read")
    user_email = current_session.user_email
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


@router.get("/api/grading/jobs/{job_id}/submissions/{submission_id}/preview")
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


@router.delete("/api/grading/jobs/{job_id}/cache", response_model=GradingJobRead)
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


@router.get("/api/grading/jobs/{job_id}/export.csv")
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
