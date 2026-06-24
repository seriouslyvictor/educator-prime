# Plan 022 — Two-pass grading: flag only true outliers in a second, whole-class pass

> Source: Notion TODO (paraphrased): the LLM currently makes too many "observações"
> — nearly every activity gets flagged, and the flags are usually just restating
> errors already covered in the feedback. Change the flow: **first** the LLM grades
> every submission; **then** it reviews all gradings/submissions again and flags
> only work that genuinely departs from the class pattern (wrong exercise, delivery
> far outside the class norm, a student in clear difficulty). Preference: send a
> **single batch** (if it fits the context window) with submissions separated by
> **XML markers**; the response returns **only the flags** — only true exceptions.
> Theme: **D — Grading engine quality**. Priority P1. Effort L. Depends on: none,
> but interacts with Plan 019 (live drafting) — see Sequencing.
> Base: branch off `main` @ `6d6b264`.

## Why
Flags are currently produced **per submission, during drafting**: each grade call
returns `result.flags`, and `_draft_submission` writes the first one onto
`submission.flag` (`drafting.py:273, 326-329`). With no cross-class context, the
model flags almost everything, and those flags duplicate the feedback. The wrap
screen's "Vale uma segunda olhada" list is built from those noisy flags
(`GraderWrap.tsx:61-63, 201-225`), so it is currently near-useless.

The maintainer wants flags to mean **"this is an exception worth your attention"**,
which only makes sense **relative to the whole class** — hence a second pass that
sees all gradings at once.

## Target flow
1. **Pass 1 — grade (unchanged scoring):** keep per-submission grading exactly as
   today, but **stop emitting per-submission `flag`s as the outlier signal.** Either
   drop `result.flags` from the badge entirely, or repurpose it strictly for
   mechanical issues (privacy/extraction), keeping "needs a look" out of pass 1.
2. **Pass 2 — outlier review (new):** after all drafts complete, assemble one prompt
   containing every gradable submission wrapped in XML
   (`<submission id="student_001" score="…">…scrubbed content + the draft
   grade/feedback…</submission>`), with instructions to return **only** the ids that
   are genuine outliers, each with a short reason. Map the returned ids back onto
   `submission.flag` (+ reason). Everything not returned is **unflagged**.

## Context-window guard (reuse prior thinking)
The archived plan `archive/litellm-grading-batch-intervention-plan.md` §5 already
designed a context-budget guard and XML batch assembly for a different feature
(cost batching). **Reuse its approach** here: `litellm.token_counter` +
catalog `max_input_tokens`, fill to a fraction of context, and **chunk** the class
when it doesn't fit (run pass 2 over sub-batches, then union the flags). Privacy is
unchanged — only already-scrubbed content enters the batch, and blocked/high-risk
submissions are excluded (same invariant as `_draft_submission`'s `usable` filter,
`drafting.py:135-186`).

## Files
- `apps/api/src/classroom_downloader/grading_engine.py` — add an outlier-review
  request/result to the engine protocol (e.g. `review_outliers(OutlierBatchRequest)
  -> list[OutlierFlag]`); mock engine returns a deterministic subset.
- `apps/api/src/classroom_downloader/litellm_engine.py` — implement the batched
  XML prompt + strict-schema parse (gate on `supports_response_schema`); return
  `[{id, reason}]`.
- `apps/api/src/classroom_downloader/grading/drafting.py` — (a) remove/relabel the
  pass-1 `flag` assignment (lines 326-329) so drafting no longer over-flags; (b) add
  a `review_outliers_for_job(...)` step invoked at the end of `draft_grading_job`
  (after the per-submission loop, `drafting.py:464-476`) that runs pass 2, applies
  flags, and refreshes counts (`_refresh_counts` uses `flag` at line 369).
- `apps/api/src/classroom_downloader/routers/grading.py` — the draft SSE stream
  should emit a final "outlier review" phase/event so the UI can show "analisando
  exceções…" and then the flagged set. A new settings flag
  (`CD_GRADING_OUTLIER_REVIEW=on`) lets it be disabled.
