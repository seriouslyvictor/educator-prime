"""Real Google API provider implementation and provider factory."""
from io import BytesIO
from urllib.parse import urlencode

from ..observability import (
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
from ..settings import get_settings
from .cache import (
    _ACCOUNT_PROFILE_CACHE,
    _DRIVE_METADATA_CACHE,
    _GRADE_SUMMARY_CACHE,
    _PROFILE_CACHE,
    _TtlCacheEntry,
    _cache_hit,
    _ttl,
)
from .credentials import DbTokenStore, TokenStore, encrypt_credentials_json
from .mock_provider import MockGoogleProvider
from .types import (
    GOOGLE_NATIVE_EXPORTS,
    AccountProfile,
    ClassroomActivity,
    ClassroomCourse,
    GoogleProvider,
    SubmissionFile,
    SubmissionGradeSummary,
    SubmissionLink,
    _grade_summary_from_submissions,
    submission_has_classroom_grade,
)


logger = get_logger(__name__)


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


def _looks_like_user_id(value: str | None) -> bool:
    """A bare numeric Google account id leaking in as a display name (e.g. when a
    profile lookup failed). Never show these to the teacher."""
    return bool(value) and value.isdigit() and len(value) >= 10


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
        settings = get_settings()
        cached = _ACCOUNT_PROFILE_CACHE.get("me")
        if _cache_hit(cached):
            profile = cached.value
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
        _ACCOUNT_PROFILE_CACHE["me"] = _TtlCacheEntry(
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
            page = 0
            for response in self._student_submission_pages(course_id, activity_id):
                page += 1
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
        log_event(
            logger,
            "google.submission_files.complete",
            course_id=course_id,
            activity_ids=activities,
            file_count=len(files),
            files=[safe_fields(file) for file in files],
        )
        return files

    def _student_submission_pages(self, course_id: str, activity_id: str):
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
            yield response
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def submission_grade_summary(
        self, course_id: str, activity_ids: list[str]
    ) -> dict[str, SubmissionGradeSummary]:
        settings = get_settings()
        summaries: dict[str, SubmissionGradeSummary] = {}
        for activity_id in activity_ids:
            cache_key = f"{course_id}:{activity_id}"
            cached = _GRADE_SUMMARY_CACHE.get(cache_key)
            if _cache_hit(cached) and isinstance(cached.value, SubmissionGradeSummary):
                summaries[activity_id] = cached.value
                log_cache_hit(logger, "google.submission_grade_summary", cache_key)
                continue
            log_cache_miss(logger, "google.submission_grade_summary", cache_key)
            submissions: list[dict] = []
            for response in self._student_submission_pages(course_id, activity_id):
                submissions.extend(response.get("studentSubmissions", []))
            summary = _grade_summary_from_submissions(submissions)
            _GRADE_SUMMARY_CACHE[cache_key] = _TtlCacheEntry(
                summary,
                _ttl(settings.google_profile_cache_ttl_minutes),
            )
            summaries[activity_id] = summary
        return summaries

    def ungraded_submission_ids(self, course_id: str, activity_id: str) -> set[str]:
        ids: set[str] = set()
        for response in self._student_submission_pages(course_id, activity_id):
            for submission in response.get("studentSubmissions", []):
                if not submission_has_classroom_grade(submission):
                    submission_id = submission.get("id")
                    if submission_id:
                        ids.add(submission_id)
        return ids

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
        page = 0
        for response in self._student_submission_pages(course_id, activity_id):
            page += 1
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
            request = self.drive.files().get_media(fileId=file_id, supportsAllDrives=True)
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
            # No readable profile (stale roster/profile scopes or a restricted user).
            # Return no name so callers fall back to the Drive display name, then to a
            # friendly placeholder — never the raw numeric Google user id.
            log_error(logger, "google.profile.failed", user_id=user_id)
            fallback = (None, None)
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
            # supportsAllDrives so files stored in a Shared/Team Drive resolve
            # instead of 404ing (Drive v3 defaults the flag to false).
            .get(fileId=file_id, fields="id,name,mimeType", supportsAllDrives=True)
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
        student_name = file.student_name or last_modifier.get("displayName")
        if _looks_like_user_id(student_name):
            student_name = None
        hydrated = SubmissionFile(
            id=file.id,
            course_id=file.course_id,
            activity_id=file.activity_id,
            student_email=file.student_email or last_modifier.get("emailAddress"),
            student_name=student_name,
            source_file_id=file.source_file_id,
            source_name=metadata.get("name") or file.source_name,
            mime_type=metadata.get("mimeType") or file.mime_type,
            classroom_submission_id=file.classroom_submission_id,
        )
        log_event(logger, "google.drive.metadata.hydrated", before=safe_fields(file), after=safe_fields(hydrated))
        return hydrated


def make_google_provider(session_id: str | None, db) -> GoogleProvider:
    settings = get_settings()
    log_debug(logger, "google.provider.select", provider=settings.google_provider)
    if settings.google_provider == "google":
        store = DbTokenStore(session_id, db)
        return GoogleApiProvider(store.load_valid_credentials())
    return MockGoogleProvider()


def get_google_provider() -> GoogleProvider:
    """Legacy single-user helper. Use make_google_provider() for multi-user flows."""
    settings = get_settings()
    if settings.google_provider == "google":
        token_store = TokenStore(settings.google_token_path)
        return GoogleApiProvider(token_store.load_valid_credentials())
    return MockGoogleProvider()
