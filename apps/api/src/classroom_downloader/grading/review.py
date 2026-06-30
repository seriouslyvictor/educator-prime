"""Manual-review domain mutation: replace criterion scores, derive final_score,
refresh job counts, and commit — without any FastAPI plumbing.

The router parses the HTTP request and calls apply_review(); it then reads the
refreshed snapshot and builds its response.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from ..models import (
    GradingCriterion,
    GradingJob,
    GradingStatus,
    GradingSubmission,
    GradingSubmissionCriterionScore,
)
from ..schemas import GradingReviewUpdate


def apply_review(
    job: GradingJob,
    submission: GradingSubmission,
    payload: GradingReviewUpdate,
    session: Session,
) -> GradingJob:
    """Apply a teacher review to a single submission and return the refreshed job.

    Validates that:
    - The submission belongs to the job.
    - All criterion IDs in payload.criterion_scores belong to the job.

    Then atomically:
    - Replaces GradingSubmissionCriterionScore rows (if criterion_scores provided).
    - Derives submission.final_score from the per-criterion points (single source
      of truth), or uses payload.final_score directly when no criteria are given.
    - Updates submission.feedback, reviewed, updated_at.
    - Recalculates job.reviewed_submissions, flagged_submissions, total_submissions.
    - Transitions job.status to reviewing or completed.
    - Commits and returns the refreshed job.
    """
    if submission.job_id != job.id:
        raise HTTPException(status_code=404, detail="Grading submission not found.")

    # When per-criterion points are provided the overall score is DERIVED from
    # them (single source of truth).  Replace stored criterion rows atomically.
    if payload.criterion_scores is not None:
        # Reject criterion ids that don't belong to this job rather than storing
        # orphan rows that would never reconcile against the job's criteria.
        valid_criterion_ids = {
            row.id
            for row in session.exec(
                select(GradingCriterion).where(GradingCriterion.job_id == job.id)
            ).all()
        }
        unknown = [
            cs.criterion_id
            for cs in payload.criterion_scores
            if cs.criterion_id not in valid_criterion_ids
        ]
        if unknown:
            raise HTTPException(
                status_code=400, detail="Unknown criterion id in review payload."
            )

        existing_cs = session.exec(
            select(GradingSubmissionCriterionScore).where(
                GradingSubmissionCriterionScore.submission_id == submission.id
            )
        ).all()
        for row in existing_cs:
            session.delete(row)
        for cs in payload.criterion_scores:
            session.add(
                GradingSubmissionCriterionScore(
                    id=str(uuid4()),
                    submission_id=submission.id,
                    criterion_id=cs.criterion_id,
                    earned=cs.earned,
                )
            )
        # Derive overall final_score from the parts.
        derived_score = round(sum(cs.earned for cs in payload.criterion_scores), 2)
        submission.final_score = derived_score
    else:
        submission.final_score = payload.final_score

    submission.feedback = payload.feedback
    submission.reviewed = payload.reviewed
    submission.updated_at = datetime.now(UTC)
    session.add(submission)

    submissions = session.exec(
        select(GradingSubmission).where(GradingSubmission.job_id == job.id)
    ).all()
    job.reviewed_submissions = sum(1 for row in submissions if row.reviewed)
    job.flagged_submissions = sum(1 for row in submissions if row.flag or row.error)
    job.total_submissions = len(submissions)
    if job.total_submissions and job.reviewed_submissions == job.total_submissions:
        job.status = GradingStatus.completed
    else:
        job.status = GradingStatus.reviewing
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
