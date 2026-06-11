# Plan — Image submission grading (vision extraction stage + layered error handling)

> **Status:** in execution on branch `codex/image-grading`; Phase 0 complete.
> **Execution progress:**
> - Phase 0 baseline complete: `uv run pytest -q` in `apps/api` -> 123 passed; `pnpm install --frozen-lockfile; pnpm build` in `apps/web` -> build succeeded.
> - Phase 1 error taxonomy complete: added shared LLM error classification, grading-stage retryable persistence, snapshot/frontend retry surfacing, and tests. Gate: `uv run pytest -q` in `apps/api` -> 127 passed; `pnpm build` in `apps/web` -> build succeeded.
> **Updated 2026-06-10** after the `grading.py` → `grading/` package split (`plan-grading-split.md`,
> commits `5d02ad1`…`9b72d83`): all grading-layer references below now point at the package
> submodules. The compat shim `grading/__init__.py` keeps `classroom_downloader.grading.*`
> imports working, so nothing outside the grading layer changed.
> **Audience:** an executing agent with no prior context. Read §0–§5 before touching code.
> **Line numbers are as-of-writing guides, not truth — re-derive every location with `grep -n`
> at execution time.**
> **Scope:** backend `apps/api/src/classroom_downloader/`, frontend `apps/web/src/`. No changes
> to Google provider, OAuth, exports, or naming.

---

## 0. Goal & context

Image submissions (`image/*`) are currently rejected at extraction time:
`content_extraction.py` → `extract_submission_content` returns
`status="unsupported", error="unsupported_visual_submission"`, the scrub layer blocks them,
and the grading engine never sees them.

This feature adds a **vision extraction stage**: the image is sent **once** to the LLM to be
transcribed into text, and that text re-enters the existing pipeline unchanged
(regex scrub → pseudonyms → audit → cache → text-only grading call). We deliberately do
**not** grade images directly in a multimodal grading call. Reasons (do not re-litigate):

1. **Pseudonymization survives.** Brazilian students routinely write their full name on the
   worksheet. The transcription passes through `privacy.scrub_submission`, whose
   `_name_detector` already has the roster name and redacts it. A direct multimodal grading
   call would show the model the real name next to the work.
2. **Everything downstream is unchanged.** Scrub, audit, scrub cache, grading engine, teacher
   loop, CSV export all operate on text and keep working as-is.
3. **Cost.** The scrub cache (`GradingScrubCache`) makes the transcription a one-time purchase
   per job; regrades after rubric changes are text-only calls. Direct multimodal grading
   re-sends the image on every regrade.

The images can be of many natures and the extraction prompt must handle all of them:
- a photo of work displayed on a computer screen
- a handwritten assignment photographed afterwards
- a screenshot of code output / frontend work
- screenshots of other computer work (documents, spreadsheets, IDEs, terminals)

A second, separable deliverable rides along: **layered, explicit error reporting** for LLM
calls (extraction *and* grading). Today `grading/drafting.py` (`_draft_submission`) catches a
bare `Exception` around `grading_engine.grade(...)` and collapses everything into
`safe_error="grading_engine_failed"`.
503s from the provider — currently common and perfectly retryable — look identical to a
malformed model response. The teacher must be able to tell, on the grading screen:
**(a)** the file never left the machine, **(b)** the API was unreachable/overloaded (retry
later), or **(c)** the model received the image and failed at the task.

**Definition of done**
- Image attachments (`image/jpeg`, `image/png`, `image/webp`) are transcribed by a
  vision-capable model, scrubbed, cached, and graded like any text submission — but only
  when the teacher opted in on the job (§4.1).
- Default-off: with consent off (and for all existing jobs), behavior is byte-for-byte
  today's behavior (`unsupported_visual_submission`).
- Every LLM failure (both stages) lands in one of the typed error codes of §3, persisted with
  a `retryable` flag, and rendered in PT-BR on the grading review screen with a retry
  affordance for retryable rows.
