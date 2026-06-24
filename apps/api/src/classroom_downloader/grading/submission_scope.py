from ..google_provider import GoogleProvider, SubmissionFile
from ..models import GradingJob
from .submissions import group_key_for


def files_for_grading_scope(
    provider: GoogleProvider,
    job: GradingJob,
    files: list[SubmissionFile],
) -> list[SubmissionFile]:
    if job.grade_scope != "remaining":
        return files
    ungraded_ids = provider.ungraded_submission_ids(job.course_id, job.activity_id)
    return [file for file in files if group_key_for(file) in ungraded_ids or file.id in ungraded_ids]
