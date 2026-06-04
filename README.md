# Classroom Downloader

Classroom Downloader helps teachers move Google Classroom submissions into safer, inspectable workflows for local export and draft-only AI-assisted grading.

It currently achieves:

- Local export of Classroom and Drive submissions into an organized folder structure.
- Draft grading workflows where the teacher stays in control.
- A privacy audit before AI drafting, using pseudonyms and safe metadata instead of raw student identifiers.
- Blocking or flagging unsupported and high-risk submissions before they can enter the grading path.

Privacy is a product requirement. Audit reports do not store extracted submission text, scrubbed text, prompts, raw student names, or student emails. AI grading remains draft-only and does not post grades or comments back to Classroom.

## Stack

- Frontend: Vite, React, TypeScript, shadcn-style local UI primitives
- Backend: FastAPI, SQLModel, SQLite for development
- Export target: Chromium File System Access API

## Development

Backend:

```powershell
cd apps/api
uv run --extra dev python -m uvicorn classroom_downloader.main:app --app-dir src --reload --port 8000
```

Frontend:

```powershell
cd apps/web
pnpm install
pnpm run dev
```

Open `http://127.0.0.1:5173`.

Keep the backend running while using the frontend. Vite proxies `/api/*` requests to
`http://127.0.0.1:8000`; if the API is not listening, the browser will show a generic
request failure from the proxy.

The backend runs in mock Google mode by default, so the product workflow can be tested before Google OAuth credentials are configured.

## Backend Settings

Copy `apps/api/.env.example` to `apps/api/.env` for local overrides.

| Setting | Values | Purpose |
| --- | --- | --- |
| `CD_GOOGLE_PROVIDER` | `mock`, `google` | Use fake local data or real Google OAuth/Classroom/Drive. |
| `CD_GRADING_ENGINE` | `mock`, `litellm` | Selects deterministic local grading or the configured LiteLLM grading engine when enabled. |
| `CD_LITELLM_MODEL` | model id | Model id from the merged LLM catalog. |
| `CD_LLM_MODEL_CATALOG_MODE` | `remote_cached`, `local_only`, `remote_required` | Controls dynamic LiteLLM price-map fetching. |
| `CD_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Controls backend console verbosity. |
| `CD_LOG_RICH` | `true`, `false` | Enables Rich-formatted console logs. |
| `CD_LOG_PAYLOAD_PREVIEWS` | `true`, `false` | Shows text previews for extraction, privacy scrub, and grading payloads. |
| `CD_LOG_PREVIEW_CHARS` | integer | Max characters shown for text previews. |
| `CD_GRADING_CACHE_TTL_HOURS` | integer | Hours before cached grading source files expire. |

LiteLLM smoke test:

```powershell
cd apps/api
$env:CD_GRADING_ENGINE="litellm"
$env:CD_LITELLM_MODEL="openai/gpt-5"
uv run python scripts/smoke_litellm_grading.py
```
