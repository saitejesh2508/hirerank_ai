import { useEffect, useState } from "react";
import { ArrowUpRight, BriefcaseBusiness, CalendarClock, Check, Clock3, Eye, MessageSquareText, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, EmptyState, ErrorState, Loading, PageTitle, ScoreBadge } from "../components/Shared";
import { api } from "../services/api";
import type { Candidate } from "../types";

type ClientDashboard = {
  organization: string;
  requisitions: { id: number; title: string }[];
  stats: Record<string, number>;
  submissions: Candidate[];
};
export default function ClientPage() {
  const [data, setData] = useState<ClientDashboard | null>(null);
  const [error, setError] = useState("");
  const [reasonId, setReasonId] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [interviewId, setInterviewId] = useState<number | null>(null);
  const [interviewTime, setInterviewTime] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api<ClientDashboard>("/api/client/dashboard").then(setData).catch(reason => setError(reason.message));
  useEffect(() => { void load(); }, []);
  async function decision(candidate: Candidate, value: "shortlisted" | "rejected") {
    setBusy(true); setError(""); setFeedback("");
    try {
      await api(`/api/client/submissions/${candidate.submission_id}/decision`, { method: "POST", body: JSON.stringify({ decision: value, reason: value === "rejected" ? reason : null }) });
      setReasonId(null); setReason(""); setFeedback(value === "shortlisted" ? "Candidate shortlisted." : "Candidate rejected with feedback."); await load();
    } catch (issue) { setError(issue instanceof Error ? issue.message : "Could not save your decision"); }
    finally { setBusy(false); }
  }
  async function propose(candidate: Candidate) {
    setBusy(true); setError(""); setFeedback("");
    try {
      await api(`/api/client/submissions/${candidate.submission_id}/interviews`, { method: "POST", body: JSON.stringify({ starts_at: new Date(interviewTime).toISOString(), note: "Interview proposed by client" }) });
      setInterviewId(null); setInterviewTime(""); setFeedback("Interview proposal sent to the recruiting team."); await load();
    } catch (issue) { setError(issue instanceof Error ? issue.message : "Could not propose interview"); }
    finally { setBusy(false); }
  }
  if (error && !data) return <ErrorState error={error} onRetry={() => { setError(""); void load(); }} />;
  if (!data) return <Loading />;
  return <div className="page-stack client-page">
    <PageTitle eyebrow="CLIENT HIRING PORTAL" title={`Your talent, ${data.organization}`} description="Review candidates shared specifically with your organization. Personal contact information is protected." />
    {error && <ErrorState error={error} />}
    {feedback && <div className="notice notice-success"><Check size={16} /> {feedback}</div>}
    <div className="client-stats">{[{ label: "Assigned requisitions", value: data.stats.assigned_requisitions, icon: BriefcaseBusiness }, { label: "Candidates received", value: data.stats.submitted_candidates, icon: Users }, { label: "Pending your review", value: data.stats.pending_review, icon: Clock3 }, { label: "Shortlisted", value: data.stats.shortlisted, icon: Check }].map(({ label, value, icon: Icon }) => <article className="client-stat panel" key={label}><div className="client-stat-icon"><Icon size={17} /></div><div><small>{label}</small><strong>{value ?? 0}</strong></div></article>)}</div>
    <section className="panel client-submissions"><div className="panel-heading"><div><h2>Submitted candidates</h2><p>Evidence and scorecard detail are available for each submission.</p></div><span className="privacy-chip">Private to your organization</span></div>
      {!data.submissions.length ? <EmptyState title="No candidates shared yet" message="Your recruiter will share reviewed candidate profiles here." /> : <div className="client-candidate-list">{data.submissions.map(candidate => <article className="client-candidate-card" key={candidate.submission_id}>      <div className="client-candidate-top"><div className="candidate-avatar">{candidate.name[0]}</div><div className="client-candidate-name"><h3>{candidate.name}</h3><span>{candidate.current_role || "Role not provided"} {candidate.experience_years !== null && `· ${candidate.experience_years} yrs`}</span><small>{candidate.requisition_title}</small></div>{candidate.synthetic && <span className="synthetic-inline">Synthetic demo</span>}<ScoreBadge score={candidate.score?.overall_score} category={candidate.score?.category} /><span className={`status-pill status-${(candidate.status || "submitted").toLowerCase()}`}><i />{candidate.status}</span></div>
        <div className="client-candidate-detail"><div><span>Skills</span><div className="skill-inline">{candidate.skills.length ? candidate.skills.slice(0, 5).map(skill => <span key={skill}>{skill}</span>) : <small>Not found</small>}</div></div><div><span>Experience</span><strong>{candidate.experience_years === null ? "Not provided" : `${candidate.experience_years} yrs`}</strong></div><div><span>Notice</span><strong>{candidate.notice_days === null ? "Not provided" : `${candidate.notice_days} days`}</strong></div><div><span>Contact details</span><strong>{candidate.email} · {candidate.phone}</strong></div></div>
        {candidate.score?.criteria?.length ? <div className="client-evidence"><strong><MessageSquareText size={14} /> Evidence snapshot</strong><div>{candidate.score.criteria.slice(0, 2).map(item => <span key={item.criterion}><b>{item.criterion}:</b> {item.quotation}</span>)}</div></div> : null}
        <div className="client-card-actions"><Link className="button button-secondary" to={`/candidates/${candidate.id}?requisitionId=${candidate.requisition_id}`}><Eye size={15} /> Full profile</Link>{["submitted", "interview"].includes(candidate.status || "") && <><Button variant="secondary" disabled={busy} onClick={() => void decision(candidate, "shortlisted")}><Check size={15} /> Shortlist</Button><Button variant="ghost" disabled={busy} onClick={() => { setReasonId(candidate.submission_id || null); setReason(""); }}><MessageSquareText size={15} /> Reject</Button><Button variant="ghost" disabled={busy} onClick={() => setInterviewId(candidate.submission_id || null)}><CalendarClock size={15} /> Propose interview</Button></>}</div>
        {reasonId === candidate.submission_id && <div className="inline-action"><label>Reason for rejection <textarea rows={2} required value={reason} onChange={event => setReason(event.target.value)} placeholder="Share concise, job-related feedback…" /></label><Button variant="danger" disabled={busy || !reason.trim()} onClick={() => void decision(candidate, "rejected")}>Confirm rejection</Button><button className="text-button" onClick={() => setReasonId(null)}>Cancel</button></div>}
        {interviewId === candidate.submission_id && <div className="inline-action interview-action"><label>Proposed interview time<input type="datetime-local" value={interviewTime} onChange={event => setInterviewTime(event.target.value)} /></label><Button disabled={busy || !interviewTime} onClick={() => void propose(candidate)}>Send proposal</Button><button className="text-button" onClick={() => setInterviewId(null)}>Cancel</button></div>}
      </article>)}</div>}
    </section>
    {data.requisitions.length > 0 && <section className="panel assigned-roles"><div className="panel-heading"><div><h2>Assigned requisitions</h2><p>Roles currently being worked on for your organization</p></div></div><div className="assigned-role-list">{data.requisitions.map(req => <div key={req.id}><div className="req-avatar">{req.title.slice(0, 2).toUpperCase()}</div><strong>{req.title}</strong><span>Active</span><ArrowUpRight size={15} /></div>)}</div></section>}
  </div>;
}