- Vision extraction cost/usage is recorded as a `GradingAiAttempt` row (`stage="extraction"`)
  so job cost totals stay true.
- All pre-existing tests pass; new unit tests cover §8.1; live tests (§8.2) are env-gated and
  skipped by default.
- `graphify update .` re-run at the end.

**Out of scope (do not build):** direct multimodal grading mode, local face blurring /
OpenCV, Tesseract OCR pre-flight, HEIC support (see §5.2), a separate extraction-model
setting (we reuse the job's grading model, gated on `supports_vision` — revisit later if
teachers want a cheaper extraction model).

---

## 1. Files touched (overview)

| File | Change |
|---|---|
| `llm_errors.py` **(new)** | litellm exception → `(code, retryable)` classifier shared by both stages |
| `image_preprocessing.py` **(new)** | EXIF strip, orientation, downscale, re-encode |
| `grading_engine.py` | `VisionExtractionRequest/Result` dataclasses; protocol method `extract_image`; mock impl |
| `litellm_engine.py` | `extract_image` impl (multimodal message + structured output) |
| `content_extraction.py` | `ExtractedSubmissionContent` gains optional `pii_observed`, `content_kind`; image branch returns `pending_vision` when consent on |
| `privacy.py` | merge model-reported PII into `PrivacyReport`; escalation rules |
| `grading/caching.py` | scrub-cache bypass rules; vision call orchestration in `scrub_submission_cached` |
| `grading/drafting.py` | typed error handling around `grade()`; pass the vision extractor from `_draft_submission` |
| `grading/attempts.py` | extraction attempt recording (`stage="extraction"`, reuse `_record_attempt`/`_attempt_metadata`) |
| `grading/_common.py` | `pending_vision` added to `_EXTRACTION_STATUS_RANK` |
| `grading/snapshots.py` | submission snapshot exposes `error_retryable` |
| `privacy_audit.py` | image rows with consent → `pending_vision`, audit_pass=True with warning |
| `models.py` | `GradingJob.include_visual_submissions`; `GradingAiAttempt.stage`, `.retryable` |
| `database.py` | dev-migration ALTERs for the new columns (follow `ensure_sqlite_dev_migrations` pattern) |
| `schemas.py` | job create/read + submission snapshot expose new fields |
| `routers/grading.py` | accept consent flag on job create; no new endpoints (retry endpoint exists) |
| `apps/web` | GraderSetup consent checkbox; graderStatus.ts labels; GraderReview error layers + retry button; audit panel image notice |
| `apps/api/pyproject.toml` | add `pillow` |

Re-derive all symbol locations with `grep -n` — e.g. `grep -rn "def scrub_submission_cached" apps/api/src/classroom_downloader/grading/`.

**DAG note (new since the split).** The `grading/` package keeps a strict one-way import DAG
(`plan-grading-split.md §1`). The changes above add two edges, both acyclic and allowed:
`caching → attempts` (recording extraction attempts inside `scrub_submission_cached`) and
`caching → grading_engine` (sibling module, for the `VisionExtractor` typing). Do **not** import
`drafting` or `inference` from `caching`. The shim `grading/__init__.py` needs no new re-exports —
no external module consumes a new grading-layer symbol (`scrub_submission_cached` is already
exported; its new keyword-only param is invisible to the shim).

---

## 2. Pipeline design

### 2.1 Where extraction happens — draft time, never audit time

`scrub_submission_cached(session, job, submission, cache_file, commit=True)` (in
`grading/caching.py`) is called from two places: `privacy_audit.run_privacy_audit` (no engine
available, must stay free/local) and `_draft_submission` in `grading/drafting.py` (engine
available).

Change the signature to:

```python
def scrub_submission_cached(
    session, job, submission, cache_file, commit=True,
    vision_extractor: VisionExtractor | None = None,
) -> CachedScrubbedSubmission
```

