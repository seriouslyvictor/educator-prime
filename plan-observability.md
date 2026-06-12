# Plan — Observability: Sentry, persisted events/LLM logs, admin page (shadcn)

> **Status:** implementation in progress on branch `codex/observability-admin`.
> **Execution progress:**
> - Phase 0 baseline complete: prerequisite verified in `archive/plan-image-grading.md` as implementation complete/validated; `uv run --extra dev pytest -q` in `apps/api` -> 160 passed, 4 skipped; `pnpm build` in `apps/web` -> build succeeded.
> - Phase 1 Sentry complete: added `CD_SENTRY_DSN`/`CD_SENTRY_ENVIRONMENT`, DSN-gated backend Sentry init with error-only settings and total sensitive-field scrubber, plus light import/scrubber tests. Gate: `uv run --extra dev pytest -q` in `apps/api` -> 163 passed, 4 skipped; `pnpm build` in `apps/web` -> build succeeded.
> - Phase 2 event persistence complete: added structured `cd_event`/`cd_fields` extras without changing formatted output, request/user contextvars, `AppEvent`, guarded lazy DB logging handler, startup/admin-shareable retention purge, and sink tests. Gate: `uv run --extra dev pytest -q` in `apps/api` -> 169 passed, 4 skipped; `pnpm build` in `apps/web` -> build succeeded.
> **Audience:** an executing agent with no prior context. Read §0–§8 before touching code.
> **Line numbers / symbol locations are as-of-writing guides — re-derive every location with
> `grep -n` at execution time.**
> **Hard prerequisite:** `plan-image-grading.md` is fully executed and validated **first** —
> no deviations from it are tolerated, and this plan deliberately consumes its outputs
> (`llm_errors.py`, the typed `safe_error` codes, `GradingAiAttempt.stage`/`.retryable`).
> Both plans touch `models.py`, `database.py`, `grading/attempts.py`, `litellm_engine.py`,
> `routers/grading.py`, and `graderStatus.ts`; executing this plan second avoids all conflicts.

---

## 0. Goal & context

The app is becoming a multi-user internal tool (~5 trusted users) on a VPS. Today every
structured event from `observability.py` (`log_event` taxonomy, redaction, JSON option) goes
to **stdout and dies there**. `GradingAiAttempt` persists LLM-call *metadata* (model, status,
`safe_error`, tokens, cost, latency — and post-image-plan, `stage` + `retryable`) but not the
prompt/response bodies. Auth events (`auth.google.callback.invalid_state`,
`google.auth.refresh_failed`, …) are well-instrumented but unqueryable. Checking the console
24/7 is the only "alerting".

Four deliverables, layered so each is independently shippable:

1. **Sentry (SaaS free tier)** — unhandled-exception capture + email alerting on the backend.
   The only piece that *tells* someone something broke.
2. **Persisted app events** — a DB-backed `AppEvent` table fed from the existing
   `log_event/log_warning/log_error` helpers (WARNING+ and all `auth.*` events), with retention.
3. **Persisted LLM payloads** — scrubbed prompt + raw response stored per
   `GradingAiAttempt`, TTL-bound, settings-gated.
4. **Admin page** in `apps/web` to browse 2 and 3 — and the vehicle for **folding shadcn/ui
   into the project** via the user-supplied preset `b4X1u3HhEA`. shadcn is adopted for the
   **new admin area only**; existing views are not restyled (see §7 scope rule).

**Definition of done**
- With `CD_SENTRY_DSN` unset, behavior is byte-for-byte today's (Sentry fully inert).
- WARNING+ log events and all `auth.*` events land in `appevent` rows with redacted fields;
  console output is **byte-for-byte unchanged** (the formatted-string contract holds).
- Every `GradingAiAttempt` (grading *and* extraction stage) can optionally persist its scrubbed
  prompt + raw response; payloads are purged after `llm_payload_retention_days`.
- `/api/admin/*` endpoints exist, gated by an email allowlist; non-admins get 403.
- `apps/web` has Tailwind v4 + shadcn (preset `b4X1u3HhEA`) and an Admin view (PT-BR) with
  Events and LLM-calls tabs; **existing views render visually unchanged** (§5.2 no-preflight rule).
