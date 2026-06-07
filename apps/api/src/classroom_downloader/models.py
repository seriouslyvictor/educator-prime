from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ExportStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class GradingStatus(StrEnum):
    ready = "ready"
    drafting = "drafting"
    reviewing = "reviewing"
    completed = "completed"


class Course(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    section: str | None = None
    course_state: str = "ACTIVE"
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Activity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    course_id: str = Field(index=True)
    title: str
    work_type: str = "ASSIGNMENT"
    state: str = "PUBLISHED"
    due_label: str | None = None
    description: str | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExportJob(SQLModel, table=True):
    id: str = Field(primary_key=True)
    course_id: str = Field(index=True)
    course_name: str
    status: ExportStatus = Field(default=ExportStatus.queued)
    total_files: int = 0
    completed_files: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExportFile(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    course_id: str
    activity_id: str
    activity_name: str
    student_email: str | None = None
    student_name: str | None = None
    source_file_id: str
    source_name: str
    mime_type: str
    export_mime_type: str | None = None
    output_path: str
    status: str = "ready"
    error: str | None = None
    cached_path: str | None = None
    content_hash: str | None = None
    byte_size: int | None = None
    cache_expires_at: datetime | None = None


class ExportError(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    message: str
    file_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingJob(SQLModel, table=True):
    id: str = Field(primary_key=True)
    course_id: str = Field(index=True)
    course_name: str
    activity_id: str = Field(index=True)
    activity_title: str
    activity_description: str | None = None
    rubric_mode: str
    teacher_loop: str
    rubric_text: str | None = None
    batch_mode: str = "per_submission"
    status: GradingStatus = Field(default=GradingStatus.ready)
    total_submissions: int = 0
    reviewed_submissions: int = 0
    flagged_submissions: int = 0
    total_prompt_tokens: int | None = None
    total_completion_tokens: int | None = None
    total_cached_tokens: int | None = None
    total_cost_cents: float | None = None
    wall_clock_ms: int | None = None
    submissions_graded: int = 0
    ai_engine: str | None = None
    ai_mode: str | None = None
    ai_model: str | None = None
    cache_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingCriterion(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    name: str
    weight: int
    description: str | None = None
    latest_ai_note: str | None = None


class GradingSubmission(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    student_email: str | None = None
    student_name: str | None = None
    source_file_id: str
    source_name: str
    mime_type: str
    ai_score: float | None = None
    confidence: float | None = None
    final_score: float | None = None
    feedback: str | None = None
    reviewed: bool = False
    flag: str | None = None
    error: str | None = None
    classroom_submission_id: str | None = None
    alternate_link: str | None = None
    posted_to_classroom: bool = False
    posted_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingFileCache(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    submission_id: str = Field(index=True)
    source_file_id: str
    source_name: str
    mime_type: str
    cached_path: str
    content_hash: str
    byte_size: int
    expires_at: datetime
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingPseudonym(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    submission_id: str = Field(index=True)
    student_label: str
    source_label: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingAiAttempt(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    submission_id: str = Field(index=True)
    engine: str
    model: str | None = None
    status: str
    extraction_status: str
    privacy_status: str
    safe_error: str | None = None
    flags_json: str = "[]"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    token_count: int | None = None
    cached_prompt_tokens: int | None = None
    cache_write_tokens: int | None = None
    cost_cents: float | None = None
    latency_ms: int | None = None
    retry_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingScrubCache(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    submission_id: str = Field(index=True)
    content_hash: str = Field(index=True)
    identity_hash: str = Field(index=True)
    student_label: str
    source_label: str
    safe_source_label: str
    scrubbed_content: str
    extraction_status: str
    extraction_error: str | None = None
    privacy_status: str
    privacy_flags_json: str = "[]"
    redaction_counts_json: str = "{}"
    byte_size: int
    expires_at: datetime
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PrivacyAudit(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    status: str = "running"
    total_files: int = 0
    passed_files: int = 0
    redacted_files: int = 0
    blocked_files: int = 0
    high_risk_files: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PrivacyAuditRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    audit_id: str = Field(index=True)
    job_id: str = Field(index=True)
    submission_id: str = Field(index=True)
    student_label: str
    redacted_source_name: str
    mime_type: str
    byte_size: int
    extraction_status: str
    extraction_error: str | None = None
    privacy_status: str
    privacy_flags_json: str = "[]"
    redaction_counts_json: str = "{}"
    remaining_direct_identifier_hits_json: str = "[]"
    audit_pass: bool = False
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
