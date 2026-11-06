# HireRank AI — Local and Deployment Guide

## Requirements

- Python 3.10 or later
- Node.js 20 or later and npm
- PostgreSQL 14+ for shared/production use (SQLite is the default for local development)

## Local installation

From the project root, copy `.env.example` to `.env` and set a unique `JWT_SECRET`. Do not commit `.env`. Run the following from the project root so both services read the same environment file.

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://localhost:8000`; OpenAPI docs are at `/docs`. On initial startup the application creates synthetic demo organization, recruiter/client accounts, a sample approved requisition, and five synthetic candidates. The demo seed runs only when the database has no users.

### Frontend

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Set `VITE_API_URL` to the backend origin when it is not `http://localhost:8000`.

## PostgreSQL

Create a database and application user, then set `DATABASE_URL` to a SQLAlchemy URL such as:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

Run migrations from `backend/`:

```powershell
alembic upgrade head
```

The local default is `sqlite:///./hirerank.db`. For the configured demo database, startup seeds demo records automatically. A repeatable CLI seed can be run from the project root with `python -m app.seed` after setting `PYTHONPATH=backend`; it is intentionally a no-op if users already exist.

## Environment variable names

`DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_MINUTES`, `UPLOAD_DIR`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `FRONTEND_ORIGIN`, and frontend build variable `VITE_API_URL`.

`AI_API_KEY` is optional. Without it, transparent deterministic rule-based scoring is used. Do not store credentials in source control.

## Tests and build

From the repository root:

```powershell
python -m pytest backend/tests -q
cd frontend
npm test
npm run build
```

## Synthetic demo logins

- Recruiter: `recruiter@hirerank.demo` / `Recruiter@123`
- Client hiring manager: `client@hirerank.demo` / `Client@123`

Every seeded candidate and contact value is synthetic.

## Render deployment

1. Push the source repository to your public or private GitHub repository.
2. In Render, create a Blueprint from the repository and review `render.yaml`.
3. Render provisions a PostgreSQL database, API service, persistent upload disk, and static frontend.
4. Set the frontend service’s `VITE_API_URL` to the deployed API origin. Set the API service’s `FRONTEND_ORIGIN` to the deployed frontend origin.
5. Keep Render’s generated `JWT_SECRET`; optionally configure `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL`.
6. The API build runs `alembic upgrade head`; the frontend service runs `npm ci` and `npm run build`.
7. Check API `/api/health`, API `/docs`, frontend sign-in, and role isolation after deployment. Use only synthetic or consented resumes.

The persistent disk keeps uploaded files across API restarts. Confirm Render plan availability and pricing for the selected region before provisioning. No deployment URL is assumed here.

## Submission ZIP

The submission archive is designed to contain exactly:

- `Technical_Design_Document.pdf` (or `.docx`)
- `deployment.md`

Keep application source in the separate GitHub repository. To regenerate the archive after updating the design document, generate a PDF or DOCX from `Technical_Design_Document.md` and zip only that document and this `deployment.md`.

## GitHub push

```powershell
git init
git add .
git commit -m "Build HireRank AI recruitment platform"
git branch -M main
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Replace the owner and repository placeholders with your own GitHub repository values.
