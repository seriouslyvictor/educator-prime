# Plan 025: Add e2e coverage for image and PDF preview retry, including the PDF load-timeout regression

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 9bac651..HEAD -- apps/web/src/components/grader/review/SubmissionPreview.tsx apps/web/e2e/submission-preview-retry.spec.ts`
> If either in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Why this matters

Plan 020 added retry controls to the three submission-preview renderers (image,
PDF, text). Only the **text** path has an e2e test
(`e2e/submission-preview-retry.spec.ts`). The image and PDF paths shipped with
**zero** coverage — and that gap directly caused a real bug: the PDF renderer used
an 8-second load-timeout guard that flipped a *successfully loaded* PDF into the
error state, because the iframe's `onLoad` handler called `setFailed(false)` (a
no-op when already `false`), so the timer was never cleared. That bug was fixed by
adding a `loaded` flag, but **nothing tests it**, so it can silently regress.

This plan adds two deterministic Playwright tests in mock mode: (1) an image
preview that fails then recovers on retry, and (2) a PDF preview that loads
successfully and **stays visible past the 8-second timeout** (the regression
guard). These follow the exact pattern of the existing text-preview spec.

## Current state

Files:

- `apps/web/src/components/grader/review/SubmissionPreview.tsx` — the three preview
  renderers. The fix this plan guards is in `PdfPreview`:

```tsx
// SubmissionPreview.tsx — PdfPreview (current, fixed shape)
function PdfPreview({ url, title }: { url: string; title: string }) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    setAttempt(0);
    setFailed(false);
    setLoaded(false);
  }, [url]);
  useEffect(() => {
    if (failed || loaded) return;
    const timeout = window.setTimeout(() => setFailed(true), 8000);
    return () => window.clearTimeout(timeout);
  }, [attempt, failed, loaded]);
  ...
  return <iframe key={attempt} className="preview-frame" src={src} title={title} onLoad={() => setLoaded(true)} />;
}
```

The image renderer uses a bare `<img onError={() => setFailed(true)}>` and a shared
`PreviewErrorState` with a **"Tentar novamente"** button that bumps a cache-busting
`?r=<attempt>` nonce. The error UI text is
`"Não foi possível carregar a previsualização."`.

- `apps/web/e2e/submission-preview-retry.spec.ts` — the existing spec to copy. It:
  - stubs `/api/auth/me`, `/api/grading/health`, `/api/courses`,
    `/api/courses/.../activities`, the grading job + privacy-audit/draft SSE streams,
    and the preview endpoint;
  - drives the UI from the workspace into the grader review screen;
  - asserts the retry button appears on failure, recovers on click, and the preview
    endpoint was requested at least twice.

The preview URL the renderers hit is
`/api/grading/jobs/<jobId>/submissions/<submissionId>/preview?file=<sourceFileId>`
(matched in the spec with the glob `**/api/grading/jobs/job-preview/submissions/sub-1/preview**`).

Conventions to follow:

- Tests are Playwright specs in `apps/web/e2e/`, run with `pnpm e2e`. Each test
  uses `page.route(...)` to stub every network call (mock mode, fully
  deterministic) — no real backend.
- To switch a submission's MIME so the renderer picks a different branch, set
  `mime_type` and the `files[0].mime_type` on the submission object (the
  `submission(...)` factory at the top of the existing spec). `image/png` →
  `ImagePreview`; `application/pdf` → `PdfPreview`.
- Reuse the existing spec's helper functions (`submission`, `sse`) and the full set
  of `page.route` stubs verbatim — only the submission MIME, the preview-route
  fulfillment, and the assertions change per test.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run the new spec only | `pnpm e2e e2e/submission-preview-retry.spec.ts` (from `apps/web`) | all tests in file pass |
| Run full e2e suite | `pnpm e2e` (from `apps/web`) | all pass (was 6; now 8 with the two new tests) |
| Lint | `pnpm lint` (from `apps/web`) | exit 0 (14 pre-existing warnings allowed, 0 errors) |

(The repo has **no** React Testing Library / component-test harness — `jsdom` is
present but unused, and every `*.test.ts` is pure logic. Do **not** introduce a
component-test setup; preview rendering is browser behavior and belongs in
Playwright e2e, matching the existing text-preview test.)

## Scope

**In scope** (the only file you should modify):
- `apps/web/e2e/submission-preview-retry.spec.ts` (add two tests to the existing file)

**Out of scope** (do NOT touch):
- `apps/web/src/components/grader/review/SubmissionPreview.tsx` — this plan only
  adds tests; it does not change the component. (If a test reveals the component is
  wrong, that is a STOP condition, not a fix-in-place.)
- Any other e2e spec, the Playwright config, or `package.json`.

## Git workflow

- Branch: `advisor/025-preview-retry-e2e-coverage`
- One commit; message style matches `git log` (e.g. `test(web): cover image + PDF preview retry e2e`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add an image-preview retry test

In `apps/web/e2e/submission-preview-retry.spec.ts`, add a second `test(...)` that
duplicates the existing test's setup but makes the submission an image:

- In the submission object, set `mime_type: "image/png"` and
  `files: [{ source_file_id: "sub-1-file", source_name: "Ana.png", mime_type: "image/png" }]`.
- Keep the failing-then-recovering preview route: first response `status: 500`,
  then after the retry click, a `200` with a tiny valid PNG body
  (`contentType: "image/png"`, body can be any non-empty buffer — the test asserts
  on the retry control and request count, not pixels).
- Assertions:
  - The **"Tentar novamente"** button is visible after the image fails to load
    (the `<img onError>` fires on the 500).
  - After clicking it, the preview endpoint is requested again
    (`previewRequests >= 2`) — the cache-busting nonce forces a re-request.

Note: an `<img>` pointing at a 500 fires `onError` in Chromium, which is what flips
the renderer into the error state — so the failing route is enough to surface the
retry control. If the error button does not appear, see STOP conditions.

**Verify**: `pnpm e2e e2e/submission-preview-retry.spec.ts` (from `apps/web`) → the new image test passes.

### Step 2: Add a PDF success-past-timeout regression test

Add a third `test(...)` that makes the submission a PDF and asserts it does **not**
flip to the error state after the 8-second guard:

- In the submission object, set `mime_type: "application/pdf"` and
  `files: [{ source_file_id: "sub-1-file", source_name: "Ana.pdf", mime_type: "application/pdf" }]`.
- Make the preview route **succeed immediately** with a minimal valid PDF:
  `contentType: "application/pdf"`, body = a minimal PDF byte string (a one-page
  `%PDF-1.4 ... %%EOF` literal is sufficient; the iframe just needs to fire
  `onLoad`).
- Assertions:
  - The `iframe.preview-frame` is visible after load.
  - The error text `"Não foi possível carregar a previsualização."` is **not**
    present.
  - Wait past the timeout: `await page.waitForTimeout(9000);` then assert **again**
    that the error text is still **not** present and the iframe is still visible.
    (This is the regression: before the `loaded`-flag fix, the iframe was replaced
    by the error state at the 8s mark even though it had loaded.)

Use a locator like `page.locator("iframe.preview-frame")` for visibility and
`page.getByText("Não foi possível carregar a previsualização.")` with
`.not.toBeVisible()` for the negative assertion.

**Verify**: `pnpm e2e e2e/submission-preview-retry.spec.ts` (from `apps/web`) → all three tests pass (this one takes ~10s due to the deliberate wait).

### Step 3: Full suite + lint green

**Verify**:
- `pnpm e2e` (from `apps/web`) → all pass (was 6, now 8).
- `pnpm lint` (from `apps/web`) → exit 0, no new errors.

## Test plan

- Two new tests in the existing `apps/web/e2e/submission-preview-retry.spec.ts`:
  1. `retries a failed image submission preview` — image `onError` → retry control →
     re-request.
  2. `keeps a loaded PDF preview visible past the load timeout` — the regression
     guard for the `loaded`-flag fix.
- Pattern source: the existing `retries a failed text submission preview` test in
  the same file (reuse its `submission`/`sse` helpers and route stubs).
- Verification: `pnpm e2e` → 8 tests pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `pnpm e2e` (from `apps/web`) exits 0 with 8 tests (was 6).
- [ ] `pnpm lint` (from `apps/web`) exits 0 (0 errors; the 14 pre-existing warnings are fine).
- [ ] `grep -c "^test(" apps/web/e2e/submission-preview-retry.spec.ts` returns 3.
- [ ] No files outside `apps/web/e2e/submission-preview-retry.spec.ts` are modified (`git status`).
- [ ] `plans/README.md` status row for plan 025 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The `PdfPreview` excerpt in "Current state" does not match the live
  `SubmissionPreview.tsx` (e.g. there is no `loaded` state) — the fix this test
  guards may not be present; report it rather than testing the wrong shape.
- The PDF test fails because the iframe never fires `onLoad` for the stubbed PDF in
  headless Chromium (some PDF bodies don't trigger `onLoad`). If so, report it —
  do **not** weaken the assertion or change the component; the executor may need a
  different minimal-PDF body, which is a judgment call to surface.
- The image error control never appears on a 500 response. Report it — do not change
  the component to make the test pass.

## Maintenance notes

- The PDF test includes a deliberate `waitForTimeout(9000)` to cross the component's
  hardcoded 8000ms guard. If that guard's duration changes in
  `SubmissionPreview.tsx`, update the wait to stay above it.
- Reviewer should confirm the PDF test actually asserts **after** the timeout window
  (the negative assertion post-`waitForTimeout`), not only at load time — the
  before-timeout assertion alone would not catch the regression.
- These are the first e2e tests that exercise non-text preview branches; if more
  preview MIME types are added to `SubmissionPreview.tsx`, extend this file.
