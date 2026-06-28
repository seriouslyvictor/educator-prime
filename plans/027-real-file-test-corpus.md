# Plan 027 — Real-file test corpus + per-format extraction coverage (and finish plan 018)

> Source: maintainer directive (2026-06-28) — "stop testing with mock files, work
> with real data; from now on always run tests against live files + the usual suite."
> Real corpus supplied at repo-root `test_files/`. Theme: **Testing / grading engine**.
> Priority P1 (unblocks plan 018). Effort **L** (backend tests + mock-provider wiring).
> Base: the plan-018 worktree branch `worktree-agent-ae6cec215aae6d124` (holds the
> uncommitted 018 implementation — see "Already done" below).

## Why
We're shifting from synthetic mock submissions to **real-file testing as a standing
practice**. The trigger: plan 018 (per-criterion score bars) is implemented and
backend-green, but its two *integration* tests can't be exercised because the mock
provider's `course-1/activity-1` submissions are an unextractable PNG + gdoc, so no
submission ever gets an AI score — and therefore no per-criterion scores to assert on.

The maintainer supplied a real corpus at `test_files/` (low/no PII — the maintainer's
own work or very old student submissions; recent code has no PII) spanning docx, xlsx,
pdf, zip, and html/js/css. This plan wires that corpus into the suite, proves every
extraction lane works on real bytes, points plan 018's integration tests at real
gradeable content, and (optionally) runs one **gated** live-LLM grade via `GEMINI_TEST_KEY`.

**Standing policy (already saved to maintainer memory):** tests run against live files
in addition to the usual mock suite. Live-LLM tests are gated on `GEMINI_TEST_KEY` and
skip when it is absent (CI stays green/cost-free). Mock grading engine remains the
default for deterministic, no-cost grading assertions.

**Known gap (out of scope, noted for later):** no **handwriting** samples yet — this
corpus is not the full breadth of inputs the app must handle (handwriting → vision/OCR
lane still needs its own fixtures).

## Already done this session (uncommitted on the 018 worktree)
Do **not** redo these — verify they're present and commit them with this work:
- Plan 018 backend + frontend implementation (per-criterion scores: new
  `GradingSubmissionCriterionScore` table, derived `final_score` review endpoint,
  snapshot exposure, mock distributes sub-scores; editable progress bars in
  `GraderReview.tsx`). Inline styles are clean (only dynamic bar-fill widths).
