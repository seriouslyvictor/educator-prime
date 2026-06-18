from classroom_downloader.google_scopes import (
    CAPABILITY_SCOPES,
    CLASSROOM_READ_SCOPES,
    DRIVE_READ_SCOPES,
    IDENTITY_SCOPES,
    STUDENT_PROFILE_SCOPES,
    SUBMISSIONS_READ_SCOPES,
    has_capability,
    missing_scopes,
    normalize_scopes,
)


def test_scope_groups_match_google_capabilities() -> None:
    assert IDENTITY_SCOPES == frozenset({"openid", "email", "profile"})
    assert CLASSROOM_READ_SCOPES == frozenset({
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    })
    assert SUBMISSIONS_READ_SCOPES == frozenset({
        "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    })
    assert STUDENT_PROFILE_SCOPES == frozenset({
        "https://www.googleapis.com/auth/classroom.profile.emails",
        "https://www.googleapis.com/auth/classroom.profile.photos",
        "https://www.googleapis.com/auth/classroom.rosters.readonly",
    })
    assert DRIVE_READ_SCOPES == frozenset({
        "https://www.googleapis.com/auth/drive.readonly",
    })
    assert set(CAPABILITY_SCOPES) == {
        "identity",
        "classroom_read",
        "submissions_read",
        "student_profile_read",
        "drive_read",
    }


def test_normalize_scopes_drops_empty_values() -> None:
    assert normalize_scopes(["openid", "", "email", "openid"]) == {"openid", "email"}
    assert normalize_scopes(None) == set()


def test_capability_helpers_require_all_scopes() -> None:
    granted = {
        "openid",
        "email",
        "https://www.googleapis.com/auth/classroom.courses.readonly",
    }

    assert has_capability(granted, "identity") is False
    assert missing_scopes(granted, "identity") == ["profile"]
    assert has_capability(granted | {"profile"}, "identity") is True
    assert missing_scopes(granted, "classroom_read") == [
        "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    ]
