# HireRank AI

Evidence-led resume screening and client shortlist workspace for staffing teams. This repository includes a React + TypeScript frontend and a FastAPI backend with SQLAlchemy persistence, JWT authentication, PDF/DOCX parsing, explainable match scoring, client review, and a recruitment pipeline.

All built-in candidate examples and contact details are synthetic. Read [deployment.md](./deployment.md) for local setup, tests, and Render deployment.

## Quick start

1. Copy `.env.example` to `.env` and set `JWT_SECRET`.
2. Start the backend from `backend/`: `python -m pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --reload`.
3. Start the frontend from `frontend/`: `npm ci && npm run dev`.
4. Sign in with one of the synthetic demo accounts documented in [deployment.md](./deployment.md).

## Project layout

- `frontend/` React, TypeScript, Vite, Tailwind UI
- `backend/` FastAPI application, SQLAlchemy entities, Alembic, and tests
- `sample_data/resumes/` synthetic resume text examples
- `Technical_Design_Document.md` architecture, data, AI, fairness, and privacy decisions
