from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ExportStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


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
