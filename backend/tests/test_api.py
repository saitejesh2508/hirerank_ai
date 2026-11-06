import io

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models import (
    BaseCandidate, CandidateScore, CandidateSkill, ClientFeedback, JobScorecard, Organization, Requisition,
    PipelineEvent, Resume, ScoreEvidence, ShortlistSubmission, User,
)
from app.services.resume_parser import parse_resume
from app.services.scoring import evidence_is_valid, score_candidate


@pytest.fixture()
def context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    organization = Organization(name="Test client")
    other_organization = Organization(name="Other client")
    db.add_all([organization, other_organization])
    db.flush()
    recruiter = User(email="recruiter@test.demo", full_name="Test Recruiter", role="recruiter", password_hash=hash_password("Recruiter@123"))
    client_user = User(email="client@test.demo", full_name="Test Client", role="client", organization_id=organization.id, password_hash=hash_password("Client@123"))
    other_client = User(email="other@test.demo", full_name="Other Client", role="client", organization_id=other_organization.id, password_hash=hash_password("Client@123"))
    db.add_all([recruiter, client_user, other_client])
    db.flush()
    requisition = Requisition(title="Senior Java Developer", organization_id=organization.id, description="Build Java services", location="Noida", min_experience=5, max_experience=8, required_skills=["Java", "Spring Boot", "Microservices"], preferred_skills=["Hibernate"], max_notice_days=60, scorecard_approved=True, created_by=recruiter.id)
    other_req = Requisition(title="Private role", organization_id=other_organization.id, description="Private", scorecard_approved=True, created_by=recruiter.id)
    db.add_all([requisition, other_req])
    db.flush()
    candidate = BaseCandidate(external_id="CND-TEST1", name="Synthetic Person", email="person@example.com", phone="+91 90000 11111", current_role="Java Developer", experience_years=6, notice_days=30, location="Noida", education=["Synthetic B.Tech"], employers=[], missing_information=[])
    db.add(candidate)
    db.flush()
    for skill in ["Java", "Spring Boot", "Microservices"]:
        db.add(CandidateSkill(candidate_id=candidate.id, skill=skill))
    resume_text = "Synthetic Person\nJava Developer\nperson@example.com\n6 years of experience building services.\nSkills: Java, Spring Boot, Microservices\nNotice period: 30 days\nLocation: Noida"
    db.add(Resume(candidate_id=candidate.id, requisition_id=requisition.id, filename="synthetic.pdf", sha256="synthetic-hash", extracted_text=resume_text, synthetic=True))
    score = CandidateScore(candidate_id=candidate.id, requisition_id=requisition.id, overall_score=90, category="Strong match", breakdown={}, scoring_method="rule-based", missing_information=[], warnings=[])
    db.add(score)
    db.flush()
    db.add(ScoreEvidence(score_id=score.id, criterion="Must-have skills", status="match", score=100, quotation="Skills: Java, Spring Boot, Microservices", explanation="Skills match.", confidence=.9))
    submission = ShortlistSubmission(candidate_id=candidate.id, requisition_id=requisition.id, organization_id=organization.id, submitted_by=recruiter.id, status="submitted")
    db.add(submission)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield {
            "client": client, "db": db, "recruiter": recruiter, "client_user": client_user,
            "other_client": other_client, "organization": organization, "requisition": requisition,
            "other_req": other_req, "candidate": candidate, "submission": submission,
            "resume_text": resume_text,
        }
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_and_role_permissions(context):
    client = context["client"]
    recruiter_token = token(client, "recruiter@test.demo", "Recruiter@123")
    assert client.get("/api/dashboard", headers={"Authorization": f"Bearer {recruiter_token}"}).status_code == 200
    assert client.get("/api/client/dashboard", headers={"Authorization": f"Bearer {recruiter_token}"}).status_code == 403
    client_token = token(client, "client@test.demo", "Client@123")
    assert client.get("/api/dashboard", headers={"Authorization": f"Bearer {client_token}"}).status_code == 403
    assert client.post("/api/auth/login", json={"email": "recruiter@test.demo", "password": "bad"}).status_code == 401


def test_resume_parser_extracts_only_present_fields():
    result = parse_resume("Alex Example\nalex@example.com\n5 years of experience\nSkills: Java, Spring Boot\nNotice period: 30 days")
    assert result["name"] == "Alex Example"
    assert result["email"] == "alex@example.com"
    assert result["experience_years"] == 5
    assert result["notice_days"] == 30
    assert result["current_ctc"] is None
    assert "current_ctc" in result["missing_information"]


def test_duplicate_resume_detection_and_scoring(context):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), "New Synthetic\nnew@example.com\nJava Developer\n6 years of experience building systems.\nSkills: Java, Spring Boot, Microservices\nNotice period: 30 days\nLocation: Noida")
    content = document.tobytes()
    document.close()
    headers = {"Authorization": f"Bearer {token(context['client'], 'recruiter@test.demo', 'Recruiter@123')}"}
    response = context["client"].post(
        f"/api/requisitions/{context['requisition'].id}/resumes",
        headers=headers,
        files=[("files", ("new.pdf", content, "application/pdf")), ("files", ("copy.pdf", content, "application/pdf"))],
    )
    assert response.status_code == 422
    response = context["client"].post(
        f"/api/requisitions/{context['requisition'].id}/resumes",
        headers=headers,
        files=[("files", ("new.pdf", content, "application/pdf")), ("files", ("copy.pdf", content, "application/pdf"))],
        data={"consent_confirmed": "true"},
    )
    assert response.status_code == 200
    result = response.json()["results"]
    assert result[0]["status"] == "success"
    assert result[1]["status"] == "duplicate"
    candidate = context["db"].query(BaseCandidate).filter_by(email="new@example.com").one()
    score = score_candidate(context["requisition"], candidate, "Skills: Java, Spring Boot, Microservices\n6 years of experience")
    assert score["overall_score"] >= 70
    assert score["scoring_method"] == "rule-based"
    assert all(evidence_is_valid(item["quotation"], "Skills: Java, Spring Boot, Microservices\n6 years of experience") for item in score["criteria"])


