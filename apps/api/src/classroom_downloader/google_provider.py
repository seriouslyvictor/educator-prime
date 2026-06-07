from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

from .settings import get_settings
from .observability import (
    byte_preview,
    get_logger,
    log_cache_hit,
    log_cache_miss,
    log_debug,
    log_error,
    log_event,
    log_warning,
    safe_fields,
)


logger = get_logger(__name__)


GOOGLE_NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


@dataclass
class _TtlCacheEntry:
    value: object
    expires_at: datetime


_GOOGLE_PROVIDER_CACHE: dict[str, tuple[object, float | None]] = {}
_PROFILE_CACHE: dict[str, _TtlCacheEntry] = {}
_ACCOUNT_PROFILE_CACHE: _TtlCacheEntry | None = None
_DRIVE_METADATA_CACHE: dict[str, _TtlCacheEntry] = {}


def clear_google_provider_caches() -> None:
    _GOOGLE_PROVIDER_CACHE.clear()
    _PROFILE_CACHE.clear()
    global _ACCOUNT_PROFILE_CACHE
    _ACCOUNT_PROFILE_CACHE = None
    _DRIVE_METADATA_CACHE.clear()
    log_event(logger, "google.cache.clear")


def _ttl(minutes: int) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def _cache_hit(entry: _TtlCacheEntry | None) -> bool:
    return bool(entry and entry.expires_at > datetime.now(UTC))


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
    log_event(
        logger,
        "google.oauth.url.build",
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope_count=len(scopes),
        scopes=scopes,
        state=state,
    )
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
                classroom_submission_id=submission_id or None,
            )
        )
    log_event(
        logger,
        "google.classroom.submission.attachments",
        course_id=course_id,
        activity_id=activity_id,
        submission_id=submission_id,
        user_id=submission.get("userId"),
        student_email=student_email,
        student_name=student_name,
        file_count=len(files),
        files=[safe_fields(file) for file in files],
    )
    return files


def submission_links_from_submission(
    submission: dict,
    student_email: str | None,
) -> list[SubmissionLink]:
    submission_id = submission.get("id", "")
    alternate_link = submission.get("alternateLink")
    attachments = (
        submission.get("assignmentSubmission", {}).get("attachments", [])
        if isinstance(submission.get("assignmentSubmission"), dict)
        else []
    )
    links: list[SubmissionLink] = []
    for attachment in attachments:
        drive_file = attachment.get("driveFile")
        if not isinstance(drive_file, dict):
            continue
        file_id = drive_file.get("id")
        if not file_id:
            continue
        links.append(
            SubmissionLink(
                source_file_id=file_id,
                classroom_submission_id=submission_id,
                alternate_link=alternate_link,
                student_email=student_email,
            )
        )
    return links


class TokenStore:
    def __init__(self, token_path: str):
        self.token_path = Path(token_path)

    def exists(self) -> bool:
        exists = self.token_path.exists()
        log_event(logger, "google.token.exists", path=str(self.token_path), exists=exists)
        return exists

    def save(self, credentials_json: str) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials_json, encoding="utf-8")
        clear_google_provider_caches()
        log_event(
            logger,
            "google.token.save",
            path=str(self.token_path),
            byte_size=len(credentials_json.encode("utf-8")),
        )

    def delete(self) -> None:
        self.token_path.unlink(missing_ok=True)
        clear_google_provider_caches()
        log_event(logger, "google.token.delete", path=str(self.token_path))

    def load_credentials(self):
        if not self.token_path.exists():
            log_warning(logger, "google.token.missing", path=str(self.token_path))
            raise FileNotFoundError(self.token_path)
        from google.oauth2.credentials import Credentials

        log_event(logger, "google.token.load", path=str(self.token_path))
        return Credentials.from_authorized_user_file(str(self.token_path))

    def load_valid_credentials(self):
        credentials = self.load_credentials()
        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request

            log_event(logger, "google.token.refresh", path=str(self.token_path))
            credentials.refresh(Request())
            self.save(credentials.to_json())
            return credentials

        from google.auth.exceptions import RefreshError

        log_warning(
            logger,
            "google.token.not_refreshable",
            path=str(self.token_path),
            expired=credentials.expired,
            has_refresh_token=bool(credentials.refresh_token),
        )
        raise RefreshError("Stored Google credentials cannot be refreshed.")