- `apps/api/src/classroom_downloader/settings.py` — the toggle + batch-size/context
  knobs (reuse names from the archived plan where sensible).
- Tests: `test_grading.py` (pass-2 applies flags only to the returned ids, others
  cleared), `test_litellm_engine.py` (XML assembly + parse + chunking),
  `test_grading_resume.py` (resume doesn't double-run pass 2).

Frontend (small):
- `apps/web/src/hooks/useGradingJob.ts` — handle the new stream phase/event in
  `continueToGradingDraft` (`useGradingJob.ts:582-623`); update flags when pass 2
  reports.
- `apps/web/src/components/grader/GraderReview.tsx` / `GraderWrap.tsx` — the flag
  badge + "Vale uma segunda olhada" list now reflect only real outliers (no code
  change to the rendering, but verify the empty state reads well when nothing is
  flagged — which should now be common).

## Sequencing with Plan 019 (review while drafting)
019 lets the teacher accept students mid-stream. Pass 2 runs **after** drafting, so
a student may already be reviewed before being flagged as an outlier. Decide the
UX: surface pass-2 flags non-destructively (do **not** un-review or change a score
the teacher already accepted — flag is advisory). Implement pass 2 to **never**
overwrite `final_score`/`reviewed`; it only sets `flag`/reason. If both plans are
scheduled, land 019 first, then make 022 respect reviewed rows.

## Acceptance / STOP
- Backend `uv run pytest` green: a class where everyone did fine yields **zero**
  flags; a planted outlier (wrong exercise / far-below-norm) is the only flagged id;
  chunking is exercised when the batch exceeds the (test-lowered) context fraction;
  privacy/blocked rows never enter the batch.
- The feature is gated by `CD_GRADING_OUTLIER_REVIEW` and off cleanly reverts to
  no-flag drafting.
- Frontend build/test/lint/e2e green; wrap screen's outlier list shows only pass-2
  flags; empty state is graceful.
- No raw submission text or raw model responses logged (existing invariant).
- **STOP** to confirm with the maintainer whether pass-1 `flags` should be fully
  dropped or retained for mechanical (privacy/extraction) issues only — this changes
  what the badge means and is a one-line product decision.


## Implementation log
- Status: DONE (2026-06-24).
- Product STOP resolved by maintainer: pass-1 flags are retained only for mechanical privacy/extraction issues; per-submission LLM review flags no longer drive the outlier badge.
- Added `OutlierBatchRequest` / `OutlierSubmission` / `OutlierFlag` to the grading engine contract, plus deterministic mock outlier review.
- Implemented LiteLLM outlier review with XML submission markers, strict JSON schema when supported, ID filtering, response parsing, and context-aware chunking via `litellm.token_counter`.
- Added the end-of-draft `review_outliers_for_job(...)` pass: it uses scrubbed cached content only, excludes blocked/error rows, preserves `reviewed` and scores, applies only returned outlier reasons to `submission.flag`, clears non-outliers back to privacy/extraction flags, records one `outlier_review` attempt marker, and skips duplicate pass-2 runs on resume.
- Added `CD_GRADING_OUTLIER_REVIEW`, max-submission, and context-fraction settings; the off switch keeps drafting free of outlier flags while preserving mechanical flags.
- Added an SSE `outlier_review` phase and frontend progress handling so review remains active while the final exception pass runs.
- Updated snapshots to expose row AI/privacy status from the latest `grading` attempt only, so extraction/outlier marker attempts do not corrupt row-level status.
- Tests added/updated for pass-2 flag application, disabled mode, blocked-row exclusion, resume idempotency, LiteLLM prompt/parse/chunking/schema calls, and visual/extraction attempt history.
- Verification: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` -> 234 passed, 4 skipped.
- Verification: `pnpm lint` -> 0 errors, 14 existing warnings.
- Verification: `pnpm test:run` -> 26 passed.
- Verification: `pnpm build` -> passed.
- Verification: `pnpm e2e` -> 6 passed.