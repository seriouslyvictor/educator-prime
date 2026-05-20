from pydantic import BaseModel

from .models import ExportStatus


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
    provider: str


class AuthStart(BaseModel):
    authorization_url: str | None = None
    mock_connected: bool = False
    scopes: list[str]