- All pre-existing tests pass; new unit tests cover §8; `pnpm build` green; `graphify update .`.

**Out of scope (do not build):** frontend Sentry (`@sentry/react`) — revisit later; restyling
any existing component to shadcn; log-aggregation stacks (Loki/ELK); live-tail/WebSocket
streaming of events; admin actions that *mutate* (user management, job deletion).

---

## 1. Files touched (overview)

| File | Change |
|---|---|
| `apps/api/pyproject.toml` | add `sentry-sdk[fastapi]` |
| `settings.py` | `sentry_dsn`, `sentry_environment`, `admin_emails`, `app_event_retention_days`, `llm_payload_logging`, `llm_payload_retention_days` |
| `main.py` | Sentry init (DSN-gated); request-id middleware; retention purge in `lifespan`; register admin router |
| `observability.py` | log helpers also attach structured `extra={"cd_event", "cd_fields"}`; `DbEventHandler`; contextvars for request id / user email |
| `models.py` | `AppEvent` table; `GradingAiAttemptPayload` table |
| `database.py` | nothing (new tables come from `create_all`; no ALTERs needed) |
| `api/deps.py` | `require_admin` dependency; `get_current_session` sets the user-email contextvar |
| `routers/auth.py` + `schemas.py` | `AuthState.is_admin` |
| `routers/admin.py` **(new)** | events list, attempts list, payload detail, stats |
| `grading/attempts.py` | `_record_attempt` gains optional payload args; writes `GradingAiAttemptPayload` |
| `grading_engine.py`, `litellm_engine.py` | engines expose `last_prompt_text` / `last_response_text` (mirroring `last_usage`) |
| `grading/drafting.py`, `grading/caching.py` | pass payloads through to `_record_attempt` (grading + extraction stages) |
| `apps/web` (root) | Tailwind v4, `@/*` alias, `components.json` via preset, shadcn `ui/` components |
| `apps/web/src` | `AdminView` (new, shadcn), Rail entry, `api.ts`/`types.ts` additions |
| `apps/api/.env.example`, `apps/web/.env.example` | document new vars |

---

## 2. Sentry (backend)

- New settings: `sentry_dsn: str | None = None`, `sentry_environment: str = "dev"`.
- Init in `main.py` right after `settings = get_settings()`, **only when `sentry_dsn` is set**:

```python
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=False,
        max_request_body_size="never",   # request bodies contain student work
        traces_sample_rate=0.0,          # errors only — protects the free-tier quota
        before_send=_scrub_sentry_event, # reuse observability._SENSITIVE_FIELDS
    )
```

- `_scrub_sentry_event(event, hint)`: walk `event.get("extra", {})`, `event.get("contexts", {})`,
  and breadcrumb `data` dicts, replacing values whose key is in
  `observability._SENSITIVE_FIELDS` with `"<redacted>"`. Keep it dumb and total — return the
  event, never raise.
- **No code changes needed at call sites.** sentry-sdk's default logging integration turns
  INFO logs into breadcrumbs and ERROR logs into events — so every existing `log_event(...)`
  becomes context attached to a crash, and every `log_error(...)` (it calls
  `logger.exception`) becomes a Sentry issue with the traceback. Unhandled exceptions in
  routes are captured by the FastAPI/Starlette integration automatically.
- LLM payloads and scrubbed student text must **never** reach Sentry: they only ever appear in
  function locals (not sent — sentry default) and the `cd_fields` extra is pre-redacted by
  `observability` before it reaches the logger.
- Free-tier note: ~5k events/month is far beyond what 5 users generate with errors-only
  config. Configure the Sentry project's alert rule (email on new issue) in the Sentry UI —
  that's the "stop watching the console" deliverable. Manual step; document in `.env.example`.

---

## 3. Persisted app events

### 3.1 Structured extras (no console change)

In `observability.py`, change the four helpers to pass structured data alongside the
already-formatted message — the rendered console line stays byte-for-byte identical:

```python
def log_event(logger, event, **fields):
    logger.info(_format_event(event, fields),
                extra={"cd_event": event, "cd_fields": _safe_payload(fields)})
```

