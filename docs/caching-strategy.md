# Caching Strategy

## Decision Summary

This app is network-bound, not compute-bound. Almost every expensive operation is a
round-trip to Google Classroom or Drive, and today almost none of those round-trips are
cached. Two good caches already exist and should be treated as the reference patterns to
extend rather than reinvent:

- **`GradingFileCache`** — Drive bytes written to `.cache/grading/<job>/`, mirrored in
  SQLite, 24h TTL, with an explicit hit-check before refetch
  (`apps/api/src/classroom_downloader/grading.py`, `cache_submission_file`).
- **`llm_catalog`** — remote JSON cached to disk with a staleness check and stale-fallback
  on fetch failure (`apps/api/src/classroom_downloader/llm_catalog.py`, `_load_upstream`).

The plan below is organized into four tiers, ordered by return on investment. Tier 1 is the
recommended starting point: ~50 lines, no schema or dependency changes, and it eliminates the
largest chunk of redundant Google calls.

A hard constraint runs through every tier: this is student PII (emails, names, submission
content). Every new cache must adopt the same lifecycle discipline the grading cache already
has — explicit TTLs and invalidation on logout. `auth_logout` and `provider_dependency`
already call `purge_cached_classroom_state`; every new cache layer must be wired into that
same purge path, or logout will leak student data.

## Implementation Progress

Updated 2026-06-04:

- **Tier 1 complete.** Added `GradingScrubCache`, keyed by `content_hash` plus an identity
  hash, and routed both privacy audit and grading draft through the shared
  `scrub_submission_cached` helper. The privacy audit no longer performs the redundant
  `_direct_hits` regex rescan. Deleting a grading job cache now marks scrub cache rows
  deleted as well.
- **Tier 2 complete.** Added process-local Google provider caching per token file identity,
  plus TTL caches for account profile, roster profiles, and Drive metadata. `TokenStore`
  save/delete and the app purge path clear these caches.
- **Tier 3 complete.** Added `fetched_at` freshness columns to `Course` and `Activity`, wired
  SQLite dev migrations, and changed course/activity endpoints to serve fresh DB rows first
  with stale fallback on non-auth provider failures. `auth_me` also benefits from the
  provider/account-profile cache.
- **Tier 4 complete.** Added export byte caching under `.cache/exports`, content-derived
  ETags, `Cache-Control: private`, and `304 Not Modified` handling for export file streams
  plus CSV/JSON export responses. Logout/purge clears export cache metadata and files.
- **Tier 5 complete.** Added a lightweight frontend request cache in `apps/web/src/lib/api.ts`
  with in-flight coalescing, TTL freshness, stale fallback/revalidation, and cache
  invalidation after auth, export, and grading mutations. This avoids adding a new dependency
  while delivering the planned client-side cache behavior.

Verification:

- `uv run pytest -q` in `apps/api`: 46 passed.
- `pnpm build` in `apps/web`: passed.

## Current Hotspots

Ranked by redundant work observed in the code.

0. **The privacy audit is the hottest path and is fully recomputed every run.**
   `run_privacy_audit` runs `download → extract → scrub` for every submission (30+ per class)
   and is the most-called heavy function in the app. Scrubbing is a pure function of
   `(file content, student_name, student_email)`, and `GradingFileCache` already stores a
   `content_hash` of that content — yet nothing memoizes the result, so a rerun where nothing
   changed reprocesses all 30 submissions. See the dedicated evaluation and Tier 1 below.

