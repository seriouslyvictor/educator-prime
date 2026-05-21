# Classroom Downloader

Hosted SaaS-style MVP for exporting Google Classroom student submissions into a regular local folder tree.

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
npm install
npm run dev
```

Open `http://localhost:5173`.

Keep the backend running while using the frontend. Vite proxies `/api/*` requests to
`http://127.0.0.1:8000`; if the API is not listening, the browser will show a generic
request failure from the proxy.

The backend runs in mock Google mode by default, so the product workflow can be tested before Google OAuth credentials are configured.
