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
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn classroom_downloader.main:app --reload --port 8000
```

Frontend:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`.

The backend runs in mock Google mode by default, so the product workflow can be tested before Google OAuth credentials are configured.
