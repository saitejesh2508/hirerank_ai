from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserView(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    organization_id: int | None
    model_config = ConfigDict(from_attributes=True)


class RequisitionCreate(BaseModel):
    title: str
    organization_id: int
    description: str
    location: str | None = None
    min_experience: float | None = None
    max_experience: float | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    max_notice_days: int | None = None
    min_ctc: float | None = None
    max_ctc: float | None = None


class ScorecardApproval(BaseModel):
    approved: bool


class CandidateDecision(BaseModel):
    decision: str
    reason: str | None = None


class InterviewProposal(BaseModel):
    starts_at: datetime
    note: str | None = None


class PipelineUpdate(BaseModel):
    stage: str
    note: str | None = None