where `_safe_payload(fields)` applies `_safe_value` per key (the same redaction the formatter
applies) and returns a JSON-serializable dict. Same for `log_debug`, `log_warning`,
`log_error`. `JsonEventFormatter` and the text formatters ignore unknown `extra` keys — no
output change.

### 3.2 Request/user context (contextvars)

- `observability.py` gains two module-level `contextvars.ContextVar`s: `current_request_id`,
  `current_user_email` (defaults `None`).
- `main.py`: a tiny pure-ASGI/`@app.middleware("http")` middleware sets
  `current_request_id` to `uuid4().hex[:12]` per request.
- `api/deps.py::get_current_session`: after resolving the row, set
  `current_user_email.set(row.user_email)` (also in the mock branch). One line; nothing else
  in deps changes.

### 3.3 The DB sink

`AppEvent` model (`models.py`) — new table, so `init_db()`'s `create_all` picks it up; **no
dev-migration ALTER needed** (those are only for new columns on existing tables):

```python
class AppEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)                  # uuid4
    created_at: datetime = Field(default_factory=..., index=True)
    level: str = Field(index=True)                     # WARNING/ERROR/INFO
    event: str = Field(index=True)                     # e.g. auth.google.callback.invalid_state
    logger_name: str
    user_email: str | None = Field(default=None, index=True)
    request_id: str | None = None
    fields_json: str = "{}"                            # pre-redacted (§3.1)
    exc_text: str | None = None                        # traceback for ERROR records
```

`DbEventHandler(logging.Handler)` in `observability.py`, attached once in
`configure_logging()`:

- **Persist rule:** record has a `cd_event` attr AND (`record.levelno >= logging.WARNING`
  OR `cd_event.startswith("auth.")` OR `cd_event` in `{"app.startup"}`). Records without
  `cd_event` (third-party libs) are persisted only at ERROR+.
- **Recursion/safety guards (all mandatory):** skip records from `sqlalchemy*` and
  `sentry_sdk*` loggers; a module-level re-entrancy flag (contextvar bool) set around the DB
  write; the whole `emit()` body in `try/except Exception: pass` — logging must never take
  the app down; **lazy-import the engine inside `emit()`**
  (`from .database import engine` — verify the symbol name with
  `grep -n "engine" apps/api/src/classroom_downloader/database.py`) to avoid an
  observability↔database import cycle at module load.
- Each emit opens its own short-lived `Session(engine)` — handler runs outside any request
  session and must not share one.

### 3.4 Retention

- Setting `app_event_retention_days: int = 30`.
- Purge function `purge_expired_observability_rows(session)` (delete `AppEvent` older than
  retention; also payload rows, §4) — called from `lifespan` startup and at the top of the
  admin events endpoint (cheap, keeps the table bounded without a scheduler). Follow the
  delete-then-commit style of `session_cleanup.py`.

---

## 4. Persisted LLM payloads

### 4.1 Storage — separate table, not columns

Keep `GradingAiAttempt` rows light (they are the permanent cost/audit ledger) and make the
heavy text purgeable independently:

```python
class GradingAiAttemptPayload(SQLModel, table=True):
    attempt_id: str = Field(primary_key=True)          # FK-by-convention to GradingAiAttempt.id
    job_id: str = Field(index=True)
    prompt_text: str                                    # the SCRUBBED text that was sent
    response_text: str | None = None                    # raw model output (or None on transport failure)
    created_at: datetime = Field(default_factory=..., index=True)
```

New table → `create_all`, no ALTER. Settings: `llm_payload_logging: bool = True`,
`llm_payload_retention_days: int = 14`. Purged by §3.4's function.

**Privacy stance (do not weaken):** `prompt_text` is post-scrub **by construction** — it is
the exact pseudonymized text that already left the machine for the provider. Raw student
text and real names never enter this table. Payloads are local-DB only; never attached to
Sentry or to `AppEvent.fields_json`.

### 4.2 Capture

