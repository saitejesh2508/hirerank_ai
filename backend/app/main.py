import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import (
    AuditLog, BaseCandidate, CandidateEducation, CandidateExperience, CandidateScore, JobScorecard,
    CandidateSkill, ClientFeedback, Consent, Interview, Organization, PipelineEvent,
    Requisition, Resume, ScoreEvidence, ShortlistSubmission, User,
)
from app.schemas.api import CandidateDecision, InterviewProposal, LoginRequest, PipelineUpdate, RequisitionCreate, ScorecardApproval
from app.services.resume_parser import extract_text, parse_resume
from app.services.scoring import score_candidate

app = FastAPI(title="HireRank AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer = HTTPBearer(auto_error=False)
PIPELINE_STAGES = ["Sourced", "Parsed", "Screened", "Submitted", "Shortlisted", "Interview", "Selected", "Offer", "Joined"]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def audit(db: Session, actor_id: int | None, action: str, entity_type: str, entity_id: int | str, details=None):
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=str(entity_id), details=details or {}))


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        subject = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]).get("sub")
        user = db.get(User, int(subject)) if subject else None
    except (JWTError, ValueError):
        user = None
    if not user or not user.active:
        raise HTTPException(401, "Invalid or expired access token")
    return user


def require_recruiter(user: User = Depends(current_user)) -> User:
    if user.role != "recruiter":
        raise HTTPException(403, "Recruiter access required")
    return user


def require_client(user: User = Depends(current_user)) -> User:
    if user.role != "client":
        raise HTTPException(403, "Client access required")
    return user


def candidate_payload(db: Session, candidate: BaseCandidate, requisition_id: int | None = None, masked=False):
    skills = [item.skill for item in candidate.skills]
    score = None
    if requisition_id is not None:
        score = db.scalar(select(CandidateScore).where(
            CandidateScore.candidate_id == candidate.id,
            CandidateScore.requisition_id == requisition_id,
        ).order_by(desc(CandidateScore.created_at)))
    return {
        "id": candidate.id,
        "external_id": candidate.external_id,
        "name": candidate.name or "Name not provided",
        "email": _mask_email(candidate.email) if masked else candidate.email,
        "phone": _mask_phone(candidate.phone) if masked else candidate.phone,
        "current_role": candidate.current_role,
        "experience_years": candidate.experience_years,
        "notice_days": candidate.notice_days,
        "current_ctc": None if masked else candidate.current_ctc,
        "expected_ctc": None if masked else candidate.expected_ctc,
        "location": candidate.location,
        "skills": skills,
        "education": candidate.education or [],
        "employers": candidate.employers or [],
        "missing_information": candidate.missing_information or [],
        "score": _score_payload(db, score, masked=masked),
        "synthetic": bool(candidate.resumes and candidate.resumes[0].synthetic),
    }


def _mask_email(value):
    if not value or "@" not in value:
        return "Hidden"
    name, domain = value.split("@", 1)
    return f"{name[:1]}***@{domain}"


def _mask_phone(value):
    if not value:
        return "Hidden"
    digits = re.sub(r"\D", "", value)
    return f"***{digits[-4:]}" if digits else "Hidden"


def _mask_contacts(value: str) -> str:
    value = re.sub(r"\b([A-Z0-9._%+-])[A-Z0-9._%+-]*@([A-Z0-9.-]+\.[A-Z]{2,})\b", r"\1***@\2", value, flags=re.I)
    return re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", lambda match: _mask_phone(match.group(0)), value)


def _score_payload(db: Session, score: CandidateScore | None, masked=False):
    if not score:
        return None
    evidence = db.scalars(select(ScoreEvidence).where(ScoreEvidence.score_id == score.id)).all()
    return {
        "overall_score": score.overall_score,
        "category": score.category,
        "scoring_method": score.scoring_method,
        "missing_information": score.missing_information,
        "warnings": score.warnings,
        "criteria": [{
            "criterion": item.criterion, "status": item.status, "score": item.score,
            "quotation": _mask_contacts(item.quotation) if masked else item.quotation,
            "explanation": _mask_contacts(item.explanation) if masked else item.explanation,
            "confidence": item.confidence,
        } for item in evidence],
    }


