# Plan — Grader queue item management (per-card menu + multi-select "Gerenciar")

> **Status:** implemented for review.
> **Audience:** an executing agent with no prior context. Read §0–§9 before touching code.
> **Line numbers / symbol locations are as-of-writing guides — re-derive every location with
> `grep -n` at execution time.**
> **Relationship to other plans:** independent of `plan-observability.md`, but both add columns
> via `database.py`'s dev-migration shim and both touch `models.py` + `schemas.py`. No logical
> conflict (different columns, different schema classes). If both are in flight, land this one's
> Phase 1 first or rebase its one-line `_ensure_grading_job_columns` addition carefully — it is
> the only true collision point. Does **not** depend on `plan-image-grading.md` (already
> complete on this branch).
> **Styling stance:** this plan deliberately uses the project's **existing** UI patterns
> (`ui.tsx`, `icons.tsx`, global-by-name classes in `Grader.module.css`). It does **not**
> introduce shadcn/Tailwind — that is a separate future migration. Decision recorded after
> establishing that shadcn is not yet in `apps/web` (no `components.json`, no Tailwind) and that
> `plan-observability.md` scopes its shadcn fold-in to the admin area only.

---

## 0. Goal & context

The grader queue (`apps/web/src/components/grader/GraderQueue.tsx`, rendered at `App.tsx`'s
`view === "graderQueue"`) lists activities the teacher can correct with AI. Today a queue card
is a single `<button>` whose only action is "open" — there is **no way to manage an item**
(discard drafts, remove it, declutter the list). A design prototype in `docs/UI/grader/` shows
two complementary affordances that we want to ship **together** on this screen:

1. **Per-card "⋯" menu** — a kebab on each card opening four management actions
   (`docs/UI/grader/queue.jsx` `manageActions()` / `CardMenu`):
   *Reiniciar do zero*, *Remover da fila*, *Arquivar*, *Ocultar da visualização*.
2. **"Gerenciar" multi-select mode** — a top-bar toggle that turns cards into checkboxes and
   shows a floating bulk-action bar applying the same four actions to a selection
   (`queue.jsx` `QueueView` `manageMode` + `qc-bulkbar`).

The prototype presents these as mutually-exclusive variants (`manageStyle` tweak: menu / inline
/ bulk). **We are combining the per-card menu and the bulk multi-select into one screen.**

### Where the queue comes from (the load-bearing fact)

`App.tsx` builds `queueItems` (≈ line 180) from two sources, deduped by `activity_id`:

- **Pending items** — activities just sent from Turmas, held in **in-memory React state**
  (`pendingQueue`, `App.tsx:147`). No `latest_job_id`. Not persisted anywhere; lost on reload.
- **Server jobs** — real `GradingJob` rows from `GET /api/grading/jobs`
  (`api.gradingJobs()` → `routers/grading.py::list_grading_jobs`, ~line 295). One job per
  `(course_id, activity_id)`, owned by `user_email`.

There is **no server-side concept of "queue membership"** beyond "a job exists": an activity is
in the queue because it has a job, or because it is a client-side pending item. `GradingJob` has
**no hidden/archived state**, and `routers/grading.py` has **no remove/reset/archive/hide
endpoint** (the only delete is `DELETE …/{job_id}/cache`, which clears cached files, not drafts).
So the four actions need real backend support for job-backed items; pending items can only be
"removed" client-side. **This split is the core separation of concerns this plan enforces.**

### Action semantics (the contract every layer implements)

