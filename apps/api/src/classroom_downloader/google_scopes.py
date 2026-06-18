IDENTITY_SCOPES = frozenset({"openid", "email", "profile"})
CLASSROOM_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
})
SUBMISSIONS_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
})
STUDENT_PROFILE_SCOPES = frozenset({
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/classroom.profile.photos",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
})
DRIVE_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/drive.readonly",
})

CAPABILITY_SCOPES = {
    "identity": IDENTITY_SCOPES,
    "classroom_read": CLASSROOM_READ_SCOPES,
    "submissions_read": SUBMISSIONS_READ_SCOPES,
    "student_profile_read": STUDENT_PROFILE_SCOPES,
    "drive_read": DRIVE_READ_SCOPES,
}


def normalize_scopes(scopes: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    return {scope for scope in (scopes or []) if scope}


def has_capability(granted_scopes: set[str], capability: str) -> bool:
    required = CAPABILITY_SCOPES[capability]
    return required.issubset(granted_scopes)


def missing_scopes(granted_scopes: set[str], capability: str) -> list[str]:
    return sorted(CAPABILITY_SCOPES[capability] - granted_scopes)
