"""Compatibility facade — implementation now lives under classroom_downloader.google.

All symbols previously defined here are re-exported so that existing imports
of the form ``from classroom_downloader.google_provider import X`` continue to
work without modification.
"""

# ruff: noqa: F401  (re-exports are intentional)

from .google.cache import clear_google_provider_caches
from .google.credentials import (
    DbTokenStore,
    TokenStore,
    decrypt_credentials_json,
    encrypt_credentials_json,
)
from .google.fixtures import (
    MOCK_DOCX_BYTES,
    MOCK_PDF_BYTES,
    MOCK_PNG_BYTES,
    MOCK_PPTX_BYTES,
    MOCK_XLSX_BYTES,
)
from .google.mock_provider import MockGoogleProvider
from .google.real_provider import (
    GoogleApiProvider,
    _looks_like_user_id,
    build_oauth_authorization_url,
    drive_files_from_submission,
    get_google_provider,
    make_google_provider,
    submission_links_from_submission,
)
from .google.types import (
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