- Engines: add `last_prompt_text: str | None` / `last_response_text: str | None` set inside
  `grade()` and `extract_image()` exactly where `last_usage` is set
  (`grep -n "last_usage" apps/api/src/classroom_downloader/litellm_engine.py apps/api/src/classroom_downloader/grading_engine.py`).
  `last_response_text` is the raw completion content *before* parsing (so malformed responses
  are inspectable — that's half the point). Mock engine sets canned values so the dev admin
  page always has data.
- `grading/attempts.py::_record_attempt` gains keyword-only
  `prompt_text: str | None = None, response_text: str | None = None`; when
  `settings.llm_payload_logging` and `prompt_text is not None`, write a
  `GradingAiAttemptPayload` row alongside the attempt. (`attempts` already imports `models`
  only — the package DAG is untouched.)
- Call sites pass the values through: the grading-stage site in `grading/drafting.py`
  (`_draft_submission` — the prompt text is the combined scrubbed content it already holds;
  response from `engine.last_response_text`) and the extraction-stage site the image plan
  added in `grading/caching.py` (`grep -rn '_record_attempt' apps/api/src/classroom_downloader/grading/`
  at execution time for the full list).
- On classified transport failures (`LlmCallError` with `api_*` codes) there may be no
  response; record the payload row with `response_text=None` so the prompt that failed is
  still inspectable.

---

## 5. Admin gate + API

### 5.1 Who is admin

- Setting `admin_emails: str = ""` — comma-separated, compared case-insensitively against
  `UserSession.user_email`.
- `api/deps.py::require_admin(current_session = Depends(get_current_session))`:
  mock provider → allow (dev convenience, mirrors `get_current_session`'s mock branch);
  otherwise 403 unless the email is in the parsed set. Empty list = nobody (fail closed).
- `schemas.py::AuthState` gains `is_admin: bool = False`; both `AuthState` constructions in
  `routers/auth.py` (`grep -n "return AuthState\|AuthState(" routers/auth.py`) set it from the
  same parsed set so the frontend can gate the Rail entry. `disconnected_auth_state()` keeps
  the default `False`.

### 5.2 Router (`routers/admin.py`, new)

`APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])`, registered in
`main.py` **before** the static catch-all, like every other router.

| Endpoint | Behavior |
|---|---|
| `GET /api/admin/events` | filters: `level`, `event_prefix`, `user_email`, `q` (substring on `fields_json`), `before` (ISO cursor on `created_at`), `limit` ≤ 200. Ordered `created_at DESC`. Calls the §3.4 purge first. |
| `GET /api/admin/llm/attempts` | filters: `job_id`, `status`, `stage`, `retryable`, `model`, `before`, `limit` ≤ 200. Returns attempt metadata + `has_payload` flag (EXISTS on the payload table). |
| `GET /api/admin/llm/attempts/{attempt_id}/payload` | 404 if purged/disabled; returns `prompt_text`, `response_text`. |
| `GET /api/admin/stats` | header cards: event counts by level (24h), attempt count / failure count / total `cost_cents` (7d, via the existing rollup fields — sum over attempts). |

Schemas: `AppEventRead`, `AiAttemptAdminRead`, `AiAttemptPayloadRead`, `AdminStats` in
`schemas.py`. Read-only — no mutation endpoints in this plan.

---

## 6. shadcn fold-in (`apps/web`)

Current state (verified): Vite 6 + React 19 + TS, `packageManager: pnpm@10.28.1`,
CSS Modules + `styles/tokens.css` + homegrown `ui.tsx`, `lucide-react` already installed,
**no Tailwind, no `components.json`, no `@/*` alias**.

### 6.1 Pre-steps the preset needs (run in `apps/web`)

1. `pnpm add tailwindcss @tailwindcss/vite`
2. `vite.config.ts`: add the `tailwindcss()` plugin and
   `resolve: { alias: { "@": path.resolve(__dirname, "./src") } }`.
3. `tsconfig.json`: add `"baseUrl": "."`, `"paths": { "@/*": ["./src/*"] }` (single tsconfig
   in this app — verify, no `tsconfig.app.json` exists at plan time).
4. Create `src/styles/tailwind.css` and import it in `main.tsx` **after** the existing
   `tokens.css`/`base.css` imports — see §6.2 for its contents.

### 6.2 ⚠️ No-preflight rule — protect the existing UI

A full `@import "tailwindcss";` ships preflight (a global CSS reset) that **will** change the
rendering of every existing CSS-module view — unacceptable while the grader screens were just
validated under `plan-image-grading.md`. Import the layers without preflight:

```css
/* src/styles/tailwind.css */
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/utilities.css" layer(utilities);
/* NO tailwindcss/preflight.css — existing views must stay byte-identical */
```

The preset's `init` will write its theme variables/`@theme` block into the project CSS — let
it, but if it rewrites the import to the full `@import "tailwindcss"`, restore the two-layer
form above. If a shadcn component visibly depends on a preflight rule (e.g. border-color
default), add the minimal rule scoped under the admin container (`.adminRoot ...`) — never
globally. The existing `styles/base.css` already establishes the app's own resets; verify
overlap before adding anything.

### 6.3 Apply the preset

```bash
cd apps/web
pnpm dlx shadcn@latest init --preset b4X1u3HhEA
```

Note: the user quoted `apply --preset`; the CLI subcommand for an existing project is
`init --preset <code>` per current shadcn docs. Run `pnpm dlx shadcn@latest --help` first and
use whichever form the installed CLI supports — **pass the code verbatim; never decode or
fetch preset codes manually.** Run it inside `apps/web` so `components.json`, aliases, and CSS
land in the right app.

Then add the components the admin page composes (skip any the preset already installed —
check `components.json` / `src/components/ui/`):

```bash
pnpm dlx shadcn@latest add button card badge table tabs select input field \
  input-group sheet separator skeleton empty spinner sonner
```

After adding: review the generated files against the shadcn skill's critical rules (icon
imports must be `lucide-react` — already the project's library; fix any `@/components/ui`
alias mismatches).

### 6.4 Gate for this phase

`pnpm build` green **and** a manual smoke of the existing views (connect, turmas, grader
setup/review, history) confirming zero visual drift — that is the entire point of §6.2.

---

## 7. Admin UI (`apps/web/src/components/admin/`)

Scope rule, stated once and binding: **shadcn components are used only under
`src/components/admin/`** in this plan. No existing component is migrated, restyled, or
edited beyond the Rail entry and `App.tsx` view wiring. (Broader shadcn migration is a future
plan once the preset has proven itself here.)

- `types.ts`: `AppView` union gains `"admin"`; `AuthState` gains `is_admin?: boolean`;
  new `AppEventItem`, `AiAttemptItem`, `AiAttemptPayload`, `AdminStats` types mirroring §5.2.
- `api.ts`: `adminListEvents(params)`, `adminListAttempts(params)`,
  `adminGetAttemptPayload(id)`, `adminGetStats()` following the existing fetch-helper style.
- `Rail.tsx`: admin entry (lucide `ShieldCheck` or similar), rendered only when
  `auth.is_admin`.
- `AdminView.tsx` (+ small subcomponents), all PT-BR copy matching `graderStatus.ts` tone:
  - Header: `Card`s from `/stats` (eventos 24h por nível, chamadas de IA 7d, custo 7d,
    falhas 7d).
  - `Tabs`: **Eventos** | **Chamadas de IA**.
  - Eventos: filter row (`Select` nível, `Input` busca, `Select` área — `auth.`, `grading.`,
    `cache.`…), `Table` (horário, nível como `Badge`, evento, usuário), row click → `Sheet`
    with pretty-printed `fields_json` + `exc_text`. "Carregar mais" cursor pagination via
    `before`. `Skeleton` while loading, `Empty` when no rows.
  - Chamadas de IA: filters (`Select` status/etapa, `Badge` retryable), `Table` (horário,
    job, etapa, modelo, status/`safe_error`, tokens, custo, latência), row click → `Sheet`
    with prompt/response in `<pre className="...">` blocks (when `has_payload`; otherwise an
    `Empty` explaining the payload was purged or logging is off).
- Follow the shadcn skill's critical rules throughout (Field/FieldGroup for the filter form,
  `gap-*` not `space-y-*`, semantic tokens only, `data-icon` on button icons, DialogTitle/
  SheetTitle present).

