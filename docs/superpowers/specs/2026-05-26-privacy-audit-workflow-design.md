# Privacy Audit Workflow Design

## Summary
Build a reusable in-app privacy audit workflow for Classroom assignment submissions before any AI grading step. The audit uses the same Drive/Classroom file resolution, cache, extraction, pseudonymization, and redaction path that grading will use, but it never calls an AI provider and never persists extracted or scrubbed submission text.

The goal is trust: teachers can inspect whether an assignment is safe to draft with AI before any future AI engine is allowed to see student work.

## Goals
- Add a first-class privacy audit checkpoint to the AI grader flow.
- Produce an inspectable report with counts and per-submission safe metadata.
- Let the teacher export safe CSV/JSON audit logs.
- Block or clearly flag submissions that should not proceed to AI.
- Reuse the audit result when drafting grades so privacy behavior is consistent.

## Non-Goals
- No LiteLLM or real AI provider integration in this phase.
- No Classroom posting or write scopes.
- No local-folder product UI yet; the product workflow audits Classroom assignment submissions.
- No persistence of extracted text, scrubbed text, prompts, source bytes, or model-shaped payloads in the audit report.
- No OCR or multimodal parsing upgrade in this phase.

## User Flow
1. Teacher opens **Grade with AI** and chooses an assignment.
2. Teacher configures rubric source and teacher-in-loop mode.
3. Teacher runs **Privacy Audit** before drafting.
4. App shows an audit report:
   - Total files.
   - Passed files.
   - Redacted files.
   - Blocked/unsupported files.
   - High-risk files.
   - Per-submission rows using pseudonyms like `student_001`.
5. Teacher can export safe CSV/JSON.
6. **Continue to draft** is enabled only when no high-risk privacy failures exist.
7. Unsupported files are allowed to remain in the job as blocked/manual-review rows, but they are not sent to any grading engine.

## Backend Design
Add a privacy audit service that mirrors the grading preflight path:
- Resolve Classroom submission files for one course/activity.
- Create or reuse a `GradingJob` and `GradingSubmission` rows.
- Cache source bytes under the existing 24-hour grading cache policy.
- Extract supported text using `extract_submission_content`.
- Scrub/pseudonymize using `scrub_submission`.
- Persist only safe audit metadata.

Add new models:
- `PrivacyAudit`: one report per grading job or setup run.
  - `id`
  - `job_id`
  - `status`: `running`, `completed`, `completed_with_blocks`, `failed`
  - `total_files`
  - `passed_files`
  - `redacted_files`
  - `blocked_files`
  - `high_risk_files`
  - `created_at`
  - `updated_at`
- `PrivacyAuditRow`: one safe row per submission.
  - `id`
  - `audit_id`
  - `job_id`
  - `submission_id`
  - `student_label`
  - `redacted_source_name`
  - `mime_type`
  - `byte_size`
  - `extraction_status`
  - `extraction_error`
  - `privacy_status`
  - `privacy_flags_json`
  - `remaining_direct_identifier_hits_json`
  - `audit_pass`
  - `blocked_reason`

The audit service must not store:
- Raw filename if it includes a detected identifier.
- Student name or email in audit rows.
- Extracted text.
- Scrubbed text.
- Prompt-ready payload.
- Feedback bodies.

## API Design
Add endpoints:
- `POST /api/grading/jobs/{job_id}/privacy-audit`
  - Runs or reruns the audit for an existing setup job.
  - Returns a full `PrivacyAuditRead`.
- `GET /api/grading/jobs/{job_id}/privacy-audit`
  - Returns the latest audit if one exists.
- `GET /api/grading/jobs/{job_id}/privacy-audit/export.csv`
  - Returns safe CSV only.
- `GET /api/grading/jobs/{job_id}/privacy-audit/export.json`
  - Returns safe JSON only.

Add response types:
- `PrivacyAuditRead`
- `PrivacyAuditRowRead`

The existing `POST /api/grading/jobs/{job_id}/draft` should check the latest audit before drafting:
- If no audit exists, run one automatically.
- If high-risk rows exist, return HTTP 409 with a safe message.
- If blocked unsupported rows exist, continue drafting the supported rows and preserve blocked rows as manual-review entries.

## Frontend Design
Add a privacy audit step to the grader setup/review transition:
- In `GraderSetup`, replace direct **Draft grades** with **Run privacy audit**.
- After audit completes, show an audit panel or screen before review.
- Provide:
  - Summary count cards.
  - Per-submission table.
  - Export CSV/JSON links.
  - **Continue to draft** button.

The table displays:
- Pseudonym.
- Redacted filename.
- MIME type.
- Extraction status.
- Privacy status.
- Flags.
- Blocked reason.

No raw student identifiers should appear in the audit panel.

## Safety Rules
- No AI call in this phase.
- No audit report may include raw student names, emails, or unredacted identifier-bearing filenames.
- Audit rows use only pseudonyms and redacted source names.
- High-risk rows block drafting until manually addressed in a later phase.
- Unsupported image/scanned submissions are blocked/manual-review, not silently passed.
- Audit exports are safe metadata exports only.
- Server logs must not include submission text, scrubbed text, or raw source bytes.

## Testing Strategy
Backend tests:
- Running an audit creates report and row metadata.
- Audit rows redact email-bearing filenames.
- Audit rows never include student email/name.
- Supported text/code files can pass.
- Image files become blocked rows.
- High-risk privacy rows block `draft`.
- Draft auto-runs audit if missing.
- Safe CSV/JSON exports contain no raw identifiers.
- Existing grading/download tests still pass.

Frontend/build tests:
- `pnpm run build` passes.
- Setup flow can run audit and display summary.
- Audit table shows pseudonyms and redacted filenames.
- Continue button is disabled when high-risk rows exist.
- Export links point to audit export endpoints.

## Acceptance Criteria
- A teacher can run a privacy audit from the grader setup flow before drafting.
- The audit report is inspectable in the app.
- The teacher can export safe CSV/JSON.
- Drafting cannot proceed if high-risk privacy failures exist.
- Unsupported submissions are visible as blocked/manual-review.
- No raw submission text or direct student identifiers are stored in audit rows or exported reports.
