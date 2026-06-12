"""Courses router: /api/courses — read-mirror context."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..api.auth_errors import google_auth_http_exception
from ..api.common import _is_fresh
from ..api.deps import get_current_session, provider_dependency
from ..api.google_errors import google_api_http_exception
from ..api.session_cleanup import purge_google_session_if_needed
from ..database import get_session
from ..google_provider import GoogleProvider
from ..models import Activity, Course, UserSession
from ..observability import get_logger, log_cache_hit, log_cache_miss, log_event, log_warning, safe_fields
from ..schemas import ActivityRead, CourseRead
from ..settings import get_settings

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()


@router.get("/api/courses", response_model=list[CourseRead])
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
        google_failure = google_api_http_exception(error)
        if google_failure:
            raise google_failure from error
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


@router.get("/api/courses/{course_id}/activities", response_model=list[ActivityRead])
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
        google_failure = google_api_http_exception(error)
        if google_failure:
            raise google_failure from error
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
