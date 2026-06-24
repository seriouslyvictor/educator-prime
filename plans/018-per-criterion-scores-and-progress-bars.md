# Plan 018 — Per-criterion scores as editable progress bars (points, not %)

> Source: Notion TODO "Ainda na mesma tela (grading view) a visualização das
> rubricas deve ser por barra de progresso, assim como no design original, e não
> deve ser mostrado % e sim quantos pontos o aluno fez em cada etapa, com
> possibilidade de edição do professor. Verificar com MCP como as rubricas estão
> desenhadas no design."
> Theme: **C — Grading review screen**. Priority P2. Effort **L** (backend +
> frontend). Depends on: none, but see ordering note with Plan 017.
> Base: branch off `main` @ `6d6b264`.

## Why
Today the review breakdown shows each criterion's **weight** as a percentage and an
optional AI note (`GraderReview.tsx:338-348`: `<span className="bd-weight">
{criterion.weight}%</span>` + `latest_ai_note`). The maintainer wants instead a
**progress bar per criterion showing the points the student earned on that
criterion** (e.g. 24/30), editable by the teacher — matching the "design original".

## The blocker: there are no per-criterion scores yet
`GradingEngineResult` carries `score` (overall), `confidence`, `feedback`,
`flags`, and `criterion_notes` (notes only) — **no per-criterion sub-scores**
(`grading_engine.py:27-34`). `GradingCriterion` (`types.ts:84-90`,
`models.py`) has `name/weight/description/latest_ai_note`, no score. So a
points-per-criterion bar requires the engine to **return** per-criterion scores and
the system to **persist + expose** them. This is the real work; the bar is the easy
part.

## Design reference (operator action required)
"Verificar com MCP como as rubricas estão desenhadas no design" points at the
**Educator Prime** design MCP, which is **not available in the agent
environment**. Before building the visual, the operator must supply the target
rubric/progress-bar design (screenshot or spec). If unavailable, implement the data
path (below) and render a minimal accessible progress bar
(`earned / max` per criterion), then **STOP for design review**.

## Data model: points per criterion
Each criterion's max points = its `weight` (weights already sum to 100, so a
criterion with weight 30 is worth 30 points and the job is out of 100). The
student's earned points per criterion must be produced by the engine and stored
per submission (per-criterion, per-submission — not on the shared `GradingCriterion`
row, which is job-level).

## Files
Backend:
- `apps/api/src/classroom_downloader/grading_engine.py` — add
  `criterion_scores: list[{name, earned}] | None` to `GradingEngineResult`; mock
  engine produces plausible sub-scores that sum to `score`.
- `apps/api/src/classroom_downloader/litellm_engine.py` — extend the response
  schema + `_build_messages` prompt to request a per-criterion `earned` (0..weight)
  for each criterion, and parse it in `parse_litellm_result`. Gate on
  `supports_response_schema` like the existing structured-output path; degrade
  gracefully (omit sub-scores) when the model returns none.
- `apps/api/src/classroom_downloader/models.py` — add a per-submission per-criterion
  score store. Prefer a `GradingSubmissionCriterionScore` table
  (`submission_id, criterion_id, earned`) over JSON, mirroring existing additive
  dev-migrations in `database.py` (`_ensure_*_columns`).
- `apps/api/src/classroom_downloader/grading/drafting.py` — persist the per-criterion
  scores alongside `_apply_criterion_notes` (`drafting.py:309`); include them when
  a teacher review overwrites a score (see review endpoint below).
- `apps/api/src/classroom_downloader/routers/grading.py` — include per-criterion
  scores in the submission snapshot; accept teacher edits to them on the review
  endpoint (`reviewGradingSubmission`), recomputing the overall `final_score` as the
  sum of edited criterion points (keep it consistent with the score field).
- `apps/api/src/classroom_downloader/grading/snapshots.py` — add scores to
  `grading_submission_snapshot`.
- Tests: `test_litellm_engine.py` / `test_grading.py` for schema + persistence;
  `test_grading_resume.py` for migration safety.

Frontend:
- `apps/web/src/types.ts` — add `criterion_scores` (per criterion `{criterion_id,
  earned}`) to `GradingSubmission`.
- `apps/web/src/components/grader/GraderReview.tsx` — replace the `bd-weight`
  percentage with a progress bar: filled to `earned / weight`, labelled
  `earned/weight` points, editable (input or drag) by the teacher, feeding back
  into the accept payload.
- `apps/web/src/hooks/useGradingJob.ts` / `lib/api.ts` — thread edited per-criterion
  points through `acceptGradingDraft` → `reviewGradingSubmission`.

## Steps
1. Backend schema first: add `criterion_scores` to the result + a strict schema
   field; make the **mock** engine emit sub-scores that sum to the overall score so
   the whole UI is exercisable in mock mode/CI without a real provider.
2. Persistence + migration: new table, additive dev-migration, snapshot includes
   the scores. Resume/retry paths preserve them.
3. Review endpoint accepts teacher edits to per-criterion points and keeps
   `final_score` = sum (single source of truth — decide and document whether the
   overall score is derived from the parts or independent; recommend **derived**).
4. Frontend: progress bars with point labels, editable, wired to accept.
5. Fold in Plan 017's brief-mode gate if 017 hasn't landed: brief mode shows no
   bars (no criteria).

## Acceptance / STOP
- Backend `uv run pytest` green incl. new schema/persistence/migration tests; no
  real provider calls in CI (mock emits sub-scores).
- Frontend build/test/lint/e2e green; bars render with points and are editable;
  editing a criterion updates the overall score; brief mode shows no bars.
- **STOP for design review** before merge if the Educator Prime rubric design could
  not be obtained.
- This is the largest plan in the polish pass — land the backend data path behind
  the existing structured-output gate first; the UI is safe to iterate on after.