def persist_score(db: Session, candidate: BaseCandidate, requisition: Requisition, resume_text: str):
    result = score_candidate(requisition, candidate, resume_text)
    score = CandidateScore(
        candidate_id=candidate.id, requisition_id=requisition.id,
        overall_score=result["overall_score"], category=result["category"],
        breakdown={entry["criterion"]: entry["score"] for entry in result["criteria"]},
        missing_information=result.get("missing_information", []),
        warnings=result.get("warnings", []), scoring_method=result["scoring_method"],
    )
    db.add(score)
    db.flush()
    for entry in result["criteria"]:
        db.add(ScoreEvidence(score_id=score.id, **entry))
    return score


def add_pipeline_event(db: Session, candidate_id: int, requisition_id: int, stage: str, actor_id: int, note=None):
    db.add(PipelineEvent(candidate_id=candidate_id, requisition_id=requisition_id, stage=stage, changed_by=actor_id, note=note))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    audit(db, user.id, "auth.login", "user", user.id)
    db.commit()
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer", "user": {
        "id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
        "organization_id": user.organization_id,
    }}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role, "organization_id": user.organization_id}


@app.get("/api/organizations")
def list_organizations(db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    return [{"id": item.id, "name": item.name} for item in db.scalars(select(Organization).order_by(Organization.name))]


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    requisitions = db.scalars(select(Requisition).where(Requisition.status == "active")).all()
    candidates = db.scalar(select(func.count(func.distinct(BaseCandidate.id))).join(Resume)) or 0
    screened = db.scalar(select(func.count(func.distinct(CandidateScore.candidate_id)))) or 0
    shortlisted = db.scalar(select(func.count(ShortlistSubmission.id)).where(ShortlistSubmission.status == "shortlisted")) or 0
    pending = db.scalar(select(func.count(ShortlistSubmission.id)).where(ShortlistSubmission.status == "submitted")) or 0
    pipeline_events = db.scalars(select(PipelineEvent).order_by(desc(PipelineEvent.created_at))).all()
    latest = {}
    for event in pipeline_events:
        latest.setdefault((event.candidate_id, event.requisition_id), event.stage)
    stage_counts = {stage: sum(current == stage for current in latest.values()) for stage in PIPELINE_STAGES}
    recent = db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(8)).all()
    recent_requisitions = []
    for req in sorted(requisitions, key=lambda row: row.created_at, reverse=True)[:5]:
        organization = db.get(Organization, req.organization_id)
        candidate_count = db.scalar(select(func.count(func.distinct(Resume.candidate_id))).where(Resume.requisition_id == req.id)) or 0
        screened_count = db.scalar(select(func.count(func.distinct(CandidateScore.candidate_id))).where(CandidateScore.requisition_id == req.id)) or 0
        recent_requisitions.append({"id": req.id, "title": req.title, "organization": organization.name if organization else "", "location": req.location, "created_at": req.created_at, "scorecard_approved": req.scorecard_approved, "candidate_count": candidate_count, "screened_count": screened_count})
    return {
        "stats": {"active_requisitions": len(requisitions), "total_candidates": candidates, "candidates_screened": screened, "shortlisted_candidates": shortlisted, "pending_client_reviews": pending},
        "pipeline": stage_counts,
        "recent_requisitions": recent_requisitions,
        "recent_activity": [{"action": event.action, "entity_type": event.entity_type, "entity_id": event.entity_id, "created_at": event.created_at} for event in recent],
    }


@app.get("/api/requisitions")
def requisitions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Requisition)
    if user.role == "client":
        query = query.where(Requisition.organization_id == user.organization_id)
    items = db.scalars(query.order_by(desc(Requisition.created_at))).all()
    return [{
        "id": req.id, "title": req.title, "organization_id": req.organization_id,
        "organization": (db.get(Organization, req.organization_id).name if db.get(Organization, req.organization_id) else ""),
        "description": req.description, "location": req.location,
        "min_experience": req.min_experience, "max_experience": req.max_experience,
        "required_skills": req.required_skills, "preferred_skills": req.preferred_skills,
        "max_notice_days": req.max_notice_days, "min_ctc": req.min_ctc, "max_ctc": req.max_ctc,
        "scorecard_approved": req.scorecard_approved, "status": req.status, "created_at": req.created_at,
    } for req in items]


