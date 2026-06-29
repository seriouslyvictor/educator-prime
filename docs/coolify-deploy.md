# Coolify deployment

Production domain: `https://classroom.supernovasw.cloud`

The deploy target is a single Docker container:

- FastAPI serves `/api/*`.
- FastAPI also serves the built Vite frontend from `CD_STATIC_DIR`.
- The container listens on port `8000`.
- All runtime state is stored under `/data`.

## Coolify application setup

Use this path in Coolify:

1. `Applications` -> `New` -> `Git Repository`.
2. Select this repository.
3. Build pack: `Dockerfile`.
4. Dockerfile path: `Dockerfile`.
5. Port / exposed port: `8000`.
6. Domain: `https://classroom.supernovasw.cloud`.
7. Add persistent storage:
   - Type: `Volume`.
   - Source/name: leave blank and let Coolify generate it.
   - Destination path: `/data`.

Mount the directory `/data`, not an individual SQLite file. SQLite creates sidecar
WAL/SHM files beside the DB, and the Google OAuth token plus caches also need to
survive redeploys.

## Required environment variables

Set these in Coolify `Environment Variables`:

```env
CD_FRONTEND_ORIGIN=https://classroom.supernovasw.cloud
CD_GOOGLE_REDIRECT_URI=https://classroom.supernovasw.cloud/api/auth/google/callback
CD_GOOGLE_PROVIDER=google
CD_GOOGLE_CLIENT_ID=your-google-oauth-client-id
CD_GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
CD_GRADING_ENGINE=litellm
CD_LITELLM_MODEL=openai/gpt-5
OPENAI_API_KEY=your-provider-key
```

The Dockerfile already provides production defaults for these persistent paths:

```env
CD_DATABASE_URL=sqlite:////data/classroom_downloader.db
CD_GOOGLE_TOKEN_PATH=/data/tokens/google-user.json
CD_GOOGLE_OAUTH_STATE_PATH=/data/tokens/google-oauth-state.txt
CD_GRADING_CACHE_PATH=/data/cache/grading
CD_EXPORT_CACHE_PATH=/data/cache/exports
CD_LLM_MODEL_CATALOG_CACHE_PATH=/data/cache/llm/model-prices.json
CD_STATIC_DIR=/app/static
CD_LOG_RICH=false
CD_LOG_FORMAT=json
```

You can override them in Coolify if needed, but keep all writable paths inside
the mounted `/data` directory.

## Google OAuth setup

In Google Cloud Console for the OAuth client used by this app:

- Authorized JavaScript origin:
  - `https://classroom.supernovasw.cloud`
- Authorized redirect URI:
  - `https://classroom.supernovasw.cloud/api/auth/google/callback`

The app uses read-only Classroom/Drive scopes for the current workflow. See
[constraints.md](constraints.md) for why `drive.readonly` (a Google "restricted"
scope) keeps the project in OAuth **Testing** mode and what that costs.

## Smoke checks after deploy

After Coolify reports the app as running:

1. Open `https://classroom.supernovasw.cloud/api/health`.
   - Expected response: `{"status":"ok"}`.
2. Open `https://classroom.supernovasw.cloud/`.
   - Expected: the React app loads.
3. In the app, connect Google Classroom.
   - Expected: OAuth returns to `https://classroom.supernovasw.cloud/?google=connected`.
4. Check Coolify storage after first use.
   - Expected files/directories under `/data`: `classroom_downloader.db`, `tokens/`, and `cache/`.