class GoogleApiProvider(GoogleProvider):
    def __init__(self, credentials):
        from googleapiclient.discovery import build

        log_event(logger, "google.provider.init", provider="google")
        self.classroom = build(
            "classroom", "v1", credentials=credentials, cache_discovery=False
        )
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._profile_cache: dict[str, tuple[str | None, str | None]] = {}

    def account_profile(self) -> AccountProfile:
        global _ACCOUNT_PROFILE_CACHE
        settings = get_settings()
        if _cache_hit(_ACCOUNT_PROFILE_CACHE):
            profile = _ACCOUNT_PROFILE_CACHE.value
            if isinstance(profile, AccountProfile):
                log_cache_hit(logger, "google.account_profile", "me")
                return profile
        log_cache_miss(logger, "google.account_profile", "me")
        log_debug(logger, "google.account_profile.start")
        try:
            profile = self.classroom.userProfiles().get(userId="me").execute()
        except Exception:
            log_error(logger, "google.account_profile.failed")
            return AccountProfile(name=None, email=None, picture=None)
        account = AccountProfile(
            name=profile.get("name", {}).get("fullName"),
            email=profile.get("emailAddress"),
            picture=profile.get("photoUrl"),
        )
        log_event(
            logger,
            "google.account_profile.complete",
            name=account.name,
            email=account.email,
            picture=account.picture,
        )
        _ACCOUNT_PROFILE_CACHE = _TtlCacheEntry(
            account,
            _ttl(settings.google_profile_cache_ttl_minutes),
        )
        return account

    def list_courses(self) -> list[ClassroomCourse]:
        log_debug(logger, "google.courses.start")
        courses: list[ClassroomCourse] = []
        page_token = None
        page = 0
        while True:
            page += 1
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
            log_debug(
                logger,
                "google.courses.page",
                page=page,
                page_count=len(response.get("courses", [])),
                next_page=bool(response.get("nextPageToken")),
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                log_event(
                    logger,
                    "google.courses.complete",
                    count=len(courses),
                    courses=[safe_fields(course) for course in courses],
                )
                return courses

    def get_course(self, course_id: str) -> ClassroomCourse:
        log_debug(logger, "google.course.get.start", course_id=course_id)
        course = self.classroom.courses().get(id=course_id).execute()
        row = ClassroomCourse(
            id=course["id"],
            name=course.get("name", "Untitled course"),
            section=course.get("section"),
            course_state=course.get("courseState", "ACTIVE"),
        )
        log_event(logger, "google.course.get.complete", course=safe_fields(row))
        return row

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        log_debug(logger, "google.activities.start", course_id=course_id)
        activities: list[ClassroomActivity] = []
        page_token = None
        page = 0
        while True:
            page += 1
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
                        description=activity.get("description"),
                    )
                )
            log_debug(
                logger,
                "google.activities.page",
                course_id=course_id,
                page=page,
                page_count=len(response.get("courseWork", [])),
                next_page=bool(response.get("nextPageToken")),
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                log_event(
                    logger,
                    "google.activities.complete",
                    course_id=course_id,
                    count=len(activities),
                    activities=[safe_fields(activity) for activity in activities],
                )
                return activities

    def get_activity(self, course_id: str, activity_id: str) -> ClassroomActivity:
        log_debug(logger, "google.activity.get.start", course_id=course_id, activity_id=activity_id)
        activity = (
            self.classroom.courses()
            .courseWork()
            .get(courseId=course_id, id=activity_id)
            .execute()
        )
        row = ClassroomActivity(
            id=activity["id"],
            course_id=course_id,
            title=activity.get("title", "Untitled activity"),
            work_type=activity.get("workType", "ASSIGNMENT"),
            state=activity.get("state", "PUBLISHED"),
            due_label=_due_label(activity),
            description=activity.get("description"),
        )
        log_event(logger, "google.activity.get.complete", activity=safe_fields(row))
        return row

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        log_debug(logger, "google.submission_files.start", course_id=course_id, activity_ids=activity_ids)
        files: list[SubmissionFile] = []
        activities = activity_ids or [activity.id for activity in self.list_activities(course_id)]
        for activity_id in activities:
            page_token = None
            page = 0
            while True:
                page += 1
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
                log_debug(
                    logger,
                    "google.submission_files.page",
                    course_id=course_id,
                    activity_id=activity_id,
                    page=page,
                    submission_count=len(response.get("studentSubmissions", [])),
                    accumulated_file_count=len(files),
                    next_page=bool(response.get("nextPageToken")),
                )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        log_event(
            logger,
            "google.submission_files.complete",
            course_id=course_id,
            activity_ids=activities,
            file_count=len(files),
            files=[safe_fields(file) for file in files],
        )
        return files

    def list_submission_links(
        self, course_id: str, activity_id: str
    ) -> list[SubmissionLink]:
        log_debug(
            logger,
            "google.submission_links.start",
            course_id=course_id,
            activity_id=activity_id,
        )
        links: list[SubmissionLink] = []
        page_token = None
        page = 0
        while True:
            page += 1
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
                email, _ = self._student_identity(
                    course_id=course_id,
                    user_id=submission.get("userId", "me"),
                )
                links.extend(submission_links_from_submission(submission, email))
            log_debug(
                logger,
                "google.submission_links.page",
                course_id=course_id,
                activity_id=activity_id,
                page=page,
                submission_count=len(response.get("studentSubmissions", [])),
                accumulated_link_count=len(links),
                next_page=bool(response.get("nextPageToken")),
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        log_event(
            logger,
            "google.submission_links.complete",
            course_id=course_id,
            activity_id=activity_id,
            link_count=len(links),
            links=[safe_fields(link) for link in links],
        )
        return links

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        from googleapiclient.http import MediaIoBaseDownload

        log_event(logger, "google.drive.content.start", file_id=file_id)
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
        content = buffer.getvalue()
        log_event(
            logger,
            "google.drive.content.complete",
            file_id=file_id,
            metadata=metadata,
            media_type=media_type,
            byte_size=len(content),
            byte_preview=byte_preview(content),
        )
        return content, media_type

    def _profile(self, user_id: str) -> tuple[str | None, str | None]:
        settings = get_settings()
        cached = _PROFILE_CACHE.get(user_id)
        if _cache_hit(cached):
            profile = cached.value
            if isinstance(profile, tuple):
                log_cache_hit(logger, "google.profile", user_id)
                return profile
        log_cache_miss(logger, "google.profile", user_id)
        try:
            profile = self.classroom.userProfiles().get(userId=user_id).execute()
        except Exception:
            log_error(logger, "google.profile.failed", user_id=user_id)
            fallback = (None, user_id)
            _PROFILE_CACHE[user_id] = _TtlCacheEntry(
                fallback,
                _ttl(settings.google_profile_cache_ttl_minutes),
            )
            return fallback
        name = profile.get("name", {}).get("fullName")
        email = profile.get("emailAddress")
        _PROFILE_CACHE[user_id] = _TtlCacheEntry(
            (email, name),
            _ttl(settings.google_profile_cache_ttl_minutes),
        )
        log_event(logger, "google.profile.complete", user_id=user_id, email=email, name=name)
        return email, name

    def _student_identity(
        self, course_id: str, user_id: str
    ) -> tuple[str | None, str | None]:
        log_event(logger, "google.student_identity.profile", course_id=course_id, user_id=user_id)
        return self._profile(user_id)

    def _drive_metadata(self, file_id: str) -> dict:
        settings = get_settings()
        cached = _DRIVE_METADATA_CACHE.get(file_id)
        if _cache_hit(cached) and isinstance(cached.value, dict):
            log_cache_hit(logger, "google.drive.metadata", file_id)
            return cached.value
        log_cache_miss(logger, "google.drive.metadata", file_id)
        log_debug(logger, "google.drive.metadata.start", file_id=file_id)
        metadata = (
            self.drive.files()
            .get(fileId=file_id, fields="id,name,mimeType")
            .execute()
        )
        _DRIVE_METADATA_CACHE[file_id] = _TtlCacheEntry(
            metadata,
            _ttl(settings.google_drive_metadata_cache_ttl_minutes),
        )
        log_event(logger, "google.drive.metadata.complete", file_id=file_id, metadata=metadata)
        return metadata

    def _hydrate_drive_metadata(self, file: SubmissionFile) -> SubmissionFile:
        try:
            metadata = self._drive_metadata(file.source_file_id)
        except Exception:
            log_error(logger, "google.drive.metadata.failed", file=safe_fields(file))
            return file
        last_modifier = metadata.get("lastModifyingUser", {})
        hydrated = SubmissionFile(
            id=file.id,
            course_id=file.course_id,
            activity_id=file.activity_id,
            student_email=file.student_email or last_modifier.get("emailAddress"),
            student_name=file.student_name or last_modifier.get("displayName"),
            source_file_id=file.source_file_id,
            source_name=metadata.get("name") or file.source_name,
            mime_type=metadata.get("mimeType") or file.mime_type,
        )
        log_event(logger, "google.drive.metadata.hydrated", before=safe_fields(file), after=safe_fields(hydrated))
        return hydrated


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
        ClassroomActivity(
            "activity-2",
            "course-1",
            "Lab Notes: Osmosis",
            "ASSIGNMENT",
            "PUBLISHED",
            "May 28",
            description="Record your osmosis observations.",
        ),
        ClassroomActivity(
            "activity-3",
            "course-2",
            "Essay Draft",
            "ASSIGNMENT",
            "PUBLISHED",
            "May 30",
            description=(
                "Write a persuasive essay of at least three paragraphs. State a clear "
                "thesis in the introduction, then support your argument with at least "
                "two pieces of textual evidence and explain how each one backs your "
                "claim. Close with a conclusion that restates the argument and its "
                "significance. You will be assessed on the strength of your thesis, the "
                "quality and integration of evidence, the clarity of your reasoning, and "
                "the organization and mechanics of your writing."
            ),
        ),
        ClassroomActivity(
            "activity-4",
            "course-2",
            "Projeto Final (multi-arquivo)",
            "ASSIGNMENT",
            "PUBLISHED",
            "Jun 5",
            description="Envie as duas partes do projeto como anexos.",
        ),
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
        # One student (Júlia) submits two attachments under a single Classroom
        # submission — they must collapse into one card graded as a set.
        SubmissionFile(
            "sub-julia:drive-file-5",
            "course-2",
            "activity-4",
            "julia.rocha@example.edu",
            "Júlia Rocha",
            "drive-file-5",
            "parte-1.txt",
            "text/plain",
            b"Parte 1: introducao do projeto final de Julia.\n",
            classroom_submission_id="sub-julia",
        ),
        SubmissionFile(
            "sub-julia:drive-file-6",
            "course-2",
            "activity-4",
            "julia.rocha@example.edu",
            "Júlia Rocha",
            "drive-file-6",
            "parte-2.txt",
            "text/plain",
            b"Parte 2: conclusao do projeto final de Julia.\n",
            classroom_submission_id="sub-julia",
        ),
    ]

    def account_profile(self) -> AccountProfile:
        profile = AccountProfile(
            name="Teacher Example",
            email="teacher@example.edu",
            picture=None,
        )
        log_event(logger, "mock.account_profile", profile=safe_fields(profile))
        return profile

    def get_course(self, course_id: str) -> ClassroomCourse:
        for course in self.courses:
            if course.id == course_id:
                log_event(logger, "mock.course.get", course=safe_fields(course))
                return course
        raise KeyError(course_id)

    def list_courses(self) -> list[ClassroomCourse]:
        log_event(logger, "mock.courses", count=len(self.courses), courses=[safe_fields(course) for course in self.courses])
        return self.courses

    def get_activity(self, course_id: str, activity_id: str) -> ClassroomActivity:
        for activity in self.activities:
            if activity.course_id == course_id and activity.id == activity_id:
                log_event(logger, "mock.activity.get", activity=safe_fields(activity))
                return activity
        raise KeyError(activity_id)

    def list_activities(self, course_id: str) -> list[ClassroomActivity]:
        rows = [activity for activity in self.activities if activity.course_id == course_id]
        log_event(logger, "mock.activities", course_id=course_id, count=len(rows), activities=[safe_fields(row) for row in rows])
        return rows

    def list_submission_files(
        self, course_id: str, activity_ids: list[str] | None = None
    ) -> list[SubmissionFile]:
        activity_filter = set(activity_ids or [])
        rows = [
            file
            for file in self.files
            if file.course_id == course_id
            and (not activity_filter or file.activity_id in activity_filter)
        ]
        log_event(
            logger,
            "mock.submission_files",
            course_id=course_id,
            activity_ids=activity_ids,
            count=len(rows),
            files=[safe_fields(row) for row in rows],
        )
        return rows

    def list_submission_links(
        self, course_id: str, activity_id: str
    ) -> list[SubmissionLink]:
        links = [
            SubmissionLink(
                source_file_id=file.source_file_id,
                classroom_submission_id=file.id,
                alternate_link=(
                    f"https://classroom.google.com/c/{course_id}/sm/{file.id}/details"
                ),
                student_email=file.student_email,
            )
            for file in self.files
            if file.course_id == course_id and file.activity_id == activity_id
        ]
        log_event(
            logger,
            "mock.submission_links",
            course_id=course_id,
            activity_id=activity_id,
            count=len(links),
            links=[safe_fields(link) for link in links],
        )
        return links

    def get_file_content(self, file_id: str) -> tuple[bytes, str]:
        log_event(logger, "mock.file_content.start", file_id=file_id)
        for file in self.files:
            if file.id == file_id or file.source_file_id == file_id:
                export = GOOGLE_NATIVE_EXPORTS.get(file.mime_type)
                if export:
                    log_event(
                        logger,
                        "mock.file_content.complete",
                        file=safe_fields(file),
                        media_type=export[0],
                        byte_size=len(file.content),
                        byte_preview=byte_preview(file.content),
                    )
                    return file.content, export[0]
                log_event(
                    logger,
                    "mock.file_content.complete",
                    file=safe_fields(file),
                    media_type=file.mime_type,
                    byte_size=len(file.content),
                    byte_preview=byte_preview(file.content),
                )
                return file.content, file.mime_type
        log_warning(logger, "mock.file_content.missing", file_id=file_id)
        raise KeyError(file_id)


def get_google_provider() -> GoogleProvider:
    settings = get_settings()
    log_debug(logger, "google.provider.select", provider=settings.google_provider)
    if settings.google_provider == "google":
        token_store = TokenStore(settings.google_token_path)
        token_mtime = (
            token_store.token_path.stat().st_mtime
            if token_store.token_path.exists()
            else None
        )
        cached = _GOOGLE_PROVIDER_CACHE.get(settings.google_token_path)
        if cached and cached[1] == token_mtime:
            log_cache_hit(logger, "google.provider", settings.google_token_path)
            provider = cached[0]
            if isinstance(provider, GoogleProvider):
                return provider
        log_cache_miss(logger, "google.provider", settings.google_token_path)
        provider = GoogleApiProvider(token_store.load_valid_credentials())
        token_mtime = (
            token_store.token_path.stat().st_mtime
            if token_store.token_path.exists()
            else None
        )
        _GOOGLE_PROVIDER_CACHE[settings.google_token_path] = (provider, token_mtime)
        return provider
    return MockGoogleProvider()
