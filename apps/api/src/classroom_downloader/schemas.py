from pydantic import BaseModel

from .models import ExportStatus, GradingStatus


class CourseRead(BaseModel):
    id: str
    name: str
    section: str | None = None
    course_state: str


class ActivityRead(BaseModel):
    id: str
    course_id: str
    title: str
    work_type: str
    state: str
    due_label: str | None = None
    description: str | None = None


class ExportCreate(BaseModel):
    course_id: str
    activity_ids: list[str] | None = None


class ExportFileRead(BaseModel):
    id: str
    activity_id: str
    activity_name: str
    student_email: str | None
    student_name: str | None
    source_name: str
    mime_type: str
    export_mime_type: str | None
    output_path: str
    status: str
    error: str | None = None


class ExportErrorRead(BaseModel):
    id: str
    message: str
    file_id: str | None = None


class ExportJobRead(BaseModel):
    id: str
    course_id: str
    course_name: str
    status: ExportStatus
    total_files: int
    completed_files: int
    files: list[ExportFileRead] = []
    errors: list[ExportErrorRead] = []


class AuthState(BaseModel):
    signed_in: bool
    identity_scopes: bool
    classroom_scopes: bool
    drive_scopes: bool
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    provider: str


class AuthStart(BaseModel):
    authorization_url: str | None = None
    mock_connected: bool = False
    scopes: list[str]


class GradingHealthRead(BaseModel):
    engine: str
    ready: bool
    status: str
    model: str | None = None
    provider: str | None = None
    missing_keys: list[str] = []
    detail: str
    probed: bool = False
    probe_ok: bool | None = None


class GradingQueueItem(BaseModel):
    course_id: str
    course_name: str
    activity_id: str
    activity_title: str
    due_label: str | None = None
    submission_count: int
    status: str
    latest_job_id: str | None = None
    reviewed_submissions: int = 0
    total_submissions: int = 0


class GradingCriterionInput(BaseModel):
    name: str
    weight: int
    description: str | None = None


class GradingJobCreate(BaseModel):
    course_id: str
    activity_id: str
    rubric_mode: str
    teacher_loop: str = "approve"
    rubric_text: str | None = None
    criteria: list[GradingCriterionInput] | None = None


class GradingReviewUpdate(BaseModel):
    final_score: float
    feedback: str | None = None
    reviewed: bool = True


class GradingPostedUpdate(BaseModel):
    posted: bool


class GradingCriterionRead(BaseModel):
    id: str
    name: str
    weight: int
    description: str | None = None
    latest_ai_note: str | None = None


class GradingSubmissionRead(BaseModel):
    id: str
    student_email: str | None = None
    student_name: str | None = None
    source_file_id: str
    source_name: str
    mime_type: str
    ai_score: float | None = None
    confidence: float | None = None
    final_score: float | None = None
    feedback: str | None = None
    reviewed: bool
    flag: str | None = None
    error: str | None = None
    classroom_submission_id: str | None = None
    alternate_link: str | None = None
    posted_to_classroom: bool = False
    posted_at: str | None = None
    privacy_status: str | None = None
    extraction_status: str | None = None
    ai_attempt_status: str | None = None
    ai_engine: str | None = None
    ai_model: str | None = None
    ai_safe_error: str | None = None
    ai_flags: list[str] = []
    privacy_flags: list[str] = []
    ai_prompt_tokens: int | None = None
    ai_completion_tokens: int | None = None
    ai_token_count: int | None = None
    ai_cached_prompt_tokens: int | None = None
    ai_cache_write_tokens: int | None = None
    ai_cost_cents: float | None = None
    ai_latency_ms: int | None = None


class GradingFileCacheRead(BaseModel):
    id: str
    submission_id: str
    source_file_id: str
    source_name: str
    mime_type: str
    content_hash: str
    byte_size: int
    expires_at: str
    deleted_at: str | None = None


class PrivacyAuditRowRead(BaseModel):
    id: str
    submission_id: str
    student_label: str
    redacted_source_name: str
    mime_type: str
    byte_size: int
    extraction_status: str
    extraction_error: str | None = None
    privacy_status: str
    privacy_flags: list[str] = []
    redaction_counts: dict[str, int] = {}
    remaining_direct_identifier_hits: list[str] = []
    audit_pass: bool
    blocked_reason: str | None = None


class PrivacyAuditRead(BaseModel):
    id: str
    job_id: str
    status: str
    total_files: int
    passed_files: int
    redacted_files: int
    blocked_files: int
    high_risk_files: int
    created_at: str
    updated_at: str
    rows: list[PrivacyAuditRowRead] = []


class GradingJobRead(BaseModel):
    id: str
    course_id: str
    course_name: str
    activity_id: str
    activity_title: str
    rubric_mode: str
    teacher_loop: str
    rubric_text: str | None = None
    batch_mode: str = "per_submission"
    status: GradingStatus
    total_submissions: int
    reviewed_submissions: int
    flagged_submissions: int
    total_prompt_tokens: int | None = None
    total_completion_tokens: int | None = None
    total_cached_tokens: int | None = None
    total_cost_cents: float | None = None
    wall_clock_ms: int | None = None
    submissions_graded: int = 0
    ai_engine: str | None = None
    ai_mode: str | None = None
    ai_model: str | None = None
    cache_expires_at: str | None = None
    criteria: list[GradingCriterionRead] = []
    submissions: list[GradingSubmissionRead] = []
    cache_files: list[GradingFileCacheRead] = []