---

## 8. Tests (apps/api/tests; frontend gate is `pnpm build`)

- `test_observability_sink.py` **(new)**: WARNING via `log_warning` → `appevent` row with
  redacted fields (`email` key → `<redacted>`); INFO `auth.x` event persisted; INFO
  `grading.x` event NOT persisted; ERROR from a plain third-party logger persisted with
  `exc_text`; handler failure (e.g. closed engine) does not raise; console formatting
  unchanged (assert `_format_event` output for a fixed payload equals the pre-change string).
- `test_llm_payloads.py` **(new)**: attempt with payload logging on → payload row with
  scrubbed prompt; `llm_payload_logging=False` → no row; transport-failure attempt → row with
  `response_text=None`; purge removes rows past retention but keeps the attempt row.
- `test_admin_api.py` **(new)**: non-admin email → 403 on every `/api/admin/*` route; admin
  → 200; mock provider → allowed; filters (`level`, `job_id`, `before` cursor) behave;
  payload 404 after purge; `is_admin` true/false in `/api/auth/me` per `admin_emails`.
- `test_sentry_init.py` **(new, light)**: with `sentry_dsn=None` the app imports and serves
  without `sentry_sdk` initialized; `_scrub_sentry_event` redacts a planted
  `extra={"refresh_token": "..."}` and never raises on weird shapes.