| Action | Pending item (no job) | Job-backed item |
|---|---|---|
| **Reiniciar do zero** (recomeça como se a atividade tivesse acabado de entrar na fila) | n/a — offer disabled (already fresh) | **full reset = delete the job** (full cascade + cache dir), then the **frontend re-adds the item as a fresh pending card**. The job is gone, so the *next* "Começar" creates a brand-new job → criteria inference + privacy audit + file enumeration all re-run, re-accounting for file types that were unsupported when the old job ran |
| **Remover da fila** (continua disponível em Atividades) | client-side: drop from `pendingQueue` | **delete job** + all children + on-disk cache dir; **not** re-added — activity leaves the queue, stays gradeable in Turmas |
| **Arquivar** (sai da fila · fica no Histórico) | n/a — offer disabled (not persisted) | set `queue_state="archived"`; leaves the active queue, shows in the collapsed "Arquivadas e ocultas" section; reversible (restore) |
| **Ocultar da visualização** (acessível pelo Histórico) | n/a — offer disabled | set `queue_state="hidden"`; same mechanics as archive, different label/section grouping; reversible |

> **Why Reiniciar deletes instead of mutating in place:** the goal is "as if newly added" —
> the file-type filtering that *discards* unsupported submissions happens at job-creation /
> audit / extraction time. An in-place wipe of an existing job would re-run drafting but keep
> the old file enumeration, so newly-supported file types would still be excluded. Deleting and
> letting the next start build a fresh job is the only thing that genuinely re-runs the whole
> pipeline. Reiniciar and Remover therefore share **one** `DELETE` endpoint and differ only in
> the frontend's after-step (re-add vs not). There is no `/reset` endpoint and no `reset_job`
> service function.

> **Accepted consequence:** a freshly-added pending item is in-memory only (`pendingQueue`,
> lost on reload) — so a just-Reiniciado item is equally ephemeral until the teacher starts it.
> That is correct: it behaves exactly like an item just sent from Turmas and not yet started.

**Per-item availability rule (bind everywhere):** an item with `latest_job_id == null` (pending)
offers **only Remover** (it is already "fresh", so Reiniciar is meaningless and omitted); an item
with a job offers all four. The bulk bar applies each action only to selected items it is valid
for, routing per item (client filter vs endpoint).

### Definition of done

- For job-backed items, all four actions work end-to-end, ownership-guarded (`_get_owned_job`):
  Reiniciar and Remover both delete the job (full cascade + cache dir) — Reiniciar then re-adds a
  fresh pending card, Remover does not; archive/hide set `queue_state` and drop the item from the
  active queue; restore returns it.
- Pending items offer Remover only (client-side filter); the other three are hidden/disabled.
- The queue screen shows the per-card "⋯" menu **and** a top-bar "Gerenciar" multi-select with a
  bulk-action bar, coexisting (not variant-gated). A collapsed "Arquivadas e ocultas" section
  lists archived/hidden jobs with a Restaurar action.
- Destructive actions (Reiniciar, Remover) require an explicit confirm (two-click "arm" pattern
  ported from the prototype — **not** a shadcn AlertDialog; that is deferred).
