from dataclasses import dataclass
import re
from uuid import uuid4

from sqlmodel import Session, select

from .content_extraction import ExtractedSubmissionContent
from .models import GradingJob, GradingPseudonym, GradingSubmission


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
    if extracted.status in {"failed", "unsupported"}:
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

    return ScrubbedSubmission(
        student_label=pseudonym.student_label,
        source_label=pseudonym.source_label,
        content=content,
        report=PrivacyReport(status=status, flags=sorted(set(flags))),
    )


def pseudonym_for_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
) -> GradingPseudonym:
    existing = session.exec(
        select(GradingPseudonym)
        .where(GradingPseudonym.job_id == job.id)
        .where(GradingPseudonym.submission_id == submission.id)
    ).first()
    if existing:
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
    session.commit()
    session.refresh(row)
    return row


def _replace_known_identity(text: str, value: str | None, replacement: str) -> tuple[str, bool]:
    if not value:
        return text, False
    next_text = re.sub(re.escape(value), replacement, text, flags=re.IGNORECASE)
    return next_text, next_text != text
