import csv
from io import StringIO

from sqlmodel import Session, select

from ..models import GradingJob, GradingSubmission
from ..observability import get_logger

logger = get_logger(__name__)


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
