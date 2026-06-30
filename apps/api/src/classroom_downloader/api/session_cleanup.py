"""Session + provider + filesystem cache purge (side-effectful)."""
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from ..database import get_session  # noqa: F401 — re-exported for deps
from ..google_provider import clear_google_provider_caches
from ..models import (
    Activity,
    Course,
    ExportFile,
    GradingFileCache,
    GradingJob,
    GradingScrubCache,
    UserSession,
)
from ..observability import get_logger
from ..settings import get_settings
from .auth_errors import AuthFailure

settings = get_settings()
logger = get_logger(__name__)


def purge_cached_classroom_state_for_user(user_email: str, session: Session) -> None:
    clear_google_provider_caches()
    for row in session.exec(select(Activity).where(Activity.user_email == user_email)).all():
        session.delete(row)
    for row in session.exec(select(Course).where(Course.user_email == user_email)).all():
        session.delete(row)
    now = datetime.now(UTC)
    # exec(select(GradingJob.id)) yields scalar id strings, not GradingJob rows.
    job_ids = list(
        session.exec(
            select(GradingJob.id).where(GradingJob.user_email == user_email)
        ).all()
    )
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
