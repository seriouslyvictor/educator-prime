# Implementation Plan: Logging & cache observability

> Status: **Planned — not yet started.**
> Scope: `apps/api` backend logging (`observability.py` + ~168 call sites).
> Goal: make cache hit/miss measurable, keep PII out of logs, and make output
> readable and operable by default.

## Why

Findings from the current review:

- **Cache hit/miss is not cleanly measurable.** Only the grading *file* cache logs
  an explicit `.hit` **and** `.miss`. The other eight caches log a hit under one of
  two naming conventions (`cache.hit` vs `cache_hit`) and log the miss under a
  *different* name (`fetch` / `start` / `provider_result`) or not at all
  (`google.provider.cache_hit`, export stream). No counters, no hit-rate summary.
- **PII leaks into logs at INFO.** 27 sites dump full `obj.__dict__`; notably
  `google.submission_files.complete` / `.page` log `SubmissionFile.__dict__`, which
  contains `student_email` and `student_name`, bypassing `log_payload_previews` and
  the privacy-scrub effort.
- **Plain output has no timestamp/level/logger.** `basicConfig(format="%(message)s")`
  emits bare messages; the non-rich path (prod/CI/piped) can't distinguish INFO from
  WARNING or order events in time.
- **Everything is INFO.** No DEBUG tier, so a 30-submission audit emits ~200–300
  INFO lines and the chatter can't be quieted without losing signal.
- **Unbounded object dumps.** `_format_value` `repr()`s lists/dicts with no
  truncation, so single lines can be many KB on the hottest paths.
- **Inconsistent taxonomy** and **no request correlation id**.

## Reference patterns already in the repo

- `grading.cache.hit` / `grading.cache.miss` / `grading.cache.write`
  (`grading.py:274/289/326`) — the target shape for every cache.
- `text_preview` / `byte_preview` — TTL-gated, truncated payload rendering; extend
  this discipline to object dumps.
- `_refresh_audit_counts` (`privacy_audit.py`) and `grading.draft.complete` — existing
  completion-summary seams where hit/miss counters can be surfaced.

---

## Phase 0 — Safety net & conventions (no behavior change)

- Confirm `uv run --extra dev pytest -q` is green as the baseline (46 tests).
- Write down the **event-name taxonomy** in this doc and in a module docstring:
  - Format: `<area>.<entity>.<action>`.
  - Fixed verb set: `start`, `complete`, `failed`, `hit`, `miss`, `write`, `skip`.
  - Caches always emit the pair `cache.hit` / `cache.miss` with fields
    `cache="<name>"`, `key="<key>"`.
- No code changes that alter output yet; this phase only establishes the contract.

## Phase 1 — Formatter: make plain output operable (high value, low risk)

- In `observability.py::configure_logging`, give the plain `StreamHandler` a format
  that includes timestamp, level, and logger name (e.g.
  `%(asctime)s %(levelname)s %(name)s %(message)s`). Leave RichHandler as-is (it
  already renders time/level columns).
- Add an optional **JSON formatter** toggle (`log_format: "text" | "json"` in
  `settings.py`) for machine parsing. `log_event` already has structured fields, so a
  JSON formatter is a natural fit; default stays `text`.
- Risk: low. Output-only change; assert nothing in tests depends on bare-message
  format (current tests match on event substrings, not full lines — verify).

## Phase 2 — Redact PII and bound object dumps (highest-priority correctness)

- Add a `safe_fields(obj, drop={...})` / `redact` helper in `observability.py` that
  renders a domain object's dict **without** identifier fields (`student_email`,
  `student_name`, raw tokens) and **through** the existing preview/truncation gate.
- Replace the 27 `__dict__` dumps with `safe_fields(...)`, prioritizing the PII-bearing
  ones first:
  - `google_provider.py` `google.submission_files.complete` / `.page` (`:467`, page event)
  - any provider result that includes student identity.
- Truncate list/dict renders in `_format_value` (or via the helper) so single lines are
  bounded, mirroring `text_preview`'s `log_preview_chars` behavior.
- Risk: medium — touches many call sites, but mechanical. Add a test asserting
  `student_email` never appears in emitted submission-files logs.

## Phase 3 — Uniform cache hit/miss instrumentation (the core ask)

For each of the nine caches, emit the standard pair via a tiny helper, e.g.
`log_cache_hit(logger, cache, key, **ctx)` / `log_cache_miss(...)`:

