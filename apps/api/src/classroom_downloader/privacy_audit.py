from datetime import UTC, datetime
import csv
import json
from io import StringIO
from uuid import uuid4

from sqlmodel import Session, select

from .google_provider import GoogleProvider, SubmissionFile
from .grading import (
    _submission_for_file,
    cache_submission_file,
    scrub_submission_cached,
)
from .models import GradingJob, GradingSubmission, PrivacyAudit, PrivacyAuditRow
from .observability import get_logger, log_debug, log_event, safe_fields
from .privacy import pseudonym_for_submission
from .schemas import PrivacyAuditRead, PrivacyAuditRowRead

logger = get_logger(__name__)


def run_privacy_audit(
    session: Session,
    job: GradingJob,
    provider: GoogleProvider,
    on_progress=None,
) -> PrivacyAudit:
    log_event(
        logger,
        "privacy_audit.start",
        job_id=job.id,
        course_id=job.course_id,
        course_name=job.course_name,
        activity_id=job.activity_id,
        activity_title=job.activity_title,
    )
    audit = PrivacyAudit(
        id=str(uuid4()),
        job_id=job.id,
        status="running",
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)

    files = provider.list_submission_files(job.course_id, [job.activity_id])
    log_event(
        logger,
        "privacy_audit.files_loaded",
        audit_id=audit.id,
        job_id=job.id,
        count=len(files),
        files=[safe_fields(file) for file in files],
    )
    file_cache_hits = 0
    file_cache_misses = 0
    scrub_cache_hits = 0
    scrub_cache_misses = 0
    total = len(files)
    for index, file in enumerate(files, start=1):
        log_debug(logger, "privacy_audit.row.start", audit_id=audit.id, file=safe_fields(file))
        submission = _submission_for_audit(session, job, file)
        cache_file = cache_submission_file(
            session, job, submission, file, provider, commit=False
        )
        if getattr(cache_file, "_cache_hit", False):
            file_cache_hits += 1
        else:
            file_cache_misses += 1
        cached_scrub = scrub_submission_cached(
            session, job, submission, cache_file, commit=False
        )
        if cached_scrub.cache_hit:
            scrub_cache_hits += 1
        else:
            scrub_cache_misses += 1
        extracted = cached_scrub.extracted
        scrubbed = cached_scrub.scrubbed
        blocked = extracted.status in {"unsupported", "failed"}
        audit_pass = not blocked
        blocked_reason = extracted.error if blocked else None
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
            redaction_counts_json=json.dumps(scrubbed.report.counts),
            remaining_direct_identifier_hits_json=json.dumps([]),
            audit_pass=audit_pass,
            blocked_reason=blocked_reason,
        )
        session.add(row)
        log_event(
            logger,
            "privacy_audit.row.complete",
            audit_id=audit.id,
            job_id=job.id,
            submission_id=submission.id,
            student_email=submission.student_email,
            student_name=submission.student_name,
            student_label=scrubbed.student_label,
            source_name=file.source_name,
            redacted_source_name=extracted.safe_source_label,
            mime_type=cache_file.mime_type,
            byte_size=cache_file.byte_size,
            extraction_status=extracted.status,
            extraction_error=extracted.error,
            privacy_status=scrubbed.report.status,
            privacy_flags=scrubbed.report.flags,
            redaction_counts=scrubbed.report.counts,
            scrub_cache_hit=cached_scrub.cache_hit,
            audit_pass=audit_pass,
            blocked_reason=blocked_reason,
        )
        if on_progress:
            on_progress(index, total, file.source_name)

    session.commit()
    _refresh_audit_counts(session, audit)
    log_event(
        logger,
        "privacy_audit.complete",
        audit_id=audit.id,
        job_id=job.id,
        status=audit.status,
        total_files=audit.total_files,
        passed=audit.passed_files,
        redacted=audit.redacted_files,
        blocked=audit.blocked_files,
        high_risk=audit.high_risk_files,
        file_cache_hits=file_cache_hits,
        file_cache_misses=file_cache_misses,
        scrub_cache_hits=scrub_cache_hits,
        scrub_cache_misses=scrub_cache_misses,
    )
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
                redaction_counts=json.loads(row.redaction_counts_json),
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
            "redaction_counts",
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
                "redaction_counts": "; ".join(
                    f"{category}×{count}"
                    for category, count in sorted(row.redaction_counts.items())
                ),
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
    # Group a student's attachments into one submission (shared with the draft path),
    # then ensure the pseudonym exists. The audit still emits one row per file.
    submission = _submission_for_file(session, job, file)
    pseudonym_for_submission(session, job, submission, commit=False)
    return submission


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