def test_evidence_quotes_must_exist_in_source():
    assert evidence_is_valid("Java and Spring Boot", "Skills: Java and Spring Boot")
    assert not evidence_is_valid("Excellent Java candidate", "Skills: Java and Spring Boot")


def test_client_tenant_isolation_and_masking(context):
    client = context["client"]
    client_token = token(client, "client@test.demo", "Client@123")
    headers = {"Authorization": f"Bearer {client_token}"}
    visible = client.get(f"/api/requisitions/{context['requisition'].id}/candidates", headers=headers)
    assert visible.status_code == 200 and len(visible.json()) == 1
    assert visible.json()[0]["email"] == "p***@example.com"
    hidden = client.get(f"/api/requisitions/{context['other_req'].id}/candidates", headers=headers)
    assert hidden.status_code == 404
    profile = client.get(f"/api/candidates/{context['candidate'].id}?requisition_id={context['requisition'].id}", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["phone"] != "+91 90000 11111"
    assert "person@example.com" not in profile.json()["resume_text"]
    assert "+91 90000 11111" not in profile.json()["resume_text"]
    other_headers = {"Authorization": f"Bearer {token(client, 'other@test.demo', 'Client@123')}"}
    assert client.get(f"/api/candidates/{context['candidate'].id}?requisition_id={context['requisition'].id}", headers=other_headers).status_code == 404


def test_rejection_reason_and_shortlist_submission(context):
    client = context["client"]
    client_headers = {"Authorization": f"Bearer {token(client, 'client@test.demo', 'Client@123')}"}
    missing_reason = client.post(f"/api/client/submissions/{context['submission'].id}/decision", headers=client_headers, json={"decision": "rejected"})
    assert missing_reason.status_code == 422
    rejected = client.post(f"/api/client/submissions/{context['submission'].id}/decision", headers=client_headers, json={"decision": "rejected", "reason": "Experience with distributed systems is below this role's requirement."})
    assert rejected.status_code == 200
    feedback = context["db"].query(ClientFeedback).filter_by(submission_id=context["submission"].id).one()
    assert feedback.reason
    accepted = client.post(f"/api/client/submissions/{context['submission'].id}/decision", headers=client_headers, json={"decision": "shortlisted"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "shortlisted"


def test_scorecard_creation_and_approval_are_persisted(context):
    client = context["client"]
    headers = {"Authorization": f"Bearer {token(client, 'recruiter@test.demo', 'Recruiter@123')}"}
    response = client.post("/api/requisitions", headers=headers, json={
        "title": "QA Engineer", "organization_id": context["organization"].id,
        "description": "Test systems", "required_skills": ["Testing"],
    })
    assert response.status_code == 200
    scorecard = context["db"].query(JobScorecard).filter_by(requisition_id=response.json()["id"]).one()
    assert scorecard.approved is False
    assert client.post(f"/api/requisitions/{response.json()['id']}/approve", headers=headers, json={"approved": True}).status_code == 200
    context["db"].refresh(scorecard)
    assert scorecard.approved is True
    assert scorecard.approved_by == context["recruiter"].id


def test_client_can_propose_interview(context):
    client = context["client"]
    headers = {"Authorization": f"Bearer {token(client, 'client@test.demo', 'Client@123')}"}
    result = client.post(
        f"/api/client/submissions/{context['submission'].id}/interviews",
        headers=headers,
        json={"starts_at": "2027-01-15T10:30:00Z", "note": "First-round interview"},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "proposed"


def test_recruiter_must_review_candidate_before_submission_and_pipeline_persists(context):
    client = context["client"]
    headers = {"Authorization": f"Bearer {token(client, 'recruiter@test.demo', 'Recruiter@123')}"}
    candidate_id, req_id = context["candidate"].id, context["requisition"].id
    blocked = client.post(f"/api/candidates/{candidate_id}/submit", headers=headers, json={"requisition_id": req_id})
    assert blocked.status_code == 409
    assert client.get(f"/api/candidates/{candidate_id}?requisition_id={req_id}", headers=headers).status_code == 200
    assert client.patch(f"/api/pipeline/{candidate_id}/{req_id}", headers=headers, json={"stage": "Interview"}).status_code == 200
    assert context["db"].query(PipelineEvent).filter_by(candidate_id=candidate_id, stage="Interview").count() == 1


def test_recruiter_can_submit_after_review(context):
    client = context["client"]
    headers = {"Authorization": f"Bearer {token(client, 'recruiter@test.demo', 'Recruiter@123')}"}
    candidate = BaseCandidate(external_id="CND-TEST2", name="Another Synthetic", email="another@example.com", missing_information=[])
    context["db"].add(candidate)
    context["db"].flush()
    context["db"].add(Resume(candidate_id=candidate.id, requisition_id=context["requisition"].id, filename="another.pdf", sha256="another-hash", extracted_text="Another Synthetic\nSkills: Java"))
    context["db"].commit()
    profile = client.get(f"/api/candidates/{candidate.id}?requisition_id={context['requisition'].id}", headers=headers)
    assert profile.status_code == 200
    submission = client.post(f"/api/candidates/{candidate.id}/submit", headers=headers, json={"requisition_id": context["requisition"].id})
    assert submission.status_code == 200
    assert submission.json()["status"] == "submitted"