- `apps/web` `pnpm build` is green; **existing views render visually unchanged** (only new CSS
  classes added; no global resets, no edits to other components' markup).
- New backend unit tests (§8) pass; full pre-existing suite passes with no new failures.
- `graphify update .` run as its own commit.

### Out of scope (do not build)

- shadcn/Tailwind anything — this uses existing `ui.tsx`/CSS patterns; the shadcn version of
  these components belongs to the future app-wide migration.
- Integrating archived/hidden **grading** jobs into the global `HistoryView` (which today is
  *local export* history via `lib/local-history.ts`). "Histórico" here means the **queue-local**
  collapsed section only. Cross-wiring to the global history screen is a future plan.
- **"Discard grades only"** — clearing the AI scores/feedback while keeping the job, its
  criteria, and its privacy audit (so the teacher can re-draft without re-running audit/file
  enumeration). This is a genuinely useful action and distinct from Reiniciar, **but it must also
  be available on the review screen**, and this plan deliberately does not touch the review
  screen. Building it queue-only now would split one feature across two screens and risk
  divergence. Defer to a follow-up that adds it to both surfaces at once.
- Undo for bulk delete (beyond the per-action arm-to-confirm); job soft-delete/trash.
- Any mutation to Google Classroom.

---

## 1. Files touched (overview)

| File | Change |
|---|---|
| `apps/api/src/classroom_downloader/models.py` | `GradingJob.queue_state: str = "active"` (index) |
| `apps/api/src/classroom_downloader/database.py` | add `queue_state` to `_ensure_grading_job_columns` ALTER map |
| `apps/api/src/classroom_downloader/grading/` (new `lifecycle.py` or extend `caching.py`) | `delete_job(session, job)` service fn (full child cascade) |
| `apps/api/src/classroom_downloader/routers/grading.py` | new endpoints: delete, archive, hide, restore; `state` filter on the jobs list |
| `apps/api/src/classroom_downloader/schemas.py` | `GradingQueueItem.queue_state: str = "active"` |
| `apps/web/src/types.ts` | `GradingQueueItem.queue_state`; a `QueueAction` union type |
| `apps/web/src/lib/api.ts` | `deleteGradingJob`, `archiveGradingJob`, `hideGradingJob`, `restoreGradingJob`; `gradingJobs({ state })` |
| `apps/web/src/App.tsx` | `runQueueAction(action, items)` router (pending vs job); load archived; pass handlers to `GraderQueue` |
| `apps/web/src/components/grader/GraderQueue.tsx` | combine per-card "⋯" menu + "Gerenciar" multi-select; card `<button>`→`<div role=button>`; `ArchivedSection` |
| `apps/web/src/components/grader/Grader.module.css` | port the management classes (`qc-kebab`, `qc-menu`, `qc-bulkbar`, `qc-check`, `qc-manage-row`, `queue-archived`, …) adapting tokens |
| `apps/web/src/components/icons.tsx` | register `trash` (lucide `Trash2`) for Remover (no minus/trash icon today) |

---

## 2. Data model + migration (backend)

### 2.1 `queue_state` column

`GradingJob` (`models.py:85`) gains one column — a single enum-as-string keeps it to one ALTER
and one filter (vs. parallel `archived_at`/`hidden_at` timestamps):

```python
queue_state: str = Field(default="active", index=True)   # active | archived | hidden
```

Values: `"active"` (in the live queue), `"archived"`, `"hidden"`. "Removed" and "Reiniciado" are
*not* states — both **delete** the row (Reiniciar then re-adds a fresh pending card client-side,
Remover does not). The column exists purely to keep archived/hidden jobs out of the active queue
while remaining restorable.

### 2.2 Dev migration

`GradingJob` is an existing table, so `create_all` won't add the column — extend the SQLite
dev-migration shim. In `database.py::_ensure_grading_job_columns` (≈line 48) add to the dict:

```python
"queue_state": "VARCHAR DEFAULT 'active'",
```

No new table, no other migration. (Re-verify the function name/line with
`grep -n "_ensure_grading_job_columns" apps/api/src/classroom_downloader/database.py`.)

---

## 3. Service layer — job delete (backend)

Keep the destructive logic out of the router. Put one function next to the existing
`delete_job_cache` (`grading/caching.py:395`) — either extend `caching.py` or add
`grading/lifecycle.py` (preferred for separation; mirror the module's import style). Both
Reiniciar and Remover use this same `delete_job`; there is **no** in-place reset (see §0's "Why
Reiniciar deletes instead of mutating in place").

### 3.1 Enumerate the cascade (do not miss a table)

A `GradingJob` owns rows in these child tables (re-derive the full list at execution time:
`grep -n "job_id" apps/api/src/classroom_downloader/models.py`): `GradingCriterion`,
`GradingSubmission`, `GradingSubmissionFile`, `GradingFileCache`, `GradingPseudonym`,
`GradingAiAttempt`, `GradingScrubCache` (+ any added by `plan-image-grading.md` — verify).
Plus the on-disk cache directory handled by `delete_job_cache`.

### 3.2 `delete_job(session, job) -> None`

- First call `delete_job_cache(session, job)` (removes cache files + dir, marks cache rows).
- Then `session.delete(...)` every child row (one `select(...).where(... == job.id)` per table,
  delete each), then delete the `GradingJob`, then `commit`. Follow the delete-then-commit style
  already in `grading/criteria.py:99`.
- Idempotent-ish: caller has already resolved ownership; missing children are fine.

`delete_job` is the only place that knows the child-table topology — routers and frontend stay
ignorant of it. (Reiniciar's "fresh start" is achieved entirely by the frontend re-adding a
pending card after the delete; no server reset state exists.)

---

## 4. Transport — endpoints + schema (backend)

All new routes live in `routers/grading.py`, resolve ownership via
`_get_owned_job(job_id, user_email, session)` (`grading.py:193`) → 404 for non-owner/missing,
and emit `log_event` start/complete like their neighbours. Register nothing new (same router).

| Endpoint | Behavior |
|---|---|
| `DELETE /api/grading/jobs/{job_id}` | `delete_job`; return `204 No Content` (nothing to snapshot). Used by **both** Reiniciar and Remover — they differ only in the frontend's after-step (§6) |
| `POST /api/grading/jobs/{job_id}/archive` | set `queue_state="archived"`, `updated_at=now`, commit; return `grading_job_snapshot(session, job)` (`grading/snapshots.py:91`) |
| `POST /api/grading/jobs/{job_id}/hide` | set `queue_state="hidden"`; return snapshot |
| `POST /api/grading/jobs/{job_id}/restore` | set `queue_state="active"`; return snapshot |

> Naming caution: `DELETE …/{job_id}` must be distinct from the existing
> `DELETE …/{job_id}/cache` (`grading.py:1035`). Register the new bare-job DELETE without the
> `/cache` suffix; FastAPI routes them separately.

### 4.1 List filter

`list_grading_jobs` (`grading.py:295`) currently returns every job for the user. Add a query
param to scope by state and **default to active-only** so archived/hidden drop out of the live
queue:

```python
def list_grading_jobs(state: str = "active", ...):
    # state ∈ {"active","archived","hidden"}; "all" returns every state.
    # filter GradingJob.queue_state == state (skip filter when state == "all")
```

The collapsed section (frontend §7) fetches `state=archived` and `state=hidden` (or `all` and
partitions client-side — pick one; `all` + client partition is one round-trip).

### 4.2 Schema

`schemas.py::GradingQueueItem` (≈line 88) gains `queue_state: str = "active"`. Populate it in
**both** `GradingQueueItem(...)` constructions in `grading.py` (the `/queue` single-item build
~line 279 and the `/jobs` list build ~line 324): `queue_state=job.queue_state` for job-backed,
`"active"` for the no-job `/queue` case. (`grep -n "GradingQueueItem(" routers/grading.py`.)

---

## 5. API client + types (frontend transport)

### 5.1 `types.ts`

- `GradingQueueItem` (line 67) gains `queue_state: "active" | "archived" | "hidden"`.
- Add `export type QueueAction = "restart" | "remove" | "archive" | "hide" | "restore";`
  (`"restart"` = Reiniciar; it has no dedicated endpoint — the router maps it to delete-then-readd,
  see §6.)

### 5.2 `api.ts`

Follow the existing fetch-helper + `clearApiCache` style (see `draftGradingJob`,
`deleteGradingCache`, `grading.py` neighbours at `api.ts:197–253`). Every mutator must
`clearApiCache("GET /api/grading/jobs")` and `"GET /api/grading/queue"` so the queue re-reads.

```
deleteGradingJob(jobId)     DELETE /api/grading/jobs/{id}            -> void (204)  // Reiniciar & Remover
archiveGradingJob(jobId)    POST   /api/grading/jobs/{id}/archive    -> GradingJob
hideGradingJob(jobId)       POST   /api/grading/jobs/{id}/hide       -> GradingJob
restoreGradingJob(jobId)    POST   /api/grading/jobs/{id}/restore    -> GradingJob
```

There is no `resetGradingJob` — "restart" is `deleteGradingJob` plus a client-side re-add (§6).

Extend the list reader to pass state: `gradingJobs(state = "active")` →
`/api/grading/jobs?state=${state}` (keep the existing `ttlMs: 15_000`; note the cache key now
varies by query string — confirm `clearApiCache("GET /api/grading/jobs")` still clears all
states, i.e. it prefix-matches; if it exact-matches, clear each state key).

---

## 6. App state wiring (frontend)

In `App.tsx`:

- **Action router** `runQueueAction(action: QueueAction, items: GradingQueueItem[])`:
  - Partition `items` by `latest_job_id` (pending vs job). For pending items only `remove` is
    valid → `setPendingQueue(cur => cur.filter(...))`; ignore other actions for them.
  - For job items, map the action to an api call:
    - `remove` → `deleteGradingJob(id)`, then drop from local state (do **not** re-add).
    - `restart` → `deleteGradingJob(id)`, **then re-add the item to `pendingQueue`** built from
      the `GradingQueueItem` fields already in hand (`course_id`, `course_name`, `activity_id`,
      `activity_title`, `due_label`, `submission_count`), with `latest_job_id: null`,
      `status: "ready"`, `queue_state: "active"`, counts zeroed. This makes it reappear as a
      fresh "IA pronta" card; the next "Começar" creates a new job and re-runs the full pipeline.
    - `archive`/`hide`/`restore` → the matching api call.
  - Bulk = run sequentially (`for … of`), tolerate a per-item 404 (already-gone) without aborting
    the batch, then a single `loadGradingQueue()` refresh at the end (the `restart` re-adds are
    local-state updates and survive the refresh because they live in `pendingQueue`, which
    `loadGradingQueue` does not clear — verify).
  - If the action touches the currently-open job (`gradingJob?.id`), clear/refresh it.
- **Archived data**: add state for archived/hidden items; load via `api.gradingJobs("all")` (or
  two calls) when the queue view mounts (extend the existing `if (nextView === "graderQueue")
  void loadGradingQueue();` at `App.tsx:397`). Partition into active vs archived/hidden.
- Pass to `<GraderQueue>` (`App.tsx:1061`): `onAction={runQueueAction}` and the archived list.
  Keep existing `onSetup`/`onOpenJob`/`onDownloadInstead`/`onRefresh`.

Keep the router dumb about child tables and ownership — it only calls api methods and updates the
two state slices (`pendingQueue`, `gradingQueue`/archived).

---

## 7. Presentation — combine menu + multi-select (frontend)

All in `GraderQueue.tsx`. Port structure from `docs/UI/grader/queue.jsx` but adapt to this app's
real props (`GradingQueueItem`, `AppIcon`, global class names) — the prototype uses mock data
and a global `Icon`.

### 7.1 Card refactor (a11y-critical)

The card is currently `<button …>` (`GraderQueue.tsx:163`). A button **cannot** contain the
kebab button or the checkbox (nested interactive elements). Change `ReferenceQueueCard`'s root to
`<div role="button" tabIndex={0}>` with `onClick` and an `onKeyDown` activating on Enter/Space,
preserving the focus ring (`:focus-visible`) the `.queue-card` styles already imply. Verify the
`data-screen-label` and keyboard open still work.

### 7.2 Per-card "⋯" menu

Port `manageActions(item)` and `CardMenu` from `queue.jsx`:
- `moreHorizontal` kebab in the card top-right (`qc-top-right`), shown when **not** in manage
  mode. Opens a `qc-menu` popover (`role="menu"`) with the four actions, each disabled per §0's
  availability rule (pending item → only Remover enabled; the other three omitted/disabled).
- Destructive actions (restart, remove) use the prototype's **two-click arm-to-confirm**
  (`arming` state, label swaps to the confirm question, second click fires). Both discard a job;
  Reiniciar's confirm copy should make clear it restarts from scratch (re-runs criteria + audit),
  not just clears drafts. Do **not** introduce a shadcn AlertDialog — record a
  `// TODO: shadcn AlertDialog in the app-wide migration` so the future plan knows the swap point.
- Outside-click + Escape close (the prototype's `useEffect` handlers port directly).
- `onClick` handlers call `onAction(actionId, [item])` (single-item array — same router).

### 7.3 "Gerenciar" multi-select

Port from `QueueView`:
- A `manageMode` state and a top-bar toggle button in `g-topbar-actions` (next to Refresh /
  Download), label "Gerenciar" ↔ "Concluir" (`listChecks` / `check` icons).
- In manage mode: hide the kebab + CTA; show a `qc-check` checkbox on each card; clicking the
  card toggles selection (`onToggleSelect`); selected → `.selected` class.
- A floating `qc-bulkbar` (`role="toolbar"`) with selection count + the four actions + a close
  button; each bulk action calls `onAction(actionId, selectedItems)` then clears the selection.
  Disable bulk actions when nothing is selected, and per §0 only act on items the action is
  valid for.
- Reset `manageMode`/selection when leaving the view or after a bulk action.

### 7.4 Archived/hidden section

Port `ArchivedSection`: a collapsed `queue-archived` block under the active sections, listing
archived/hidden items with a "Restaurar" button → `onAction("restore", [item])`. Empty → render
nothing.

### 7.5 Styling

The real `Grader.module.css` (huge, ~2982 lines) has **none** of the management classes — they
live only in the prototype `docs/UI/grader/styles.css` (51 matching rules:
`qc-kebab`, `qc-menu`, `qc-menu-item`, `qc-bulkbar`, `qc-check`, `qc-manage-row`, `qc-chip`,
`queue-archived`, `qa-*`, `.queue-card.managing`, `.queue-card.selected`, `.queue-card.menu-open`).
Port those rules into `Grader.module.css`, next to the existing `.queue-card` block (~line 93):

- Vite is configured `css.modules.generateScopedName: "[local]"` (see `vite.config.ts`), so
  module class names are **not hashed** — reference them as plain string `className="qc-kebab"`
  exactly like the existing `className="queue-card"` markup. Add them to this module file; do
  **not** create a new global stylesheet.
- Replace the prototype's raw colors with the app's design tokens from `styles/tokens.css`
  (`var(--muted)`, `var(--warning)`, `var(--ai)`, surface/border tokens — grep tokens.css for
  the right names). Match the existing grader card visuals.

---

## 8. Tests (apps/api/tests; frontend gate is `pnpm build` + manual smoke)

Backend (the only layer with logic worth unit-testing):

- `test_queue_management_api.py` **(new)**:
  - **Ownership:** every new route returns 404 for a job owned by another `user_email`.
  - **delete (covers both Reiniciar and Remover, same endpoint):** a job with
    submissions/criteria/cache → after `DELETE`, the `GradingJob` and **every** child-table row
    are gone (assert each table empties for that `job_id`) and the cache dir is removed; route
    returns 204. (Reiniciar's "fresh start" is a frontend re-add — no server behavior to test
    beyond the delete.)
  - **archive/hide/restore:** set `queue_state` correctly; `GET /jobs` (default) excludes
    archived/hidden; `GET /jobs?state=archived` includes only archived; restore returns it to
    the default list.
  - **list filter:** `state=all` returns every state; unknown state → sensible default or 422
    (pick one and assert it).
  - **schema:** `queue_state` present in `/jobs` and `/queue` payloads.
- Existing suite: same baseline counts, zero new failures.

Frontend: `pnpm build` green + manual smoke (§9 Phase 5) — kebab menu opens/acts, Reiniciar makes
the card reappear as a fresh "IA pronta" item, Gerenciar selects + bulk-acts, archived section
restores, pending item offers only Remover, existing grader screens visually unchanged.

---

## 9. Execution phases (each ends with the full suite + `pnpm build` green)

- **Phase 0 — baseline.** Record pytest counts (`cd apps/api; uv run --extra dev pytest -q`) and
  confirm `pnpm build` green in `apps/web`. Re-derive all line numbers in this plan with
  `grep -n` before editing.
- **Phase 1 — backend (data + service + transport).** §2 (`queue_state` + migration), §3
  (`delete_job` cascade), §4 (4 endpoints — delete/archive/hide/restore — + list filter + schema
  field) + §8 tests. Backend fully exercisable via curl/OpenAPI before any UI exists. Commit.
- **Phase 2 — frontend transport.** §5 (`types.ts`, `api.ts`). Pure additions; `pnpm build`
  green. Commit.
- **Phase 3 — app-state wiring.** §6 (`runQueueAction` router, archived load, prop pass-through).
  Build green; the queue still renders as today (no new UI yet, handlers ready). Commit.
- **Phase 4 — presentation.** §7 (card `<button>`→`<div>`, `CardMenu`, multi-select + bulk bar,
  `ArchivedSection`, CSS port). Gate: build green **and** zero visual drift on other views
  (connect, turmas, grader setup/review/wrap, history) — only new classes were added. Commit
  the CSS port and the component change together.
- **Phase 5 — wrap.** Manual smoke of every action (single + bulk + restore + pending-only
  Remover); `graphify update .` as its own commit; flip this plan's status line.

**Git hygiene:** `git add` only touched files per phase — never `git add -A`.

---

## 10. Watch-items (gotchas that will bite)

- **Cascade completeness (§3.1):** a forgotten child table orphans rows on delete.
  Enumerate from `models.py` at execution time, not from this plan's list — `plan-image-grading.md`
  may have added tables.
- **Reiniciar is delete + client re-add (§0, §6):** there is no server reset. The "fresh start"
  depends entirely on the frontend re-adding a pending card after the delete succeeds — if the
  delete fails, do not re-add. The re-added item is ephemeral (`pendingQueue`), which is correct
  and matches a freshly-added-from-Turmas item.
- **Card `<button>`→`<div role="button">` (§7.1):** the #1 a11y trap. Nested interactive
  elements are invalid inside a button; the refactor is mandatory before adding the kebab or
  checkbox. Preserve Enter/Space activation and the focus ring.
- **Pending vs job split (§0):** never call a job endpoint with `latest_job_id == null`. The
  availability rule must be enforced in *both* the per-card menu and the bulk bar, and in the
  `App.tsx` router as a backstop.
- **Two DELETE routes:** the new bare `DELETE …/{job_id}` must not shadow or be shadowed by the
  existing `DELETE …/{job_id}/cache`. Verify both resolve after wiring.
- **List-cache invalidation (§5.2):** `gradingJobs` now varies by `?state=` — make sure
  `clearApiCache("GET /api/grading/jobs")` actually clears the state-suffixed keys (prefix vs
  exact match). A stale active-list after archiving is the likely bug.
- **CSS scoping (§7.5):** `generateScopedName: "[local]"` means class names are global-by-value;
  a generic ported class name could collide with another view's class. Keep the prototype's
  `qc-`/`qa-`/`queue-` prefixes; don't rename to something generic.
- **No-restyle guarantee:** add only new classes to `Grader.module.css`; do not touch
  `styles/base.css`/`tokens.css` globals or other components' markup. The grader screens were
  validated under `plan-image-grading.md`.
- **Icon gap:** no `minus`/`trash` is registered in `icons.tsx`; add `trash: Trash2` (import from
  `lucide-react`) for Remover, or reuse `x`. Don't invent an icon name that isn't in the map.
- **Multi-user isolation:** `queue_state` is per-job and jobs are per `user_email`, so states are
  naturally per-user — no shared-visibility surprises on the VPS. Confirm `_get_owned_job` guards
  every new route (no global scans).
- **shadcn deferral:** resist pulling in Tailwind/AlertDialog here. Leave a `TODO` at the confirm
  site so the future migration knows the swap point; keep the two-click arm confirm for now.