where `VisionExtractor` is a small protocol/callable wrapping the grading engine's
`extract_image`. `privacy_audit.py` passes nothing (audit stays free and sends nothing).
`_draft_submission` passes an adapter when **all** of: the job has
`include_visual_submissions=True`, the engine's catalog model has `supports_vision=True`
(field exists — `grep -n supports_vision apps/api/src/classroom_downloader/llm_catalog.py`),
and the engine is not the mock (mock implements `extract_image` too, returns canned data —
see §6.3).

Behavior matrix for an `image/*` cache file inside `scrub_submission_cached` /
`extract_submission_content`:

| consent | vision_extractor | result |
|---|---|---|
| off | — | today's behavior: `unsupported` / `unsupported_visual_submission` |
| on | `None` (audit path) | `status="pending_vision"`, empty text, **no scrub-cache write** |
| on | present (draft path) | vision call → §2.2 |

`pending_vision` is a new extraction status. Add it to `_EXTRACTION_STATUS_RANK` in
`grading/_common.py` with rank 1 (same severity as `degraded`) and to the frontend `extractionLabel`
map (PT-BR: `"aguardando extração visual"`).

### 2.2 The vision extraction call (draft path)

Per image file, in order:

1. **Scrub-cache lookup with bypass rule.** A cache hit is honored **unless** the row is an
   image-mime row whose `extraction_status` is `pending_vision`, or is `unsupported` with
   `extraction_error="unsupported_visual_submission"` (a stale pre-feature / pre-consent row).
   Those are treated as misses. ⚠️ Without this rule the feature silently does nothing for
   any job that already ran an audit.
2. **Local preprocessing** (§5). Local failures here produce extraction `status="failed"`
   with a `local_*` error code (§3) — the image **never left the machine**, and the UI must
   say so.
3. **Vision call** via `vision_extractor` → `VisionExtractionResult` (§6.1) or a classified
   error (§3).
   - **Transient API errors (`retryable=True`): do NOT write a scrub-cache row.** The next
     draft/retry must re-attempt. Record the failed extraction attempt row (§2.4), set the
     submission error, stop processing this file.
   - Permanent errors (`content_blocked`, `vision_unreadable`, …): cache as
     `status="failed"` so retries don't re-bill a hopeless image.
4. **Assemble text.** `transcription + "\n\n[descrição visual]\n" + visual_description`
   (skip the second block when empty). Map `legibility`: `full→supported`,
   `partial→degraded`, `unreadable→failed (error="vision_unreadable")`.
5. **Scrub.** The assembled text goes through the existing `scrub_submission` unchanged
   (regex catches roster name, CPF, etc. in the transcription). Then merge the model's
   `pii_observed` (§6.1) into the report: each category increments `counts` under its own
   key; status escalation: `face` or `id_document` present →
   `high_reidentification_risk`; any other category present → at least `redacted`.
   Implement the merge in `privacy.py` (new function `merge_reported_pii(report, observed)`),
   not inline in the grading package.
6. **Cache write** exactly as today (`GradingScrubCache` row; the new pii categories ride in
   the existing `privacy_flags_json` / `redaction_counts_json`).
7. **Record the extraction attempt** (§2.4).

Note: `ensure_privacy_audit_allows_draft` (routers/grading.py) already blocks drafting while
an audit has high-risk rows — so the `high_reidentification_risk` escalation from step 5 has
real teeth on a subsequent audit run. No new gate needed.

### 2.3 Multi-attachment submissions

`_draft_submission` already iterates per file and `_combine_submission_content` labels parts
`=== Arquivo N ===`. One vision call **per image file** (cache is per `content_hash`).
A submission mixing a `.py` file and a photo simply gets both text bodies combined. No change
to the combiner.

### 2.4 Attempt recording & cost

Add to `GradingAiAttempt`: `stage: str = "grading"` and `retryable: bool = False`
(models.py + dev-migration in database.py — follow the existing
`ensure_sqlite_dev_migrations` ALTER-TABLE pattern, `grep -n "ADD COLUMN" database.py`).

