# Plan 026: Stop the Turmas activities list from blocking on one Classroom call per activity

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 9bac651..HEAD -- apps/api/src/classroom_downloader/routers/courses.py apps/api/src/classroom_downloader/schemas.py apps/web/src/lib/api.ts apps/web/src/hooks/useExportWorkspace.ts`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Planned at**: commit `9bac651`, 2026-06-24

## Why this matters

Plan 016 (grade-awareness) made the activities endpoint compute graded/ungraded
counts by calling the Google Classroom `studentSubmissions.list` API **once per
activity**. This now happens on **every** response from
`GET /api/courses/{course_id}/activities`, including the fast path that serves
activities straight from the local DB cache. For a course with N assignments,
opening Turmas fires **N sequential Classroom API calls** (each possibly
multi-page) on a cold grade-summary cache (30-minute TTL). Before plan 016 the
endpoint returned cached rows with **zero** Classroom calls.

Concretely: a teacher opening a class with 30 assignments waits on ~30 serialized
network round-trips before the activity list renders, and burns Classroom API
quota doing it — a latency spike and a rate-limit risk that scales with class size.

The counts are a *nice-to-have decoration* on each row (a "X/Y corrigidas" chip),
not data the list needs to render. So they should be fetched **lazily, off the
critical render path**: return the activity list immediately (fast, no Classroom
calls), then fetch the grade summaries in a second request and merge the counts in
when they arrive. The list paints instantly; the chips fill in a moment later.

This is the alternative the plan-016 author explicitly anticipated ("or add
`GET /api/courses/{course_id}/activities/grade-summary`").

## Current state

The N+1 was introduced by `_activity_read_rows`, called on every return path of
`list_activities` (`apps/api/src/classroom_downloader/routers/courses.py`):

```python
# courses.py:25-45 — runs the per-activity Classroom calls on EVERY response
def _activity_read_rows(provider: GoogleProvider, course_id: str, activities: list[Activity]) -> list[ActivityRead]:
    summaries = provider.submission_grade_summary(course_id, [activity.id for activity in activities])  # N calls
    rows: list[ActivityRead] = []
    for activity in activities:
        summary = summaries.get(activity.id)
        rows.append(ActivityRead(
            id=activity.id, course_id=activity.course_id, title=activity.title,
            work_type=activity.work_type, state=activity.state, due_label=activity.due_label,
            description=activity.description,
            total_submissions=summary.total if summary else 0,
            graded_submissions=summary.graded if summary else 0,
            ungraded_submissions=summary.ungraded if summary else 0,
            concluded=summary.concluded if summary else False,
        ))
    return rows
```

`_activity_read_rows` is called at `courses.py:127` (DB-cache-hit path), `:141`
(stale-fallback), and `:174` (fresh-fetch). The real provider's
`submission_grade_summary` (`google_provider.py:673-695`) loops the activity ids and
page-walks `studentSubmissions` for each, caching per `(course, activity)` for
`google_profile_cache_ttl_minutes` (30 min).

`ActivityRead` already defaults every count field, so an activity row is valid with
no summary attached (`apps/api/src/classroom_downloader/schemas.py:15-26`):

```python
class ActivityRead(BaseModel):
    id: str
    course_id: str
    title: str
    work_type: str
    state: str
    due_label: str | None = None
    description: str | None = None
    total_submissions: int = 0
    graded_submissions: int = 0
    ungraded_submissions: int = 0
    concluded: bool = False
```

The provider already exposes exactly the map this needs —
`provider.submission_grade_summary(course_id, activity_ids) -> dict[str, SubmissionGradeSummary]`
where `SubmissionGradeSummary` has `.total/.graded/.ungraded` and a `.concluded`
property (`google_provider.py:210-219`).

Frontend — the activities loader (`apps/web/src/hooks/useExportWorkspace.ts:93-109`):

```ts
async function loadActivities(courseId: string) {
  setActivitiesLoading(true);
  setError(null);
  setSelectedActivityIds([]);
  setJob(null);
  try {
    const activityList = await api.activities(courseId);
    setActivities(activityList);
    setSelectedActivityIds([]);
    await loadGradingQueue();
  } catch (caught) {
    setActivities([]);
    setError(appError(caught, "Falha ao carregar atividades."));
  } finally {
    setActivitiesLoading(false);
  }
}
```

The API client (`apps/web/src/lib/api.ts:263-267`) — note the `request<T>(path, init, { ttlMs })`
shape used throughout:

```ts
courses: () => request<Course[]>("/api/courses", undefined, { ttlMs: 120_000 }),
activities: (courseId: string) =>
  request<Activity[]>(`/api/courses/${courseId}/activities`, undefined, { ttlMs: 120_000 }),