1. **`_hydrate_drive_metadata` re-fetches per-file Drive metadata on every call.**
   `list_submission_files` (`google_provider.py`) issues a Drive `files.get` once per
   attachment, every call. It is called from `grading_queue`, `create_export`, **and**
   `draft_grading_job`. Opening the queue → creating a job → drafting therefore re-fetches
   the same per-file metadata three times, N Drive calls each, for data that does not change
   (a submitted file's name and mime type).

2. **Provider rebuilt every request; profile cache discarded.** `provider_dependency`
   (`main.py`) calls `get_google_provider()` per request, which runs two `build()` discovery
   constructions and a fresh empty `_profile_cache`. The roster-email lookup in `_profile`
   only survives within a single request. Across queue → job → draft, every student profile
   is re-fetched from `userProfiles().get`.

3. **SQLite mirror is write-only.** `list_courses` / `list_activities` always call Google,
   then `session.merge`, then read back. The DB is never consulted as a read cache or
   fallback. `auth_me` likewise hits `userProfiles().get` on every page load (the frontend
   calls `authMe` on every bootstrap).

4. **Export streaming has no cache and no HTTP headers.** `stream_export_file` (`main.py`)
   downloads from Drive on every request and returns raw bytes with no `Cache-Control` or
   `ETag`. Preview images re-download on every render. `get_file_content` also re-fetches
   `_drive_metadata` a fourth time before the byte download.

5. **Frontend has no fetch cache.** Plain `fetch` + `useState` (`api.ts`, `App.tsx`).
   Re-navigating reloads courses and activities; there is no request dedup, no
   stale-while-revalidate, and no in-flight coalescing.

---

## Privacy Audit: Efficiency Evaluation

Because the privacy audit runs on every class (30+ submissions each), it is the most-called
heavy function in the app and deserves a dedicated assessment.

**Verdict on the logic — appropriately scoped, not overkill.** Pseudonyms, known-identity
replacement (name/email), and the four PII regexes (email, phone, URL, student-ID) are a
reasonable, defensible scrub for student work. The patterns are compiled once at module load
(`privacy.py`) and none contain nested quantifiers, so there is no catastrophic-backtracking
(ReDoS) risk even on large extracted PDF/DOCX text. Do **not** trim what it checks.

**Verdict on the execution — inefficient in four specific ways.** The cost is recomputation,
not over-checking:

1. **`_direct_hits` is redundant dead computation.** `scrub_submission` already runs
   `EMAIL/PHONE/URL/ID .subn()`, replacing every match with `[email]`/`[phone]`/etc. The
   audit then calls `_direct_hits(scrubbed.content)`, re-running the same four regexes via
   `.search()` on the already-scrubbed text. By construction those patterns can no longer
   match (the placeholders contain no emails/phones/digits), so
   `remaining_direct_identifier_hits` is always `[]`. That is four regex scans × 30
   submissions × every run for a guaranteed-empty result. The real re-identification signal
   is the `identifier_remaining` substring check inside `scrub_submission`.

2. **Extract + scrub run twice per submission.** The audit does `download → extract → scrub`
   for all submissions; `draft_grading_job` then repeats `cache_submission_file →
   extract_submission_content → scrub_submission` identically. The byte download is shared via
   `GradingFileCache`, but disk read + decode + the full regex scrub are recomputed — 60
   passes where 30 would do.

3. **The audit result is recomputed from scratch on every run.** Scrub is deterministic on
   `(content, student_name, student_email)`, and `GradingFileCache.content_hash` already
   captures the content. Nothing memoizes against it, so a "rerun" with no changes
   reprocesses everything.

4. **Per-submission DB commits multiply.** `_submission_for_audit` commits,
   `pseudonym_for_submission` commits, and `cache_submission_file` commits — roughly three
   fsyncs per submission, ~90 SQLite commits for one 30-submission audit.

These four are addressed by Tier 1.

---

## Tier 1 — Privacy audit and scrub memoization (hottest path)

**Goal:** Make the most-called function near-instant on reruns and stop duplicating the
extract/scrub work between audit and draft.

**Why first:** Highest call volume in the app, and the work is deterministic and
content-addressable, so it caches cleanly. No new dependency required.

**Changes:**

- **Memoize the scrub/extraction result by `content_hash`.** Store the computed
  `(extraction_status, privacy_status, flags)` keyed by the existing
  `GradingFileCache.content_hash` (plus an identity component, since name/email are inputs).
  On rerun or draft, a matching hash skips extract + scrub entirely. This is the single
  biggest win on the hottest path.
- **Share the audit's result with `draft_grading_job`.** Have draft consume the memoized
  scrub result instead of recomputing it, eliminating the second pass per submission.
- **Drop or downgrade `_direct_hits`.** Remove the redundant four-regex rescan, or keep it
  only as a cheap debug-time assertion. Trust `scrub_submission`'s own flags.
- **Batch the audit transaction.** Build submissions, pseudonyms, and audit rows and commit
  once per audit (or in a few batches) instead of per submission.

**Correctness guard:** Memoization keys on `content_hash`, so an updated file (new hash on
re-download) correctly misses the cache and re-scrubs. The audit must stay conservative — a
cache hit only short-circuits when the content hash *and* identity inputs match exactly.

**Invalidation:** Scrub memo entries clear with the job's cache (the existing
`delete_job_cache` / cache-expiry path) and on logout via `purge_cached_classroom_state`.

**Estimated effort:** Moderate — a memo table or column keyed by `content_hash`, plus reuse
wiring in `privacy_audit.py` and `grading.py`. No frontend change.

---

## Tier 2 — Process-level provider and metadata memoization

**Goal:** Stop rebuilding the provider per request and stop re-fetching unchanged
Drive/profile data within a working session.

