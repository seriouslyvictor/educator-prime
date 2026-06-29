"""Criterion scoring policy for the grading pipeline.

Provides _apply_criterion_scores, which replaces per-criterion earned-points
rows for a submission and derives the overall score from their sum.
"""
from uuid import uuid4

from sqlmodel import Session, select

from ..models import (
    GradingCriterion,
    GradingSubmission,
    GradingSubmissionCriterionScore,
)


def _apply_criterion_scores(
    session: Session,
    submission: GradingSubmission,
    criteria: list[GradingCriterion],
    criterion_scores: list[dict[str, str | float]],
) -> float | None:
    """Replace per-criterion earned-points rows for this submission and return the
    derived overall score (the sum of the stored whole-point earned values), or
    None when no criterion matched (brief mode, or a response whose criterion
    names didn't match the rubric — caller then keeps the holistic score).

    The per-criterion judgement is the source of truth: earned points are stored
    as WHOLE NUMBERS (no fractional granularity) clamped to [0, weight], and the
    overall score is DERIVED from their sum rather than the model's separate (and
    sometimes contradictory) holistic number.

    Matches engine output (keyed by criterion name) against the job's
    GradingCriterion rows.  Idempotent: deletes existing rows for this submission
    first."""
    # Always clear stale rows first so a retry produces clean state.
    existing = session.exec(
        select(GradingSubmissionCriterionScore).where(
            GradingSubmissionCriterionScore.submission_id == submission.id
        )
    ).all()
    for row in existing:
        session.delete(row)

    if not criterion_scores:
        return None

    # The engine returns scores in the same order it received the criteria, so when
    # the counts line up we match by POSITION — keeps the bars correct even when the
    # provider garbles the echoed criterion names (e.g. charset corruption in the
    # feedback text). Otherwise fall back to name match.
    use_positional = len(criterion_scores) == len(criteria)
    criteria_by_name = {c.name: c for c in criteria}
    total: float | None = None
    for index, entry in enumerate(criterion_scores):
        earned = entry.get("earned")
        if earned is None:
            continue
        if use_positional:
            criterion = criteria[index]
        else:
            name = entry.get("criterion", "")
            criterion = criteria_by_name.get(name) if isinstance(name, str) and name.strip() else None
        if criterion is None:
            continue
        # Whole points only, clamped to the criterion's maximum (its weight).
        earned_pts = float(max(0, min(int(round(float(earned))), criterion.weight)))
        session.add(
            GradingSubmissionCriterionScore(
                id=str(uuid4()),
                submission_id=submission.id,
                criterion_id=criterion.id,
                earned=earned_pts,
            )
        )
        total = (total or 0.0) + earned_pts
    return total