@app.post("/api/requisitions")
def create_requisition(payload: RequisitionCreate, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    if not db.get(Organization, payload.organization_id):
        raise HTTPException(404, "Organization not found")
    if payload.min_experience is not None and payload.max_experience is not None and payload.min_experience > payload.max_experience:
        raise HTTPException(422, "Minimum experience cannot exceed maximum experience")
    req = Requisition(**payload.model_dump(), created_by=user.id)
    db.add(req)
    db.flush()
    db.add(JobScorecard(
        requisition_id=req.id, required_skills=req.required_skills, preferred_skills=req.preferred_skills,
        experience_range={"min": req.min_experience, "max": req.max_experience},
        location=req.location, max_notice_days=req.max_notice_days,
        ctc_range={"min": req.min_ctc, "max": req.max_ctc},
        scoring_weights={"must_have_skills": 45, "experience": 25, "preferred_skills": 10, "notice_period": 10, "location": 5, "ctc_compatibility": 5},
    ))
    audit(db, user.id, "requisition.created", "requisition", req.id)
    db.commit()
    db.refresh(req)
    return {"id": req.id, "title": req.title, "scorecard_approved": req.scorecard_approved}


@app.post("/api/requisitions/extract-scorecard")
def extract_scorecard(payload: dict, user: User = Depends(require_recruiter)):
    description = str(payload.get("description", ""))
    skills = ["Java", "Spring Boot", "Microservices", "Hibernate", "REST APIs", "Python", "SQL", "Excel", "KYC", "AML", "AWS", "Azure", "React", "TypeScript", "Kubernetes", "Docker"]
    found = [skill for skill in skills if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", description, re.I)]
    exp = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", description, re.I)
    notice = re.search(r"(?:notice(?:\s+period)?|within)\s*[:\-]?\s*(\d+)\s*days?", description, re.I)
    location_match = re.search(r"(?:location|based\s+in)\s*[:\-]\s*([^\n,]+)", description, re.I)
    ctc_match = re.search(r"(?:ctc|compensation|salary)(?:\s+range)?\s*[:\-]?\s*(?:₹|inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)?", description, re.I)
    return {
        "title": payload.get("title") or (description.splitlines()[0][:180] if description.splitlines() else ""),
        "required_skills": found[:6], "preferred_skills": found[6:],
        "min_experience": float(exp.group(1)) if exp else None,
        "max_experience": float(exp.group(2)) if exp else None,
        "max_notice_days": int(notice.group(1)) if notice else None,
        "location": location_match.group(1).strip() if location_match else None,
        "min_ctc": float(ctc_match.group(1)) if ctc_match else None,
        "max_ctc": float(ctc_match.group(2)) if ctc_match else None,
        "note": "Draft extracted from job description. Review and edit every field before saving.",
    }


@app.post("/api/requisitions/{requisition_id}/approve")
def approve_scorecard(requisition_id: int, payload: ScorecardApproval, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    req = db.get(Requisition, requisition_id)
    if not req:
        raise HTTPException(404, "Requisition not found")
    req.scorecard_approved = payload.approved
    scorecard = db.scalar(select(JobScorecard).where(JobScorecard.requisition_id == req.id))
    if not scorecard:
        scorecard = JobScorecard(requisition_id=req.id)
        db.add(scorecard)
    scorecard.approved = payload.approved
    scorecard.approved_by = user.id if payload.approved else None
    scorecard.approved_at = datetime.utcnow() if payload.approved else None
    audit(db, user.id, "scorecard.approved" if payload.approved else "scorecard.unapproved", "requisition", req.id)
    db.commit()
    return {"id": req.id, "scorecard_approved": req.scorecard_approved}


@app.post("/api/requisitions/{requisition_id}/resumes")
async def upload_resumes(requisition_id: int, files: list[UploadFile] = File(...), consent_confirmed: bool = Form(False), db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    req = db.get(Requisition, requisition_id)
    if not req:
        raise HTTPException(404, "Requisition not found")
    if not req.scorecard_approved:
        raise HTTPException(409, "Approve the scorecard before uploading and scoring resumes")
    if not consent_confirmed:
        raise HTTPException(422, "Confirm that candidates have consented to employment screening before upload")
    if len(files) > 500:
        raise HTTPException(413, "A maximum of 500 resumes may be uploaded at once")
    os.makedirs(settings.upload_dir, exist_ok=True)
    results = []
    for upload in files:
        filename = Path(upload.filename or "resume").name
        if Path(filename).suffix.lower() not in {".pdf", ".docx"}:
            results.append({"filename": filename, "status": "failed", "error": "Only PDF and DOCX files are accepted"})
            continue
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            results.append({"filename": filename, "status": "failed", "error": "File exceeds the 10 MB limit"})
            continue
        digest = hashlib.sha256(content).hexdigest()
        if db.scalar(select(Resume.id).where(Resume.sha256 == digest)):
            results.append({"filename": filename, "status": "duplicate", "error": "Identical resume content already exists"})
            continue
        try:
            text = extract_text(filename, content)
            if not text:
                raise ValueError("No readable text found; scanned PDF OCR is not configured")
            parsed = parse_resume(text)
            if parsed["email"] and db.scalar(select(BaseCandidate.id).where(func.lower(BaseCandidate.email) == parsed["email"].lower())):
                results.append({"filename": filename, "status": "duplicate", "error": "Candidate email already exists"})
                continue
            candidate = BaseCandidate(
                name=parsed["name"], email=parsed["email"], phone=parsed["phone"],
                current_role=parsed["current_role"], experience_years=parsed["experience_years"],
                notice_days=parsed["notice_days"], current_ctc=parsed["current_ctc"],
                expected_ctc=parsed["expected_ctc"], location=parsed["location"],
                education=parsed["education"], employers=parsed["employers"],
                missing_information=parsed["missing_information"],
            )
            db.add(candidate)
            db.flush()
            candidate.external_id = f"CND-{candidate.id:05d}"
            for skill in parsed["skills"]:
                db.add(CandidateSkill(candidate_id=candidate.id, skill=skill))
            for qualification in parsed["education"]:
                db.add(CandidateEducation(candidate_id=candidate.id, qualification=qualification))
            for employer in parsed["employers"]:
                db.add(CandidateExperience(candidate_id=candidate.id, employer=employer, title=parsed["current_role"]))
            stored_path = os.path.join(settings.upload_dir, digest + Path(filename).suffix.lower())
            with open(stored_path, "wb") as file:
                file.write(content)
            resume = Resume(candidate_id=candidate.id, requisition_id=req.id, filename=filename, sha256=digest, extracted_text=text)
            db.add(resume)
            db.add(Consent(candidate_id=candidate.id, purpose=f"Employment screening for {req.title}", granted=consent_confirmed))
            add_pipeline_event(db, candidate.id, req.id, "Parsed", user.id)
            score = persist_score(db, candidate, req, text)
            add_pipeline_event(db, candidate.id, req.id, "Screened", user.id, score.category)
            audit(db, user.id, "resume.parsed_and_scored", "candidate", candidate.id, {"requisition_id": req.id})
            db.commit()
            results.append({"filename": filename, "status": "success", "candidate_id": candidate.id, "external_id": candidate.external_id, "score": score.overall_score})
        except Exception as error:
            db.rollback()
            results.append({"filename": filename, "status": "failed", "error": str(error) or "Resume processing failed"})
    return {"results": results, "total": len(files), "successful": sum(row["status"] == "success" for row in results), "duplicates": sum(row["status"] == "duplicate" for row in results)}


@app.get("/api/requisitions/{requisition_id}/candidates")
def requisition_candidates(requisition_id: int, q: str = "", category: str = "", sort: str = "score", db: Session = Depends(get_db), user: User = Depends(current_user)):
    req = db.get(Requisition, requisition_id)
    if not req:
        raise HTTPException(404, "Requisition not found")
    if user.role == "client" and user.organization_id != req.organization_id:
        raise HTTPException(404, "Requisition not found")
    candidates = db.scalars(select(BaseCandidate).join(Resume).where(Resume.requisition_id == req.id).distinct()).all()
    if user.role == "client":
        submitted_ids = set(db.scalars(select(ShortlistSubmission.candidate_id).where(
            ShortlistSubmission.requisition_id == req.id,
            ShortlistSubmission.organization_id == user.organization_id,
        )).all())
        candidates = [candidate for candidate in candidates if candidate.id in submitted_ids]
    result = [candidate_payload(db, item, req.id, masked=user.role == "client") for item in candidates]
    if q:
        term = q.casefold()
        result = [item for item in result if term in (item["name"] or "").casefold() or term in (item["current_role"] or "").casefold() or any(term in skill.casefold() for skill in item["skills"])]
    if category:
        result = [item for item in result if item["score"] and item["score"]["category"] == category]
    result.sort(key=lambda item: (item["score"]["overall_score"] if item["score"] else -1), reverse=sort != "name")
    if sort == "name":
        result.sort(key=lambda item: item["name"].casefold())
    return result


@app.get("/api/candidates/{candidate_id}")
def candidate_detail(candidate_id: int, requisition_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    candidate = db.get(BaseCandidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    resume = db.scalar(select(Resume).where(Resume.candidate_id == candidate.id, Resume.requisition_id == requisition_id).order_by(desc(Resume.uploaded_at)))
    if not resume:
        raise HTTPException(404, "Resume not found for requisition")
    req = db.get(Requisition, requisition_id)
    submission = db.scalar(select(ShortlistSubmission).where(
        ShortlistSubmission.candidate_id == candidate.id,
        ShortlistSubmission.requisition_id == requisition_id,
        ShortlistSubmission.organization_id == user.organization_id,
    ))
    if user.role == "client" and (not req or user.organization_id != req.organization_id or not submission):
        raise HTTPException(404, "Candidate not found")
    audit(db, user.id, "candidate.profile_view", "candidate", candidate.id, {"requisition_id": requisition_id})
    db.commit()
    data = candidate_payload(db, candidate, requisition_id, masked=user.role == "client")
    data["resume_text"] = _mask_contacts(resume.extracted_text) if user.role == "client" else resume.extracted_text
    data["resume_filename"] = resume.filename
    data["status"] = submission.status if submission else None
    return data


@app.post("/api/candidates/{candidate_id}/submit")
def submit_candidate(candidate_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    requisition_id = int(payload.get("requisition_id", 0))
    req = db.get(Requisition, requisition_id)
    candidate = db.get(BaseCandidate, candidate_id)
    if not req or not candidate:
        raise HTTPException(404, "Candidate or requisition not found")
    review_logs = db.scalars(select(AuditLog).where(
        AuditLog.actor_id == user.id, AuditLog.action == "candidate.profile_view",
        AuditLog.entity_id == str(candidate_id),
    )).all()
    reviewed = any(log.details.get("requisition_id") == requisition_id for log in review_logs)
    if not reviewed:
        raise HTTPException(409, "Open and review the candidate profile before submitting")
    if not db.scalar(select(Resume.id).where(Resume.candidate_id == candidate_id, Resume.requisition_id == requisition_id)):
        raise HTTPException(404, "Candidate has no resume for this requisition")
    existing = db.scalar(select(ShortlistSubmission).where(ShortlistSubmission.candidate_id == candidate_id, ShortlistSubmission.requisition_id == requisition_id))
    if existing:
        raise HTTPException(409, "Candidate has already been submitted")
    submission = ShortlistSubmission(candidate_id=candidate_id, requisition_id=req.id, organization_id=req.organization_id, submitted_by=user.id)
    db.add(submission)
    add_pipeline_event(db, candidate_id, req.id, "Submitted", user.id)
    audit(db, user.id, "candidate.submitted", "candidate", candidate_id, {"requisition_id": req.id})
    db.commit()
    return {"id": submission.id, "status": submission.status}


@app.get("/api/client/dashboard")
def client_dashboard(db: Session = Depends(get_db), user: User = Depends(require_client)):
    assigned = db.scalars(select(Requisition).where(Requisition.organization_id == user.organization_id, Requisition.status == "active")).all()
    submitted = db.scalars(select(ShortlistSubmission).where(ShortlistSubmission.organization_id == user.organization_id).order_by(desc(ShortlistSubmission.submitted_at))).all()
    return {
        "organization": db.get(Organization, user.organization_id).name if user.organization_id else "",
        "requisitions": [{"id": row.id, "title": row.title} for row in assigned],
        "stats": {"assigned_requisitions": len(assigned), "submitted_candidates": len(submitted), "pending_review": sum(row.status == "submitted" for row in submitted), "shortlisted": sum(row.status == "shortlisted" for row in submitted)},
        "submissions": [_submission_payload(db, row) for row in submitted],
    }


@app.get("/api/client/submissions")
def client_submissions(db: Session = Depends(get_db), user: User = Depends(require_client)):
    items = db.scalars(select(ShortlistSubmission).where(ShortlistSubmission.organization_id == user.organization_id).order_by(desc(ShortlistSubmission.submitted_at))).all()
    return [_submission_payload(db, item) for item in items]


def _submission_payload(db, item):
    candidate = db.get(BaseCandidate, item.candidate_id)
    req = db.get(Requisition, item.requisition_id)
    data = candidate_payload(db, candidate, item.requisition_id, masked=True)
    data.update({"submission_id": item.id, "requisition_id": item.requisition_id, "requisition_title": req.title if req else "", "status": item.status, "submitted_at": item.submitted_at})
    return data


def _owned_submission(db, submission_id: int, user: User):
    item = db.get(ShortlistSubmission, submission_id)
    if not item or item.organization_id != user.organization_id:
        raise HTTPException(404, "Submission not found")
    return item


@app.post("/api/client/submissions/{submission_id}/decision")
def client_decision(submission_id: int, payload: CandidateDecision, db: Session = Depends(get_db), user: User = Depends(require_client)):
    submission = _owned_submission(db, submission_id, user)
    if payload.decision not in {"shortlisted", "rejected"}:
        raise HTTPException(422, "Decision must be shortlisted or rejected")
    if payload.decision == "rejected" and not (payload.reason or "").strip():
        raise HTTPException(422, "A rejection reason is required")
    submission.status = payload.decision
    db.add(ClientFeedback(submission_id=submission.id, user_id=user.id, decision=payload.decision, reason=payload.reason))
    add_pipeline_event(db, submission.candidate_id, submission.requisition_id, "Shortlisted" if payload.decision == "shortlisted" else "Rejected", user.id, payload.reason)
    audit(db, user.id, f"candidate.{payload.decision}", "submission", submission.id, {"reason": payload.reason})
    db.commit()
    return {"id": submission.id, "status": submission.status}


@app.post("/api/client/submissions/{submission_id}/interviews")
def propose_interview(submission_id: int, payload: InterviewProposal, db: Session = Depends(get_db), user: User = Depends(require_client)):
    submission = _owned_submission(db, submission_id, user)
    interview = Interview(submission_id=submission.id, proposed_by=user.id, starts_at=payload.starts_at, note=payload.note)
    db.add(interview)
    submission.status = "interview"
    add_pipeline_event(db, submission.candidate_id, submission.requisition_id, "Interview", user.id, payload.note)
    audit(db, user.id, "interview.proposed", "submission", submission.id)
    db.commit()
    return {"id": interview.id, "status": interview.status, "starts_at": interview.starts_at}


@app.get("/api/pipeline")
def pipeline(db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    events = db.scalars(select(PipelineEvent).order_by(desc(PipelineEvent.created_at))).all()
    latest = {}
    for event in events:
        key = (event.candidate_id, event.requisition_id)
        if key not in latest:
            latest[key] = event
    columns = {stage: [] for stage in PIPELINE_STAGES}
    for (candidate_id, requisition_id), event in latest.items():
        if event.stage not in columns:
            continue
        candidate = db.get(BaseCandidate, candidate_id)
        req = db.get(Requisition, requisition_id)
        if candidate:
            data = candidate_payload(db, candidate, requisition_id)
            data.update({"requisition_id": requisition_id, "requisition_title": req.title if req else "", "stage": event.stage, "updated_at": event.created_at})
            columns[event.stage].append(data)
    return [{"stage": stage, "count": len(cards), "candidates": cards} for stage, cards in columns.items()]


@app.patch("/api/pipeline/{candidate_id}/{requisition_id}")
def update_pipeline(candidate_id: int, requisition_id: int, payload: PipelineUpdate, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    if payload.stage not in PIPELINE_STAGES:
        raise HTTPException(422, "Invalid pipeline stage")
    if not db.get(BaseCandidate, candidate_id) or not db.get(Requisition, requisition_id):
        raise HTTPException(404, "Candidate or requisition not found")
    add_pipeline_event(db, candidate_id, requisition_id, payload.stage, user.id, payload.note)
    audit(db, user.id, "pipeline.stage_changed", "candidate", candidate_id, {"requisition_id": requisition_id, "stage": payload.stage})
    db.commit()
    return {"candidate_id": candidate_id, "stage": payload.stage}


@app.get("/api/candidates/{candidate_id}/history")
def candidate_history(candidate_id: int, db: Session = Depends(get_db), user: User = Depends(require_recruiter)):
    rows = db.scalars(select(PipelineEvent).where(PipelineEvent.candidate_id == candidate_id).order_by(desc(PipelineEvent.created_at))).all()
    return [{"stage": row.stage, "note": row.note, "created_at": row.created_at, "changed_by": row.changed_by} for row in rows]


@app.post("/api/candidates/{candidate_id}/deletion-request")
def request_candidate_deletion(candidate_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "client":
        raise HTTPException(403, "Candidate deletion requests are handled by the recruiter")
    consent = db.scalar(select(Consent).where(Consent.candidate_id == candidate_id).order_by(desc(Consent.recorded_at)))
    if not consent:
        raise HTTPException(404, "Consent record not found")
    consent.deletion_requested = True
    audit(db, user.id, "candidate.deletion_requested", "candidate", candidate_id)
    db.commit()
    return {"candidate_id": candidate_id, "deletion_requested": True}


def seed_data():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        if db.scalar(select(User.id).limit(1)):
            return
        org = Organization(name="Northstar Technologies")
        db.add(org)
        db.flush()
        recruiter = User(email="recruiter@hirerank.demo", full_name="Aarav Mehta", role="recruiter", password_hash=hash_password("Recruiter@123"))
        client = User(email="client@hirerank.demo", full_name="Neha Kapoor", role="client", organization_id=org.id, password_hash=hash_password("Client@123"))
        db.add_all([recruiter, client])
        db.flush()
        req = Requisition(
            title="Senior Java Developer", organization_id=org.id,
            description="Build resilient Java services with Spring Boot and Microservices.",
            location="Noida", min_experience=5, max_experience=8,
            required_skills=["Java", "Spring Boot", "Microservices"], preferred_skills=["Hibernate", "REST APIs"],
            max_notice_days=60, scorecard_approved=True, created_by=recruiter.id,
        )
        db.add(req)
        db.flush()
        db.add(JobScorecard(
            requisition_id=req.id, required_skills=req.required_skills, preferred_skills=req.preferred_skills,
            experience_range={"min": req.min_experience, "max": req.max_experience},
            location=req.location, max_notice_days=req.max_notice_days,
            ctc_range={"min": req.min_ctc, "max": req.max_ctc},
            scoring_weights={"must_have_skills": 45, "experience": 25, "preferred_skills": 10, "notice_period": 10, "location": 5, "ctc_compatibility": 5},
            approved=True, approved_by=recruiter.id, approved_at=datetime.utcnow(),
        ))
        samples = [
            ("CND-91022", "Ritika Bansal", "ritika.bansal@example.com", "+91 98765 43210", "Senior Java Developer", 6.5, 60, "Noida", ["Java", "Spring Boot", "Microservices", "Hibernate"], "Ritika Bansal\nSenior Java Developer\nEmail: ritika.bansal@example.com\nPhone: +91 98765 43210\nCurrent role: Senior Java Developer\n6.5 years of experience building Java services.\nSkills: Java, Spring Boot, Microservices, Hibernate\nNotice period: 60 days\nLocation: Noida\nEducation: B.Tech Computer Science"),
            ("CND-91047", "Arjun Rawat", "arjun.rawat@example.com", "+91 98765 43211", "KYC Analyst", 3, 30, "Delhi", ["KYC", "AML Checks", "Excel"], "Arjun Rawat\nKYC Analyst\nEmail: arjun.rawat@example.com\nPhone: +91 98765 43211\nCurrent role: KYC Analyst\n3 years of experience in customer due diligence.\nSkills: KYC, AML Checks, Excel\nNotice period: 30 days\nLocation: Delhi\nEducation: MBA Finance"),
            ("CND-91088", "Pooja Nair", "pooja.nair@example.com", "+91 98765 43212", "Java Developer", 4, 90, "Noida", ["Java", "Hibernate", "REST APIs"], "Pooja Nair\nJava Developer\nEmail: pooja.nair@example.com\nPhone: +91 98765 43212\nCurrent role: Java Developer\n4 years of experience developing REST APIs.\nSkills: Java, Hibernate, REST APIs\nNotice period: 90 days\nLocation: Noida\nEducation: B.Tech Information Technology"),
            ("CND-91104", "Kabir Sethi", "kabir.sethi@example.com", "+91 98765 43213", "Java Engineer", 7, 45, "Noida", ["Java", "Spring Boot", "Microservices", "REST APIs"], "Kabir Sethi\nJava Engineer\nEmail: kabir.sethi@example.com\nPhone: +91 98765 43213\nCurrent role: Java Engineer\n7 years of experience developing distributed systems.\nSkills: Java, Spring Boot, Microservices, REST APIs\nNotice period: 45 days\nLocation: Noida\nEducation: M.Tech Software Engineering"),
            ("CND-91119", "Meera Iyer", "meera.iyer@example.com", "+91 98765 43214", "Backend Developer", 5.5, 30, "Gurugram", ["Java", "Spring Boot", "SQL"], "Meera Iyer\nBackend Developer\nEmail: meera.iyer@example.com\nPhone: +91 98765 43214\nCurrent role: Backend Developer\n5.5 years of experience building backend applications.\nSkills: Java, Spring Boot, SQL\nNotice period: 30 days\nLocation: Gurugram\nEducation: B.E. Computer Engineering"),
        ]
        for external, name, email, phone, role, years, notice, location, skills, text in samples:
            candidate = BaseCandidate(external_id=external, name=name, email=email, phone=phone, current_role=role, experience_years=years, notice_days=notice, location=location, education=["Synthetic degree record"], employers=[], missing_information=["current_ctc", "expected_ctc"])
            db.add(candidate)
            db.flush()
            for skill in skills:
                db.add(CandidateSkill(candidate_id=candidate.id, skill=skill))
            if candidate.education:
                for qualification in candidate.education:
                    db.add(CandidateEducation(candidate_id=candidate.id, qualification=qualification))
            digest = hashlib.sha256(text.encode()).hexdigest()
            db.add(Resume(candidate_id=candidate.id, requisition_id=req.id, filename=f"{external.lower()}.txt", sha256=digest, extracted_text=text, synthetic=True))
            db.add(Consent(candidate_id=candidate.id, purpose="Synthetic demonstration data", granted=True))
            add_pipeline_event(db, candidate.id, req.id, "Screened", recruiter.id, "Synthetic sample")
            persist_score(db, candidate, req, text)
        audit(db, recruiter.id, "demo.seeded", "organization", org.id, {"synthetic": True})
        db.commit()
    finally:
        db.close()


seed_data()
