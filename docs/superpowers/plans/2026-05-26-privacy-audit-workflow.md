# Privacy Audit Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable in-app privacy audit checkpoint for Classroom grading jobs before AI drafting.

**Architecture:** Add a backend `privacy_audit` service that reuses the existing grading cache, extraction, pseudonymization, and scrubber pipeline, then exposes safe audit report/read/export endpoints. Update the grader setup flow so teachers run and inspect a privacy audit before drafting, while `draft` auto-runs or enforces the latest audit as a server-side safety gate.

**Tech Stack:** FastAPI, SQLModel, Pydantic, pytest, React, TypeScript, Vite, existing shadcn-like local UI primitives.

---

## File Structure

- Create `apps/api/src/classroom_downloader/privacy_audit.py`: audit service, safe row building, safe CSV/JSON export helpers.
- Modify `apps/api/src/classroom_downloader/models.py`: add `PrivacyAudit` and `PrivacyAuditRow`.
- Modify `apps/api/src/classroom_downloader/schemas.py`: add `PrivacyAuditRead` and `PrivacyAuditRowRead`.
- Modify `apps/api/src/classroom_downloader/main.py`: add audit endpoints and enforce audit before draft.
- Modify `apps/api/src/classroom_downloader/grading.py`: allow drafting to skip blocked submissions cleanly and reuse latest audit metadata.
- Modify `apps/api/tests/test_grading.py`: backend TDD coverage for audit report, exports, and draft gate.
- Modify `apps/web/src/types.ts`: add audit response types and `"graderAudit"` app view.
- Modify `apps/web/src/lib/api.ts`: add audit API methods/export URLs.
- Modify `apps/web/src/App.tsx`: create audit state and route setup to audit to draft.
- Modify `apps/web/src/components/Grader.tsx`: add `GraderAudit` screen and change setup CTA to "Run privacy audit".
- Modify `apps/web/src/styles.css`: add audit report styles.

## Task 1: Backend Audit Models and Schemas

**Files:**
- Modify: `apps/api/src/classroom_downloader/models.py`
- Modify: `apps/api/src/classroom_downloader/schemas.py`
- Test: `apps/api/tests/test_grading.py`

- [ ] **Step 1: Write failing model/API shape test**

Add this import to `apps/api/tests/test_grading.py`:

```python
from classroom_downloader.models import PrivacyAudit, PrivacyAuditRow
```

Add this test:

```python
def test_privacy_audit_endpoint_returns_safe_report_shape(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        response = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job["id"]
    assert body["total_files"] == 2
    assert body["passed_files"] + body["blocked_files"] == 2
    assert "rows" in body
    assert len(body["rows"]) == 2
    assert all(row["student_label"].startswith("student_") for row in body["rows"])
    assert all("@" not in row["student_label"] for row in body["rows"])
    assert all("student_email" not in row for row in body["rows"])
    assert all("student_name" not in row for row in body["rows"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_grading.py::test_privacy_audit_endpoint_returns_safe_report_shape -q
```

Expected: FAIL with import error for `PrivacyAudit` or 404 for `/privacy-audit`.

- [ ] **Step 3: Add SQLModel tables**

In `apps/api/src/classroom_downloader/models.py`, add:

```python
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
    remaining_direct_identifier_hits_json: str = "[]"
    audit_pass: bool = False
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Add Pydantic schemas**

In `apps/api/src/classroom_downloader/schemas.py`, add:

```python
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
```

- [ ] **Step 5: Run test and keep expected failure**

Run:

```powershell
uv run pytest tests/test_grading.py::test_privacy_audit_endpoint_returns_safe_report_shape -q
```

Expected: FAIL with 404 for missing endpoint.

## Task 2: Privacy Audit Service and Endpoint

**Files:**
- Create: `apps/api/src/classroom_downloader/privacy_audit.py`
- Modify: `apps/api/src/classroom_downloader/main.py`
- Test: `apps/api/tests/test_grading.py`

- [ ] **Step 1: Implement audit service**

Create `apps/api/src/classroom_downloader/privacy_audit.py` with:

```python
from datetime import UTC, datetime
import csv
import json
from io import StringIO
from pathlib import Path
import re
from uuid import uuid4