**Why:** Biggest reduction in Google calls for the smallest change, and it directly speeds the
privacy audit's opening `list_submission_files` (which triggers the per-file Drive metadata
fetches). No schema migration, no new dependency (hand-rolled in the `llm_catalog` style, or
`cachetools.TTLCache`). Process-local is acceptable for a single-user local desktop app.

**Changes:**

- Cache the `GoogleApiProvider` instance (and its `classroom` / `drive` discovery clients)
  per credential identity instead of constructing one per request. Invalidate when the token
  changes or is deleted.
- Promote `_profile_cache` from per-instance to process scope, keyed by `user_id`, with a TTL
  (suggest 30 min). Collapses repeated `userProfiles().get` across queue/create/draft.
- Add a TTL'd in-process memo for `_drive_metadata`, keyed by `file_id` (suggest 15–30 min).
  Collapses the 3–4× refetch of file name/mime type into a single call per session.

**Invalidation:** All three caches clear on logout and on auth failure. Wire them into the
existing `purge_cached_classroom_state` / `TokenStore.delete` paths.

**Estimated effort:** ~50 lines, isolated to `google_provider.py` plus a clear hook in
`main.py`'s logout/auth-failure handling.

---

## Tier 3 — Promote SQLite to a read-through cache

**Goal:** Make the existing mirror earn its keep; serve instant navigation and reduce
list calls.

**Changes:**

- Add a `fetched_at` timestamp to `Course` and `Activity`. Serve from SQLite when fresh
  (suggest <10 min); otherwise revalidate from Google (on explicit refresh, or background
  revalidate). The mirror finally becomes a real cache instead of write-only.
- Cache `account_profile` (DB or process) with a short TTL so `auth_me` stops calling
  Classroom on every page load.

**Invalidation:** Freshness window plus the existing purge-on-logout. Add an explicit
"refresh" affordance so users can force a re-fetch when they know Classroom changed.

**Estimated effort:** Small schema addition + a freshness check in the two list endpoints.

---

## Tier 4 — HTTP caching on byte and export endpoints

**Goal:** Let the browser skip re-downloading files it already has.

**Changes:**

- Add `ETag` (reuse the `sha256` content hash already computed in the grading cache) plus
  `Cache-Control: private, max-age=...` and `304 Not Modified` handling to
  `stream_export_file` and the CSV / JSON export endpoints.
- Optionally back `stream_export_file` with the same on-disk byte cache the grading flow
  already uses, so export and grading share a single download per file. This also removes the
  redundant fourth `_drive_metadata` fetch in `get_file_content`.

**Invalidation:** `ETag` is content-derived, so it is self-invalidating. Keep `max-age`
conservative and `private` given PII.

**Estimated effort:** Header/conditional-request plumbing on a handful of endpoints, plus
optional reuse of the existing disk cache.

---

## Tier 5 — Frontend data-layer cache

**Goal:** Dedup, cache-on-navigate, and stale-while-revalidate on the client.

**Changes:**

- Adopt TanStack Query (React Query) for `courses`, `activities`, `authMe`, and `gradingJob`.
  Replaces the manual `useState` / `useEffect` fetching in `App.tsx` with request dedup,
  stale-while-revalidate, cache-on-navigate, in-flight coalescing, and retry for free.

**Invalidation:** Invalidate the relevant query keys on logout, on course/activity refresh,
and after mutations (job create, draft, review, retry, cache delete) so the UI reflects
server state without a manual reload.

**Estimated effort:** Add the dependency and migrate the fetch call sites; highest
UX-leverage frontend change, but larger surface area than the backend tiers.

---

## Recommended Sequencing

1. **Tier 1** — privacy audit/scrub memoization. Hottest path, deterministic, content-keyed;
   the biggest real-world win since the audit runs on every class. Start here.
2. **Tier 2** — process-level provider + metadata/profile memo. Small, isolated, and it
   compounds with Tier 1 by cutting the audit's opening `list_submission_files` calls.
3. **Tier 4** — HTTP ETags on byte/export endpoints; independent quick win on preview-image
   and export re-downloads.
4. **Tier 3** — SQLite read-through; schema touch, designed once the process memo is proven so
   the within-session and across-session layers fit together.
5. **Tier 5** — frontend migration; last, once the API's caching semantics (ETags, freshness)
   are settled so the client cache mirrors them.

## Cross-Cutting Requirements

- **PII lifecycle:** Every cache clears on logout and auth failure via the existing purge
  path. No cache outlives the session's credentials.
- **Explicit TTLs:** No unbounded caches. Reuse `grading_cache_ttl_hours` style settings in
  `settings.py` for any new TTL so they are configurable and visible.
- **Stale-fallback over hard-fail:** Follow the `llm_catalog` precedent — prefer serving
  slightly stale cached data to failing a request when Google is unreachable, except where
  correctness demands a fresh read.
