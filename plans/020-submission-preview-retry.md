# Plan 020 — Retry a failed submission preview

> Source: Notion TODO "Ao falhar uma pré-visualização, deve ser possível tentar
> novamente exibir aquela tarefa, no exemplo abaixo não há opção para tentar
> novamente" (with a screenshot of a preview that failed with no retry control).
> Theme: **C — Grading review screen**. Priority P2. Effort S. Depends on: none.
> Base: branch off `main` @ `6d6b264`.

## Why
This is about the **document preview** rendering failing (loading the student's
file into the review pane), **not** the AI being unable to grade — the AI-blocked
case already has a retry (`BlockedEvidence`, `SubmissionPreview.tsx:227-265`,
shown via `GraderReview.tsx:258-259`). The preview renderers have inconsistent
error handling:
- **Image** (`SubmissionPreview.tsx:130-135`): a bare `<img src={url}>` with **no
  `onError`** — a failed image silently shows a broken image, no retry.
- **PDF** (line 140-141): a bare `<iframe>` — **no error handling**, no retry.
- **Text/code** (`SubmissionTextPreview`, lines 157-225): does catch fetch errors
  and shows a message, but offers **only "Baixar original"**, no **retry**.

The preview URL is stable (`api.submissionPreviewUrl(job.id, submission.id,
file.source_file_id)`); a transient 5xx/network blip leaves the teacher stuck with
no way to re-attempt short of switching students and back.

## Files
- `apps/web/src/components/grader/review/SubmissionPreview.tsx` — all three
  renderers (`SubmissionPreview` image/pdf branches, `SubmissionTextPreview`).

## Steps
1. **Image:** wrap the `<img>` in a small component with `onError` →
   error state showing a "Não foi possível carregar a previsualização" message + a
   **"Tentar novamente"** button. Retry by forcing a reload — bump a cache-busting
   nonce on the `src` (e.g. `?r=${attempt}`) so the browser re-requests rather than
   reusing the failed response. Reset state when `submission.id`/`file` changes.
2. **PDF:** same pattern around the `<iframe>` (`onError`, or a load-timeout guard
   since iframes don't always fire `onError` for failed loads). Provide a retry
   (re-key the iframe / nonce) and keep "Baixar original" as a fallback.
3. **Text/code:** in `SubmissionTextPreview`'s error branch (line 214-217), add a
   **"Tentar novamente"** button next to the message that re-runs the fetch (lift
   the fetch into a callback keyed by an `attempt` counter so the button can
   re-trigger the `useEffect`).
4. Keep the existing download fallback in every state — retry and download are
   complementary.
5. Make the retry control a shared small subcomponent (e.g. `PreviewErrorState`
   with `message` + `onRetry`) to avoid three copies.

## Notes
- This is preview-only; do **not** touch the AI retry (`onRetry` →
  `retryGradingDraft`) or `BlockedEvidence`.
- Don't retry automatically in a loop — one explicit teacher-triggered retry per
  attempt (a runaway auto-retry would hammer the preview endpoint).

## Acceptance
- Build/test/lint green.
- A unit/component test (or e2e in mock mode) that simulates a failing preview
  response and asserts the retry control appears and re-requests on click.
- Manual: force a preview 500 (or offline), confirm each of image/pdf/text shows a
  retry that recovers once the resource is reachable again.
