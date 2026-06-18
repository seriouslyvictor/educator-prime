# Plan 012: Gradual Google permissions

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the next
> step. If a STOP condition occurs, stop and report; do not broaden scopes or
> redesign the product flow silently. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 50ccfce..HEAD -- apps/api/src/classroom_downloader/routers/auth.py apps/api/src/classroom_downloader/google_provider.py apps/api/src/classroom_downloader/schemas.py apps/api/src/classroom_downloader/models.py apps/web/src/hooks/useConnection.ts apps/web/src/components/ConnectView.tsx apps/web/src/lib/api.ts apps/web/src/types.ts`
> If any of these changed since this plan was written, compare the "Current
> state" section against live code before proceeding. Treat a semantic mismatch
> as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: 003 (credential encryption already landed)
- **Category**: privacy / OAuth / UX
- **Planned at**: commit `50ccfce`, 2026-06-17

## Why this matters

The app currently asks for identity, Google Classroom, roster/profile, student
submission, and full Drive read permissions in a single login prompt from
`apps/web/src/hooks/useConnection.ts:12-23`. That is more access than the app
needs at first launch and it weakens user trust: a teacher cannot connect their
account just to see the app without also granting Drive read access.

Google's current OAuth guidance recommends incremental authorization and asking
for scopes in context. Its policies also require requesting the smallest set of
scopes needed for functionality the user knowingly chooses, checking which
scopes were actually granted, disabling only missing-scope functionality, and
re-prompting only after renewed feature intent. Drive is especially important:
`drive.readonly` is a restricted scope. `drive.file` is narrower and
non-sensitive, but it only fits user-selected/shared-with-app file workflows,
not the current automatic "download Classroom submission attachments" workflow.

This plan preserves the server-owned OAuth authorization-code flow, but changes
the product contract:

1. Connect/sign in asks only for identity.
2. Entering the Classroom workspace asks for Classroom read scopes.
3. Exporting/downloading submission files asks for Drive read permission only at
   the point of use.
4. The backend stores and reports actual granted scopes, not just requested
   scopes.
5. The UI supports partial consent without kicking the user back to the first
   screen.

## Research sources

- Google OAuth web-server flow and incremental auth:
  https://developers.google.com/identity/protocols/oauth2/web-server
- Google granular permissions:
  https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions
- Google OAuth policies:
  https://developers.google.com/identity/protocols/oauth2/policies
- Google API Services User Data Policy:
  https://developers.google.com/terms/api-services-user-data-policy
- Google Drive scope selection:
  https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- Google Classroom scope list:
  https://developers.google.com/workspace/classroom/guides/auth

## Current state

- `apps/web/src/hooks/useConnection.ts:12-23` defines one `classroomScopes`
  array containing `openid`, `email`, `profile`, Classroom read scopes, profile
  scopes, roster read, student submissions read, and `drive.readonly`.
- `apps/web/src/hooks/useConnection.ts:56-68` treats the app as connected only
  when `signed_in && classroom_scopes && drive_scopes`.
- `apps/web/src/hooks/useConnection.ts:94-103` calls
  `api.connectGoogle(classroomScopes)` from the initial connect action.
- `apps/web/src/components/ConnectView.tsx:27-31` tells users up front that the
  app will read Classroom lists, assignments/submissions, and attached Drive
  files.
- `apps/api/src/classroom_downloader/routers/auth.py:143-178` accepts arbitrary
  posted scopes, stores them in `OAuthState.scopes_json`, and builds the Google
  URL with those scopes.
- `apps/api/src/classroom_downloader/google_provider.py:238-267` already sets
  `access_type=offline` and `include_granted_scopes=true`.
- `apps/api/src/classroom_downloader/routers/auth.py:224-255` stores
  `flow.credentials.to_json()` after callback, but `auth_me` reports capability
  flags from `credentials.scopes`; it does not distinguish requested vs actual
  granted scopes.
- `apps/api/src/classroom_downloader/schemas.py:61-70` exposes only boolean
  scope flags, not the concrete granted scopes or missing capabilities.
- `apps/api/src/classroom_downloader/models.py:289-295` stores user sessions
  with encrypted `google_credentials_json`; there is no separate scope ledger.
- `apps/api/src/classroom_downloader/models.py:298-301` stores only
  `OAuthState.scopes_json`; there is no feature/context for audit or redirect.
- `apps/api/src/classroom_downloader/routers/exports.py:106-127` needs Drive
  content access for the export/download flow and should become the Drive
  permission boundary.

## Scope

**In scope**:
- Backend scope definitions, capability checks, and actual-granted-scope
  persistence.
- Auth start/callback changes for incremental authorization, partial grants, and
  feature context.
- API errors for missing Google capability scopes.
- Frontend scope constants, just-in-time permission prompts, partial-consent UI,
  and retry-after-consent behavior.
- Tests for callback granted-scope handling, API capability gates, frontend
  auth state, and mock-mode flow.
- Documentation of the Drive restricted-scope decision.

**Out of scope**:
- Switching to `drive.file` in this plan. That requires a separate Google Picker
  or user-selected file design and would not preserve the current automatic
  Classroom attachment export.
- Any Classroom write scopes.
- Any change to the encryption scheme from Plan 003.
- Any production Google Cloud Console verification work; this plan documents the
  requirements but does not perform external console changes.

## Permission model to implement

Create a single source of truth for scopes in the backend, then mirror it in the
frontend only as typed capability names.

| Capability | Ask when | Required scopes | Fallback if denied |
|---|---|---|---|
| `identity` | Initial connect | `openid`, `email`, `profile` | Stay on connect screen; app cannot create a session |
| `classroom_read` | User enters/continues to Turmas/workspace | `classroom.courses.readonly`, `classroom.coursework.students.readonly` | Keep signed in; show "Connect Classroom" call to action |
| `submissions_read` | User creates grader/export job for an activity | `classroom.student-submissions.students.readonly` | Keep course/activity browsing; block submission-backed actions |
| `student_profile_read` | User needs student names/emails/photos in submissions | `classroom.profile.emails`, `classroom.profile.photos`, `classroom.rosters.readonly` | Show safe placeholders; allow user to grant for names/emails |
| `drive_read` | User starts export/download or grading needs attachment content | `drive.readonly` | Keep Classroom browsing; block file-content actions and explain Drive access |

Notes:
- Keep `drive.readonly` for current behavior, with explicit documentation that it
  is restricted. Do not pretend `drive.file` can cover automatic Classroom
  attachments unless a Picker/user-selected-file flow is built.
- Batch only tightly coupled scopes. For example, `classroom_read` may include
  courses and coursework together because listing activities needs both. Do not
  include Drive in that batch.
- Always pass `include_granted_scopes=true`.
- Avoid `prompt=consent` on every incremental request unless tests prove refresh
  token loss or missing refresh token. Repeated forced consent is consent
  fatigue. Keep `access_type=offline`; consider `prompt=consent` only when no
  refresh token exists and the app truly needs offline refresh.

## Git workflow

- Branch: `codex/gradual-google-permissions`
- Commit style: phase commits:
  - `feat(api): track granted Google scopes`
  - `feat(api): gate Google capabilities by scope`
  - `feat(web): request Google permissions just in time`
  - `docs: document Google permission model`
- Stage explicit paths only. The current worktree may contain unrelated
  `.gitignore`, `.env.example`, `uv.lock`, `smoke_gemini.py`, and `teste_files/`
  changes.

## Commands

Backend, from `apps/api`:

```powershell
uv run --extra dev pytest tests/test_oauth_callback.py tests/test_api.py tests/test_error_contract.py tests/test_google_real_provider.py tests/test_google_provider_units.py -q
uv run --extra dev pytest -q
```

Frontend, from `apps/web`:

```powershell
pnpm build
pnpm test:run
pnpm lint
pnpm e2e
```

Graph/update if this becomes a delivery branch:

```powershell
graphify update .
```

If Graphify refuses because the new graph is smaller, rerun:

```powershell
graphify update . --force
```

## Steps

### Step 1: Add backend scope constants and capability helpers

Create `apps/api/src/classroom_downloader/google_scopes.py`.

The module must export:

```python
IDENTITY_SCOPES = frozenset({"openid", "email", "profile"})
CLASSROOM_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
})
SUBMISSIONS_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
})
STUDENT_PROFILE_SCOPES = frozenset({
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/classroom.profile.photos",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
})
DRIVE_READ_SCOPES = frozenset({
    "https://www.googleapis.com/auth/drive.readonly",
})