Each vision extraction call (success or failure) records an attempt row with
`stage="extraction"`, usage/cost from `engine.last_usage` / latency exactly like
`_record_attempt` does for grading (reuse `_attempt_metadata` — both live in
`grading/attempts.py`). Job cost rollups already sum attempt rows — verify with
`grep -n total_cost_cents apps/api/src/classroom_downloader/grading/drafting.py`
(`_refresh_cost_rollup`) and ensure extraction attempts are included in the same rollup.

---

## 3. Error taxonomy (both stages) — the layered-error deliverable

New module `llm_errors.py`:

```python
@dataclass(frozen=True)
class LlmCallError(Exception):
    code: str        # one of the codes below
    retryable: bool
    detail: str | None = None   # for logs only, never shown to user, never PII

def classify_llm_exception(exc: Exception) -> LlmCallError: ...
```

Mapping (litellm exposes typed exceptions; import from `litellm.exceptions`):

| litellm exception | code | retryable |
|---|---|---|
| `ServiceUnavailableError`, `InternalServerError` | `api_unavailable` | **yes** |
| `RateLimitError` | `api_rate_limited` | **yes** |
| `Timeout` | `api_timeout` | **yes** |
| `APIConnectionError` | `api_connection` | **yes** |
| `AuthenticationError`, `PermissionDeniedError` | `api_auth_failed` | no |
| `ContextWindowExceededError` | `context_window_exceeded` | no |
| `ContentPolicyViolationError` (and Gemini safety blocks) | `content_blocked` | no |
| `BadRequestError` (other) | `api_bad_request` | no |
| `ValueError("malformed_llm_response")` (our parser) | `malformed_llm_response` | **yes** (one-off model flake) |
| anything else | `llm_call_failed` | no |

Note `litellm.completion` is already called with `num_retries` — these codes surface only
after litellm's internal retries are exhausted. Do **not** add another retry loop; classify,
persist, and let the teacher (or a later manual action) retry via the existing endpoint
`POST /api/grading/jobs/{job_id}/submissions/{submission_id}/retry`
(`grep -n "submissions/{submission_id}/retry" apps/api/src/classroom_downloader/routers/grading.py`).

**Stage prefixing:** extraction-stage errors are persisted as `safe_error = "vision_" + code`
(e.g. `vision_api_unavailable`); grading-stage errors as the bare code. Local preprocessing
errors (never sent): `local_preprocessing_failed`, `local_unsupported_image_format`,
`local_image_too_large`, plus the existing `cached_file_missing`. This gives the UI the three
layers the teacher must distinguish:

1. `local_*` / `cached_file_missing` → "the image never left the machine"
2. `vision_api_*` / `api_*` (retryable) → "the provider was unreachable — retry later"
3. `vision_unreadable`, `content_blocked`, `malformed_llm_response`, `vision_malformed_response`
   → "the model received it and failed at the task"

**Grading-stage wiring:** replace the bare `except Exception` around
`grading_engine.grade(...)` in `grading/drafting.py`
(`grep -n grading_engine_failed apps/api/src/classroom_downloader/grading/drafting.py`) with
`except LlmCallError` after wrapping the engine call, persist `code` as `safe_error` and
`retryable` on the attempt row, and mirror both onto the submission
(`submission.error = code`; expose `error_retryable` in the submission snapshot DTO —
`grep -n "def _submission_read" apps/api/src/classroom_downloader/grading/snapshots.py` and
`grep -n "class GradingSubmissionRead" apps/api/src/classroom_downloader/schemas.py`).
Keep `grading_engine_failed` parsing-compat nowhere — it is replaced, and the frontend label
map is updated in the same PR (§7).

---

## 4. Consent gate

### 4.1 Backend

- `GradingJob.include_visual_submissions: bool = False` (models.py + dev-migration ALTER,
  SQLite `INTEGER DEFAULT 0`).
- `GradingJobCreate` / `GradingJobRead` in schemas.py expose it; job-create router passes it
  through.
