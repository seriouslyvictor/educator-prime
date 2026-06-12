# Plan — Error communication: contract, catalog, screens (shadcn-aware)

> **Status:** in progress. Phase 0 complete on `codex/error-screens`: baseline API
> `CD_GOOGLE_PROVIDER=mock uv run pytest -q` = 178 passed, 4 skipped; baseline web
> `pnpm build` = passed. Phase 0 decision: shadcn is present (`components.json` and
> `src/components/ui/*`), so `components/errors/` will use shadcn primitives per §4.1.
> Phase 1 complete: backend structured error contract, Google transient classifier,
> LLM budget code, busy-db handler, `X-App-Version`, OpenAPI snapshot, and
> superseded `scripts/route_snapshot.py` removal are implemented. Verification:
> `CD_GOOGLE_PROVIDER=mock uv run pytest -q` = 188 passed, 4 skipped; `pnpm build` =
> passed; `graphify update .` = passed.
> Phase 2 complete: `ApiError`, structured fetch parsing, network `unreachable`,
> PT-BR catalog, upgraded shared `InlineError`, render `ErrorBoundary`, and
> `api_budget_exhausted` row copy are implemented. Compatibility note: legacy local
> string errors are still accepted by the UI shim, but catalog fallback copy renders
> instead of raw strings. Verification: `pnpm build` = passed;
> `CD_GOOGLE_PROVIDER=mock uv run pytest -q` = 188 passed, 4 skipped;
> `graphify update .` = passed.
> Phase 3 complete: shadcn-backed `Gate`/`FullError`, partial-consent gate,
> gate-tier replacement rendering, API connectivity tracking, offline pill, and
> persistent unsupported-browser export notice are implemented. Verification:
> `pnpm build` = passed; `CD_GOOGLE_PROVIDER=mock uv run pytest -q` = 188 passed,
> 4 skipped; `graphify update .` = passed.
> Phase 4 complete: SSE streams retry 3 times with reconnecting progress copy
> before surfacing resume guidance, folder export skips per-file failures and
> summarizes them in `DoneView`, and empty states now explicitly say the condition
> is normal rather than an error. Verification: `pnpm build` = passed;
> `CD_GOOGLE_PROVIDER=mock uv run pytest -q` = 188 passed, 4 skipped;
> `graphify update .` = passed.
> **Audience:** an executing agent with no prior context. Read §0–§8 before touching code.
> **Line numbers / symbol locations are as-of-writing guides — re-derive every location with
> `grep -n` at execution time.**
> **Relationship to other plans:** Phases 1–2 and 4 have **zero dependency** on
> `plan-observability.md`. Phase 3 (screens) *prefers* shadcn primitives, which arrive via
> `plan-observability.md` §6 — see the §4.1 fallback rule if that hasn't landed or if the
> port balloons. This plan deliberately **extends** plan-observability's "shadcn only under
> `admin/`" scope rule to also cover `src/components/errors/` — that supersession is
> intentional and approved.

---

## 0. Goal & context

The app is onboarding ~5 non-technical teachers (PT-BR, SENAI) who will use it without
Victor nearby. Today almost every failure collapses into one of two bad outcomes:

- a generic red `InlineError` banner showing a raw backend `detail` string (English) or
  `"Requisição falhou com 500"` — no action, no explanation; or
- **silence**: `lib/api.ts` stale-while-revalidate swallows background failures
  (`.catch(() => undefined)`), so a dead API shows stale data with zero indication.

Observed user behavior: a red 500 with no action → the teacher gives up and assumes the app
is broken.

