# Plan 016 — Turmas grade-awareness (detect already-graded work, graded/ungraded counts, partial-grade choice)

> Source: Notion TODO items
> - "Implementar lógica para buscar alunos com notas e atualizar o doneView para
>   refletir isso automaticamente."
> - "Tela de turmas ⇒ Implementar verificação para sinalizar atividades já
>   corrigidas fora do sistema … contador de ungraded/graded … se parcialmente
>   corrigido, o usuário deve poder escolher corrigir apenas os restantes ou todos."
> Theme: **B — Turmas grade-awareness**. Priority P1. Effort M–L. Depends on: none
> (independent of the grading-engine plans).
> Base: branch off `main` @ `6d6b264`.

## Why
The Activities list shows a grading chip only for work graded **inside this tool**
(`gradingByActivity` → `referenceQueueStatus`, `ActivityList.tsx:67-101`). It is
blind to grades a teacher already entered **in Google Classroom directly**. The
maintainer wants the Turmas screen to:
1. Know, per activity, how many submissions already have a Classroom grade
   (graded vs ungraded counter).
2. Mark an activity as **concluded** when every submission is already graded
   (nothing left to do), and reflect that automatically.
3. When an activity is **partially** graded, let the teacher choose to grade only
   the remaining (ungraded) students or re-grade everyone — surfaced on the
   rubric-prep / privacy-audit setup screen.

## The data is already one field away
The provider already lists `studentSubmissions` for files and links
(`google_provider.py:576-674`, `.studentSubmissions().list(courseWorkId=…)`). The
Classroom `studentSubmissions` resource carries `assignedGrade`, `draftGrade`, and
`state` (`TURNED_IN`, `RETURNED`, …) on the **same response** — they are currently
read for files only and otherwise discarded. No new OAuth scope is needed
(`classroom.coursework.students.readonly` already covers grades).

## Files
Backend:
- `apps/api/src/classroom_downloader/google_provider.py` — add a method that
  returns per-activity grade tallies from the existing `studentSubmissions` call
  (e.g. `submission_grade_summary(course_id, activity_ids) -> {activity_id:
  {total, graded, ungraded, returned}}`). Reuse the existing pagination + TTL
  cache pattern; mirror in the mock provider (`MockGoogleProvider`) so tests and
  mock-mode UI work.
- `apps/api/src/classroom_downloader/routers/courses.py` — extend the activities
  response (or add `GET /api/courses/{course_id}/activities/grade-summary`) to
  include `{graded, ungraded, total, concluded}` per activity. Prefer extending
  `ActivityRead` so the list already carries it (one round trip).
- `apps/api/src/classroom_downloader/schemas.py` — add the fields to `ActivityRead`.
- `apps/api/tests/test_api.py` (or a new `test_grade_summary.py`) — cover the
  mock provider's tallies and the concluded/partial classification.

Frontend:
- `apps/web/src/types.ts` — add `graded`, `ungraded`, `concluded` to `Activity`.
- `apps/web/src/components/workspace/ActivityList.tsx` — render a graded/ungraded
  counter chip per row; when `concluded`, show a "Concluída" state and de-emphasize
  the primary CTA (still allow re-grade).
- `apps/web/src/components/grader/GraderSetup.tsx` — when the selected activity is
  partially graded, show a choice: **"Corrigir apenas os X restantes"** vs
  **"Corrigir todos os Y"**. Thread the choice into the create-job payload.
- `apps/web/src/hooks/useGradingJob.ts` / `lib/api.ts` — pass a
  `scope: "remaining" | "all"` (or `skip_graded: boolean`) into `createGradingJob`.

## Steps
1. **Backend tally.** Add `submission_grade_summary` to both real and mock
   providers, derived from `studentSubmissions` (`state` + `assignedGrade` present).
   Define "graded" = has `assignedGrade` (or `state == RETURNED`); make the rule a
   single documented helper so the UI and the grading scope filter agree.
2. **Surface it.** Add the fields to `ActivityRead` + `Activity`; populate in
   `list_activities`. Keep it cheap — one `studentSubmissions` page-walk per
   activity already happens for counts; do not add an N+1 across activities without
   the existing TTL cache.
3. **Counters + concluded.** In `ActivityList`, show `graded/total` and a
   "Concluída" chip when `ungraded === 0 && total > 0`. This is the automatic
   "doneView" reflection the Notion asks for: the activity row reflects external
   grading without the teacher re-entering the tool's grading flow.
4. **Partial choice.** In `GraderSetup`, when `0 < graded < total`, render the
   remaining-vs-all toggle (default **remaining**). Pass the scope to the backend.
5. **Backend scope honored.** In job creation / `draft_grading_job`, when
   `scope === "remaining"`, skip submissions that already carry a Classroom grade
   (filter in `list_submission_files`/`_group_files` against the grade summary).
   When "all", behave as today.

## Open interpretation to confirm with the maintainer
"doneView" in the first TODO is ambiguous — there is a `DoneView.tsx` but it is the
**export**-completion screen, unrelated to grading. This plan interprets "doneView"
as **the Turmas activity row reflecting Classroom grade state automatically**
(step 3). If the maintainer meant something else (e.g. the grader wrap screen or
the queue's completed state), adjust step 3's surface. **Ask before building if
unsure** — the backend tally (steps 1–2) is correct either way and can land first.

## Acceptance / STOP
- Backend: `uv run pytest` green, including new tally tests for graded / ungraded /
  partial / concluded against the mock provider.
- Frontend: build/test/lint green; counter + concluded chip render in mock mode;
  partial activity shows the remaining-vs-all choice.
- `pnpm --filter web e2e` green (mock mode covers the list render).
- No new OAuth scope requested (verify the scope set in `routers/auth.py` is
  unchanged).
- **STOP** at the end of step 2 to confirm the "doneView" interpretation if there
  is any doubt, before building the UI in steps 3–5.
