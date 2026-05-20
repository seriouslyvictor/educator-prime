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
    content: bytes


class GoogleProvider:
    def list_courses(self) -> list[ClassroomCourse]:
        raise NotImplementedError

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        raise NotImplementedError

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        raise NotImplementedError

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        raise NotImplementedError


class MockGoogleProvider(GoogleProvider):
    courses = [
        ClassroomCourse("course-1", "Biology 101", "Morning", "ACTIVE"),
        ClassroomCourse("course-2", "Literature Seminar", "Afternoon", "ACTIVE"),
        ClassroomCourse("course-archived", "Archived Algebra", None, "ARCHIVED"),
    ]

    activities = [
        ClassroomActivity("activity-1", "course-1", "Cell Diagram", "ASSIGNMENT", "PUBLISHED", "May 24"),
        ClassroomActivity("activity-2", "course-1", "Lab Notes: Osmosis", "ASSIGNMENT", "PUBLISHED", "May 28"),
        ClassroomActivity("activity-3", "course-2", "Essay Draft", "ASSIGNMENT", "PUBLISHED", "May 30"),
    ]

    files = [
        SubmissionFile(
            "export-file-1",
            "course-1",
            "activity-1",
            "ana.silva@example.edu",
            "Ana Silva",
            "drive-file-1",
            "diagram.png",
            "image/png",
            b"Mock PNG bytes for Ana Silva\n",
        ),
        SubmissionFile(
            "export-file-2",
            "course-1",
            "activity-1",
            "bruno.costa@example.edu",
            "Bruno Costa",
            "drive-file-2",
            "cell-diagram.gdoc",
            "application/vnd.google-apps.document",
            b"Mock exported PDF bytes for Bruno Costa\n",
        ),
        SubmissionFile(
            "export-file-3",
            "course-1",
            "activity-2",
            None,
            "Carla Mendes",
            "drive-file-3",
            "osmosis notes.pdf",
            "application/pdf",
            b"Mock PDF bytes for Carla Mendes\n",
        ),
        SubmissionFile(
            "export-file-4",
            "course-2",
            "activity-3",
            "diego.lima@example.edu",
            "Diego Lima",
            "drive-file-4",
            "essay draft.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"Mock DOCX bytes for Diego Lima\n",
        ),
    ]

    def list_courses(self) -> list[ClassroomCourse]:
        return self.courses

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        return [activity for activity in self.activities if activity.course_id == course_id]

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        activity_filter = set(activity_ids or [])
        return [
            file
            for file in self.files
            if file.course_id == course_id
            and (not activity_filter or file.activity_id in activity_filter)
        ]

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        for file in self.files:
            if file.id == file_id or file.source_file_id == file_id:
                export = GOOGLE_NATIVE_EXPORTS.get(file.mime_type)
                if export:
                    return file.content, export[0]
                return file.content, file.mime_type
        raise KeyError(file_id)


def get_google_provider() -> GoogleProvider:
    return MockGoogleProvider()
