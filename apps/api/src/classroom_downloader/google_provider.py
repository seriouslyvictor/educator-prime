from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode


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
    content: bytes = b""


@dataclass(frozen=True)
class AccountProfile:
    name: str | None
    email: str | None
    picture: str | None


class GoogleProvider:
    def account_profile(self) -> AccountProfile:
        return AccountProfile(name=None, email=None, picture=None)

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


def build_oauth_authorization_url(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    scopes: list[str],
    state: str,
) -> str:
    del client_secret
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }
    )
    return f"https://accounts.google.com/o/oauth2/auth?{query}"


def drive_files_from_submission(
    course_id: str,
    submission: dict,
    student_email: str | None,
    student_name: str | None,
) -> list[SubmissionFile]:
    activity_id = submission.get("courseWorkId", "")
    submission_id = submission.get("id", "")
    attachments = (
        submission.get("assignmentSubmission", {}).get("attachments", [])
        if isinstance(submission.get("assignmentSubmission"), dict)
        else []
    )
    files: list[SubmissionFile] = []
    for attachment in attachments:
        drive_file = attachment.get("driveFile")
        if not isinstance(drive_file, dict):
            continue
        file_id = drive_file.get("id")
        if not file_id:
            continue
        files.append(
            SubmissionFile(
                id=f"{submission_id}:{file_id}",
                course_id=course_id,
                activity_id=activity_id,
                student_email=student_email,
                student_name=student_name,
                source_file_id=file_id,
                source_name=drive_file.get("title") or drive_file.get("name") or file_id,
                mime_type=drive_file.get("mimeType") or "application/octet-stream",
            )
        )
    return files


class TokenStore:
    def __init__(self, token_path: str):
        self.token_path = Path(token_path)

    def exists(self) -> bool:
        return self.token_path.exists()

    def save(self, credentials_json: str) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials_json, encoding="utf-8")

    def load_credentials(self):
        if not self.token_path.exists():
            raise FileNotFoundError(self.token_path)
        from google.oauth2.credentials import Credentials

        return Credentials.from_authorized_user_file(str(self.token_path))


