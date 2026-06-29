"""Workflow helpers: pre-conditions and preparation steps shared across grading
endpoints.  These are domain-level checks that sit above a single model operation
but below the HTTP layer.
"""

from fastapi import HTTPException
from sqlmodel import Session, select

from ..google_provider import GoogleProvider
from ..grading_engine import GradingEngine
from ..models import GradingCriterion, GradingJob
from ..privacy_audit import latest_privacy_audit, run_privacy_audit
from .criteria import _criteria_match_defaults
from .inference import infer_job_criteria


def ensure_privacy_audit_allows_draft(
    job: GradingJob,
    session: Session,
    provider: GoogleProvider,
):
    """Run (or reuse) the privacy audit and raise 409 if high-risk files exist."""
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
