"""Provider data models, base class, and shared constants."""
from dataclasses import dataclass


GOOGLE_NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


@dataclass(frozen=True)
class ClassroomCourse:
    id: str
    name: str
    section: str | None
    course_state: str


@dataclass(frozen=True)
class ClassroomActivity:
    id: str
    course_id: str
    title: str
    work_type: str
    state: str
    due_label: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class SubmissionFile:
    id: str
    course_id: str
    activity_id: str
    student_email: str | None
    student_name: str | None
    source_file_id: str
    source_name: str
    mime_type: str
    content: bytes = b""
    # Groups a student's attachments into one submission. Real provider sets this to
    # the Classroom studentSubmission id; when absent, callers fall back to source_file_id.
    classroom_submission_id: str | None = None


@dataclass(frozen=True)
class SubmissionLink:
    source_file_id: str
    classroom_submission_id: str
    alternate_link: str | None
    student_email: str | None = None


@dataclass(frozen=True)
class AccountProfile:
    name: str | None
    email: str | None
    picture: str | None


@dataclass(frozen=True)
class SubmissionGradeSummary:
    total: int
    graded: int
    ungraded: int
    returned: int = 0

    @property
    def concluded(self) -> bool:
        return self.total > 0 and self.ungraded == 0


def submission_has_classroom_grade(submission: dict) -> bool:
    return submission.get("assignedGrade") is not None or submission.get("state") == "RETURNED"


def _grade_summary_from_submissions(submissions: list[dict]) -> SubmissionGradeSummary:
    total = len(submissions)
    graded = sum(1 for submission in submissions if submission_has_classroom_grade(submission))
    returned = sum(1 for submission in submissions if submission.get("state") == "RETURNED")
    return SubmissionGradeSummary(total=total, graded=graded, ungraded=max(total - graded, 0), returned=returned)


class GoogleProvider:
    def account_profile(self) -> AccountProfile:
        return AccountProfile(name=None, email=None, picture=None)

    def get_course(self, course_id: str) -> ClassroomCourse:
        raise NotImplementedError

    def list_courses(self) -> list[ClassroomCourse]:
        raise NotImplementedError

    def get_activity(self, course_id: str, activity_id: str) -> ClassroomActivity:
        raise NotImplementedError

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        raise NotImplementedError

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        raise NotImplementedError

    def list_submission_links(
        self, course_id: str, activity_id: str
    ) -> list[SubmissionLink]:
        raise NotImplementedError

    def submission_grade_summary(
        self, course_id: str, activity_ids: list[str]
    ) -> dict[str, SubmissionGradeSummary]:
        raise NotImplementedError

    def ungraded_submission_ids(self, course_id: str, activity_id: str) -> set[str]:
        raise NotImplementedError

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        raise NotImplementedError