- It is set at job creation and is **immutable after drafting starts** (same rule as
  criteria edits — `grep -n "Criteria can only be edited" routers/grading.py` for the 409
  pattern if you add an update path; simplest is create-time only).

### 4.2 Audit semantics

In `run_privacy_audit`: image rows behave per the §2.1 matrix. With consent **on**, the row
gets `extraction_status="pending_vision"`, `audit_pass=True`, `blocked_reason=None`, and the
audit UI shows an explicit notice on such rows: the pixels cannot be pre-scrubbed and will be
sent to the model for transcription at drafting time. With consent **off**, unchanged
(blocked, `unsupported_visual_submission`).

---

## 5. Image preprocessing (new module `image_preprocessing.py`)

Add `pillow` to `apps/api/pyproject.toml`.

```python
@dataclass(frozen=True)
class PreparedImage:
    data: bytes          # re-encoded JPEG
    mime_type: str       # always "image/jpeg" after re-encode
    width: int
    height: int

def prepare_image_for_llm(path: Path, *, max_dimension: int = 1536,
                          max_input_bytes: int = 15_000_000) -> PreparedImage
```

Steps: reject files over `max_input_bytes` (`local_image_too_large`); open with Pillow
(failure → `local_preprocessing_failed`); `ImageOps.exif_transpose` (bake orientation);
convert to RGB; downscale so the longest side ≤ `max_dimension`; re-encode JPEG quality 85
**without** EXIF/metadata (privacy: phone photos carry GPS + device IDs — re-encoding from
the pixel buffer drops them; do not copy `exif=` into `save()`).

Accepted input mimes: `image/jpeg`, `image/png`, `image/webp`. Anything else `image/*`
(HEIC, TIFF, SVG, GIF) → `local_unsupported_image_format` (extraction `status="unsupported"`).
HEIC is explicitly deferred; note it in the error label so the teacher understands
("formato de imagem não suportado (ex.: HEIC)").

Raise typed errors (reuse `LlmCallError` with the `local_*` codes, `retryable=False`) so the
caller persists them uniformly.

Also: add `.jpg`, `.jpeg`, `.webp` to `SAFE_SOURCE_EXTENSIONS` in `content_extraction.py`
(`.png` is already there) so `safe_source_label` keeps the extension.

---

## 6. Engine changes

### 6.1 Contracts (grading_engine.py)

```python
@dataclass(frozen=True)
class VisionExtractionRequest:
    job_id: str
    submission_id: str
    activity_title: str
    source_label: str          # pseudonym, never the real filename
    image_data: bytes          # preprocessed JPEG (§5)
    image_mime_type: str

@dataclass(frozen=True)
class VisionExtractionResult:
    transcription: str         # the student's work, as text
    visual_description: str    # layout/visual elements worth grading, "" if n/a
    content_kind: str          # handwriting | screen_photo | code_screenshot
                               # | app_screenshot | document_photo | other
    legibility: str            # full | partial | unreadable
    pii_observed: list[str]    # name_visible | face | id_document | contact_info | other_pii
```

Add `extract_image(request) -> VisionExtractionResult` to the `GradingEngine` protocol.

### 6.2 LiteLLM implementation (litellm_engine.py)

Multimodal user message:

```python
{"role": "user", "content": [
    {"type": "text", "text": <context json: activity_title, source_label>},
    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
]}
```

System prompt requirements (write it in English, demand PT-BR field values where free-text):
- The image is one of: photo of a computer screen, photographed handwritten work, screenshot
  of code/terminal output, screenshot of frontend/UI work, screenshot of other computer work.
  Identify which (`content_kind`).
- Transcribe **the student's work** faithfully and completely (`transcription`). For visual
  work (UI, diagrams), also describe layout/structure/colors succinctly
  (`visual_description`) — the grader sees only this text, never the image.
