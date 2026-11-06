import { useEffect, useState } from "react";
import { ArrowLeft, ArrowUpRight, CalendarClock, FileText, ShieldCheck, UserRound } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, ErrorState, Loading, PageTitle, ScoreBadge, SyntheticTag } from "../components/Shared";
import { api } from "../services/api";
import type { Candidate, User } from "../types";

export default function CandidateProfilePage({ user }: { user: User }) {
  const [params] = useSearchParams();
  const requisitionId = params.get("requisitionId");
  const candidateId = location.pathname.split("/").pop();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    if (!candidateId || !requisitionId) { setError("Candidate and requisition are required."); return; }
    try { setCandidate(await api<Candidate & { status?: string }>(`/api/candidates/${candidateId}?requisition_id=${requisitionId}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load candidate"); }
  }
  useEffect(() => { void load(); }, [candidateId, requisitionId]);
  async function submit() {
    setBusy(true); setError(""); setMessage("");
    try {
      await api(`/api/candidates/${candidateId}/submit`, { method: "POST", body: JSON.stringify({ requisition_id: Number(requisitionId) }) });
      setMessage("Candidate submitted to the client successfully.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Submission failed"); }
    finally { setBusy(false); }
  }
  if (error && !candidate) return <div className="page-stack"><Link className="back-link" to="/candidates"><ArrowLeft size={15} /> Back to candidates</Link><ErrorState error={error} onRetry={() => { setError(""); void load(); }} /></div>;
  if (!candidate) return <Loading />;
  const score = candidate.score;
  const recruiter = user.role === "recruiter";
  return <div className="page-stack">
    <Link className="back-link" to={recruiter ? `/candidates?requisitionId=${requisitionId}` : "/client"}><ArrowLeft size={15} /> Back to {recruiter ? "candidates" : "client review"}</Link>
    <PageTitle eyebrow={candidate.external_id} title={candidate.name} description={candidate.current_role || "Current role not provided"} action={recruiter ? <Button onClick={submit} disabled={busy || !!message}>{busy ? "Submitting…" : message ? "Submitted" : "Submit to client"} <ArrowUpRight size={15} /></Button> : <span className="status-pill status-submitted"><i /> {candidate.status || "Submitted"}</span>} />
    {candidate.synthetic && <SyntheticTag />}
    {error && <ErrorState error={error} />}
    {message && <div className="notice notice-success"><ShieldCheck size={16} /> {message}</div>}
    <div className="profile-layout">
      <div className="profile-main">
        <section className="panel profile-summary"><div className="profile-summary-head"><div className="profile-avatar"><UserRound size={25} /></div><div><h2>{candidate.name}</h2><p>{candidate.current_role || "Role not provided"} {candidate.experience_years !== null && `· ${candidate.experience_years} years experience`}</p></div><div className="profile-score"><ScoreBadge score={score?.overall_score} category={score?.category} /><small>{score?.scoring_method === "rule-based" ? "Rule-based fallback" : "AI-assisted"} score</small></div></div>
          <div className="profile-facts"><div><span>Experience</span><strong>{candidate.experience_years === null ? "Not provided" : `${candidate.experience_years} years`}</strong></div><div><span>Notice period</span><strong>{candidate.notice_days === null ? "Not provided" : `${candidate.notice_days} days`}</strong></div><div><span>Location</span><strong>{candidate.location || "Not provided"}</strong></div><div><span>Contact</span><strong>{candidate.email || "Not provided"}</strong>{candidate.phone && <small>{candidate.phone}</small>}</div></div>
        </section>
        <section className="panel"><div className="panel-heading"><div><h2>Match breakdown</h2><p>Evidence and criterion-level fit from the approved scorecard</p></div><div className="method-chip"><ShieldCheck size={14} /> Explainable score</div></div>
          {score ? <div className="evidence-list">{score.criteria.map(item => <article className="evidence-card" key={item.criterion}><div className="evidence-top"><div><span className="evidence-criterion">{item.criterion}</span><span className={`match-status status-${item.status.replaceAll("_", "-")}`}>{item.status.replaceAll("_", " ")}</span></div><strong>{Math.round(item.score)}<small>%</small></strong></div><div className="criterion-track"><span style={{ width: `${item.score}%` }} /></div><blockquote>{item.quotation === "Insufficient evidence" ? "Insufficient evidence" : `“${item.quotation}”`}</blockquote><p>{item.explanation}</p><small className="confidence"><span>Confidence</span><span>{Math.round(item.confidence * 100)}%</span></small></article>)}</div> : <div className="quiet-empty">No score is available for this candidate.</div>}
        </section>
        {score?.warnings.map(warning => <div className="notice notice-info" key={warning}>{warning}</div>)}
      </div>
      <aside className="profile-side">
        <section className="panel side-panel"><div className="side-heading"><UserRound size={16} /><h3>Skills</h3></div><div className="skill-cloud">{candidate.skills.length ? candidate.skills.map(skill => <span key={skill}>{skill}</span>) : <small>No skills found in resume</small>}</div></section>
        <section className="panel side-panel"><div className="side-heading"><FileText size={16} /><h3>Education & experience</h3></div><div className="profile-list">{candidate.education.length ? candidate.education.map((item, index) => <div key={`${item}-${index}`}><i /><span>{item}</span></div>) : <small className="muted">Education not provided</small>}{candidate.employers.map((item, index) => <div key={`${item}-${index}`}><i /><span>{item}</span></div>)}</div></section>
        <section className="panel side-panel"><div className="side-heading"><CalendarClock size={16} /><h3>Missing information</h3></div>{candidate.missing_information.length ? <div className="missing-list">{candidate.missing_information.map(item => <span key={item}>{item.replaceAll("_", " ")}</span>)}</div> : <p className="muted">No missing fields identified.</p>}</section>
        <section className="panel side-panel resume-panel"><div className="side-heading"><FileText size={16} /><h3>Resume preview</h3></div><div className="resume-file"><FileText size={16} /><span>{candidate.resume_filename || "Resume text"}</span></div><pre>{candidate.resume_text || "Resume text is unavailable."}</pre></section>
      </aside>
    </div>
  </div>;
}