- `apps/api/openapi.snapshot.json` regenerated for the new `criterion_scores` fields.
- `apps/web/src/types.ts`: `criterion_scores?` made **optional** (matches the
  component's `?? []`), fixing the frontend build break.
- 3 passing engine-contract tests in `test_grading.py`
  (`test_mock_engine_criterion_scores_sum_to_overall_score`,
  `..._omits_criterion_scores_without_criteria`, `..._omits_criterion_scores_when_no_score`).
- 2 integration tests **written but currently failing** (need the corpus — see Step 4):
  `test_draft_persists_criterion_scores_and_review_derives_final_score` (in
  `test_grading.py`) and `test_draft_resume_keeps_one_criterion_score_row_per_criterion`
  (in `test_grading_resume.py`).

## How extraction works (reuse — do not rebuild)
`extract_submission_content(cache_file, *, allow_visual_pending=False)`
(`apps/api/src/classroom_downloader/content_extraction.py:103`) reads
`cache_file.cached_path` from disk and returns
`ExtractedSubmissionContent(status, text, ...)`:
- text/code/html/js/json + `.docx`/`.xlsx` (`_extract_office_content` → `extract_office_text`)
  + `.zip` (`_extract_zip_content` → `extract_zip_submission` / `render_zip_submission_text`)
  → `status="supported"` (or `"degraded"` if truncated/partial), with `text`.
- `.pdf` + images → `status="pending_vision"` when `allow_visual_pending=True`, else `"unsupported"`.
Office deps (`python-docx`, `openpyxl`) are already in `pyproject.toml`; the existing
suite already grades a mock `.docx`/`.xlsx`, so the lanes work in-env.

## Files
- **New:** `apps/api/tests/corpus.py` (path resolver), `apps/api/tests/test_content_extraction.py`,
  `apps/api/tests/test_litellm_live.py` (gated, optional), and committed `test_files/**`.
- **Edit:** `apps/api/src/classroom_downloader/google_provider.py` (new course/activity/files),
  `apps/api/tests/test_grading.py` (point 018 integration test at the corpus),
  `apps/api/tests/test_grading_resume.py` (fix `ensure_default_criteria` call — see Step 4),
  `plans/README.md` (mark 018 DONE; add a 027 row), optionally
  `config/llm-model-overrides.json` (enable a low-cost Gemini model for the live test).

## Steps
1. **Commit the corpus.** Copy `test_files/` into the worktree and commit it (~1 MB, no
   PII). Add `apps/api/tests/corpus.py` exposing `CORPUS_ROOT` (walk up to the repo root
   containing `test_files/`) and a `corpus_path("submissions-office-suite/…")` helper.
2. **Per-format extraction tests** — new `tests/test_content_extraction.py`,
   self-contained: build a `GradingFileCache` with `cached_path` pointed at each real
   file (no provider/network) and assert lane + non-empty text. One test per
   representative format:
   - `.docx` (`PIM_I_FINAL_CORRIGIDO.docx`) → `status in {"supported","degraded"}`, text has expected words.
   - `.xlsx` (`05 - FÓRMULAS E FUNÇÕES.xlsx`) → supported/degraded, non-empty text.
   - `.zip` (`greenfit.zip`) → supported/degraded, rendered tree text non-empty.
   - `.html` + `.js` (`tcc_golpe_zero/index.html`, `script.js`) → supported, text non-empty.
   - `.pdf` (`PIM I - FINAL.pdf`) → `pending_vision` with `allow_visual_pending=True`; `unsupported` without.
   Assert on lane/shape and stable substrings only — never exact char counts.
3. **Wire a real-file corpus into `MockGoogleProvider`** (`google_provider.py`). Add
   **new** entries only (leave `course-1/2` untouched so the ~14 inventory-specific
   tests — which assert membership / specific-activity counts, not totals — keep passing):
   - `ClassroomCourse("course-real", "Projetos Reais", …)` in the module-level `courses` (~L876);
   - `ClassroomActivity("activity-real", "course-real", …)` in `activities` (~L882);
   - `SubmissionFile` entries in `files` (~L940–1025) whose `content` is read from the
     corpus via a **guarded** loader (best-effort: skip silently if a file is missing so
     import never crashes). Map a few real files to distinct synthetic students: docx +
     html (text lane, gradeable), xlsx (text lane), pdf (vision lane), zip (zip lane).
4. **Finish plan 018's integration tests against the corpus.**
   - In `test_grading.py`, point `test_draft_persists_criterion_scores_and_review_derives_final_score`
     at `course-real/activity-real` with criteria `[{Lógica,70},{Estilo,30}]`; select the
     first submission with a non-null `ai_score` (the docx/html); assert its persisted
     `criterion_scores` sum to `ai_score`; POST `/review` with edited per-criterion points
     and assert the derived `final_score` (= sum) and persistence on re-GET.
   - In `test_grading_resume.py`, the idempotency test uses an inline custom provider and
     fails only because it passes **dicts** to `ensure_default_criteria`, which expects
     `GradingCriterionInput` objects (`.name/.weight/.description`). Fix: construct
     `GradingCriterionInput(...)` (or pass `None` for defaults and have the engine return
     criterion names matching `DEFAULT_CRITERIA`). Assert exactly one criterion-score row
     per criterion after drafting twice (no duplicates), summing to the score.
5. **Optional, gated — one live Gemini grade.** New `tests/test_litellm_live.py`,
   `@pytest.mark.skipif(not os.environ.get("GEMINI_TEST_KEY"))`: set `GEMINI_API_KEY` from
   `GEMINI_TEST_KEY`; select/enable a low-cost Gemini model in the catalog/overlay
   (`config/llm-model-overrides.json`; resolve the exact enabled id at implement time);
   build `LiteLlmGradingEngine`; grade one real extracted submission; assert a sane result
   (score ∈ [0,100], confidence ∈ [0,1]; if `supports_response_schema`, `criterion_scores`
   sum ≈ score). Skips cleanly without the key. **This item is droppable** — the rest of
   the plan delivers full real-file extraction + 018 coverage with zero LLM spend.

## Acceptance / STOP
- `cd apps/api && uv run pytest -q` → full suite green (baseline was 235p/4s; expect
  +per-format extraction, +2 unblocked 018 integration tests, +idempotency; live Gemini
  test skipped unless `GEMINI_TEST_KEY` is set).
- With the key set: `uv run pytest tests/test_litellm_live.py -q` → 1 live grade passes.
- Re-confirm the OpenAPI snapshot test passes (already regenerated this session).
- Frontend already green this session — re-confirm: `pnpm --filter web build` ✓,
  `lint` ✓ (0 errors), `test` ✓ (28), and run `e2e`.
- Commit logically (corpus + extraction infra; then 018 impl + tests), mark plan 018
  **DONE** and add a 027 row in `plans/README.md`. **Do NOT merge or push** — the
  maintainer reviews. Plan 015's login screen is already committed on its own branch and
  is out of scope here.
