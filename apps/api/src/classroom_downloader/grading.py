from datetime import UTC, datetime, timedelta
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import shutil
from uuid import uuid4

from sqlmodel import Session, select

from .google_provider import GoogleProvider, SubmissionFile
from .models import (
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingStatus,
    GradingSubmission,
)
from .schemas import (
    GradingCriterionInput,
    GradingCriterionRead,
    GradingFileCacheRead,
    GradingJobRead,
    GradingSubmissionRead,
)
from .settings import get_settings


DEFAULT_CRITERIA = [
    GradingCriterionInput(
        name="Understanding",
        weight=30,
        description="Shows command of the core concepts in the assignment.",
    ),
    GradingCriterionInput(
        name="Evidence",
        weight=25,
        description="Uses relevant details, sources, examples, or artifacts.",
    ),
    GradingCriterionInput(
        name="Reasoning",
        weight=30,
        description="Connects evidence to conclusions with clear logic.",
    ),
    GradingCriterionInput(
        name="Clarity",
        weight=15,
        description="Communicates in an organized, readable way.",
    ),
]


def default_cache_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(hours=settings.grading_cache_ttl_hours)


def ensure_default_criteria(
    session: Session,
    job_id: str,
    criteria: list[GradingCriterionInput] | None,
) -> None:
    rows = criteria or DEFAULT_CRITERIA
    for criterion in rows:
        session.add(
            GradingCriterion(
                id=str(uuid4()),
                job_id=job_id,
                name=criterion.name,
                weight=criterion.weight,
                description=criterion.description,
            )
        )


def grading_job_snapshot(session: Session, job: GradingJob) -> GradingJobRead:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    criteria = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job.id)
    ).all()
    cache_files = session.exec(
        select(GradingFileCache).where(GradingFileCache.job_id == job.id)
    ).all()
    return GradingJobRead(
        id=job.id,
        course_id=job.course_id,
        course_name=job.course_name,
        activity_id=job.activity_id,
        activity_title=job.activity_title,
        rubric_mode=job.rubric_mode,
        teacher_loop=job.teacher_loop,
        status=job.status,
        total_submissions=job.total_submissions,
        reviewed_submissions=job.reviewed_submissions,
        flagged_submissions=job.flagged_submissions,
        cache_expires_at=_iso(job.cache_expires_at),
        criteria=[
            GradingCriterionRead.model_validate(row, from_attributes=True)
            for row in criteria
        ],
        submissions=[
            GradingSubmissionRead.model_validate(row, from_attributes=True)
            for row in submissions
        ],
        cache_files=[
            GradingFileCacheRead(
                id=row.id,
                submission_id=row.submission_id,
                source_file_id=row.source_file_id,
                source_name=row.source_name,
                mime_type=row.mime_type,
                content_hash=row.content_hash,
                byte_size=row.byte_size,
                expires_at=_iso(row.expires_at) or "",
                deleted_at=_iso(row.deleted_at),
            )
            for row in cache_files
        ],
    )


def draft_grading_job(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
) -> GradingJob:
    now = datetime.now(UTC)
    job.status = GradingStatus.drafting
    job.updated_at = now
    job.cache_expires_at = job.cache_expires_at or default_cache_expiry()
    session.add(job)
    session.commit()

    files = provider.list_submission_files(job.course_id, [job.activity_id])
    for file in files:
        submission = _submission_for_file(session, job, file)
        cache_submission_file(session, job, submission, file, provider)
        ai_score, confidence, flag = mock_grade(file)
        submission.ai_score = ai_score
        submission.confidence = confidence
        submission.final_score = submission.final_score or ai_score
        submission.feedback = submission.feedback or mock_feedback(
            student_name=file.student_name,
            activity_title=job.activity_title,
            source_name=file.source_name,
            score=ai_score,
            confidence=confidence,
            flag=flag,
        )
        submission.flag = flag
        submission.error = None
        submission.updated_at = datetime.now(UTC)
        session.add(submission)

    _refresh_counts(session, job)
    job.status = GradingStatus.completed if job.reviewed_submissions == job.total_submissions and job.total_submissions else GradingStatus.reviewing
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def retry_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    provider: GoogleProvider,
) -> GradingJob:
    file = SubmissionFile(
        id=submission.id,
        course_id=job.course_id,
        activity_id=job.activity_id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        mime_type=submission.mime_type,
    )
    cache_submission_file(session, job, submission, file, provider)
    ai_score, confidence, flag = mock_grade(file)
    submission.ai_score = ai_score
    submission.confidence = confidence
    submission.final_score = ai_score
    submission.feedback = mock_feedback(
        student_name=file.student_name,
        activity_title=job.activity_title,
        source_name=file.source_name,
        score=ai_score,
        confidence=confidence,
        flag=flag,
    )
    submission.reviewed = False
    submission.flag = flag
    submission.error = None
    submission.updated_at = datetime.now(UTC)
    session.add(submission)
    _refresh_counts(session, job)
    job.status = GradingStatus.reviewing
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def cache_submission_file(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    file: SubmissionFile,
    provider: GoogleProvider,
) -> GradingFileCache:
    now = datetime.now(UTC)
    existing = session.exec(
        select(GradingFileCache)
        .where(GradingFileCache.job_id == job.id)
        .where(GradingFileCache.submission_id == submission.id)
        .where(GradingFileCache.deleted_at.is_(None))
        .order_by(GradingFileCache.created_at.desc())
    ).first()
    if (
        existing
        and _aware(existing.expires_at) > now
        and Path(existing.cached_path).exists()
    ):
        return existing

    content, media_type = provider.get_file_content(file.source_file_id)
    cache_root = Path(get_settings().grading_cache_path)
    job_dir = cache_root / job.id
    job_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(content).hexdigest()
    suffix = Path(file.source_name).suffix or ".bin"
    cached_path = job_dir / f"{submission.id}-{digest[:12]}{suffix}"
    cached_path.write_bytes(content)
    row = GradingFileCache(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=media_type or file.mime_type,
        cached_path=str(cached_path),
        content_hash=digest,
        byte_size=len(content),
        expires_at=default_cache_expiry(),
    )
    session.add(row)
    job.cache_expires_at = row.expires_at
    session.add(job)
    session.commit()
    session.refresh(row)
    return row


