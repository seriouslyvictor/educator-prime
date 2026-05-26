from datetime import UTC, datetime
import csv
import json
from io import StringIO
from uuid import uuid4

from sqlmodel import Session, select

from .content_extraction import extract_submission_content
from .google_provider import GoogleProvider, SubmissionFile
from .grading import cache_submission_file
from .models import GradingJob, GradingSubmission, PrivacyAudit, PrivacyAuditRow
from .privacy import (
    EMAIL_PATTERN,
    ID_PATTERN,
    PHONE_PATTERN,
    URL_PATTERN,
    pseudonym_for_submission,
    scrub_submission,
)
from .schemas import PrivacyAuditRead, PrivacyAuditRowRead


DIRECT_PATTERNS = {
    "email": EMAIL_PATTERN,
    "phone": PHONE_PATTERN,
    "url": URL_PATTERN,
    "student_id": ID_PATTERN,
}


def run_privacy_audit(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
) -> PrivacyAudit:
    audit = PrivacyAudit(
        id=str(uuid4()),
        job_id=job.id,
        status="running",
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)

    files = provider.list_submission_files(job.course_id, [job.activity_id])
    for file in files:
        submission = _submission_for_audit(session, job, file)
        cache_file = cache_submission_file(session, job, submission, file, provider)
        extracted = extract_submission_content(cache_file)
        scrubbed = scrub_submission(session, job, submission, extracted)
        remaining_hits = _direct_hits(scrubbed.content)
        blocked = extracted.status in {"unsupported", "failed"}
        high_risk = scrubbed.report.status == "high_reidentification_risk"
        audit_pass = bool(not blocked and not remaining_hits and not high_risk)
        blocked_reason = (
            extracted.error
            if blocked
            else "high_reidentification_risk"
            if high_risk
            else None
        )
        row = PrivacyAuditRow(
            id=str(uuid4()),
            audit_id=audit.id,
            job_id=job.id,
            submission_id=submission.id,
            student_label=scrubbed.student_label,
            redacted_source_name=extracted.safe_source_label,
            mime_type=cache_file.mime_type,
            byte_size=cache_file.byte_size,
            extraction_status=extracted.status,
            extraction_error=extracted.error,
            privacy_status=scrubbed.report.status,
            privacy_flags_json=json.dumps(scrubbed.report.flags),
            remaining_direct_identifier_hits_json=json.dumps(remaining_hits),
            audit_pass=audit_pass,
            blocked_reason=blocked_reason,
        )
        session.add(row)

    session.commit()
    _refresh_audit_counts(session, audit)
    return audit


def latest_privacy_audit(session: Session, job_id: str) -> PrivacyAudit | None:
    return session.exec(
        select(PrivacyAudit)
        .where(PrivacyAudit.job_id == job_id)
        .order_by(PrivacyAudit.created_at.desc())
    ).first()


def privacy_audit_snapshot(session: Session, audit: PrivacyAudit) -> PrivacyAuditRead:
    rows = session.exec(
        select(PrivacyAuditRow)
        .where(PrivacyAuditRow.audit_id == audit.id)
        .order_by(PrivacyAuditRow.created_at)
    ).all()
    return PrivacyAuditRead(
        id=audit.id,
        job_id=audit.job_id,
        status=audit.status,
        total_files=audit.total_files,
        passed_files=audit.passed_files,
        redacted_files=audit.redacted_files,
        blocked_files=audit.blocked_files,
        high_risk_files=audit.high_risk_files,
        created_at=audit.created_at.isoformat(),
        updated_at=audit.updated_at.isoformat(),
        rows=[
            PrivacyAuditRowRead(
                id=row.id,
                submission_id=row.submission_id,
                student_label=row.student_label,
                redacted_source_name=row.redacted_source_name,
                mime_type=row.mime_type,
                byte_size=row.byte_size,
                extraction_status=row.extraction_status,
                extraction_error=row.extraction_error,
                privacy_status=row.privacy_status,
                privacy_flags=json.loads(row.privacy_flags_json),
                remaining_direct_identifier_hits=json.loads(
                    row.remaining_direct_identifier_hits_json
                ),
                audit_pass=row.audit_pass,
                blocked_reason=row.blocked_reason,
            )
            for row in rows
        ],
    )


def privacy_audit_csv(session: Session, audit: PrivacyAudit) -> str:
    snapshot = privacy_audit_snapshot(session, audit)
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "student_label",
            "redacted_source_name",
            "mime_type",
            "byte_size",
            "extraction_status",
            "extraction_error",
            "privacy_status",
            "privacy_flags",
            "remaining_direct_identifier_hits",
            "audit_pass",
            "blocked_reason",
        ],
    )
    writer.writeheader()
    for row in snapshot.rows:
        writer.writerow(
            {
                "student_label": row.student_label,
                "redacted_source_name": row.redacted_source_name,
                "mime_type": row.mime_type,
                "byte_size": row.byte_size,
                "extraction_status": row.extraction_status,
                "extraction_error": row.extraction_error or "",
                "privacy_status": row.privacy_status,
                "privacy_flags": ",".join(row.privacy_flags),
                "remaining_direct_identifier_hits": ",".join(
                    row.remaining_direct_identifier_hits
                ),
                "audit_pass": row.audit_pass,
                "blocked_reason": row.blocked_reason or "",
            }
        )
    return buffer.getvalue()


def _submission_for_audit(
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
    pseudonym_for_submission(session, job, row)
    return row


def _refresh_audit_counts(session: Session, audit: PrivacyAudit) -> None:
    rows = session.exec(
        select(PrivacyAuditRow).where(PrivacyAuditRow.audit_id == audit.id)
    ).all()
    audit.total_files = len(rows)
    audit.passed_files = sum(1 for row in rows if row.audit_pass)
    audit.redacted_files = sum(1 for row in rows if row.privacy_status == "redacted")
    audit.blocked_files = sum(1 for row in rows if row.blocked_reason)
    audit.high_risk_files = sum(
        1 for row in rows if row.privacy_status == "high_reidentification_risk"
    )
    audit.status = (
        "completed_with_blocks"
        if audit.blocked_files or audit.high_risk_files
        else "completed"
    )
    audit.updated_at = datetime.now(UTC)
    session.add(audit)
    session.commit()
    session.refresh(audit)


def _direct_hits(text: str) -> list[str]:
    return sorted(
        name for name, pattern in DIRECT_PATTERNS.items() if pattern.search(text)
    )