```

`ActivityList.tsx:99-110` renders the chips from `activity.total_submissions`,
`activity.graded_submissions`, and `activity.concluded` — it shows the
"X/Y corrigidas" chip only when `total_submissions > 0`, so a zero-count activity
simply shows no chip until the summary merges in. The `Activity` type already has
`graded_submissions?`, `ungraded_submissions?`, `concluded?` (`types.ts:87-89`) and
required `total_submissions/graded_submissions/ungraded_submissions/concluded`
(`types.ts:40-42`).

Conventions to follow:

- New FastAPI route: add it next to `list_activities` in `courses.py`, mirror its
  dependency injection (`get_session`, `provider_dependency`, `get_current_session`)
  and its `user_email`-scoped access pattern. Return a Pydantic model from
  `schemas.py`.
- API client methods live in the `api` object in `lib/api.ts`; reuse the `request<T>`
  helper. Use a short `ttlMs` (e.g. `30_000`) for the summary call so counts refresh
  reasonably without hammering.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Backend tests | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` (from `apps/api`) | all pass |
| Backend, scoped | `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q apps/api/tests/test_api.py` (from `apps/api`) | all pass |
| OpenAPI snapshot | the suite includes an OpenAPI snapshot test; if it fails it will tell you to regenerate — follow the repo's existing regen step (see STOP conditions) | snapshot test passes |
| Frontend lint | `pnpm lint` (from `apps/web`) | exit 0, no new errors |
| Frontend build | `pnpm build` (from `apps/web`) | exit 0 |
| Frontend e2e | `pnpm e2e` (from `apps/web`) | all pass |

## Scope

