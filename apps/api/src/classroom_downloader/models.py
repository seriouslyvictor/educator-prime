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
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Activity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    course_id: str = Field(index=True)
    title: str
    work_type: str = "ASSIGNMENT"
    state: str = "PUBLISHED"
    due_label: str | None = None
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
    rubric_mode: str
    teacher_loop: str
    status: GradingStatus = Field(default=GradingStatus.ready)
    total_submissions: int = 0
    reviewed_submissions: int = 0
    flagged_submissions: int = 0
    cache_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GradingCriterion(SQLModel, table=True):
    id: str = Field(primary_key=True)
    job_id: str = Field(index=True)
    name: str
    weight: int
    description: str | None = None


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