- Existing suite: same counts as baseline, zero new failures.

---

## 9. Execution phases (each ends with the full suite + `pnpm build` green)

- **Phase 0 — baseline.** Record pytest counts (`cd apps/api; uv run --extra dev pytest -q`)
  and confirm `pnpm build` green in `apps/web`. Confirm `plan-image-grading.md` status says
  executed/validated; **abort if not.**
- **Phase 1 — Sentry.** §2. Deliverable: email alerting on unhandled errors. Manual step:
  create the Sentry project, set the alert rule, put the DSN in the VPS `.env`.
- **Phase 2 — event persistence.** §3 (structured extras, contextvars, `AppEvent`,
  `DbEventHandler`, retention) + its tests.
- **Phase 3 — LLM payloads.** §4 + tests.
- **Phase 4 — admin API.** §5 (settings, `require_admin`, `is_admin`, `routers/admin.py`,
  schemas) + tests. Backend is now fully usable via curl/OpenAPI docs even before the UI.
- **Phase 5 — shadcn fold-in.** §6. Gate: build green + zero visual drift on existing views.
  Commit the preset/init output separately from hand-written code.
- **Phase 6 — admin UI.** §7. Gate: build green + manual smoke of the admin page against the
  Phase-4 endpoints (mock engine provides attempt + payload data).
- **Phase 7 — wrap.** `.env.example` files updated (`CD_SENTRY_DSN`, `CD_ADMIN_EMAILS`,
  retention/payload toggles); full suite; `graphify update .` as its own commit; update this
  plan's status line.

**Git hygiene:** `git add` only touched files per phase — never `git add -A`. The shadcn
init/add output (Phase 5) is one commit; hand-written admin UI (Phase 6) is separate.

---

## 10. Watch-items (gotchas that will bite)

- **§3.3 recursion** is the #1 trap: a DB write inside a logging handler triggers SQLAlchemy
  logging triggers the handler. The re-entrancy contextvar + logger-name skip list are both
  required, not alternatives.
- **Console contract:** routers/tests grep nothing from log lines today, but the JSON format
  is a documented operational surface — §3.1 must not change a single rendered byte.
- **`get_current_session` mock branch** returns a synthetic `UserSession` without touching
  the DB — `require_admin` and the contextvar line must handle that branch too.
- **Static catch-all ordering** in `main.py`: the admin router must be registered before it,
  with the other routers.
- **Preflight regression (§6.2)** is the one frontend risk that breaks the "no deviations"
  guarantee around the freshly-validated grader screens. The two-layer import is mandatory;
  re-check it after the preset runs, because `init` may rewrite the CSS imports.
- **Payload size:** prompts for class-batch mode can be large; SQLite handles multi-MB TEXT
  fine, but keep `limit ≤ 200` on admin lists and never join payloads into list endpoints
  (`has_payload` EXISTS only).
- **Sentry in tests:** `CD_TESTING` runs must never init Sentry — guaranteed by
  `sentry_dsn=None` default; don't add a DSN to any test fixture.