from sqlmodel import Session, select

from .content_extraction import extract_submission_content
from .google_provider import GoogleProvider
from .grading import cache_submission_file
from .models import GradingJob, GradingSubmission, PrivacyAudit, PrivacyAuditRow
from .privacy import EMAIL_PATTERN, ID_PATTERN, PHONE_PATTERN, URL_PATTERN, pseudonym_for_submission, scrub_submission
from .schemas import PrivacyAuditRead, PrivacyAuditRowRead


DIRECT_PATTERNS = {
    "email": EMAIL_PATTERN,
    "phone": PHONE_PATTERN,
    "url": URL_PATTERN,
    "student_id": ID_PATTERN,
}
EMAIL_IN_NAME = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s-]+", re.IGNORECASE)


def run_privacy_audit(session: Session, job: GradingJob, provider: GoogleProvider) -> PrivacyAudit:
    audit = PrivacyAudit(
        id=str(uuid4()),
        job_id=job.id,
        status="running",
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)

    files = provider.list_submission_files(job.course_id, [job.activity_id])
    for file in files:
        submission = _submission_for_audit(session, job, file)
        cache_file = cache_submission_file(session, job, submission, file, provider)
        extracted = extract_submission_content(cache_file)
        scrubbed = scrub_submission(session, job, submission, extracted)
        remaining_hits = _direct_hits(scrubbed.content)
        blocked = extracted.status in {"unsupported", "failed"}
        high_risk = scrubbed.report.status == "high_reidentification_risk"
        audit_pass = bool(blocked or (not remaining_hits and not high_risk))
        blocked_reason = extracted.error if blocked else "high_reidentification_risk" if high_risk else None
        row = PrivacyAuditRow(
            id=str(uuid4()),
            audit_id=audit.id,
            job_id=job.id,
            submission_id=submission.id,
            student_label=scrubbed.student_label,
            redacted_source_name=redact_source_name(file.source_name),
            mime_type=cache_file.mime_type,
            byte_size=cache_file.byte_size,
            extraction_status=extracted.status,
            extraction_error=extracted.error,
            privacy_status=scrubbed.report.status,
            privacy_flags_json=json.dumps(scrubbed.report.flags),
            remaining_direct_identifier_hits_json=json.dumps(remaining_hits),
            audit_pass=audit_pass,
            blocked_reason=blocked_reason,
        )
        session.add(row)

    session.commit()
    _refresh_audit_counts(session, audit)
    return audit


def latest_privacy_audit(session: Session, job_id: str) -> PrivacyAudit | None:
    return session.exec(
        select(PrivacyAudit)
        .where(PrivacyAudit.job_id == job_id)
        .order_by(PrivacyAudit.created_at.desc())
    ).first()


def privacy_audit_snapshot(session: Session, audit: PrivacyAudit) -> PrivacyAuditRead:
    rows = session.exec(
        select(PrivacyAuditRow)
        .where(PrivacyAuditRow.audit_id == audit.id)
        .order_by(PrivacyAuditRow.created_at)
    ).all()
    return PrivacyAuditRead(
        id=audit.id,
        job_id=audit.job_id,
        status=audit.status,
        total_files=audit.total_files,
        passed_files=audit.passed_files,
        redacted_files=audit.redacted_files,
        blocked_files=audit.blocked_files,
        high_risk_files=audit.high_risk_files,
        created_at=audit.created_at.isoformat(),
        updated_at=audit.updated_at.isoformat(),
        rows=[
            PrivacyAuditRowRead(
                id=row.id,
                submission_id=row.submission_id,
                student_label=row.student_label,
                redacted_source_name=row.redacted_source_name,
                mime_type=row.mime_type,
                byte_size=row.byte_size,
                extraction_status=row.extraction_status,
                extraction_error=row.extraction_error,
                privacy_status=row.privacy_status,
                privacy_flags=json.loads(row.privacy_flags_json),
                remaining_direct_identifier_hits=json.loads(row.remaining_direct_identifier_hits_json),
                audit_pass=row.audit_pass,
                blocked_reason=row.blocked_reason,
            )
            for row in rows
        ],
    )


