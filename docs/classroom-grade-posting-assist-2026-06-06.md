# Postar no Classroom — final posting assist on "Pronto para fechar"

**Date:** 2026-06-06
**Status:** Implemented
**Scope:** Add a final action on the grading "Pronto para fechar" screen to push grades + feedback to Google Classroom.

---

## 1. Context & motivation

The grading flow ends on the **"Pronto para fechar"** screen
(`apps/web/src/components/grader/GraderWrap.tsx`, rendered when a `GradingJob.status === "completed"`).
Today it only summarizes grades and exports a CSV, with the note
*"nada é publicado no Classroom nesta versão."* We want a final action there to push grades **and
feedback** back to Google Classroom.

### Critical platform constraint (verified against Google's official docs)

Fully automatic posting is **not possible** for this app's workflow, for two independent reasons:

1. **Grades can only be written to coursework that the app's own OAuth project created.**
   > *"This request must be made by the Developer Console project of the OAuth client ID used to
   > create the corresponding course work item."*
   > — [studentSubmissions.patch reference](https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWork.studentSubmissions/patch)

   This app is a **downloader**: it reads assignments teachers created in the Classroom web UI
   (owned by Google's first-party project, not our client). Calling `patch` / `return` /
   `modifyAttachments` on those assignments returns **403 PERMISSION_DENIED**. Confirmed still
   current in 2025 ([Google dev forum thread](https://discuss.google.dev/t/google-classroom-api-permission-denied-on-grade-submission/270881)).

2. **Feedback / private comments have no API at all.**
   > *"...features such as student submission comments aren't currently exposed through the API..."*
   > — [Assignment Workflows tutorial](https://developers.google.com/workspace/classroom/tutorials/assignment-workflows)

   Only `draftGrade` / `assignedGrade` are writable on a `StudentSubmission`. There is no
   comment/feedback endpoint.

**Conclusion:** A button that silently auto-posts all grades + feedback to existing teacher-created
assignments cannot be built. The chosen design is a **human-in-the-loop assist**.

### Chosen approach

A **"Postar no Classroom"** panel that makes manual posting fast and accurate. Per student it:
- puts the grade + feedback on the clipboard,
- deep-links straight to that submission in the Classroom grading UI,
- tracks which students are done.

**No new OAuth scopes** are required — write scopes would be useless given the 403 rule, and the
deep links come from the `alternateLink` field already returned by the existing **read-only**
`studentSubmissions.list` call.

---

## 2. Backend changes (`apps/api/src/classroom_downloader/`)

### 2.1 `models.py` — extend `GradingSubmission` (after `error`, ~line 134)
```python
classroom_submission_id: str | None = None
alternate_link: str | None = None          # Classroom web URL for this submission
posted_to_classroom: bool = False
posted_at: datetime | None = None
```

### 2.2 `database.py` — dev migration for the new columns
Add `_ensure_grading_submission_columns(target_engine)` mirroring `_ensure_grading_job_columns`
(line 45), and register it in `ensure_sqlite_dev_migrations` (line 25). Columns:

| column | type |
| --- | --- |
| `classroom_submission_id` | `VARCHAR` |
| `alternate_link` | `VARCHAR` |
| `posted_to_classroom` | `BOOLEAN DEFAULT 0` |
| `posted_at` | `DATETIME` |

### 2.3 `google_provider.py` — read-only links lookup
- Add a `SubmissionLink` dataclass: `source_file_id`, `classroom_submission_id`, `alternate_link`,
  `student_email`.
- Add `list_submission_links(course_id, activity_id) -> list[SubmissionLink]` to the
  `GoogleProvider` base, the real `GoogleApiProvider`, and `MockProvider`.
  - **Real impl:** reuse the `studentSubmissions().list()` loop pattern in `list_submission_files`
    (line 425). `alternateLink` and `id` are returned by default — no field mask, no new scope. For
    each attachment `driveFile.id`, emit one `SubmissionLink` keyed by `source_file_id` so it joins
    cleanly to `GradingSubmission`. Mirror `drive_files_from_submission` (line 156); additionally
    read `submission["alternateLink"]` and `submission["id"]`.
  - **Mock impl:** return deterministic stub links
    (e.g. `https://classroom.google.com/c/{course_id}/sm/{id}/details`) so the feature works in
    default dev (`CD_GOOGLE_PROVIDER` unset).

### 2.4 `main.py` — two thin endpoints (mirror existing grading endpoints)
- `POST /api/grading/jobs/{job_id}/classroom-links` — `Depends(provider_dependency)`. Calls
  `provider.list_submission_links(job.course_id, job.activity_id)`, joins to `GradingSubmission`
  rows by `source_file_id`, persists `classroom_submission_id` + `alternate_link`, returns
  `grading_job_snapshot(session, job)`. This **backfills old jobs and populates new ones** in one
  call. Wrap the provider call defensively (on `HttpError` / auth failure, log and return the job
  unchanged rather than 500).
- `POST /api/grading/jobs/{job_id}/submissions/{submission_id}/posted` — body `{"posted": bool}`.
  Sets/clears `posted_to_classroom` + `posted_at`, returns the job snapshot. Mirror the existing
  `.../submissions/{id}/review` endpoint.

### 2.5 `schemas.py` — extend `GradingSubmissionRead` (line 130)
Add `classroom_submission_id: str | None = None`, `alternate_link: str | None = None`,
`posted_to_classroom: bool = False`, `posted_at: str | None = None`.

### 2.6 `grading.py` — map fields in `_submission_read` (line 1198)
Pass the four new fields through into `GradingSubmissionRead`. No other call sites change — the job
snapshot already flows through `_submission_read`.

---

## 3. Frontend changes (`apps/web/src/`)

### 3.1 `types.ts` — extend `GradingSubmission` (line 94)
Add `classroom_submission_id: string | null`, `alternate_link: string | null`,
`posted_to_classroom: boolean`, `posted_at: string | null`.

### 3.2 `lib/api.ts` — two methods (mirror `reviewGradingSubmission`, line 203)
```ts
prepareClassroomLinks: (jobId: string) =>
  request<GradingJob>(`/api/grading/jobs/${jobId}/classroom-links`, { method: "POST" })
    .then((j) => { clearApiCache(`GET /api/grading/jobs/${jobId}`); return j; }),

markSubmissionPosted: (jobId: string, submissionId: string, posted: boolean) =>
  request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/posted`, {
    method: "POST",
    body: JSON.stringify({ posted }),
  }).then((j) => {
    clearApiCache(`GET /api/grading/jobs/${jobId}`);
    clearApiCache("GET /api/grading/jobs");
    return j;
  }),
```

### 3.3 `components/grader/GraderWrap.tsx` — the "Postar no Classroom" panel
- Add an `onJobUpdate: (job: GradingJob) => void` prop; in `App.tsx` pass
  `onJobUpdate={setGradingJob}` where `GraderWrap` is rendered (~`App.tsx:542`).
- On mount, if any graded submission lacks `alternate_link`, call `api.prepareClassroomLinks(job.id)`
  once and `onJobUpdate(updated)`. Also expose this as a "Preparar postagem" retry button (for when
  it failed or ran without auth).
- Replace the *"nada é publicado..."* note with an honest one-liner: the Classroom API can't
  auto-post grades/feedback to teacher-created assignments, so this panel speeds up manual posting.
- New panel listing each **graded** submission (`final_score != null`), sorted by student:
  - student name · grade `X/100` · feedback preview.
  - **"Copiar nota + feedback"** → `navigator.clipboard.writeText(`Nota: ${score}/100\n\n${feedback ?? ""}`)`
    with a transient "Copiado!" state.
  - **"Abrir no Classroom"** → `<a href={alternate_link} target="_blank" rel="noopener">`; if
    `alternate_link` is null, hide the button / fall back to an activity-level link.
  - **"Marcar como postado"** toggle → `api.markSubmissionPosted(...)` then `onJobUpdate`.
  - Header progress counter: `{posted} de {graded} postados`.
- Keep the existing CSV export + cache-delete controls.

### 3.4 Styles
Add row styling consistent with the existing `.outlier-row` / `.wrap-side` rules (same global grader
stylesheet that defines `.wrap-grid`). No new design-system work.

---

## 4. Out of scope (documented, not built)
- **Direct API posting** would require the app to *create* the assignment itself (so it owns the
  coursework) and would still be grades-only (feedback as an attached Drive doc). That is a
  different product workflow — deferred.
- **No OAuth scope changes** — the `App.tsx:44` scope list stays read-only.

---

## 5. Verification
1. **Migration:** start the API
   (`uv run --extra dev python -m uvicorn classroom_downloader.main:app --reload --port 8000`)
   against an existing SQLite DB; confirm the 4 columns are added on startup
   (`PRAGMA table_info(gradingsubmission)`), no errors.
2. **Backend (mock provider, default dev):**
   - `POST /api/grading/jobs/{id}/classroom-links` returns submissions with non-null `alternate_link`.
   - `POST /api/grading/jobs/{id}/submissions/{sid}/posted {"posted":true}` flips
     `posted_to_classroom` and persists across a `GET`.
3. **Frontend** (`pnpm run dev`): open a completed grading job → "Pronto para fechar". Confirm the
   panel renders, "Copiar" puts `Nota: …` + feedback on the clipboard, "Abrir no Classroom" opens
   the link, "Marcar como postado" persists across reload, and the progress counter updates.
4. **Types/build:** `pnpm run build` (tsc) passes; run backend tests if present (`uv run pytest`).
5. **Real provider (optional):** with `CD_GOOGLE_PROVIDER=google` and a connected account, confirm
   `classroom-links` populates real `alternateLink`s and the deep links open the correct submission.

---

## 6. File-change checklist

**Backend**
- [x] `models.py` — 4 new `GradingSubmission` fields
- [x] `database.py` — `_ensure_grading_submission_columns` + register
- [x] `google_provider.py` — `SubmissionLink` + `list_submission_links` (base, real, mock)
- [x] `main.py` — `classroom-links` + `posted` endpoints
- [x] `schemas.py` — 4 new `GradingSubmissionRead` fields
- [x] `grading.py` — map fields in `_submission_read`

**Frontend**
- [x] `types.ts` — 4 new `GradingSubmission` fields
- [x] `lib/api.ts` — `prepareClassroomLinks` + `markSubmissionPosted`
- [x] `components/grader/GraderWrap.tsx` — panel + `onJobUpdate` wiring
- [x] `App.tsx` — pass `onJobUpdate={setGradingJob}`
- [x] grader stylesheet — panel row styles

---

## 7. Implementation notes

- Backend targeted verification passed: `uv run pytest tests/test_database.py::test_sqlite_dev_migration_adds_cache_and_grading_metadata_columns tests/test_grading.py::test_classroom_links_endpoint_backfills_links_and_posted_state`.
- Full backend suite passed: `uv run pytest` (`101 passed`).
- Frontend build verification passed: `pnpm run build`.
- Browser verification on `http://localhost:5173` with an existing completed job confirmed the panel renders, Classroom links are present, copy shows `Copiado!`, and mark/unmark updates the counter from `0 de 15 postados` to `1 de 15 postados` and back.
