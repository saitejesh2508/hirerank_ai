# HireRank AI — Technical Design Document

## 1. Overview

HireRank AI is a recruitment workspace for staffing recruiters and client hiring managers. Recruiters manage requisitions, approve scorecards, parse and review resumes, and share selected profiles. Client users can review only submissions assigned to their organization, provide job-related decisions, and propose interviews.

## 2. Architecture

The application is a two-tier web system:

- **Frontend:** React 18, TypeScript, Vite, React Router, Tailwind CSS, Lucide React, and Recharts. The UI uses a compact custom component system with responsive navigation, tables, score explanations, and client-first review cards.
- **Backend:** Python 3.10+, FastAPI REST API, Pydantic request validation, SQLAlchemy 2 ORM, and Alembic schema migrations.
- **Persistence:** PostgreSQL in hosted environments; SQLite is the local default to reduce setup friction. `DATABASE_URL` selects the engine.
- **Authentication:** bearer JWT tokens and bcrypt password hashes. API dependencies enforce recruiter/client role access.
- **Documents:** PyMuPDF extracts PDF text and python-docx extracts DOCX text. Scanned PDFs with no embedded text are reported as processing errors; OCR support is optional and not enabled by default.
- **Hosting:** Render web services and managed PostgreSQL. The frontend is a static Vite build with SPA route rewrites.

Request flow: browser → typed API helper with bearer token → FastAPI endpoint and authorization check → SQLAlchemy transaction → PostgreSQL/SQLite. Candidate upload is parsed and scored on the API worker and is intended for demonstration and moderate workloads, not a high-throughput background processing queue.

## 3. Database design

The schema separates organizations, people, roles, candidate records, resume versions, score results, and client review:

| Entity | Purpose |
|---|---|
| `organizations` | Client organization boundary and display name |
| `users` | Recruiter/client accounts, password hash, role, organization |
| `requisitions` | Job description, location, experience, skills, notice, CTC, and approval state |
| `candidates` | Parsed contact/profile fields and missing-information inventory |
| `candidate_skills` | Normalized candidate skill rows |
| `candidate_experience`, `candidate_education` | Structured prior-work and education record tables |
| `resumes` | Requisition-linked original content hash, extracted text, filename, and parse status |
| `candidate_scores` | Versioned score, category, criterion breakdown, method, and warnings |
| `score_evidence` | Criterion status, score, verbatim evidence, explanation, confidence |
| `shortlist_submissions` | Recruiter-to-client candidate submission and current review status |
| `client_feedback` | Shortlist/reject decision and optional job-related reason |
| `interviews` | Proposed date/time, proposing user, status, and note |
| `pipeline_events` | Append-only stage history for each candidate/requisition |
| `candidate_consents` | Hiring-purpose consent and deletion-request state |
| `audit_logs` | Authentication, profile views, submissions, decisions, and pipeline actions |

Primary/foreign keys, unique email and external candidate identifiers, unique organization names, and lookup indexes are present. Resume SHA-256 hashes enable content duplicate detection. Migration entry point: `backend/alembic`.

## 4. Main workflows

1. Recruiter signs in and creates a requisition for an existing organization.
2. The scorecard extraction endpoint drafts skills, experience range, location, and notice days from the JD. The recruiter can edit all fields and explicitly approve the scorecard.
3. Resume upload accepts up to 500 PDF/DOCX files per request, capped at 10 MB per file. Invalid formats, unreadable documents, duplicate content, and already-known email addresses are surfaced per file.
4. Parsed candidate fields are persisted without inventing unknown values. Skills and consent are recorded, scoring is calculated, and pipeline events are written.
5. Recruiters search/rank candidates, open each profile, inspect the resume and evidence, then submit to the requisition’s client.
6. Client users see only submissions within their organization. Personal email and phone values are masked. The client can shortlist, reject with a mandatory reason, or propose an interview time.
7. Recruiters view persisted pipeline history and update stages.

## 5. AI methodology and scoring

The scoring engine is a separate service. Default deterministic weights are:

- Must-have skills: 45%
- Experience: 25%
- Preferred skills: 10%
- Notice period: 10%
- Location: 5%
- CTC compatibility: 5%