- **PII substitution at the source:** any personal name, ID number, e-mail, phone, or handle
  visible in the image must appear in the transcription as `[student]`, `[cpf]`, `[email]`,
  `[phone]`, `[social]` — never verbatim — and the corresponding `pii_observed` category must
  be reported. Faces and ID documents are reported in `pii_observed` only, never described.
  (The regex scrub then runs over the output as defense in depth.)
- `legibility`: `full` if essentially everything was readable, `partial` if meaningful chunks
  were not, `unreadable` if the work cannot be assessed from this image.
- Respond JSON only.

Use a strict `json_schema` response format mirroring `_rubric_response_format`'s pattern
(enums for `content_kind`, `legibility`, `pii_observed` items; all five fields required).
Empty/whitespace `transcription` **and** `visual_description` with `legibility != "unreadable"`
→ treat as `malformed_llm_response`. Parse failures → `vision_malformed_response`
(retryable, like grading-stage malformed). Wrap the `litellm.completion` call with
`classify_llm_exception`. Capture `last_usage` / latency the same way `grade()` does.
Reuse `self.max_output_tokens` but allow up to 2000 for dense handwriting
(`min(model cap, 2000)`).

### 6.3 Mock engine

`MockGradingEngine.extract_image` returns a deterministic result seeded from
`job_id|submission_id` (mirror `grade()`'s sha256 pattern): a short canned transcription,
`content_kind="handwriting"`, `legibility="full"`, `pii_observed=["name_visible"]` so the
PII-merge path is exercised in every dev run. The mock's existing `visual_submission` flag
behavior in `grade()` stays.

---

## 7. Frontend (apps/web)

All copy in PT-BR, matching existing tone in `graderStatus.ts`.

1. **GraderSetup**: checkbox "Incluir envios visuais (fotos e capturas de tela)" with the
   consent explanation: pixels cannot be pre-anonymized; the image is sent once to the AI
   provider for transcription; the transcription is anonymized before grading. Default off.
   Sent on job create (`api.ts` + `types.ts`: `include_visual_submissions`).
2. **Audit panel** (GraderSetup audit section): rows with `pending_vision` show the warning
   notice (§4.2); when consent is off, image rows keep today's blocked rendering.
3. **graderStatus.ts**:
   - `extractionLabel`: add `pending_vision: "aguardando extração visual"`.
   - `safeStatusLabel`: add every §3 code, three layers explicit, e.g.
     `local_preprocessing_failed: "falha ao preparar a imagem (não foi enviada)"`,
     `local_unsupported_image_format: "formato de imagem não suportado (não foi enviada)"`,
     `vision_api_unavailable: "IA indisponível na extração — tente novamente"`,
     `api_unavailable: "IA indisponível — tente novamente"`,
     `api_rate_limited: "limite de requisições — tente novamente em instantes"`,
     `vision_unreadable: "a IA não conseguiu ler a imagem"`,
     `content_blocked: "conteúdo bloqueado pelo provedor"`,
     `malformed_llm_response: "resposta inválida do modelo — tente novamente"`, etc.
   - `redactionLabel`: add `name_visible: "Nome (na imagem)"`, `face: "Rosto"`,
     `id_document: "Documento"`, `contact_info: "Contato (na imagem)"`, `other_pii: "Outros dados pessoais"`.
4. **GraderReview / StudentRow**: this is where the teacher decides — render the error with
   its layer label and, when the submission snapshot says `error_retryable`, a
   "Tentar novamente" button calling the existing retry endpoint (check `api.ts` for an
   existing retry helper; the backend route exists). Show a small badge for visual
   submissions (`content_kind` present or image mime) so teachers know feedback came from a
   transcription.
5. **types.ts**: extend `GradingSubmission` with `error_retryable?: boolean` and whatever
   snapshot fields §3 added; extend `GradingJob` with `include_visual_submissions`.

---

## 8. Tests (apps/api/tests, follow conftest.py fixtures)

### 8.1 Unit (no network, run in CI)

- `test_image_preprocessing.py`: EXIF GPS tag present in input → absent in output;
  orientation-6 input comes out upright; 4000px input → ≤1536px; HEIC/TIFF rejected with
  `local_unsupported_image_format`; oversize rejected.
- `test_llm_errors.py`: every row of the §3 table (construct litellm exceptions directly).
- `test_vision_extraction.py` (monkeypatch `litellm.completion`, mirror
  `test_litellm_engine.py` patterns): happy path (legibility mapping to
  supported/degraded/failed); pii merge escalation (`face` →
  `high_reidentification_risk`); roster-name in transcription gets regex-redacted; transient
  API error → **no scrub-cache row written** and attempt row has
  `stage="extraction"`, `retryable=True`; permanent error → cached as failed; stale
  `unsupported_visual_submission` cache row bypassed when consent on; consent off →
  today's behavior byte-for-byte; audit path (no extractor) → `pending_vision`, no cache
  write, no LLM call.
- `test_grading.py` additions: grading-stage 503 → `api_unavailable`, `retryable=True` on
  attempt and submission snapshot.

### 8.2 Live (env-gated, manual)

Real-call tests gated like the existing real-provider tests
(`grep -n "skip" apps/api/tests/test_google_real_provider.py` and mirror the gating):
skip unless `LIVE_LLM_TESTS=1` and a real model is configured. Fixture images go in
`apps/api/tests/fixtures/images/` (the maintainer is curating real samples — one per §0
nature: screen photo, handwriting photo, code screenshot, app screenshot). Each test asserts
only structural truths (non-empty transcription, valid enums, pii reported when the fixture
contains a planted name) — never exact text. Skip individually when a fixture file is absent.

### 8.3 Verification gates

- Phase order below; full test suite green after every phase.
- After final phase: `graphify update .`

---

## 9. Execution phases

Each phase is independently shippable and ends with the full suite green.

- **Phase 0 — baseline.** Run the suite, record the count.
- **Phase 1 — error taxonomy (standalone value, no vision yet).** `llm_errors.py`; columns
  `GradingAiAttempt.stage`/`.retryable` + migrations; replace the bare except around
  `grade()`; snapshot exposes `error_retryable`; frontend labels + retry button. This alone
  fixes today's 503 experience.
- **Phase 2 — consent plumbing.** `GradingJob.include_visual_submissions` + migration +
  schemas + GraderSetup checkbox; audit `pending_vision` semantics (§4.2) including the
  no-cache-write rule; `_EXTRACTION_STATUS_RANK` + frontend label.
- **Phase 3 — preprocessing.** `image_preprocessing.py` + pillow dep + unit tests +
  `SAFE_SOURCE_EXTENSIONS` additions.
- **Phase 4 — vision extraction.** Engine contracts + litellm + mock implementations;
  `scrub_submission_cached` integration (bypass rule, no-cache-on-transient, pii merge,
  extraction attempt recording); unit tests of §8.1.
- **Phase 5 — review-screen surfacing.** GraderReview error layers, visual badge, audit
  panel notice; remaining labels.
- **Phase 6 — live validation.** Fixtures + env-gated tests; run once manually with real
  images; `graphify update .`; update this plan's status line.

---

## 10. Known accepted limitations (document, don't fix)

- The scrub cache is keyed per `job_id` — a **new** job on the same activity re-pays vision
  extraction even though the transcription exists under the old job. Accepted for v1.
- Cache expiry (`expires_at`) on a vision-extracted row re-bills on next draft. Accepted —
  same TTL discipline as file cache.
- Rubric inference samples are collected before drafting, so image submissions never
  contribute samples to `infer_rubric`. Accepted.
- Transcription is lossy for genuinely visual assignments; `visual_description` +
  `degraded` status are the v1 mitigation. A direct multimodal grading mode is explicitly
  deferred.
- The first transit of the image to the provider cannot be pre-audited; the consent gate +
  EXIF strip + provider no-training API terms are the mitigation.