class GoogleApiProvider(GoogleProvider):
    def __init__(self, credentials):
        from googleapiclient.discovery import build

        self.classroom = build(
            "classroom", "v1", credentials=credentials, cache_discovery=False
        )
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._profile_cache: dict[str, tuple[str | None, str | None]] = {}
        self._roster_cache: dict[str, dict[str, tuple[str | None, str | None]]] = {}

    def account_profile(self) -> AccountProfile:
        try:
            profile = self.classroom.userProfiles().get(userId="me").execute()
        except Exception:
            return AccountProfile(name=None, email=None, picture=None)
        return AccountProfile(
            name=profile.get("name", {}).get("fullName"),
            email=profile.get("emailAddress"),
            picture=profile.get("photoUrl"),
        )

    def list_courses(self) -> list[ClassroomCourse]:
        courses: list[ClassroomCourse] = []
        page_token = None
        while True:
            response = (
                self.classroom.courses()
                .list(courseStates=["ACTIVE"], pageSize=100, pageToken=page_token)
                .execute()
            )
            for course in response.get("courses", []):
                courses.append(
                    ClassroomCourse(
                        id=course["id"],
                        name=course.get("name", "Untitled course"),
                        section=course.get("section"),
                        course_state=course.get("courseState", "ACTIVE"),
                    )
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                return courses

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        activities: list[ClassroomActivity] = []
        page_token = None
        while True:
            response = (
                self.classroom.courses()
                .courseWork()
                .list(
                    courseId=course_id,
                    courseWorkStates=["PUBLISHED"],
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )
            for activity in response.get("courseWork", []):
                activities.append(
                    ClassroomActivity(
                        id=activity["id"],
                        course_id=course_id,
                        title=activity.get("title", "Untitled activity"),
                        work_type=activity.get("workType", "ASSIGNMENT"),
                        state=activity.get("state", "PUBLISHED"),
                        due_label=_due_label(activity),
                    )
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                return activities

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        files: list[SubmissionFile] = []
        activities = activity_ids or [activity.id for activity in self.list_activities(course_id)]
        for activity_id in activities:
            page_token = None
            while True:
                response = (
                    self.classroom.courses()
                    .courseWork()
                    .studentSubmissions()
                    .list(
                        courseId=course_id,
                        courseWorkId=activity_id,
                        pageSize=100,
                        pageToken=page_token,
                    )
                    .execute()
                )
                for submission in response.get("studentSubmissions", []):
                    email, name = self._student_identity(
                        course_id=course_id,
                        user_id=submission.get("userId", "me"),
                    )
                    submission_files = drive_files_from_submission(
                        course_id=course_id,
                        submission=submission,
                        student_email=email,
                        student_name=name,
                    )
                    files.extend(
                        self._hydrate_drive_metadata(file) for file in submission_files
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        return files

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        from googleapiclient.http import MediaIoBaseDownload

        metadata = self._drive_metadata(file_id)
        export = GOOGLE_NATIVE_EXPORTS.get(metadata.get("mimeType", ""))
        if export:
            request = self.drive.files().export_media(fileId=file_id, mimeType=export[0])
            media_type = export[0]
        else:
            request = self.drive.files().get_media(fileId=file_id)
            media_type = metadata.get("mimeType", "application/octet-stream")

        buffer = BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue(), media_type

    def _profile(self, user_id: str) -> tuple[str | None, str | None]:
        if user_id in self._profile_cache:
            return self._profile_cache[user_id]
        try:
            profile = self.classroom.userProfiles().get(userId=user_id).execute()
        except Exception:
            self._profile_cache[user_id] = (None, user_id)
            return self._profile_cache[user_id]
        name = profile.get("name", {}).get("fullName")
        email = profile.get("emailAddress")
        self._profile_cache[user_id] = (email, name)
        return self._profile_cache[user_id]

    def _student_identity(
        self, course_id: str, user_id: str
    ) -> tuple[str | None, str | None]:
        roster = self._course_roster(course_id)
        if user_id in roster:
            return roster[user_id]
        return self._profile(user_id)

    def _course_roster(self, course_id: str) -> dict[str, tuple[str | None, str | None]]:
        if course_id in self._roster_cache:
            return self._roster_cache[course_id]

        roster: dict[str, tuple[str | None, str | None]] = {}
        page_token = None
        try:
            while True:
                response = (
                    self.classroom.courses()
                    .students()
                    .list(courseId=course_id, pageSize=100, pageToken=page_token)
                    .execute()
                )
                for student in response.get("students", []):
                    user_id = student.get("userId")
                    profile = student.get("profile", {})
                    if not user_id:
                        continue
                    roster[user_id] = (
                        profile.get("emailAddress"),
                        profile.get("name", {}).get("fullName"),
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except Exception:
            roster = {}

        self._roster_cache[course_id] = roster
        return roster

    def _drive_metadata(self, file_id: str) -> dict:
        return (
            self.drive.files()
            .get(fileId=file_id, fields="id,name,mimeType")
            .execute()
        )

    def _hydrate_drive_metadata(self, file: SubmissionFile) -> SubmissionFile:
        try:
            metadata = self._drive_metadata(file.source_file_id)
        except Exception:
            return file
        last_modifier = metadata.get("lastModifyingUser", {})
        return SubmissionFile(
            id=file.id,
            course_id=file.course_id,
            activity_id=file.activity_id,
            student_email=file.student_email or last_modifier.get("emailAddress"),
            student_name=file.student_name or last_modifier.get("displayName"),
            source_file_id=file.source_file_id,
            source_name=metadata.get("name") or file.source_name,
            mime_type=metadata.get("mimeType") or file.mime_type,
        )


def _due_label(activity: dict) -> str | None:
    due_date = activity.get("dueDate")
    if not due_date:
        return None
    year = due_date.get("year")
    month = due_date.get("month")
    day = due_date.get("day")
    if not year or not month or not day:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


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

    def account_profile(self) -> AccountProfile:
        return AccountProfile(
            name="Teacher Example",
            email="teacher@example.edu",
            picture=None,
        )

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
    from .settings import get_settings

    settings = get_settings()
    if settings.google_provider == "google":
        return GoogleApiProvider(TokenStore(settings.google_token_path).load_credentials())
    return MockGoogleProvider()
