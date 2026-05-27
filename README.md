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