**In scope**:
- `apps/api/src/classroom_downloader/routers/courses.py` (stop inline summary calls; add the lazy endpoint)
- `apps/api/src/classroom_downloader/schemas.py` (add the summary response model)
- `apps/api/openapi.snapshot.json` (regenerate if the snapshot test requires it — via the repo's documented regen, not hand-editing)
- `apps/api/tests/test_api.py` (update the grade-count assertions to the new endpoint; keep coverage)
- `apps/web/src/lib/api.ts` (add the summary fetch)
- `apps/web/src/hooks/useExportWorkspace.ts` (fetch + merge summaries after activities load)

**Out of scope** (do NOT touch):
- `apps/api/src/classroom_downloader/google_provider.py` — the provider's
  `submission_grade_summary` is reused as-is; do not change its caching or the
  graded rule.
- The grading-scope (`remaining`/`all`) logic — unrelated to this change.
- `ActivityList.tsx` / `TurmasView.tsx` rendering — they already read the count
  fields and tolerate zeros; no change needed.
- The `concluded`-driven "Reclassificar" button label logic — it already keys off
  `activity.concluded`, which will populate after the merge.

## Git workflow

- Branch: `advisor/026-lazy-activity-grade-summaries`
- Commit per logical unit (backend, then frontend) or one cohesive commit; message
  style matches `git log` (e.g. `perf(api): fetch Turmas grade summaries lazily off the activities path`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the grade-summary response model

In `apps/api/src/classroom_downloader/schemas.py`, add:

```python
class ActivityGradeSummaryRead(BaseModel):
    activity_id: str
    total_submissions: int = 0
    graded_submissions: int = 0
    ungraded_submissions: int = 0
    concluded: bool = False
```

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q apps/api/tests/test_api.py` (from `apps/api`) — still passes (no behavior change yet).

### Step 2: Make `list_activities` fast again (no inline Classroom calls)

In `courses.py`, change `_activity_read_rows` so it builds `ActivityRead` rows from
the activities **without** calling `provider.submission_grade_summary` — let the
count fields fall to their schema defaults (0 / False). Keep all three call sites
(`:127`, `:141`, `:174`) but they now do zero Classroom work for counts.

Replace the body of `_activity_read_rows` so it no longer takes/uses `provider` for
summaries (you may keep the signature and simply stop calling the provider, or drop
the `provider` argument and update the three call sites — prefer dropping it for
clarity).

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q apps/api/tests/test_api.py` — the existing test that asserts counts on the activities response (around `test_api.py:55-65`) will now **fail** because counts are no longer inline. That failure is expected here; you fix it in Step 4. Confirm the *only* failures are the grade-count assertions.

### Step 3: Add the lazy grade-summary endpoint

In `courses.py`, add:

```python
@router.get(
    "/api/courses/{course_id}/activities/grade-summary",
    response_model=list[ActivityGradeSummaryRead],
)
def activity_grade_summary(
    course_id: str,
    session: Session = Depends(get_session),
    provider: GoogleProvider = Depends(provider_dependency),
    current_session: UserSession = Depends(get_current_session),
) -> list[ActivityGradeSummaryRead]:
    user_email = current_session.user_email
    activities = session.exec(
        select(Activity)
        .where(Activity.course_id == course_id)
        .where(Activity.user_email == user_email)
    ).all()
    summaries = provider.submission_grade_summary(course_id, [a.id for a in activities])
    rows: list[ActivityGradeSummaryRead] = []
    for activity in activities:
        summary = summaries.get(activity.id)
        rows.append(ActivityGradeSummaryRead(
            activity_id=activity.id,
            total_submissions=summary.total if summary else 0,
            graded_submissions=summary.graded if summary else 0,
            ungraded_submissions=summary.ungraded if summary else 0,
            concluded=summary.concluded if summary else False,
        ))
    return rows
```

Match the `user_email`-scoped query pattern already in this file. Import
`ActivityGradeSummaryRead` from `..schemas`.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q apps/api/tests/test_api.py` — still only the count-assertion failures from Step 2 remain.

### Step 4: Move the backend count assertions to the new endpoint

In `apps/api/tests/test_api.py`, update the test that currently asserts
graded/ungraded/concluded on the `/activities` response (it reads
`rows["activity-1"]["concluded"]` etc. around `test_api.py:55-65`) so that:

- the `/activities` response no longer carries non-zero counts (or simply stop
  asserting counts there), and
- a new assertion hits `GET /api/courses/{course_id}/activities/grade-summary` and
  checks the same graded/ungraded/concluded values it used to check inline.

Keep the same coverage of the partial/concluded classification — just sourced from
the new endpoint.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q apps/api/tests/test_api.py` → all pass.

### Step 5: Regenerate the OpenAPI snapshot if required

The suite has an OpenAPI snapshot test (`apps/api/openapi.snapshot.json`). The new
route + schema will change it. Regenerate it the way the repo already does (look for
a snapshot-update marker in the failing test's message or a script/fixture that
writes `openapi.snapshot.json`). Do **not** hand-edit the JSON.

**Verify**: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` (from `apps/api`) → full suite passes, snapshot included.

### Step 6: Frontend — add the summary fetch

In `apps/web/src/lib/api.ts`, add to the `api` object:

```ts
activityGradeSummaries: (courseId: string) =>
  request<{
    activity_id: string;
    total_submissions: number;
    graded_submissions: number;
    ungraded_submissions: number;
    concluded: boolean;
  }[]>(`/api/courses/${courseId}/activities/grade-summary`, undefined, { ttlMs: 30_000 }),
```

**Verify**: `pnpm build` (from `apps/web`) → exit 0 (type-checks the new method).

### Step 7: Frontend — merge summaries after activities render

In `apps/web/src/hooks/useExportWorkspace.ts`, in `loadActivities`, after
`setActivities(activityList)` and the existing flow, fetch the summaries
**without blocking the initial render** and merge them into state by `activity.id`.
Do not let a summary failure clear the activity list — the list already rendered.
Example shape:

```ts
const activityList = await api.activities(courseId);
setActivities(activityList);
setSelectedActivityIds([]);
await loadGradingQueue();
// Lazy, non-blocking: counts are decoration; a failure must not wipe the list.
void api
  .activityGradeSummaries(courseId)
  .then((summaries) => {
    const byId = new Map(summaries.map((s) => [s.activity_id, s]));
    setActivities((current) =>
      current.map((a) => {
        const s = byId.get(a.id);
        return s
          ? {
              ...a,
              total_submissions: s.total_submissions,
              graded_submissions: s.graded_submissions,
              ungraded_submissions: s.ungraded_submissions,
              concluded: s.concluded,
            }
          : a;
      }),
    );
  })
  .catch(() => {
    /* counts are best-effort; leave activities as-is */
  });
```

Guard against a stale merge if the user switched courses before the summary
resolved: only merge when the merged activities still belong to `courseId` — e.g.
check `current[0]?.course_id === courseId` inside the `setActivities` updater before
mapping, or capture the selected course id and bail if it changed. Pick whichever
matches the hook's existing patterns; do not introduce a new state library.

**Verify**:
- `pnpm lint` (from `apps/web`) → exit 0, no new errors.
- `pnpm build` (from `apps/web`) → exit 0.

### Step 8: Frontend behavior check

**Verify**: `pnpm e2e` (from `apps/web`) → all pass. (The existing
`submission-preview-retry.spec.ts` stubs `**/api/courses/.../activities**` with
inline counts; that glob still matches the activities route and the test does not
assert on the new summary endpoint, so it remains green. If any e2e calls the new
endpoint and 404s noisily, add a stub returning `[]` — but do not change
assertions.)

## Test plan

- Backend: update `apps/api/tests/test_api.py` so the graded/ungraded/concluded
  coverage now asserts against `GET /api/courses/{course_id}/activities/grade-summary`
  (partial → non-zero graded < total; fully graded → `concluded: true`). Keep a
  check that the `/activities` response itself is cheap (counts default to 0).
  Pattern: the existing activities test in the same file.
- Frontend: no new unit test required (the merge is plumbing); `pnpm build` +
  `pnpm e2e` are the gates.
- Verification: `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` and
  `pnpm e2e` both pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "submission_grade_summary" apps/api/src/classroom_downloader/routers/courses.py` shows it called **only** inside the new `activity_grade_summary` endpoint, **not** in `_activity_read_rows` / `list_activities`.
- [ ] `GET /api/courses/{course_id}/activities/grade-summary` exists and returns the per-activity counts (covered by an updated `test_api.py` assertion).
- [ ] `CD_GOOGLE_PROVIDER=mock uv run --extra dev pytest -q` (from `apps/api`) exits 0, snapshot included.
- [ ] `pnpm lint` (from `apps/web`) exits 0; `pnpm build` exits 0; `pnpm e2e` passes.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row for plan 026 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The "Current state" excerpts don't match the live code (drift since `9bac651`).
- You cannot find how the OpenAPI snapshot is regenerated (no script, no
  update-on-fail marker). Do **not** hand-edit `openapi.snapshot.json` — report it
  so the operator can point you at the regen step.
- Removing the inline summaries breaks a test you did not anticipate (something
  besides the activities count assertions depends on counts being inline) — report
  what depends on it rather than re-adding the N+1.
- The frontend merge would require restructuring the hook's state model (more than
  adding the fetch + a `setActivities` map) — report it; the change should be
  additive.

## Maintenance notes

- The counts now arrive a beat after the list renders — that's intended. If a future
  change needs counts to be present on first paint (e.g. server-side sorting by
  graded ratio), this lazy split must be revisited; do not move the summary calls
  back onto the blocking `/activities` path without bounding them.
- The provider's per-activity Classroom calls still exist; they're just off the
  render path now and protected by the 30-minute summary cache. If a single course
  routinely has very many activities and the lazy fetch itself becomes slow, the
  next step is to parallelize `submission_grade_summary` — but note the Google API
  client is not thread-safe, so that needs per-thread service construction, which is
  why it's deferred here.
- The summary cache is not invalidated when grades are posted through the tool, so
  counts can lag up to 30 minutes after guided posting. Acceptable today; flagged
  here for whoever wires up post-posting refresh.
- Reviewer should confirm the frontend merge is guarded against course-switch races
  (a summary for course A must not merge onto course B's activities).