- **Already correct:** grading file cache — align field names only.
- **Add explicit `.miss`, rename for consistency:**
  - Grading scrub cache (`grading.py`): add `grading.scrub_cache.miss` alongside `.write`.
  - Google profile (`google_provider.py:507/509`): `cache_hit`→`cache.hit`,
    `fetch`→`cache.miss`.
  - Drive metadata (`:539/541`): `cache_hit`→`cache.hit`, `start`→`cache.miss`.
  - Account profile (`:268`): add explicit miss.
  - Provider instance (`:739`): add a miss log on the construct path.
  - Classroom courses/activities (`main.py:358/407`): `cache_hit`→`cache.hit`,
    treat `provider_result` path as `cache.miss`.
  - Export stream (`main.py:1019`): log a miss when `_export_file_cache_response`
    returns `None`.
- Carry a consistent `cache="<name>"` field so all caches are greppable with one query
  and groupable by a metrics tool.
- Risk: medium — many files, but each change is local and additive. Keep old event
  names out (don't dual-emit) to avoid double-counting; update any tests that match the
  renamed events.

## Phase 4 — Hit-rate summaries & DEBUG tier (readability)

- **Per-operation counters:** accumulate hit/miss counts during an audit/draft and
  surface them in the existing completion summaries —
  `privacy_audit.complete … file_cache_hits=N misses=M scrub_cache_hits=… ` and
  `grading.draft.complete … `. This makes a hit *rate* one line instead of a
  grep-and-divide. Hook into the `_refresh_audit_counts` / draft-complete seams.
- **Level discipline:** move trace-level lifecycle events (`*.start`, `*.page`,
  `row.start`, `*.select`) to `DEBUG`; keep outcomes (`cache.hit/miss`, `*.complete`
  summaries, warnings, errors) at INFO. Add `log_debug` to `observability.py`.
- Net effect: default INFO logs go from ~200–300 lines/audit to a readable handful,
  with full detail available at `log_level=DEBUG`.

## Phase 5 — Request correlation (optional, nice-to-have)

- Add a request-id middleware in `main.py` (generate/propagate `X-Request-ID`), stash
  it in a `contextvar`, and have `_format_event` append `request_id=…` automatically.
- Lets concurrent audits be untangled in logs.
- Risk: low–medium; isolated to `observability.py` + one middleware.

## Phase 6 — Verify & commit

- `uv run --extra dev pytest -q` green; add the new assertions (no PII in logs;
  cache miss events present).
- Manual smoke: run a mock-provider audit and a draft, eyeball that
  `cache.hit`/`cache.miss` and the completion-summary counters appear, and that
  `student_email` does not.
- Commit in phase-sized chunks on the working branch; no PR unless requested.

---

## Settings touched (`settings.py`)

- `log_format: Literal["text", "json"] = "text"` (Phase 1).
- (Reuse existing `log_level`, `log_rich`, `log_payload_previews`, `log_preview_chars`.)

## Risk notes

- The bulk of risk is in Phases 2–3 (many call sites). All changes are mechanical and
  output-only; no business logic changes. The main test impact is updating substring
  matches for renamed events — enumerate those up front (`grep` the test suite for the
  old names) and change them in lockstep.
- Keep cache event renames single-emit (no dual old+new names) to avoid skewing any
  future hit-rate counts.

## Sequencing / priority

1. **Phase 2 (PII redaction)** — correctness/privacy, do first.
2. **Phase 3 (uniform cache hit/miss)** — directly answers "are we getting hits or
   misses?".
3. **Phase 1 (formatter)** — small, makes everything else readable.
4. **Phase 4 (summaries + DEBUG)** — biggest readability win.
5. **Phase 5 (request id)** — optional.

## Quick reference — cache log sites

| Cache | File:line | Current hit | Current miss |
|---|---|---|---|
| Grading file cache | `grading.py:274/289/326` | `grading.cache.hit` | `grading.cache.miss` + `.write` |
| Grading scrub cache | `grading.py:377/414` | `grading.scrub_cache.hit` | `.write` (implicit) |
| Google profile | `google_provider.py:507/509` | `google.profile.cache_hit` | `google.profile.fetch` |
| Drive metadata | `google_provider.py:539/541` | `google.drive.metadata.cache_hit` | `google.drive.metadata.start` |
| Account profile | `google_provider.py:268` | `google.account_profile.cache_hit` | (fetch path) |
| Provider instance | `google_provider.py:739` | `google.provider.cache_hit` | (none) |
| Classroom courses | `main.py:358` | `classroom.courses.cache_hit` | `classroom.courses.provider_result` |
| Classroom activities | `main.py:407` | `classroom.activities.cache_hit` | `…provider_result` |
| Export stream | `main.py:1019/1035` | `export.file.stream.cache_hit` | returns `None` silently |
