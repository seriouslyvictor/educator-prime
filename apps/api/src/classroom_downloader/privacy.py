from dataclasses import dataclass
import re
from uuid import uuid4

from sqlmodel import Session, select

from .content_extraction import ExtractedSubmissionContent
from .models import GradingJob, GradingPseudonym, GradingSubmission
from .observability import get_logger, log_event, text_preview


logger = get_logger(__name__)


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")
URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)
ID_PATTERN = re.compile(r"\b(?:student|school|id)\s*#?:?\s*[A-Z0-9-]{4,}\b", re.IGNORECASE)


@dataclass(frozen=True)
class PrivacyReport:
    status: str
    flags: list[str]


@dataclass(frozen=True)
class ScrubbedSubmission:
    student_label: str
    source_label: str
    content: str
    report: PrivacyReport


def scrub_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    extracted: ExtractedSubmissionContent,
) -> ScrubbedSubmission:
    pseudonym = pseudonym_for_submission(session, job, submission)
    log_event(
        logger,
        "privacy.scrub.start",
        job_id=job.id,
        submission_id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        extracted_status=extracted.status,
        extracted_error=extracted.error,
        extracted_preview=text_preview(extracted.text),
        student_label=pseudonym.student_label,
        source_label=pseudonym.source_label,
    )
    if extracted.status in {"failed", "unsupported"}:
        log_event(
            logger,
            "privacy.scrub.blocked_input",
            job_id=job.id,
            submission_id=submission.id,
            status="failed",
            flags=[extracted.error or extracted.status],
        )
        return ScrubbedSubmission(
            student_label=pseudonym.student_label,
            source_label=pseudonym.source_label,
            content="",
            report=PrivacyReport(status="failed", flags=[extracted.error or extracted.status]),
        )

    content = extracted.text
    flags: list[str] = []
    content, changed = _replace_known_identity(content, submission.student_name, "[student]")
    if changed:
        flags.append("student_name")
    content, changed = _replace_known_identity(content, submission.student_email, "[email]")
    if changed:
        flags.append("student_email")

    replacements = [
        (EMAIL_PATTERN, "[email]", "email"),
        (PHONE_PATTERN, "[phone]", "phone"),
        (URL_PATTERN, "[url]", "url"),
        (ID_PATTERN, "[id]", "student_id"),
    ]
    for pattern, replacement, flag in replacements:
        content, count = pattern.subn(replacement, content)
        if count:
            flags.append(flag)

    remaining_direct_identifier = False
    for value in [submission.student_name, submission.student_email]:
        if value and value.lower() in content.lower():
            remaining_direct_identifier = True
            flags.append("identifier_remaining")

    if remaining_direct_identifier:
        status = "high_reidentification_risk"
    elif flags:
        status = "redacted"
    else:
        status = "clean"

    result = ScrubbedSubmission(
        student_label=pseudonym.student_label,
        source_label=pseudonym.source_label,
        content=content,
        report=PrivacyReport(status=status, flags=sorted(set(flags))),
    )
    log_event(
        logger,
        "privacy.scrub.complete",
        job_id=job.id,
        submission_id=submission.id,
        student_label=result.student_label,
        source_label=result.source_label,
        status=result.report.status,
        flags=result.report.flags,
        scrubbed_preview=text_preview(result.content),
    )
    return result


def pseudonym_for_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    commit: bool = True,
) -> GradingPseudonym:
    existing = session.exec(
        select(GradingPseudonym)
        .where(GradingPseudonym.job_id == job.id)
        .where(GradingPseudonym.submission_id == submission.id)
    ).first()
    if existing:
        log_event(
            logger,
            "privacy.pseudonym.hit",
            job_id=job.id,
            submission_id=submission.id,
            student_label=existing.student_label,
            source_label=existing.source_label,
        )
        return existing

    count = len(
        session.exec(select(GradingPseudonym).where(GradingPseudonym.job_id == job.id)).all()
    )
    row = GradingPseudonym(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        student_label=f"student_{count + 1:03d}",
        source_label=f"submission_{count + 1:03d}",
    )
    session.add(row)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(row)
    log_event(
        logger,
        "privacy.pseudonym.create",
        job_id=job.id,
        submission_id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        student_label=row.student_label,
        source_label=row.source_label,
    )
    return row


def _replace_known_identity(text: str, value: str | None, replacement: str) -> tuple[str, bool]:
    if not value:
        return text, False
    next_text = re.sub(re.escape(value), replacement, text, flags=re.IGNORECASE)
    return next_text, next_text != text