**What already exists (build on it, don't duplicate):**

- `fetchJson` in `apps/web/src/lib/api.ts` is the single chokepoint for all API errors —
  but it throws a plain `Error` and **discards the HTTP status**.
- App-level error state is a single `error: string | null` in `App.tsx`, rendered by
  `InlineError` (`components/ui.tsx`) on every view.
- Backend auth failures are centrally classified in `api/auth_errors.py` (session missing /
  expired / revoked, with purge semantics) — clean categories, but prose-only `detail`.
- LLM call failures have a typed taxonomy in `llm_errors.py` (`api_unavailable`,
  `api_rate_limited`, `api_timeout`, `api_connection`, `api_auth_failed`, `api_bad_request`,
  each with a `retryable` flag) and `graderStatus.ts` already maps them to per-row PT-BR
  copy. **The per-submission error tier is done.**
- `AuthState` already exposes `identity_scopes` / `classroom_scopes` / `drive_scopes`
  booleans (`schemas.py`, computed in `routers/auth.py::auth_me`) — partial-consent
  detection is already on the wire; no screen consumes it.
- Backend grading resume support exists (`test_grading_resume.py`) — the UI never offers it.
- Design drafts in `docs/UI/errors/` (~2,000 lines: `pieces.jsx`, `sections.jsx`,
  `error-styles.css`, `design-canvas.jsx`) define the visual language: `FullError` +
  `Gate` components with tone/icon/title/body/actions/foot. These are **design artifacts
  using globals — port them, never import them.**
- CI (`.github/workflows/ci.yml`) runs pytest + `pnpm build`; `tests/test_openapi_snapshot.py`
  pins the API contract — **any backend change here must regenerate the snapshot**
  (`uv run python scripts/export_openapi.py`).

**Definition of done**

- Every API failure reaching the user carries a machine-readable `code`; the frontend maps
  every code to PT-BR copy with a concrete next action ("tente novamente", "reconecte sua
  conta Google", "avise o administrador"). Unknown codes get a sane generic screen — the
  raw English `detail` string never renders again.
- The scenario matrix in §5 is fully wired (auth/7-day expiry, partial consent, API
  unreachable, Google down/rate-limited, LLM down/overloaded/out-of-credits, SSE drop +
  resume, per-file export failures, unsupported browser, empty states).
- A render crash shows a recovery screen, not a white page (ErrorBoundary).
- All pre-existing tests pass; new tests per §6; `pnpm build` green; OpenAPI snapshot
  regenerated; `graphify update .` run per phase.

**Out of scope (do not build):** retry queues / offline mutation buffering; i18n framework
(copy is PT-BR string literals like the rest of the app); frontend Sentry; restyling any
existing non-error component; a zip export implementation (the browser gate in §5.8 only
*communicates* the limitation).

---

## 1. Files touched (overview)

| File | Change |
|---|---|
| `apps/api/src/classroom_downloader/api/errors.py` **(new)** | `api_error(status, code, message)` helper → `HTTPException` with dict detail |
| `api/auth_errors.py` | attach codes: `google_session_missing`, `google_session_expired`, `google_auth_denied` |
| `api/deps.py` | codes `not_signed_in`, `session_expired` |
| `api/google_errors.py` **(new)** | classify Google `HttpError` 429 → 503 `google_rate_limited`, 5xx → 503 `google_unavailable` |
| `routers/auth.py` | code `oauth_not_configured` |
| `routers/grading.py` | codes on readiness gate (`llm_not_configured`), 409/422 sites |
| `llm_errors.py` | new code `api_budget_exhausted` (litellm `BudgetExceededError` / HTTP 402), non-retryable |
| `main.py` | exception handler: SQLite `OperationalError` "database is locked" → 503 `busy_retry`; `X-App-Version` response header |
| `apps/api/openapi.snapshot.json` | regenerated after backend changes |
| `apps/web/src/lib/api.ts` | `ApiError { status, code, message }`; network failure → `code: "unreachable"`; revalidation-failure tracking for the offline pill |
| `apps/web/src/lib/errorCatalog.ts` **(new)** | code → `{ tone, icon, title, body, action }` (PT-BR), tier routing, generic fallback |
| `apps/web/src/components/errors/` **(new)** | `FullError`, `Gate`, `ErrorBoundary`, offline pill — ported from `docs/UI/errors/`, shadcn-preferred (§4.1) |
| `components/ui.tsx` | `InlineError` upgraded to render a catalog entry (icon, tone, action button) |
| `App.tsx` | error state carries `ApiError` not string; gate routing; SSE reconnect/resume; fix mojibake (`grep -n "corre" App.tsx`) |
| `components/ConnectView.tsx` | partial-consent gate using existing `AuthState` scope booleans |
| `lib/folder-export.ts` | per-file try/catch, skip-and-summarize; directory-level aborts stay fatal |
| `components/DoneView.tsx` | export summary incl. failed-file list |
| `graderStatus.ts` | map `api_budget_exhausted` |
| `vite.config.ts` | `define: { __APP_VERSION__ }` for the version-skew check |
| `apps/api/tests/` | `test_error_contract.py` (new), snapshot updates |

---

## 2. The error contract

### 2.1 Backend: coded details

FastAPI's `HTTPException` accepts any JSON-serializable `detail`. New helper in
`api/errors.py`:

```python
def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
```

Migrate **only the sites that gate user flows** (auth, readiness, Google classification,
busy-db). The long tail of 404/409/422 in `routers/grading.py` may keep string details —
the frontend treats a string detail as `code: undefined` and falls back to the generic
catalog entry. Migrate them opportunistically, not exhaustively.

Code registry (single source of truth — document as a constant list/Enum in `api/errors.py`
so tests can assert against it):

| code | status | meaning |
|---|---|---|
| `not_signed_in` | 401 | no session |
| `session_expired` | 401 | app session expired |
| `google_session_missing` | 401 | token file gone — reconnect |
| `google_session_expired` | 401 | refresh failed (incl. the **weekly 7-day Testing-mode expiry** — most common error in the app) |
| `google_auth_denied` | 401 | hard 401/403 from Google — reconnect |
| `oauth_not_configured` | 503 | admin misconfiguration |
| `google_rate_limited` | 503 | Classroom/Drive 429 — retry later |
| `google_unavailable` | 503 | Classroom/Drive 5xx — Google's problem |
| `llm_not_configured` | 503 | readiness gate: missing provider keys |
| `busy_retry` | 503 | SQLite lock contention — transient |

(LLM per-call codes stay in `safe_error` on attempt rows — that channel already works.)

### 2.2 Google API classification

`api/google_errors.py`: mirror the shape of `auth_errors.py` (pure function,
exception → `HTTPException | None`). Classify `googleapiclient.errors.HttpError` with
`resp.status == 429` and `>= 500`. Wire it wherever `google_auth_http_exception` is already
consulted (`grep -rn "google_auth_http_exception" apps/api/src/` and add the new classifier
as the next fallback in the same except blocks). Auth classification keeps priority — a 403
must hit `auth_errors` first.

### 2.3 Frontend: `ApiError`

In `lib/api.ts`:

```ts
export class ApiError extends Error {
  constructor(
    readonly status: number,          // 0 for network failure
    readonly code: string | undefined,
    message: string,
  ) { super(message); }
}
```

`fetchJson` changes: parse `detail` as dict (`{code, message}`) or legacy string; on
`fetch` rejection (network/CORS/server down) throw `ApiError(0, "unreachable", ...)`.
`App.tsx` error state becomes `ApiError | null` (keep a string-coercion shim during the
phase so views compile incrementally).

**Back-compat sweep at execution time:** `grep -rn "detail" apps/api/tests/` — tests that
assert `detail == "..."` strings for migrated sites must be updated to assert
`detail["code"]`.

---

## 3. The catalog (`lib/errorCatalog.ts`)

One module mapping `code` (plus status fallbacks) to a PT-BR entry:

```ts
type ErrorEntry = {
  tier: "gate" | "banner";          // full-screen blocking vs inline
  tone: "info" | "warning" | "danger";
  icon: string;                      // lucide name, matching docs/UI/errors drafts
  title: string;
  body: string;
  action?: { label: string; kind: "retry" | "reconnect-google" | "reload" | "none" };
  adminHint?: boolean;               // appends "Se persistir, avise o administrador."
};
export function resolveError(err: unknown): ErrorEntry;
```

Authoring rules:

- Copy tone follows `graderStatus.ts` (lowercase-ish, direct, no jargon) and the draft
  screens in `docs/UI/errors/sections.jsx` — **lift draft copy where a scenario matches**
  (popup blocked, permission re-consent, etc.).
- `google_session_expired` is *routine maintenance*, not failure: info tone,
  "Sua conexão com o Google expirou — isso é normal e acontece toda semana. Reconecte para
  continuar." Action: `reconnect-google`.
- Admin-actionable codes (`oauth_not_configured`, `llm_not_configured`,
  `api_budget_exhausted`) get `adminHint: true` — the user's action is to tell Victor, not
  to retry.
- Unknown code / bare 500 → generic entry: "Algo deu errado do nosso lado. Tente novamente;
  se continuar, avise o administrador." This is the floor — **no raw detail strings in the
  UI**, though `resolveError` should attach the original message for an expandable
  "detalhes técnicos" line (helps remote debugging over WhatsApp screenshots).

---

## 4. Components & display tiers

### 4.1 shadcn preference rule (binding)

If `apps/web` has shadcn folded in (check: `components.json` exists and
`src/components/ui/` has generated primitives — the plan-observability §6 deliverable),
build `components/errors/` on shadcn primitives (`Card`, `Button`, `Alert`, `Empty`,
`Badge`) with the draft `error-styles.css` reduced to layout/tone tokens. **Fallback:** if
shadcn is absent at execution time, or the shadcn port of any single screen exceeds ~half a
day, drop to plan B — port `FullError`/`Gate` + `error-styles.css` from `docs/UI/errors/`
as plain CSS-module components, matching the existing `ui.tsx` style. The catalog and all
wiring (§2, §3, §5) are identical either way; only this folder's internals differ. Decide
once in Phase 0, record the decision in this file's status line.

### 4.2 Tiers

- **Tier A — `Gate` + `FullError`** (blocking, replaces the view): auth states, partial
  consent, API unreachable with no cached data, unsupported browser, render crash.
- **Tier B — `InlineError` upgraded** (banner in-view): recoverable failures where the view
  still has content — Google rate-limit/down, busy_retry, action failures. Gains icon,
  tone, and an action button (retry callback / reconnect).
- **Tier C — per-row** (exists in grading queue): only addition is `api_budget_exhausted`
  in `graderStatus.ts`.
- **ErrorBoundary** wrapping the app in `main.tsx`: catches render crashes → Tier A screen
  with a "Recarregar" button. Keep it dumb (`componentDidCatch` + state, no library).
- **Offline pill**: tiny fixed indicator ("sem conexão com o servidor — dados podem estar
  desatualizados") driven by §5.3's revalidation tracking. Not a banner — it must coexist
  with stale content, not replace it.

---

## 5. Scenario wiring (the matrix this plan exists for)

1. **Signed out / session expired / 7-day re-consent** — 401 codes → Tier A gate on any
   view. `google_session_expired` uses the routine-maintenance copy (§3). The reconnect
   action reuses the existing connect flow in `ConnectView`/`App.tsx`.
2. **Partial consent** — after connect, if `auth.signed_in && !(classroom_scopes &&
   drive_scopes)` → Tier A gate: "Faltam permissões — na tela do Google, marque todas as
   caixas." with reconnect CTA. Data is already in `AuthState`; this is pure frontend.
3. **API unreachable** — `code: "unreachable"`. No cached data → Tier A gate ("O servidor
   não respondeu. Verifique sua internet ou tente em alguns minutos."). With cached data →
   offline pill only. Implementation: `request()` in `api.ts` counts consecutive background
   revalidation failures (the currently-swallowed `.catch` at the stale-refresh site) and
   exposes a subscribable connectivity flag; any success resets it.
4. **Google/Classroom down or throttled** — `google_unavailable` / `google_rate_limited` →
   Tier B banner: "O Google Classroom está instável/limitou as requisições — aguarde um
   minuto e tente de novo." Retry action re-invokes the failed loader.
5. **LLM not configured / out of credits** — `llm_not_configured` (queue start) and
   `api_budget_exhausted` (per-row + job-level) → adminHint copy. Down/overloaded/timeout
   per-row copy already exists; verify job-level surfacing shows the same strings.
6. **SSE drop + resume** — in `App.tsx`'s `source.onerror`: auto-reconnect with backoff
   (3 attempts, 2s/5s/10s) showing "reconectando…" in the progress UI before declaring
   failure. On giving up — and on page load finding a job in a resumable state — show
   "O processamento foi interrompido, mas pode continuar de onde parou" with a **Retomar**
   action wired to the existing resume endpoint (`grep -rn "resume" apps/api/src/ apps/web/src/`
   for the exact route/client names). This also covers server-restart zombie jobs.
7. **Per-file export failures** — `folder-export.ts::exportJobToFolder`: wrap the per-file
   fetch/write in try/catch; collect `{path, reason}`; continue. Directory-handle errors
   (permission revoked mid-export, `QuotaExceededError` disk-full) stay fatal → Tier B with
   specific copy. `DoneView` shows "42 exportados, 3 falharam" + collapsible failed list
   ("o aluno pode ter excluído o arquivo do Drive").
8. **Unsupported browser** — detect `"showDirectoryPicker" in window` once at startup; if
   absent, persistent notice on the export surface ("Use Chrome ou Edge para exportar —
   neste navegador a exportação não funciona ainda"), shown *before* effort is invested,
   replacing the click-time placeholder message (and fix its mojibake sibling at
   `grep -n "placeholder" App.tsx`).
9. **Empty states ≠ errors** — explicit `Empty` rendering for: activity with zero
   submissions; submission with only links / no Drive files; file types the pipeline can't
   process. Copy must say it's normal ("Nenhuma entrega ainda — isso não é um erro.").
   Locate render sites via `ActivityList`/`ClassroomList`/`GraderQueue`.
10. **SQLite lock contention** — `busy_retry` from the §2 handler → Tier B "O servidor está
    ocupado — tente em alguns segundos." (Real concurrency work is out of scope; this makes
    the failure honest.)
11. **Version skew** — backend sends `X-App-Version` (from package metadata or a constant);
    frontend compares to `__APP_VERSION__` (vite `define`); on mismatch show a one-time
    toast/banner "Nova versão disponível — recarregue a página." Check it in `fetchJson`
    (response headers are already in hand). Keep it dumb; 5 users.
12. **Language unification** — user-facing copy lives **only** in the catalog (PT-BR);
    backend `message` strings stay English for logs/Sentry. Acceptance check: trigger each
    scenario and confirm no English reaches the DOM.

---

## 6. Tests

- `test_error_contract.py` **(new)**: every code in the §2.1 registry round-trips —
  migrated raise sites return `{"code", "message"}` dicts with the right status (auth 401s
  via the existing fake-credential fixtures; readiness 503 by clearing provider keys;
  `google_rate_limited` by faking an `HttpError` resp.status 429; `busy_retry` via a
  planted `OperationalError("database is locked")`). Assert the registry has no duplicate
  codes.
- Existing tests asserting prose `detail` strings on migrated sites: update to assert codes
  (find them with `grep -rn 'detail' apps/api/tests/`).
- **Regenerate `openapi.snapshot.json`** — the CI snapshot test fails otherwise by design.
- Frontend gate remains `pnpm build` (no JS test runner in this repo; adding vitest is out
  of scope). Each frontend phase ends with the §5 manual smoke for the scenarios it wired:
  kill the API mid-use; revoke the Google token; deny a scope on the consent screen;
  unplug network mid-export; load the app in Firefox.

---

## 7. Execution phases (each ends: full pytest green, `pnpm build` green, `graphify update .`)

Sized so any single phase fits a constrained-token session; later phases never block
earlier ones from shipping.

- **Phase 0 — baseline + decisions.** Record pytest count and build status. Decide §4.1
  (shadcn present?) and write the decision into this file's status line.
- **Phase 1 — backend contract.** §2.1 registry + helper, auth/deps/readiness migration,
  `google_errors.py`, `api_budget_exhausted`, busy-db handler, `X-App-Version` header,
  snapshot regen, `test_error_contract.py`. *Shippable: curl/log errors are now coded.*
- **Phase 2 — frontend contract + catalog.** `ApiError`, catalog with all §2.1 codes +
  generic fallback, upgraded `InlineError`, `ErrorBoundary`, mojibake fix. *Shippable:
  every error is PT-BR + actionable, even before dedicated screens exist.*
- **Phase 3 — gates & screens.** `components/errors/` (per §4.1 decision), auth/expiry/
  partial-consent/unreachable gates, offline pill, browser gate. *The visible payoff.*
- **Phase 4 — resilience flows.** SSE reconnect + resume UI; folder-export
  skip-and-summarize + `DoneView` summary; empty states.
- **Phase 5 — polish + acceptance.** Version-skew notice; copy pass against
  `docs/UI/errors` drafts; run the full §5 manual smoke matrix; update this plan's status.

**Git hygiene:** add only touched files per phase; ported-draft commits separate from
hand-written logic.

---

## 8. Watch-items (gotchas that will bite)

- **Detail dict vs string:** FastAPI emits both shapes fine, but any consumer assuming
  `detail: str` breaks — that includes existing **tests** and the frontend's current
  `detail?.detail ?? ...` line. Phase 1 and 2 must land in the stated order.
- **`fetchJson` is not the only pipe:** SSE (`EventSource`) and the export's raw `fetch` of
  file content bypass it. SSE errors are connection-level (§5.6 handles them); the export
  fetch must construct `ApiError` itself or failures will regress to plain `Error`.
- **Don't break stale-while-revalidate:** the connectivity tracker must observe failures
  without resurfacing them as `setError` — the silent catch at the stale-refresh site stays
  silent for *data*; it only feeds the pill.
- **401-during-polling loops:** when a session expires mid-grading-poll, every queued
  request fails at once — the gate must render once, not spawn N banners; debounce by
  keying on the resolved entry, and stop pollers when a gate-tier error is active.
- **Auth classification priority (§2.2):** Google 403s must reach `auth_errors` before the
  new 5xx/429 classifier — order the except-chain accordingly or revoked tokens will read
  as "Google está fora do ar".
- **OpenAPI snapshot:** Phase 1 fails CI if the regen step is forgotten. That's the
  snapshot doing its job — regenerate and commit the diff.
- **Draft files are not modules:** `docs/UI/errors/*.jsx` reference globals (`Icon`,
  `Gate`, `EP`…) and won't compile — port the markup/CSS, never import.
- **Preflight rule inheritance:** if shadcn is present, the no-preflight constraint from
  plan-observability §6.2 applies to error components too — they render inside existing
  views, so a global reset leak would restyle everything around them.
- **`scripts/route_snapshot.py`** is superseded by the OpenAPI snapshot test — delete it in
  whichever phase first touches the backend, or it will drift misleadingly.