CAPABILITY_SCOPES = {
    "identity": IDENTITY_SCOPES,
    "classroom_read": CLASSROOM_READ_SCOPES,
    "submissions_read": SUBMISSIONS_READ_SCOPES,
    "student_profile_read": STUDENT_PROFILE_SCOPES,
    "drive_read": DRIVE_READ_SCOPES,
}
```

Add helpers:

```python
def normalize_scopes(scopes: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    return {scope for scope in (scopes or []) if scope}

def has_capability(granted_scopes: set[str], capability: str) -> bool:
    required = CAPABILITY_SCOPES[capability]
    return required.issubset(granted_scopes)

def missing_scopes(granted_scopes: set[str], capability: str) -> list[str]:
    return sorted(CAPABILITY_SCOPES[capability] - granted_scopes)
```

Add focused tests in `apps/api/tests/test_google_scopes.py`.

Verify:

```powershell
uv run --extra dev pytest tests/test_google_scopes.py -q
```

### Step 2: Persist and report actual granted scopes

Add fields to `UserSession` in `apps/api/src/classroom_downloader/models.py`:

```python
google_granted_scopes_json: str = "[]"
google_last_scope_update_at: datetime | None = None
```

Update SQLite dev migration logic in `apps/api/src/classroom_downloader/database.py`
so existing DBs receive the two columns. Follow the existing
`ensure_sqlite_dev_migrations()` pattern and update `apps/api/tests/test_database.py`.

In `apps/api/src/classroom_downloader/routers/auth.py`, after
`flow.fetch_token(...)`, compute actual granted scopes from the credentials:

```python
granted_scopes = sorted(
    set(getattr(creds, "granted_scopes", None) or [])
    or set(getattr(creds, "scopes", None) or [])
    or set(scopes)
)
```

Store `google_granted_scopes_json=json.dumps(granted_scopes)` and
`google_last_scope_update_at=now` on the new `UserSession`.

In `DbTokenStore.load_valid_credentials()` in `google_provider.py`, after a
refresh, update `google_granted_scopes_json` from the refreshed credentials when
available, without erasing existing granted scopes if the library does not return
scope data.

Verify:

```powershell
uv run --extra dev pytest tests/test_oauth_callback.py tests/test_database.py tests/test_credentials_crypto.py -q
```

### Step 3: Upgrade AuthState from booleans-only to capability-aware

Modify `apps/api/src/classroom_downloader/schemas.py`:

```python
class AuthState(BaseModel):
    signed_in: bool
    identity_scopes: bool
    classroom_scopes: bool
    drive_scopes: bool
    granted_scopes: list[str] = []
    missing_capabilities: list[str] = []
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    provider: str
    is_admin: bool = False
```

Keep the existing boolean fields for frontend compatibility, but derive them
from `google_scopes.has_capability()`:

- `identity_scopes`: `identity`
- `classroom_scopes`: `classroom_read`
- `drive_scopes`: `drive_read`

Add `missing_capabilities` for any capability the app knows about but the user
has not granted. For mock mode, return all capabilities granted and no missing
capabilities.

Update `auth_me` so it uses stored `google_granted_scopes_json` first, then falls
back to `credentials.granted_scopes`/`credentials.scopes` for legacy rows.

Update `apps/web/src/types.ts` to include:

```ts
granted_scopes: string[];
missing_capabilities: Array<
  "identity" | "classroom_read" | "submissions_read" | "student_profile_read" | "drive_read"
>;
```

Verify:

```powershell
uv run --extra dev pytest tests/test_api.py tests/test_oauth_callback.py -q
pnpm test:run
```

### Step 4: Restrict auth_start input to capabilities

Replace the public contract of `POST /api/auth/google/start` from "frontend
posts arbitrary scopes" to "frontend posts requested capability and reason".

Add schema:

```python
class AuthStartRequest(BaseModel):
    capability: Literal[
        "identity",
        "classroom_read",
        "submissions_read",
        "student_profile_read",
        "drive_read",
    ]
    reason: str
```

Update `auth_start` to accept `AuthStartRequest`, resolve scopes from
`CAPABILITY_SCOPES`, and store an expanded `OAuthState` payload:

```python
requested = sorted(CAPABILITY_SCOPES[payload.capability])
db.add(OAuthState(
    id=state,
    scopes_json=json.dumps(requested),
    capability=payload.capability,
    reason=payload.reason[:500],
    expires_at=now + timedelta(minutes=10),
))
```

Add `capability: str | None = None` and `reason: str | None = None` to
`OAuthState`, plus SQLite migration coverage.

Security requirements:
- Ignore any frontend-provided scope strings. The frontend may name a capability
  only.
- Log capability and scope count; do not log tokens/codes.
- Keep state expiration and deletion behavior.

Update `build_oauth_authorization_url` so `prompt=consent` is optional:

```python
def build_oauth_authorization_url(..., prompt: str | None = None) -> str:
    params = {..., "include_granted_scopes": "true", "access_type": "offline"}
    if prompt:
        params["prompt"] = prompt
```

Start with `prompt=None` for incremental capability requests. If a test shows
the app cannot obtain refresh tokens after first identity consent, add a narrow
backend rule to use `prompt="consent"` only when the current session has no
refresh token.

Verify:

```powershell
uv run --extra dev pytest tests/test_oauth_callback.py tests/test_google_real_provider.py -q
```

### Step 5: Add backend capability gates before Google API calls

Create `apps/api/src/classroom_downloader/api/permissions.py` with:

```python
def require_google_capability(
    current_session: UserSession,
    capability: str,
) -> None:
    granted = set(json.loads(current_session.google_granted_scopes_json or "[]"))
    if has_capability(granted, capability):
        return
    raise api_error(
        403,
        "google_permission_required",
        "Google permission is required for this action.",
        capability=capability,
        missing_scopes=missing_scopes(granted, capability),
    )
```

If `api_error` does not support extra metadata today, extend the error contract
carefully and update `apps/api/tests/test_error_contract.py`.

Apply gates:
- `routers/courses.py:list_courses` and `list_activities`: require
  `classroom_read`.
- Export create and file-content endpoints in `routers/exports.py`: require
  `drive_read`; if the endpoint also lists submissions, require
  `submissions_read`.
- Grading setup paths that call `provider.list_submission_files()` or
  `provider.get_file_content()`: require `submissions_read` and `drive_read`.
- Profile hydration can require `student_profile_read`; if missing, provider
  should skip profile lookups and let callers use placeholders instead of
  failing the whole workflow.

Tests:
- Add a session with identity only; `/api/courses` returns 403
  `google_permission_required` with capability `classroom_read`.
- Add Classroom-only scopes; course browsing works but export/grading file load
  returns 403 with capability `drive_read`.
- Mock provider remains fully connected.

Verify:

```powershell
uv run --extra dev pytest tests/test_api.py tests/test_error_contract.py tests/test_grading.py -q
```

### Step 6: Frontend API and hook split

In `apps/web/src/lib/api.ts`, change `connectGoogle` to:

```ts
connectGoogle: (capability: GoogleCapability, reason: string) =>
  request<AuthStart>("/api/auth/google/start", {
    method: "POST",
    body: JSON.stringify({ capability, reason }),
  })
```

Add `GoogleCapability` to `apps/web/src/types.ts`.

In `apps/web/src/hooks/useConnection.ts`:
- Remove the frontend scope array.
- Compute `signedIn = Boolean(auth?.signed_in && auth.identity_scopes)`.
- Compute `classroomReady = Boolean(auth?.classroom_scopes)`.
- Compute `driveReady = Boolean(auth?.drive_scopes)`.
- Let bootstrap go to `connect` only when identity is missing.
- If identity exists but Classroom is missing, route to a signed-in permission
  state, not full logout.
- Add methods:
  - `connectIdentity()`
  - `connectClassroomRead()`
  - `connectDriveRead()`

Each method should call `api.connectGoogle(capability, reason)` and redirect if
`authorization_url` exists. Reasons should be short and contextual:
- identity: "Entrar no Classroom Downloader com sua conta Google escolar."
- classroom_read: "Listar suas turmas e atividades do Google Classroom."
- drive_read: "Baixar os arquivos anexados nas entregas escolhidas."

Verify:

```powershell
pnpm test:run
pnpm build
```

### Step 7: Redesign ConnectView into permission stages

Modify `apps/web/src/components/ConnectView.tsx` so it receives `auth` and three
handlers:

- `onConnectIdentity`
- `onConnectClassroom`
- `onConnectDrive`

UI states:

1. Not signed in: show one primary action "Entrar com Google" and explain only
   identity.
2. Signed in, missing Classroom: show account identity and one primary action
   "Permitir leitura do Classroom"; list only course/activity access.
3. Classroom ready, Drive missing: allow browsing workspace; show Drive prompt
   only inside export/grading actions, not as a connect-screen blocker.
4. Partial grant denied: show specific missing capability and a retry action
   only for that feature.

Do not claim "Nunca modificamos" near a Drive prompt unless the listed scopes are
read-only and the text says exactly that. Mention Drive only at export/download
time.

Update `Rail.tsx` and any connection badges to show:
- Google account
- Classroom read
- Drive file download

Verify:

```powershell
pnpm build
pnpm e2e
```

### Step 8: Add just-in-time Drive prompts at export/grading boundaries

Find frontend actions that create exports or load/grading submission content:

- `useExportWorkspace`
- `GraderSetup`
- `GraderWrap`
- any queue action that invokes submission file content

Before calling a Drive-backed API, check `auth.drive_scopes`. If missing, show a
small permission panel or modal with:

- What action is blocked: download/read attached submission files.
- Why Drive is needed: the files are stored as Classroom attachments in Drive.
- What the app will do: read/download only the selected submissions.
- What happens if declined: Classroom browsing remains available.

The primary action calls `connectDriveRead()`.

When the backend returns `google_permission_required`, map the `capability` field
to the same prompt instead of showing a generic error.

Verify with Playwright:
- Boot in mock mode still reaches workspace.
- A synthetic auth state with identity only shows Classroom prompt.
- A synthetic auth state with Classroom but no Drive can view courses but shows
  Drive prompt on export/grader file-content action.

### Step 9: Document the Drive restricted-scope decision

Create `docs/google-permissions.md` or `apps/api/docs/google-permissions.md`
(choose the repo's existing docs convention if one exists) with:

- Capability table from this plan.
- Source links from "Research sources".
- Why `drive.readonly` remains necessary for current automatic Classroom
  attachment export.
- Why `drive.file` is deferred unless a Picker/user-selected file flow is built.
- Production readiness checklist:
  - OAuth consent screen lists only implemented scopes.
  - Sensitive/restricted scopes are verified before public production use.
  - Privacy policy and in-product disclosures match actual data access.
  - Tokens stay encrypted at rest.
  - Disconnect deletes/revokes tokens when revocation is implemented.

Update README or deployment docs only if they already mention Google OAuth
scope setup.

### Step 10: Full verification and visible smoke

Run:

```powershell
cd apps/api
uv run --extra dev pytest -q
cd ..\web
pnpm build
pnpm test:run
pnpm e2e
```

Run a browser smoke in mock mode:

1. Start API with `CD_GOOGLE_PROVIDER=mock`.
2. Start web with matching `VITE_API_BASE_URL`.
3. Open the app.
4. Confirm mock mode still connects without Google OAuth.
5. Confirm the connection rail shows all mock capabilities as ready.

For real Google smoke, run only locally with a test Google account:

1. Sign in with identity only.
2. Confirm the app does not request Drive yet.
3. Enter Classroom/workspace and grant Classroom scopes.
4. Start an export/grading file action and confirm Drive is requested at that
   moment.
5. Confirm decline keeps Classroom browsing usable.

## Test plan

Backend:
- `tests/test_google_scopes.py`: capability helper coverage.
- `tests/test_oauth_callback.py`: stores actual granted scopes; partial grant
  does not mark missing scopes as granted.
- `tests/test_api.py`: `auth_me` reports booleans, granted scopes, and missing
  capabilities for identity-only, Classroom-only, Drive-ready, and mock states.
- `tests/test_error_contract.py`: `google_permission_required` response shape.
- `tests/test_google_real_provider.py`: auth URL includes
  `include_granted_scopes=true`, omits forced `prompt=consent` unless selected,
  and accepts capability-resolved scopes.
- `tests/test_database.py`: new nullable/default columns are added.

Frontend:
- Unit tests for permission-state derivation if the hook is extracted enough to
  test directly.
- Existing Vitest suite must pass.
- Playwright boot/logout/navigation flows must pass.
- Add or update an E2E fixture for partial auth state if current mock tooling can
  simulate it.

## Done criteria

- [ ] Initial connect requests only identity scopes.
- [ ] Classroom scopes are requested only after user intent to browse/use
      Classroom.
- [ ] Drive scope is requested only at export/download/grading file-content
      boundaries.
- [ ] Backend persists and reports actual granted scopes.
- [ ] Backend rejects scope-backed API calls with `google_permission_required`
      instead of making doomed Google calls.
- [ ] Partial consent keeps unrelated features usable.
- [ ] `drive.readonly` restricted-scope decision is documented with alternatives.
- [ ] Backend full test suite passes.
- [ ] Frontend build, unit tests, lint, and E2E pass, or any known lint
      non-blocker matches CI policy and is documented.
- [ ] Browser smoke validates mock mode after the UI change.
- [ ] `plans/README.md` status row for 012 is updated.

## STOP conditions

Stop and report if:

- You cannot determine actual granted scopes from Google credentials or token
  response without relying only on originally requested scopes.
- You find `drive.file` can fully support current automatic Classroom attachment
  export without Picker/user file selection; this would change the Drive
  decision and the plan should be revised before implementation.
- Any implementation path requires a Classroom write scope.
- Partial grants cannot be represented without breaking existing API clients.
- The real Google OAuth flow loses refresh tokens because `prompt=consent` was
  removed; report exact evidence and add the narrowest prompt rule.
- Tests require real Google network access. They should mock OAuth/provider
  behavior; real smoke is local/manual only.

## Maintenance notes

- Google policies change. Before production verification, re-check the Google
  links in this plan.
- `drive.readonly` may trigger restricted-scope review and security assessment
  requirements for public production use. Internal Workspace deployment may have
  different allowlisting controls, but do not assume that applies to public use.
- Add revocation as a follow-up if not already present: logout currently deletes
  the local session, but Google policy recommends revoking tokens when the app no
  longer needs access.
- If a future Picker/user-selected file flow lands, revisit replacing
  `drive.readonly` with `drive.file` for that narrower mode.
