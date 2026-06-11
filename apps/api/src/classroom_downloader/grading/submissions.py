from uuid import uuid4

from sqlmodel import Session, select

from ..google_provider import SubmissionFile
from ..models import GradingJob, GradingSubmission, GradingSubmissionFile
from ..observability import get_logger, log_event

logger = get_logger(__name__)


def _student_sort_key(group_files: list[SubmissionFile]) -> str:
    first = group_files[0]
    return (first.student_name or first.student_email or "~").casefold()


def group_key_for(file: SubmissionFile) -> str:
    """Key that collapses a student's attachments into one submission. The real
    provider supplies the Classroom submission id; otherwise each file is its own
    group (preserving single-file behavior)."""
    return file.classroom_submission_id or file.source_file_id


def _group_files(files: list[SubmissionFile]) -> list[list[SubmissionFile]]:
    """Group attachments by submission, preserving first-seen order."""
    groups: list[list[SubmissionFile]] = []
    index: dict[str, int] = {}
    for file in files:
        key = group_key_for(file)
        if key not in index:
            index[key] = len(groups)
            groups.append([])
        groups[index[key]].append(file)
    return groups


def ensure_submission_file(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    file: SubmissionFile,
    *,
    commit: bool = True,
) -> GradingSubmissionFile:
    existing = session.exec(
        select(GradingSubmissionFile)
        .where(GradingSubmissionFile.submission_id == submission.id)
        .where(GradingSubmissionFile.source_file_id == file.source_file_id)
    ).first()
    if existing:
        return existing
    row = GradingSubmissionFile(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=file.mime_type,
    )
    session.add(row)
    if commit:
        session.commit()
    else:
        session.flush()
    return row


def submission_files(
    session: Session, submission: GradingSubmission
) -> list[GradingSubmissionFile]:
    """All attachments for a submission, newest-group-first by insertion. Falls back
    to a synthetic single-file view for legacy rows created before grouping."""
    rows = session.exec(
        select(GradingSubmissionFile)
        .where(GradingSubmissionFile.submission_id == submission.id)
        .order_by(GradingSubmissionFile.created_at)
    ).all()
    if rows:
        return list(rows)
    return [
        GradingSubmissionFile(
            id=submission.id,
            job_id=submission.job_id,
            submission_id=submission.id,
            source_file_id=submission.source_file_id,
            source_name=submission.source_name,
            mime_type=submission.mime_type,
        )
    ]


def _submission_for_file(
    session: Session,
    job: GradingJob,
    file: SubmissionFile,
) -> GradingSubmission:
    group_key = group_key_for(file)
    existing = session.exec(
        select(GradingSubmission)
        .where(GradingSubmission.job_id == job.id)
        .where(GradingSubmission.group_key == group_key)
    ).first()
    if existing:
        ensure_submission_file(session, job, existing, file, commit=False)
        session.commit()
        log_event(
            logger,
            "grading.submission.hit",
            job_id=job.id,
            submission_id=existing.id,
            group_key=group_key,
            source_file_id=file.source_file_id,
            student_email=existing.student_email,
            student_name=existing.student_name,
        )
        return existing
    row = GradingSubmission(
        id=str(uuid4()),
        job_id=job.id,
        group_key=group_key,
        student_email=file.student_email,
        student_name=file.student_name,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=file.mime_type,
    )
    session.add(row)
    session.flush()
    ensure_submission_file(session, job, row, file, commit=False)
    session.commit()
    session.refresh(row)
    log_event(
        logger,
        "grading.submission.create",
        job_id=job.id,
        submission_id=row.id,
        group_key=group_key,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        student_email=file.student_email,
        student_name=file.student_name,
        mime_type=file.mime_type,
    )
    return row
