from sqlmodel import Session, select

from ..models import (
    GradingAiAttempt,
    GradingCriterion,
    GradingFileCache,
    GradingJob,
    GradingPseudonym,
    GradingScrubCache,
    GradingSubmission,
    GradingSubmissionFile,
    PrivacyAudit,
    PrivacyAuditRow,
)
from .caching import delete_job_cache


def delete_job(session: Session, job: GradingJob) -> None:
    delete_job_cache(session, job)
    child_tables = (
        GradingCriterion,
        GradingSubmissionFile,
        GradingFileCache,
        GradingPseudonym,
        GradingAiAttempt,
        GradingScrubCache,
        PrivacyAuditRow,
        PrivacyAudit,
        GradingSubmission,
    )
    for table in child_tables:
        rows = session.exec(select(table).where(table.job_id == job.id)).all()
        for row in rows:
            session.delete(row)
    session.delete(job)
    session.commit()
