# Plan 003: Encrypt stored Google OAuth credentials at rest

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat b61ac5a..HEAD -- apps/api/src/classroom_downloader/routers/auth.py apps/api/src/classroom_downloader/google_provider.py apps/api/src/classroom_downloader/models.py apps/api/src/classroom_downloader/settings.py`
> If any of those changed since this plan was written, compare the "Current
> state" excerpts against the live code before proceeding; on a mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: none (independent of the frontend plans)
- **Category**: security
- **Planned at**: commit `b61ac5a`, 2026-06-13

## Why this matters

Google OAuth credentials are stored **verbatim and unencrypted** in the SQLite
database. `auth.py:244` writes `google_credentials_json=creds.to_json()`, and
`google_provider.py:983` rewrites it on every token refresh. That JSON contains
the **refresh token and the client secret**. Per project memory this app is now
a multi-user internal tool on a VPS, so the database holds the live Google
credentials of *every* connected teacher, each with `drive.readonly` and
Classroom scopes. Anyone who can read the SQLite file (a backup, a stray volume
snapshot, a path-traversal bug elsewhere, an ops mistake) gets durable access to
every teacher's Drive and Classroom — refresh tokens persist until revoked.

The codebase already treats this value as sensitive *in transit through logs*:
`observability.py:35` lists `"credentials_json"` among `_SENSITIVE_FIELDS` that
get redacted, and Sentry scrubbing is wired in `main.py`. The gap is at rest in
the DB. There is also an unused `session_secret_key` setting
(`settings.py:42`) that has no consumer anywhere in `src/` — this plan gives it a
purpose as the encryption key source, which also resolves the "dead config"
finding.

This is a code-and-config change plus a one-time migration of existing rows. No
demonstration of misuse is included or needed.

## Current state

- `models.py:289-295` — the model:
  ```python
  class UserSession(SQLModel, table=True):
      id: str = Field(primary_key=True)
      user_email: str = Field(index=True)
      google_credentials_json: str
      created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
      expires_at: datetime
      last_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
  ```
  `google_credentials_json` holds the plaintext `creds.to_json()`.

- `routers/auth.py:238-248` — write on login:
  ```python
  session_id = token_urlsafe(32)
  now = datetime.now(UTC)
  max_age = timedelta(hours=settings.session_max_age_hours)
  db.add(UserSession(
      id=session_id,
      user_email=user_email,
      google_credentials_json=creds.to_json(),
      created_at=now,
      expires_at=now + max_age,
  ))
  db.commit()
  ```

- `google_provider.py:954-968` — read (`DbTokenStore.load_credentials`):
  ```python
  return Credentials.from_authorized_user_info(_json.loads(row.google_credentials_json))
  ```
- `google_provider.py:970-987` — refresh re-write:
  ```python
  row.google_credentials_json = credentials.to_json()
  ```
- `routers/auth.py:71-78` — `auth_me` also reads via
  `DbTokenStore(session_id, db).load_credentials()`.

- `settings.py:42` — `session_secret_key: str | None = None` (defined, never
  read anywhere in `src/` — confirmed with `grep -rn session_secret_key src/`).

- `cryptography` is already a resolved dependency (`uv.lock` line ~363,
  version 48.x) via transitive deps; this plan promotes it to a direct
  dependency in `pyproject.toml`.

- Tests run with `CD_GOOGLE_PROVIDER=mock` (see `conftest.py` and `deps.py:46`),
  where `get_current_session` returns a synthetic row with
  `google_credentials_json="{}"` and never touches the DB token store. So
  encryption only engages on the `google` provider path. There is an OAuth
  callback test: `tests/test_oauth_callback.py` — read it before changing
  `auth.py` to see how the callback is exercised.

Repo conventions to match:
- Settings are pydantic `BaseSettings` fields with the `CD_` env prefix; read
  via `get_settings()` (cached). Add new env to `apps/api/.env.example`.
- Helpers for credentials live in `google_provider.py`. Put the
  encrypt/decrypt helpers there (or a new small `crypto.py` module — your call,
  but keep it in `classroom_downloader/`).
- Error/logging uses `log_event`/`log_warning`/`log_error` from `observability`.
  Never log the credential value (it's already in `_SENSITIVE_FIELDS`, but do
  not pass it as an event field at all).

## Commands you will need

| Purpose      | Command (from `apps/api`)                          | Expected            |
|--------------|----------------------------------------------------|---------------------|
| Install dev  | `uv sync --extra dev`                              | exit 0              |
| Run tests    | `uv run --extra dev pytest -q`                     | all pass            |
| Single test  | `uv run --extra dev pytest tests/test_oauth_callback.py -q` | pass       |
| Targeted     | `uv run --extra dev pytest tests/test_credentials_crypto.py -q` | new tests pass |
| Confirm dep  | `uv run python -c "import cryptography; print(cryptography.__version__)"` | prints a version |

## Scope

**In scope**:
- `apps/api/pyproject.toml` — add `cryptography` as a direct dependency.
- `apps/api/src/classroom_downloader/google_provider.py` — encrypt on write,
  decrypt on read (both the login write path's helper and the refresh re-write),
  plus the encrypt/decrypt helpers (or a new `crypto.py`).
- `apps/api/src/classroom_downloader/routers/auth.py` — encrypt the value
  written at callback time.
- `apps/api/src/classroom_downloader/settings.py` — keep `session_secret_key`;
  add a short docstring/comment that it now keys credential encryption. Resolves
  finding #6.
- `apps/api/.env.example` — document `CD_SESSION_SECRET_KEY`.
- A one-time migration step/script for existing plaintext rows (see Step 5).
- `apps/api/tests/test_credentials_crypto.py` (create) — round-trip + backward
  read tests.

**Out of scope** (do NOT touch):
- The mock provider path and its synthetic session — encryption must be a no-op
  there (the value is `"{}"`, never a real credential).
- Any change to session-cookie handling, `OAuthState`, or the OAuth scope set.
- Re-encrypting `OAuthState.scopes_json` (not a secret).
- The frontend.

## Git workflow

- Branch: `advisor/003-encrypt-oauth-credentials-at-rest`
- Commit style: conventional commits, e.g.
  `feat(api): encrypt stored Google OAuth credentials at rest`.
- Do NOT push or open a PR unless instructed.

## Design decision (read before coding)

Use **symmetric authenticated encryption** via `cryptography`'s `Fernet`.

- **Key source**: derive a 32-byte Fernet key from `settings.session_secret_key`
  (a single configured secret), so operators set one env var. Derive with a
  fixed, documented scheme so the key is stable across restarts — e.g.
  `base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())`. Do
  **not** generate a random key at process start (that would make existing
  ciphertext undecryptable after a restart).
- **Required in production**: when `CD_GOOGLE_PROVIDER=google` and
  `session_secret_key` is unset, the app must refuse to store credentials with a
  clear error rather than silently storing plaintext. In `mock` mode, no key is
  required.
- **Backward compatibility**: existing rows are plaintext JSON
  (`{"token": ...}`). `decrypt_credentials_json()` must detect plaintext (a
  Fernet token is URL-safe base64 starting with `gAAAAA`; plaintext JSON starts
  with `{`) and pass it through, so the app keeps working before the migration
  runs. After migration, all rows are ciphertext.

If you judge a different at-rest scheme is materially better for this
deployment, STOP and report your reasoning before implementing — do not silently
substitute.

## Steps

### Step 1: Add the dependency and key derivation

Add `"cryptography>=43.0.0"` to the `dependencies` list in
`apps/api/pyproject.toml`. Run `uv sync --extra dev`.

Add helpers (in `google_provider.py` or a new `crypto.py`):
```python
def _fernet() -> "Fernet | None":
    from cryptography.fernet import Fernet
    import base64, hashlib
    settings = get_settings()
    secret = settings.session_secret_key
    if not secret:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)

