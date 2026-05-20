from classroom_downloader.google_provider import (
    ClassroomActivity,
    ClassroomCourse,
    GoogleApiProvider,
    build_oauth_authorization_url,
    drive_files_from_submission,
)


def test_build_oauth_authorization_url_uses_configured_web_client() -> None:
    url = build_oauth_authorization_url(
        client_id="client-id.apps.googleusercontent.com",
        client_secret="client-secret",
        redirect_uri="http://localhost:8000/api/auth/google/callback",
        scopes=["openid", "email"],
        state="state-123",
    )

    assert url.startswith("https://accounts.google.com/o/oauth2/auth")
    assert "client_id=client-id.apps.googleusercontent.com" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fauth%2Fgoogle%2Fcallback" in url
    assert "scope=openid+email" in url
    assert "state=state-123" in url


def test_drive_files_from_submission_extracts_drive_attachments_only() -> None:
    submission = {
        "id": "submission-1",
        "courseWorkId": "activity-1",
        "userId": "student-1",
        "assignmentSubmission": {
            "attachments": [
                {
                    "driveFile": {
                        "id": "drive-file-1",
                        "title": "Essay Draft",
                    }
                },
                {"link": {"url": "https://example.com"}},
                {"youTubeVideo": {"id": "video-1"}},
            ]
        },
    }

    files = drive_files_from_submission(
        course_id="course-1",
        submission=submission,
        student_email="student@example.edu",
        student_name="Student Example",
    )

    assert len(files) == 1
    assert files[0].id == "submission-1:drive-file-1"
    assert files[0].source_file_id == "drive-file-1"
    assert files[0].source_name == "Essay Draft"
    assert files[0].student_email == "student@example.edu"


def test_google_provider_uses_roster_identity_before_drive_modifier() -> None:
    provider = GoogleApiProvider.__new__(GoogleApiProvider)
    provider._profile_cache = {}
    provider._roster_cache = {}
    provider.classroom = FakeClassroomService()
    provider.drive = FakeDriveService()

    files = provider.list_submission_files("course-1", ["activity-1"])

    assert len(files) == 1
    assert files[0].student_email == "roster.student@example.edu"
    assert files[0].student_name == "Roster Student"
    assert files[0].source_name == "solution.py"
    assert files[0].mime_type == "text/x-python"


class FakeExecute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeStudentSubmissions:
    def list(self, **_kwargs):
        return FakeExecute(
            {
                "studentSubmissions": [
                    {
                        "id": "submission-1",
                        "courseWorkId": "activity-1",
                        "userId": "student-user-id",
                        "assignmentSubmission": {
                            "attachments": [
                                {
                                    "driveFile": {
                                        "id": "drive-file-1",
                                        "title": "student-upload.py",
                                    }
                                }
                            ]
                        },
                    }
                ]
            }
        )


class FakeCourseWork:
    def studentSubmissions(self):
        return FakeStudentSubmissions()


class FakeStudents:
    def list(self, **_kwargs):
        return FakeExecute(
            {
                "students": [
                    {
                        "userId": "student-user-id",
                        "profile": {
                            "id": "student-user-id",
                            "emailAddress": "roster.student@example.edu",
                            "name": {"fullName": "Roster Student"},
                        },
                    }
                ]
            }
        )


class FakeCourses:
    def courseWork(self):
        return FakeCourseWork()

    def students(self):
        return FakeStudents()


class FakeClassroomService:
    def courses(self):
        return FakeCourses()


class FakeDriveFiles:
    def get(self, **_kwargs):
        return FakeExecute(
            {
                "id": "drive-file-1",
                "name": "solution.py",
                "mimeType": "text/x-python",
                "lastModifyingUser": {
                    "displayName": "Drive Modifier",
                    "emailAddress": "drive.modifier@example.edu",
                },
            }
        )


class FakeDriveService:
    def files(self):
        return FakeDriveFiles()