The weighted total is normalized to 0–100. Categories are Strong match (85–100), Good match (70–84), Partial match (50–69), and Low match (<50). Scores are guidance only; there is no automatic rejection.

When `AI_API_KEY` is configured, the backend makes an OpenAI-compatible chat-completions request using `AI_BASE_URL` and `AI_MODEL`, requests JSON output, and validates every quotation against extracted resume text. Provider failure, malformed output, or invalid criteria produces the deterministic fallback with a visible fallback warning. The fallback is labeled `rule-based`; an AI response is labeled `llm`.

This implementation intentionally keeps deterministic scoring active as a functional baseline. Score semantics and evidence quality require validation by hiring experts before production use.

## 6. Evidence validation

Criterion evidence must be copied from extracted resume text. The backend checks each quoted string after conservative punctuation/whitespace normalization. Unmatched text is replaced with **Insufficient evidence**, status is changed accordingly, and confidence is set to zero. Missing fields are kept separate from negative evidence. UI profiles show evidence, explanation, score, and confidence per criterion; resume text remains available for review.

## 7. Fairness safeguards

Scoring only uses job-related criteria: skills, stated experience, notice, location, and CTC compatibility. Candidate name, gender, age, photograph, marital status, religion, caste, and other protected traits are not score inputs. Candidates are not automatically rejected or hidden; low scores remain searchable. Recruiters must review a profile before client submission, and clients must provide a reason when rejecting.

These are product controls, not a legal or statistical fairness certification. Production adoption should include an impact assessment, adverse-impact testing, human oversight training, and local employment-law review.

## 8. Privacy and security

- JWT signing key, database URL, optional AI API key, and frontend origin are environment-configured; secrets are excluded from version control.
- Passwords are bcrypt-hashed. API endpoints enforce role authorization. Client candidate reads and actions verify organization ownership and submission membership.
- Client candidate views mask email and phone. No recruiter-only notes are exposed by the API.
- Uploads are restricted by extension and size, stored under a configurable directory, and duplicate content is detected by SHA-256.
- Consent purpose, deletion request, profile views, client decisions, and pipeline changes are persisted.
- Production requirements include HTTPS, managed secret storage, least-privilege DB credentials, upload malware scanning, retention/deletion operations, rate limiting, backup/restore drills, and security monitoring.

The current deletion endpoint records a deletion request; it does not automatically purge records. Local uploads are stored on disk. Render uses a mounted disk for demo persistence; production should consider encrypted object storage and a formal retention policy.

## 9. UI/UX decisions

The interface uses white cards, light gray surfaces, navy typography, indigo action accents, restrained borders, and responsive layouts. Recruiter dashboard metrics are API-backed. Candidate profiles emphasize criterion evidence and show missing information. Client review is isolated and mobile-friendly. Pipeline stages have counts, date markers, editable stage controls, and a candidate event history.

## 10. Assumptions

- One demo client organization is seeded; recruiters can create requisitions only for existing organizations.
- Authentication is password-based for the demo. Account provisioning, password reset, and SSO are not included.
- Candidate consent is recorded at upload time for the configured hiring purpose. A real consent capture and candidate-facing disclosure flow must be added before production.
- Experience and notice extraction are heuristic. Human review is required for ambiguous resumes and scorecards.
- CTC values are interpreted in the requisition’s configured unit; the demo UI labels them LPA.
- Demo sample data is synthetic and clearly labeled.

## 11. Limitations and future improvements

- Add asynchronous parse/score jobs, resumable multipart uploads, OCR fallback, malware scanning, and object storage.
- Improve structured resume extraction with versioned schemas and recruiter corrections.
- Add admin/user management, identity provider integration, refresh tokens, rate limiting, and consent/deletion workflows.
- Add requisition-level candidate deduplication policies and score history/versioning.
- Add deeper accessibility audits, browser-based end-to-end tests, load tests, and tenant-isolation security testing.
- Validate the LLM prompt/schema per provider and introduce evaluation datasets, bias monitoring, and human override analysis.
- Add calendar integration, interview coordination, notifications, and richer pipeline transitions.