def encrypt_credentials_json(plaintext: str) -> str:
    f = _fernet()
    if f is None:
        # mock/dev with no key: store as-is (callers gate real creds on key presence)
        return plaintext
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")

def decrypt_credentials_json(stored: str) -> str:
    if stored.startswith("{"):  # legacy plaintext JSON, pre-migration
        return stored
    f = _fernet()
    if f is None:
        return stored
    from cryptography.fernet import InvalidToken
    try:
        return f.decrypt(stored.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise
```

**Verify**: `uv run python -c "import cryptography; print(cryptography.__version__)"`
prints a version; `uv run python -c "from classroom_downloader.google_provider import encrypt_credentials_json, decrypt_credentials_json; print('ok')"`
(adjust import path if you used `crypto.py`) → prints `ok`.

### Step 2: Enforce key presence on the real-credential write path

In `routers/auth.py` `auth_callback`, before storing, require the key when on
the `google` provider:
```python
if not settings.session_secret_key:
    raise api_error(503, "encryption_not_configured",
        "Credential encryption key is not configured. Set CD_SESSION_SECRET_KEY.")
```
Then store `google_credentials_json=encrypt_credentials_json(creds.to_json())`.
(The callback is only reached on the `google` provider — `mock` never hits it.)

**Verify**: `uv run --extra dev pytest tests/test_oauth_callback.py -q` → adjust
the test only if it now must set `CD_SESSION_SECRET_KEY`; see Step 6. STOP if the
test failure is anything other than "missing key" once you've set it.

### Step 3: Decrypt on read

In `DbTokenStore.load_credentials` (`google_provider.py:954-968`), wrap the read:
```python
raw = decrypt_credentials_json(row.google_credentials_json)
return Credentials.from_authorized_user_info(_json.loads(raw))
```

### Step 4: Encrypt on refresh re-write

In `DbTokenStore.load_valid_credentials` (`google_provider.py:981-986`), change
`row.google_credentials_json = credentials.to_json()` to
`row.google_credentials_json = encrypt_credentials_json(credentials.to_json())`.

**Verify**: `uv run --extra dev pytest -q` → full suite still passes (mock-mode
tests are unaffected; the value `"{}"` passes through `decrypt` unchanged because
it starts with `{`).

### Step 5: One-time migration of existing rows

Existing deployments have plaintext rows. Add a small idempotent migration the
operator runs once. Create `apps/api/scripts/encrypt_existing_credentials.py`
that: opens a DB session, selects all `UserSession` rows whose
`google_credentials_json` starts with `{` (plaintext), and rewrites each with
`encrypt_credentials_json(...)`. It must be safe to run twice (rows already
ciphertext are skipped because they don't start with `{`). Mirror the structure
of an existing script in `apps/api/scripts/` (e.g. `export_openapi.py`) for how
the app/db is imported.

Document in the script's module docstring: requires `CD_SESSION_SECRET_KEY` set
to the same value the app uses; run with
`uv run python scripts/encrypt_existing_credentials.py`.

**Verify**: write a test (Step 6) that seeds a plaintext row, runs the migration
function, and asserts the row is now ciphertext and still decrypts to the
original JSON.

### Step 6: Tests

Create `apps/api/tests/test_credentials_crypto.py`. With
`CD_SESSION_SECRET_KEY` set in the test (use `monkeypatch.setenv` and clear the
`get_settings` lru_cache — see how `conftest.py` handles settings; if settings
are cached, call `get_settings.cache_clear()`):
- Round-trip: `decrypt_credentials_json(encrypt_credentials_json(x)) == x` for a
  realistic creds JSON string.
- Ciphertext is not plaintext: `encrypt_credentials_json(x) != x` and does not
  contain the refresh-token substring.
- Backward read: `decrypt_credentials_json('{"token":"abc"}') == '{"token":"abc"}'`
  (legacy passthrough).
- Migration: seed a `UserSession` with plaintext, run the migration function,
  assert stored value no longer starts with `{` and decrypts back to the
  original.
- No-key behavior: with no key set, `encrypt_credentials_json` returns input
  unchanged (mock/dev path).

If `tests/test_oauth_callback.py` now needs `CD_SESSION_SECRET_KEY`, set it
there too (minimal change) and keep the rest of the test intact.

**Verify**: `uv run --extra dev pytest tests/test_credentials_crypto.py tests/test_oauth_callback.py -q`
→ all pass. Then `uv run --extra dev pytest -q` → full suite passes.

### Step 7: Document the env var

Add to `apps/api/.env.example`, near the session settings:
```
# Required when CD_GOOGLE_PROVIDER=google. Keys at-rest encryption of stored
# Google OAuth credentials (Fernet, derived via SHA-256). Use a long random
# value; rotating it makes existing stored sessions undecryptable (teachers
# re-consent). Generate e.g.: python -c "import secrets;print(secrets.token_urlsafe(48))"
CD_SESSION_SECRET_KEY=
```

**Verify**: `grep -n CD_SESSION_SECRET_KEY apps/api/.env.example` → present.

## Test plan

- New `tests/test_credentials_crypto.py`: round-trip, ciphertext-differs,
  legacy passthrough, migration, no-key passthrough.
- Pattern to follow: an existing focused unit test such as
  `tests/test_privacy.py` for structure, and `conftest.py` for the settings/DB
  fixtures.
- Verification: `uv run --extra dev pytest -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold (from `apps/api`):

- [ ] `uv run --extra dev pytest -q` exits 0 (full suite)
- [ ] `tests/test_credentials_crypto.py` exists with round-trip, legacy
      passthrough, and migration tests, all passing
- [ ] `grep -rn "creds.to_json()" src/classroom_downloader/routers/auth.py`
      shows the value is wrapped by `encrypt_credentials_json(...)`
- [ ] `grep -rn "credentials.to_json()" src/classroom_downloader/google_provider.py`
      shows the refresh re-write is wrapped by `encrypt_credentials_json(...)`
- [ ] `DbTokenStore.load_credentials` decrypts via `decrypt_credentials_json(...)`
- [ ] `cryptography` appears in `pyproject.toml` `dependencies`
- [ ] `CD_SESSION_SECRET_KEY` documented in `.env.example`
- [ ] `apps/api/scripts/encrypt_existing_credentials.py` exists and is idempotent
- [ ] `plans/README.md` status row for 003 updated

## STOP conditions

Stop and report back (do not improvise) if:

- You conclude a different key-management approach (e.g. per-row keys, KMS) is
  required for this deployment — report before implementing.
- The mock-provider tests start failing — encryption must be a no-op on the
  `"{}"` synthetic credential, so a failure means the passthrough/legacy
  detection is wrong.
- The OAuth callback test fails for any reason other than a missing
  `CD_SESSION_SECRET_KEY` that you then set.
- You cannot determine how `conftest.py` configures settings well enough to set
  `CD_SESSION_SECRET_KEY` in tests without `get_settings` caching defeating it.

## Maintenance notes

- **Key rotation is destructive**: changing `CD_SESSION_SECRET_KEY` invalidates
  all stored credentials; teachers must re-consent. Document this in the deploy
  notes (`docs/coolify-deploy.md`) as a deferred follow-up.
- The legacy `startswith("{")` plaintext detection can be removed once you are
  certain no plaintext rows remain (after the migration has run in every
  environment). Leave a comment marking it removable.
- A reviewer should confirm: the credential value never appears in any
  `log_event` field; encryption is genuinely a no-op in mock mode; and the
  migration script is idempotent.
- This plan resolves finding #6 (dead `session_secret_key`) by wiring it. Plan
  004's session-secret-key step is therefore conditional — if this plan has
  landed, 004 must NOT remove the setting.
