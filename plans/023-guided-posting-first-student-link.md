# Plan 023 — "Postagem guiada" should open the Classroom link for the first student

> Source: Notion TODO "Assim que clicar no botão 'Postagem guiada', já abrir o link
> do classroom para o primeiro aluno (ainda não está funcionando)."
> Theme: **E — Classroom posting**. Priority P2. Effort S. Depends on: none.
> Base: branch off `main` @ `6d6b264`.

## Why
Clicking **Postagem guiada** opens the PiP companion and a Classroom tab, but the
tab lands on the **assignment grading list**, not the **first student**:
`handleOpenPiP` calls `window.open(classroomActivityUrl(job, accountEmail), …)`
(`GraderWrap.tsx:127-141`). `classroomActivityUrl` builds the
`/submissions/by-status/.../all/all` list URL (`domain.ts:32-41`). The teacher then
has to find the first pending student manually — which is what "ainda não está
funcionando" refers to.

## What "the first student" is
`pipQueue` is the graded-but-not-yet-posted list, sorted by student label
(`GraderWrap.tsx:64-70, 122-125`); `pipQueueRef.current[0]` is the first student the
guided flow will walk. Each submission carries `alternate_link` — the per-student
Classroom URL prepared by `prepareClassroomLinks` (used per row at
`GraderWrap.tsx:266-269, 288-296`). So the first-student link is
`withAuthUser(pipQueueRef.current[0].alternate_link, accountEmail)`.

## Likely reasons the current attempt fails (investigate, then fix)
1. **It simply isn't wired** — `handleOpenPiP` hard-codes the assignment URL
   (line 139); it never reads the first student's link. This is the primary fix.
2. **Links may not be prepared yet at click time.** `prepareClassroomLinks` runs in
   an effect (`GraderWrap.tsx:86-89`) and sets `alternate_link`; if the teacher
   clicks before it resolves, `alternate_link` is null and you must fall back to the
   assignment URL. Guard for this.
3. **Popup/gesture ordering.** The existing code is careful: it kicks off the PiP
   request *before* `window.open` in the same user gesture (see the comment at
   `GraderWrap.tsx:130-140`) because `window.open` hides the opener and would block
   the PiP. **Preserve this ordering** — only change the URL passed to
   `window.open`, do not reorder the gesture.
4. **Per-student deep link format.** If `alternate_link` resolves to the assignment
   details page rather than the student's submission pane, landing "on the first
   student" may need the per-student grading URL
   (`/submissions/by-status/and-sort-first-name/all/student/<encoded studentId>` or
   the `alternate_link` Google returns for the studentSubmission). Verify what
   `alternate_link` actually points at (check `prepareClassroomLinks` in
   `routers/grading.py` and `submission_links_from_submission` in
   `google_provider.py:325`). Use the most specific per-student URL available.

## Files
- `apps/web/src/components/grader/GraderWrap.tsx` — `handleOpenPiP` (lines 127-141).
- `apps/web/src/components/grader/domain.ts` — `withAuthUser`,
  `classroomActivityUrl` (reuse; maybe add a `firstStudentPostingUrl(queue, job,
  email)` helper).
- (If link format is wrong) `apps/api/src/classroom_downloader/routers/grading.py`
  `prepareClassroomLinks` and `google_provider.py:325` — confirm the per-student
  URL.

## Steps
1. In `handleOpenPiP`, compute the target as: first queued student's
   `withAuthUser(alternate_link, accountEmail)` when present, else
   `classroomActivityUrl(job, accountEmail)` (today's behavior) as fallback.
2. Keep the gesture ordering exactly: start `openPiP()`, then `window.open(target,
   "classroom-posting")`, then `await pipReady` — only the `target` string changes.
3. If `alternate_link` is not the right per-student pane, fix it at the source
   (`prepareClassroomLinks`) so every row's "Abrir no Classroom" and the guided
   first-student open both land on the student. Don't special-case only the first
   student.
4. Confirm the empty-queue guard still holds: the button is already
   `disabled={!pipSupported || pipQueue.length === 0}` (line 250), so
   `pipQueueRef.current[0]` is safe inside the handler.

## Acceptance
- Build/test/lint green.
- Manual smoke (needs a real Classroom session — this is a real-link feature, mock
  mode can only assert the URL chosen): clicking Postagem guiada opens the PiP and a
  Classroom tab focused on the **first pending student**; if links weren't prepared
  yet, it falls back to the assignment view without error; PiP still renders (gesture
  ordering preserved).
- A unit test on the URL-selection helper: returns the first student's authuser link
  when `alternate_link` exists, the assignment URL otherwise.

## Implementation log
- Status: DONE (2026-06-24).
- Confirmed `prepareClassroomLinks` stores Google Classroom `alternateLink` on each submission, and mock links are already per-submission details URLs.
- Added `firstStudentPostingUrl(queue, job, accountEmail)` to choose the first pending student's `alternate_link` with `authuser`, falling back to the assignment grading URL when no prepared link exists.
- Updated `handleOpenPiP` to snapshot the queue, start `openPiP()`, compute the target URL, call `window.open(target, "classroom-posting")`, then await PiP readiness; popup/PiP gesture ordering is preserved.
- Added unit coverage for first-student link selection and assignment fallback.
- Verification: `pnpm test:run` -> 28 passed.
- Verification: `pnpm lint` -> 0 errors, 14 existing warnings.
- Verification: `pnpm build` -> passed.
- Verification: `pnpm e2e` -> 6 passed.
- Real Classroom smoke was not run in this environment; mock/unit coverage verifies the selected URL and existing e2e verifies PiP/review flows in mock mode.