def delete_job_cache(session: Session, job: GradingJob) -> GradingJob:
    now = datetime.now(UTC)
    rows = session.exec(
        select(GradingFileCache).where(GradingFileCache.job_id == job.id)
    ).all()
    for row in rows:
        path = Path(row.cached_path)
        if path.exists() and path.is_file():
            path.unlink()
        row.deleted_at = row.deleted_at or now
        session.add(row)
    job.cache_expires_at = None
    job.updated_at = now
    session.add(job)
    session.commit()
    shutil.rmtree(Path(get_settings().grading_cache_path) / job.id, ignore_errors=True)
    session.refresh(job)
    return job


def grading_csv(session: Session, job: GradingJob) -> str:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "student_name",
            "student_email",
            "ai_score",
            "final_score",
            "reviewed",
            "feedback",
            "confidence",
            "flag",
            "error",
        ],
    )
    writer.writeheader()
    for submission in submissions:
        writer.writerow(
            {
                "student_name": submission.student_name or "",
                "student_email": submission.student_email or "",
                "ai_score": submission.ai_score or "",
                "final_score": submission.final_score or "",
                "reviewed": submission.reviewed,
                "feedback": submission.feedback or "",
                "confidence": submission.confidence or "",
                "flag": submission.flag or "",
                "error": submission.error or "",
            }
        )
    return buffer.getvalue()


def mock_grade(file: SubmissionFile) -> tuple[float, float, str | None]:
    seed = sha256(
        f"{file.id}|{file.source_file_id}|{file.source_name}|{file.student_email}".encode(
            "utf-8"
        )
    ).hexdigest()
    score = 62 + (int(seed[:4], 16) % 36)
    confidence = round(0.72 + ((int(seed[4:8], 16) % 24) / 100), 2)
    flag = None
    if file.student_email is None:
        flag = "identity_review"
        confidence = min(confidence, 0.78)
    elif file.mime_type.startswith("image/"):
        flag = "visual_submission"
    return float(score), confidence, flag


def mock_feedback(
    student_name: str | None,
    activity_title: str,
    source_name: str,
    score: float,
    confidence: float,
    flag: str | None,
) -> str:
    learner = student_name or "This student"
    band = "strong" if score >= 85 else "developing" if score >= 72 else "emerging"
    note = (
        f"{learner} submitted {source_name} for {activity_title}. "
        f"The draft assessment is {band}: it recognizes the assignment goal, "
        "but the teacher should confirm evidence quality before finalizing."
    )
    if flag == "identity_review":
        note += " Student identity needs a quick check before export."
    if flag == "visual_submission":
        note += " Visual work may need manual inspection alongside the AI draft."
    note += f" Confidence: {int(confidence * 100)}%."
    return note


def _submission_for_file(
    session: Session,
    job: GradingJob,
    file: SubmissionFile,
) -> GradingSubmission:
    existing = session.exec(
        select(GradingSubmission)
        .where(GradingSubmission.job_id == job.id)
        .where(GradingSubmission.source_file_id == file.source_file_id)
    ).first()
    if existing:
        return existing
    row = GradingSubmission(
        id=str(uuid4()),
        job_id=job.id,
        student_email=file.student_email,
        student_name=file.student_name,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=file.mime_type,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _refresh_counts(session: Session, job: GradingJob) -> None:
    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    job.total_submissions = len(submissions)
    job.reviewed_submissions = sum(1 for row in submissions if row.reviewed)
    job.flagged_submissions = sum(1 for row in submissions if row.flag or row.error)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
