import os

os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CD_GOOGLE_PROVIDER", "mock")

from classroom_downloader.google_provider import (
    _looks_like_user_id,
    drive_files_from_submission,
)
from classroom_downloader.grading import group_key_for


def test_looks_like_user_id_only_flags_bare_numeric_ids() -> None:
    assert _looks_like_user_id("113949117621079100094") is True
    assert _looks_like_user_id("Ana Silva") is False
    assert _looks_like_user_id(None) is False
    assert _looks_like_user_id("") is False
    assert _looks_like_user_id("12345") is False  # too short to be an account id


def test_drive_files_carry_classroom_submission_id_for_grouping() -> None:
    submission = {
        "id": "sub-1",
        "courseWorkId": "cw-1",
        "assignmentSubmission": {
            "attachments": [
                {"driveFile": {"id": "f1", "title": "parte-1.pdf", "mimeType": "application/pdf"}},
                {"driveFile": {"id": "f2", "title": "parte-2.pdf", "mimeType": "application/pdf"}},
            ]
        },
    }
    files = drive_files_from_submission("course-1", submission, "ana@example.edu", "Ana Silva")

    assert [file.source_file_id for file in files] == ["f1", "f2"]
    assert all(file.classroom_submission_id == "sub-1" for file in files)
    # Both attachments collapse into one group.
    assert group_key_for(files[0]) == group_key_for(files[1]) == "sub-1"