def privacy_audit_csv(session: Session, audit: PrivacyAudit) -> str:
    snapshot = privacy_audit_snapshot(session, audit)
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "student_label",
            "redacted_source_name",
            "mime_type",
            "byte_size",
            "extraction_status",
            "extraction_error",
            "privacy_status",
            "privacy_flags",
            "remaining_direct_identifier_hits",
            "audit_pass",
            "blocked_reason",
        ],
    )
    writer.writeheader()
    for row in snapshot.rows:
        writer.writerow(
            {
                "student_label": row.student_label,
                "redacted_source_name": row.redacted_source_name,
                "mime_type": row.mime_type,
                "byte_size": row.byte_size,
                "extraction_status": row.extraction_status,
                "extraction_error": row.extraction_error or "",
                "privacy_status": row.privacy_status,
                "privacy_flags": ",".join(row.privacy_flags),
                "remaining_direct_identifier_hits": ",".join(row.remaining_direct_identifier_hits),
                "audit_pass": row.audit_pass,
                "blocked_reason": row.blocked_reason or "",
            }
        )
    return buffer.getvalue()


def redact_source_name(source_name: str) -> str:
    return EMAIL_IN_NAME.sub("[email]", Path(source_name).name)


def _submission_for_audit(session: Session, job: GradingJob, file) -> GradingSubmission:
    existing = session.exec(
        select(GradingSubmission)
        .where(GradingSubmission.job_id == job.id)
        .where(GradingSubmission.source_file_id == file.source_file_id)
    ).first()
    if existing:
        return existing
    row = GradingSubmission(
        id=str(uuid4()),
        job_id=job.id,
        student_email=file.student_email,
        student_name=file.student_name,
        source_file_id=file.source_file_id,
        source_name=file.source_name,
        mime_type=file.mime_type,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    pseudonym_for_submission(session, job, row)
    return row


def _refresh_audit_counts(session: Session, audit: PrivacyAudit) -> None:
    rows = session.exec(select(PrivacyAuditRow).where(PrivacyAuditRow.audit_id == audit.id)).all()
    audit.total_files = len(rows)
    audit.passed_files = sum(1 for row in rows if row.audit_pass)
    audit.redacted_files = sum(1 for row in rows if row.privacy_status == "redacted")
    audit.blocked_files = sum(1 for row in rows if row.blocked_reason)
    audit.high_risk_files = sum(1 for row in rows if row.privacy_status == "high_reidentification_risk")
    audit.status = "completed_with_blocks" if audit.blocked_files or audit.high_risk_files else "completed"
    audit.updated_at = datetime.now(UTC)
    session.add(audit)
    session.commit()
    session.refresh(audit)


def _direct_hits(text: str) -> list[str]:
    return sorted(name for name, pattern in DIRECT_PATTERNS.items() if pattern.search(text))
```

- [ ] **Step 2: Add endpoint imports**

In `apps/api/src/classroom_downloader/main.py`, import:

```python
from .privacy_audit import (
    latest_privacy_audit,
    privacy_audit_csv,
    privacy_audit_snapshot,
    run_privacy_audit,
)
```

Also import schema:

```python
PrivacyAuditRead,
```

- [ ] **Step 3: Add audit endpoints**

In `apps/api/src/classroom_downloader/main.py`, add after `read_grading_job`:

```python
@app.post("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
def run_grading_privacy_audit(
    job_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
) -> PrivacyAuditRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    audit = run_privacy_audit(session, job, provider)
    return privacy_audit_snapshot(session, audit)


@app.get("/api/grading/jobs/{job_id}/privacy-audit", response_model=PrivacyAuditRead)
def read_grading_privacy_audit(
    job_id: str,
    session: Session = Depends(get_session),
) -> PrivacyAuditRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    return privacy_audit_snapshot(session, audit)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
uv run pytest tests/test_grading.py::test_privacy_audit_endpoint_returns_safe_report_shape -q
```

Expected: PASS.

## Task 3: Safe Audit Exports

**Files:**
- Modify: `apps/api/src/classroom_downloader/main.py`
- Modify: `apps/api/tests/test_grading.py`

- [ ] **Step 1: Write failing export test**

Add:

```python
def test_privacy_audit_exports_safe_csv_and_json(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        audit = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit").json()
        csv_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit/export.csv")
        json_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit/export.json")

    assert csv_response.status_code == 200
    assert json_response.status_code == 200
    assert "ana.silva@example.edu" not in csv_response.text
    assert "Bruno Costa" not in csv_response.text
    assert "[email]" in csv_response.text or "diagram.png" in csv_response.text
    exported = json_response.json()
    assert exported["id"] == audit["id"]
    assert "ana.silva@example.edu" not in json_response.text
    assert all("student_email" not in row for row in exported["rows"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_grading.py::test_privacy_audit_exports_safe_csv_and_json -q
```

Expected: FAIL with 404 for export endpoints.

- [ ] **Step 3: Add export endpoints**

In `apps/api/src/classroom_downloader/main.py`, add:

```python
@app.get("/api/grading/jobs/{job_id}/privacy-audit/export.csv")
def export_privacy_audit_csv(
    job_id: str,
    session: Session = Depends(get_session),
) -> Response:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    safe_name = "".join(char if char.isalnum() else "-" for char in job.activity_title)
    return Response(
        content=privacy_audit_csv(session, audit),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}-privacy-audit.csv"'
        },
    )


@app.get("/api/grading/jobs/{job_id}/privacy-audit/export.json", response_model=PrivacyAuditRead)
def export_privacy_audit_json(
    job_id: str,
    session: Session = Depends(get_session),
) -> PrivacyAuditRead:
    job = session.get(GradingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Grading job not found.")
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Privacy audit not found.")
    return privacy_audit_snapshot(session, audit)
```

- [ ] **Step 4: Run export test**

Run:

```powershell
uv run pytest tests/test_grading.py::test_privacy_audit_exports_safe_csv_and_json -q
```

Expected: PASS.

## Task 4: Enforce Audit Gate Before Drafting

**Files:**
- Modify: `apps/api/src/classroom_downloader/main.py`
- Modify: `apps/api/src/classroom_downloader/grading.py`
- Modify: `apps/api/tests/test_grading.py`

- [ ] **Step 1: Write failing auto-audit draft test**

Add:

```python
def test_draft_auto_runs_privacy_audit_when_missing(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        audit_response = client.get(f"/api/grading/jobs/{job['id']}/privacy-audit")

    assert drafted["total_submissions"] == 2
    assert audit_response.status_code == 200
    assert audit_response.json()["total_files"] == 2
```

- [ ] **Step 2: Write failing high-risk gate test**

Add a focused unit-style test by inserting a fake audit row:

```python
def test_draft_blocks_when_latest_audit_has_high_risk_rows(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        audit = client.post(f"/api/grading/jobs/{job['id']}/privacy-audit").json()

        with Session(engine) as session:
            row = session.get(PrivacyAuditRow, audit["rows"][0]["id"])
            assert row is not None
            row.privacy_status = "high_reidentification_risk"
            row.blocked_reason = "high_reidentification_risk"
            session.add(row)
            report = session.get(PrivacyAudit, audit["id"])
            assert report is not None
            report.high_risk_files = 1
            report.blocked_files = max(report.blocked_files, 1)
            session.add(report)
            session.commit()

        response = client.post(f"/api/grading/jobs/{job['id']}/draft")

    assert response.status_code == 409
    assert "Privacy audit" in response.json()["detail"]
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_grading.py::test_draft_auto_runs_privacy_audit_when_missing tests/test_grading.py::test_draft_blocks_when_latest_audit_has_high_risk_rows -q
```

Expected: first may fail because audit is missing after draft, second fails because draft ignores high-risk audit.

- [ ] **Step 4: Add audit gate helper**

In `apps/api/src/classroom_downloader/main.py`, add:

```python
def ensure_privacy_audit_allows_draft(
    job: GradingJob,
    session: Session,
    provider: GoogleProvider,
):
    audit = latest_privacy_audit(session, job.id)
    if audit is None:
        audit = run_privacy_audit(session, job, provider)
    if audit.high_risk_files > 0:
        raise HTTPException(
            status_code=409,
            detail="Privacy audit found high-risk rows. Review the audit before drafting.",
        )
    return audit
```

In `draft_job`, call it before `draft_grading_job`:

```python
ensure_privacy_audit_allows_draft(job, session, provider)
job = draft_grading_job(session, job, provider)
```

- [ ] **Step 5: Make blocked submissions stay manual-review**

In `apps/api/src/classroom_downloader/grading.py`, keep existing `_draft_submission` behavior for unsupported rows: it records `blocked`, leaves `ai_score` as `None`, and sets safe error. Confirm no code path sends unsupported rows to `GradingEngine`.

- [ ] **Step 6: Run audit gate tests**

Run:

```powershell
uv run pytest tests/test_grading.py::test_draft_auto_runs_privacy_audit_when_missing tests/test_grading.py::test_draft_blocks_when_latest_audit_has_high_risk_rows -q
```

Expected: PASS.

## Task 5: Frontend Types and API Methods

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Add frontend types**

In `apps/web/src/types.ts`, add:

```ts
export interface PrivacyAuditRow {
  id: string;
  submission_id: string;
  student_label: string;
  redacted_source_name: string;
  mime_type: string;
  byte_size: number;
  extraction_status: string;
  extraction_error: string | null;
  privacy_status: string;
  privacy_flags: string[];
  remaining_direct_identifier_hits: string[];
  audit_pass: boolean;
  blocked_reason: string | null;
}

export interface PrivacyAudit {
  id: string;
  job_id: string;
  status: string;
  total_files: number;
  passed_files: number;
  redacted_files: number;
  blocked_files: number;
  high_risk_files: number;
  created_at: string;
  updated_at: string;
  rows: PrivacyAuditRow[];
}
```

Add `"graderAudit"` to `AppView`.

- [ ] **Step 2: Add API helpers**

In `apps/web/src/lib/api.ts`, import `PrivacyAudit` and add:

```ts
  runPrivacyAudit: (jobId: string) =>
    request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`, {
      method: "POST",
    }),
  privacyAudit: (jobId: string) =>
    request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`),
  privacyAuditCsvUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/export.csv`,
  privacyAuditJsonUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/export.json`,
```

- [ ] **Step 3: Run TypeScript build and expect component errors**

Run:

```powershell
pnpm run build
```

Expected: FAIL only if `"graderAudit"` is not handled or imports are incomplete. If it passes here, continue.

## Task 6: Audit Screen Component

**Files:**
- Modify: `apps/web/src/components/Grader.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add component export**

In `apps/web/src/components/Grader.tsx`, import `PrivacyAudit` and add:

```tsx
export function GraderAudit({
  audit,
  busy,
  onBack,
  onRerun,
  onContinue,
}: {
  audit: PrivacyAudit;
  busy: boolean;
  onBack: () => void;
  onRerun: () => void;
  onContinue: () => void;
}) {
  const highRisk = audit.high_risk_files > 0;
  return (
    <div className="grader-page">
      <GraderTopbar
        title="Privacy audit"
        subtitle="Safe metadata only. No AI call has been made."
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Back
            </button>
            <button className="btn btn-secondary" onClick={onRerun} disabled={busy}>
              <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
              Re-run
            </button>
            <button className="btn btn-primary" onClick={onContinue} disabled={busy || highRisk}>
              <AppIcon name="shield" />
              Continue to draft
            </button>
          </>
        }
      />
      <div className="audit-layout">
        <section className="audit-summary">
          <AuditStat label="Passed" value={audit.passed_files} tone="ok" />
          <AuditStat label="Redacted" value={audit.redacted_files} tone="warn" />
          <AuditStat label="Blocked" value={audit.blocked_files} tone="danger" />
          <AuditStat label="High risk" value={audit.high_risk_files} tone="danger" />
        </section>
        {highRisk ? (
          <div className="flag-note">
            Privacy audit found high-risk rows. Drafting is blocked until these submissions are handled.
          </div>
        ) : null}
        <div className="audit-actions">
          <a className="btn btn-secondary" href={api.privacyAuditCsvUrl(audit.job_id)}>
            <AppIcon name="fileDown" /> Export CSV
          </a>
          <a className="btn btn-secondary" href={api.privacyAuditJsonUrl(audit.job_id)}>
            <AppIcon name="fileText" /> Export JSON
          </a>
        </div>
        <section className="audit-table" aria-label="Privacy audit rows">
          <div className="audit-row audit-row-head">
            <span>Student</span>
            <span>File</span>
            <span>Input</span>
            <span>Privacy</span>
            <span>Flags</span>
          </div>
          {audit.rows.map((row) => (
            <div className="audit-row" key={row.id}>
              <span>{row.student_label}</span>
              <span>{row.redacted_source_name}</span>
              <span>{row.extraction_status}</span>
              <span className={`student-state ${row.privacy_status === "clean" ? "ok" : row.audit_pass ? "warn" : "danger"}`}>
                {row.blocked_reason ?? row.privacy_status}
              </span>
              <span>{row.privacy_flags.length ? row.privacy_flags.join(", ") : "None"}</span>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

function AuditStat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`audit-stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
```

- [ ] **Step 2: Change setup CTA copy**

In `GraderSetup`, change button text from:

```tsx
Draft grades for {item.submission_count}
```

to:

```tsx
Run privacy audit for {item.submission_count}
```

- [ ] **Step 3: Add CSS**

In `apps/web/src/styles.css`, add:

```css
.audit-layout {
  display: grid;
  gap: 14px;
  padding: 18px 22px;
}

.audit-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.audit-stat {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}

.audit-stat span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.audit-stat strong {
  display: block;
  margin-top: 4px;
  color: var(--ink);
  font-size: 28px;
}

.audit-stat.ok {
  border-color: color-mix(in srgb, var(--success) 32%, var(--border));
}

.audit-stat.warn {
  border-color: color-mix(in srgb, var(--warning) 32%, var(--border));
}

.audit-stat.danger {
  border-color: color-mix(in srgb, var(--danger) 32%, var(--border));
}

.audit-actions {
  display: flex;
  gap: 8px;
}

.audit-table {
  display: grid;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}

.audit-row {
  display: grid;
  grid-template-columns: 120px minmax(180px, 1.5fr) 110px 150px minmax(120px, 1fr);
  gap: 10px;
  align-items: center;
  min-width: 760px;
  padding: 10px 12px;
  border-top: 1px solid var(--border);
}

.audit-row:first-child {
  border-top: 0;
}

.audit-row-head {
  background: var(--paper);
  color: var(--muted-2);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.audit-row span {
  min-width: 0;
  overflow-wrap: anywhere;
}
```

- [ ] **Step 4: Run build and expect routing errors**

Run:

```powershell
pnpm run build
```

Expected: FAIL if `GraderAudit` is not imported/used yet, or PASS if TypeScript accepts unused export.

## Task 7: Wire Audit Flow in App

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/components/Grader.tsx`
- Test: `pnpm run build`

- [ ] **Step 1: Import and state**

In `apps/web/src/App.tsx`, import `GraderAudit` and `PrivacyAudit`:

```ts
import { GraderAudit, GraderQueue, GraderReview, GraderSetup, GraderWrap } from "./components/Grader";
```

Add type import:

```ts
PrivacyAudit,
```

Add state:

```ts
const [privacyAudit, setPrivacyAudit] = useState<PrivacyAudit | null>(null);
const [pendingGradingSetup, setPendingGradingSetup] = useState<{
  rubricMode: RubricMode;
  teacherLoop: TeacherLoopMode;
  rubricText: string;
} | null>(null);
```

- [ ] **Step 2: Split setup/audit/draft functions**

Replace `startGradingDraft` with:

```ts
async function runGradingPrivacyAudit(payload: {
  rubricMode: RubricMode;
  teacherLoop: TeacherLoopMode;
  rubricText: string;
}) {
  if (!selectedGradingItem) return;
  setGraderBusy(true);
  setError(null);
  try {
    const created = await api.createGradingJob({
      course_id: selectedGradingItem.course_id,
      activity_id: selectedGradingItem.activity_id,
      rubric_mode: payload.rubricMode,
      teacher_loop: payload.teacherLoop,
      rubric_text: payload.rubricText,
    });
    setGradingJob(created);
    setPendingGradingSetup(payload);
    const audit = await api.runPrivacyAudit(created.id);
    setPrivacyAudit(audit);
    setView("graderAudit");
    void loadGradingQueue();
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : "Failed to run privacy audit.");
  } finally {
    setGraderBusy(false);
  }
}

async function rerunGradingPrivacyAudit() {
  if (!gradingJob) return;
  setGraderBusy(true);
  setError(null);
  try {
    setPrivacyAudit(await api.runPrivacyAudit(gradingJob.id));
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : "Failed to run privacy audit.");
  } finally {
    setGraderBusy(false);
  }
}

async function continueToGradingDraft() {
  if (!gradingJob) return;
  setGraderBusy(true);
  setError(null);
  try {
    const drafted = await api.draftGradingJob(gradingJob.id);
    setGradingJob(drafted);
    setActiveGradingSubmissionId(drafted.submissions[0]?.id ?? null);
    setView("graderReview");
    void loadGradingQueue();
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : "Failed to draft grades.");
  } finally {
    setGraderBusy(false);
  }
}
```

- [ ] **Step 3: Update setup usage**

Change:

```tsx
onStart={(payload) => void startGradingDraft(payload)}
```

to:

```tsx
onStart={(payload) => void runGradingPrivacyAudit(payload)}
```

- [ ] **Step 4: Add audit route render**

In the main render, add before `graderReview`:

```tsx
{view === "graderAudit" && privacyAudit ? (
  <>
    <GraderAudit
      audit={privacyAudit}
      busy={graderBusy}
      onBack={() => setView("graderSetup")}
      onRerun={() => void rerunGradingPrivacyAudit()}
      onContinue={() => void continueToGradingDraft()}
    />
    {error ? <InlineError message={error} /> : null}
  </>
) : null}
```

- [ ] **Step 5: Clean unused pending state if unnecessary**

If TypeScript reports `pendingGradingSetup` unused, remove that state. It is only needed if the implementation wants to preserve setup choices for future edits; the backend job already stores the choices.

- [ ] **Step 6: Run build**

Run:

```powershell
pnpm run build
```

Expected: PASS.

## Task 8: Full Verification and Commit

**Files:**
- All changed files from prior tasks.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
uv run pytest -q
```

Expected: `18 passed` plus the new audit tests. The total should be higher than 18.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
pnpm run build
```

Expected: successful Vite build.

- [ ] **Step 3: Manual smoke in browser**

With the dev server at `http://127.0.0.1:5173/`:
- Open Grade with AI.
- Pick a ready assignment.
- Setup screen button reads "Run privacy audit".
- Run audit.
- Confirm audit screen shows summary cards and pseudonym rows.
- Confirm export links are visible.
- Continue to draft.
- Confirm review screen opens.

- [ ] **Step 4: Commit implementation**

Run:

```powershell
git add apps/api/src/classroom_downloader/privacy_audit.py apps/api/src/classroom_downloader/models.py apps/api/src/classroom_downloader/schemas.py apps/api/src/classroom_downloader/main.py apps/api/src/classroom_downloader/grading.py apps/api/tests/test_grading.py apps/web/src/types.ts apps/web/src/lib/api.ts apps/web/src/App.tsx apps/web/src/components/Grader.tsx apps/web/src/styles.css
git commit -m "Add in-app privacy audit workflow"
```

Expected: commit succeeds and unrelated untracked files remain untouched.
