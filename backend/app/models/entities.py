from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    organization: Mapped[Organization | None] = relationship(back_populates="users")


class Requisition(Base):
    __tablename__ = "requisitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(120))
    min_experience: Mapped[float | None] = mapped_column(Float)
    max_experience: Mapped[float | None] = mapped_column(Float)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    max_notice_days: Mapped[int | None] = mapped_column(Integer)
    min_ctc: Mapped[float | None] = mapped_column(Float)
    max_ctc: Mapped[float | None] = mapped_column(Float)
    scorecard_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobScorecard(Base):
    __tablename__ = "job_scorecards"
    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id", ondelete="CASCADE"), unique=True, index=True)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_range: Mapped[dict] = mapped_column(JSON, default=dict)
    location: Mapped[str | None] = mapped_column(String(120))
    max_notice_days: Mapped[int | None] = mapped_column(Integer)
    ctc_range: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring_weights: Mapped[dict] = mapped_column(JSON, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)


class BaseCandidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("email", name="uq_candidate_email"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(60))
    current_role: Mapped[str | None] = mapped_column(String(180))
    experience_years: Mapped[float | None] = mapped_column(Float)
    notice_days: Mapped[int | None] = mapped_column(Integer)
    current_ctc: Mapped[float | None] = mapped_column(Float)
    expected_ctc: Mapped[float | None] = mapped_column(Float)
    location: Mapped[str | None] = mapped_column(String(120))
    education: Mapped[list] = mapped_column(JSON, default=list)
    employers: Mapped[list] = mapped_column(JSON, default=list)
    missing_information: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    skills: Mapped[list["CandidateSkill"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(100), index=True)
    candidate: Mapped[BaseCandidate] = relationship(back_populates="skills")


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("sha256", name="uq_resume_sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    extracted_text: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(30), default="parsed")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    candidate: Mapped[BaseCandidate] = relationship(back_populates="resumes")


class CandidateExperience(Base):
    __tablename__ = "candidate_experience"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    employer: Mapped[str | None] = mapped_column(String(180))
    title: Mapped[str | None] = mapped_column(String(180))
    duration_text: Mapped[str | None] = mapped_column(String(100))


class CandidateEducation(Base):
    __tablename__ = "candidate_education"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str | None] = mapped_column(String(180))
    qualification: Mapped[str | None] = mapped_column(String(180))
    year: Mapped[str | None] = mapped_column(String(30))


class CandidateScore(Base):
    __tablename__ = "candidate_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"), index=True)
    overall_score: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(30))
    breakdown: Mapped[dict] = mapped_column(JSON)
    missing_information: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    scoring_method: Mapped[str] = mapped_column(String(40), default="rule-based")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScoreEvidence(Base):
    __tablename__ = "score_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    score_id: Mapped[int] = mapped_column(ForeignKey("candidate_scores.id", ondelete="CASCADE"), index=True)
    criterion: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    score: Mapped[float] = mapped_column(Float)
    quotation: Mapped[str] = mapped_column(Text, default="Insufficient evidence")
    explanation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)


class ShortlistSubmission(Base):
    __tablename__ = "shortlist_submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClientFeedback(Base):
    __tablename__ = "client_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("shortlist_submissions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("shortlist_submissions.id"), index=True)
    proposed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="proposed")


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"), index=True)
    stage: Mapped[str] = mapped_column(String(30), index=True)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Consent(Base):
    __tablename__ = "candidate_consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(180), default="employment screening")
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    deletion_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
