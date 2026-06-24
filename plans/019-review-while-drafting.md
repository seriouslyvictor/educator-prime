# Plan 019 — Let the teacher review already-drafted students while the queue is still processing

> Source: Notion TODO "Atualmente não é possível avançar os gradings enquanto a
> fila está em processamento, o professor só consegue avaliar o aluno após TODOS
> alunos terem sido processados pelo LLM."
> Theme: **C — Grading review screen**. Priority P1. Effort M. Depends on: none.
> Base: branch off `main` @ `6d6b264`.

## Why
The draft pipeline already streams per-student: `draft_grading_job` publishes the
full queue up front (`on_queued`) and emits each submission as it finishes
(`drafting.py:454-475`); the frontend seeds the whole list and applies each result
live (`useGradingJob.continueToGradingDraft`, `useGradingJob.ts:582-623`). The
review screen even renders "na fila"/"gerando rascunho" states per row
(`GraderReview.tsx:94-106, 270-279`). **But the teacher cannot act on a finished
student until the whole batch completes**, because:
- `continueToGradingDraft` holds `setGraderBusy(true)` for the **entire** stream
  and only releases it in `finally` after the last student (`useGradingJob.ts:584,
  619-622`).
- `GraderReview` disables Accept and Retry on `busy` (`disabled={!hasValidScore ||
  busy}` at line 372; retry `disabled={busy}` at 367) — and `busy` is `graderBusy`.

So the whole point of the live queue (review as they land) is defeated by one
shared busy flag.

## The fix: separate "a draft is streaming" from "this accept is in flight"
Drafting in the background should not disable per-student review. Acceptance of one
student should disable only that action briefly, not the whole screen.

## Files
- `apps/web/src/App.tsx` — `graderBusy` state shared across hooks
  (`App.tsx:48-50`, passed as `busy` to `GraderReview` at line 411).
- `apps/web/src/hooks/useGradingJob.ts` — `continueToGradingDraft` (the long-held
  busy), `acceptGradingDraft`, `retryGradingDraft`.
- `apps/web/src/components/grader/GraderReview.tsx` — the `busy` gates on Accept /
  Retry and the `accept()` guard (`!busy`).

## Steps
1. Stop holding the global `graderBusy` for the whole draft stream. In
   `continueToGradingDraft`, either:
   - introduce a dedicated `draftInProgress` flag (already inferable from
     `progress.phase === "draft" && !progress.done`, which `GraderReview` computes
     at line 94) and **do not** set `graderBusy` true for the stream duration; or
   - keep a draft-specific busy that gates only draft-level controls, not the
     per-student accept.
2. In `GraderReview`, change the Accept/Retry gating so a teacher can accept any
   student whose draft is **ready** (has `ai_score`/`final_score` or is blocked with
   a manual score) even while `draftInProgress`. Keep Accept disabled only for:
   - the active student still **pending/drafting** (`activePending` already exists,
     line 105), and
   - a brief per-action in-flight state for the accept call itself.
3. Add a per-submission "accepting" state (e.g. `acceptingId`) so the Accept button
   shows a spinner for just that row while `reviewGradingSubmission` runs, instead
   of disabling the entire screen. `acceptGradingDraft` already advances to the next
   unreviewed student (`useGradingJob.ts:636-646`) — preserve that.
4. Ensure live draft updates don't clobber a student the teacher just edited:
   `applyDraftSubmission` (`useGradingJob.ts:246-262`) replaces by id from the
   stream — confirm an accepted/reviewed row isn't overwritten by a late draft
   payload for the same id (guard: don't downgrade `reviewed` rows).
5. Keep the existing reconnect/resume semantics in `streamGradingProgress` intact —
   this plan does not change SSE handling, only what the UI lets the teacher do
   during it.

## Acceptance / STOP
- Build/test/lint green.
- e2e: extend the grader queue spec (mock mode drafts deterministically) to assert
  that an early-finishing student can be accepted **before** the stream completes,
  and that doing so does not break the running stream or the final counts.
- Manual smoke: start drafting a class; as soon as the first student shows a draft,
  accept it and advance — the rest keep drafting; accepting never freezes the
  screen.
- Regression: when drafting fails mid-stream, the resume path (`progress.error` →
  "Retomar na fila") still works and partially-reviewed work is preserved.


## Implementation status - 2026-06-24
Status: DONE

Implemented to spec:
- `continueToGradingDraft` no longer holds the global `graderBusy` flag for the entire draft stream.
- `GraderReview` disables Accept only when the active row is still pending or that row is currently being accepted.
- Added per-submission `acceptingSubmissionId` state so Accept shows a row-local spinner instead of freezing the whole review screen.
- Late draft payloads are merged without overwriting rows the teacher already reviewed.
- Existing resume/progress handling remains on the same SSE path.

Verification:
- Red/green unit test: `pnpm test:run src/hooks/useGradingJob.test.ts -t "does not downgrade"` from `apps/web`: failed before helper implementation, then passed.
- `pnpm build` from `apps/web`: passed.
- `pnpm lint` from `apps/web`: passed with existing warnings only.
- `pnpm e2e e2e/review-while-drafting.spec.ts` from `apps/web`: 1 passed.
- `pnpm e2e` from `apps/web`: 5 passed.
