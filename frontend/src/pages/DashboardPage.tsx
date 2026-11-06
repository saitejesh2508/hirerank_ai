import { useEffect, useState } from "react";
import { ArrowUpRight, BriefcaseBusiness, Clock3, Users, UserRoundCheck, UserRoundSearch } from "lucide-react";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorState, Loading, PageTitle } from "../components/Shared";
import { api } from "../services/api";
import type { Requisition } from "../types";

type Dashboard = {
  stats: Record<string, number>;
  pipeline: Record<string, number>;
  recent_requisitions: Requisition[];
  recent_activity: { action: string; entity_type: string; entity_id: string; created_at: string }[];
};
const metrics = [
  { key: "active_requisitions", label: "Active requisitions", icon: BriefcaseBusiness, tone: "blue" },
  { key: "total_candidates", label: "Total candidates", icon: Users, tone: "violet" },
  { key: "candidates_screened", label: "Candidates screened", icon: UserRoundSearch, tone: "green" },
  { key: "shortlisted_candidates", label: "Shortlisted", icon: UserRoundCheck, tone: "orange" },
  { key: "pending_client_reviews", label: "Awaiting client review", icon: Clock3, tone: "slate" },
];
const stages = ["Sourced", "Parsed", "Screened", "Submitted", "Shortlisted", "Interview", "Selected", "Offer", "Joined"];

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const load = () => api<Dashboard>("/api/dashboard").then(setData).catch(reason => setError(reason.message));
  useEffect(() => { void load(); }, []);
  if (error) return <ErrorState error={error} onRetry={() => { setError(""); void load(); }} />;
  if (!data) return <Loading />;
  const chartData = stages.map(stage => ({ stage: stage === "Shortlisted" ? "Shortlist" : stage, candidates: data.pipeline[stage] || 0 }));
  return <div className="page-stack">
    <PageTitle eyebrow="RECRUITING OVERVIEW" title="Hiring overview" description="Here’s what’s happening across your hiring pipeline today." action={<Link className="button button-primary" to="/requisitions"><span className="plus">+</span> New requisition</Link>} />
    <div className="metric-grid">{metrics.map(({ key, label, icon: Icon, tone }) => <article className="metric-card" key={key}><div className={`metric-icon ${tone}`}><Icon size={18} /></div><div className="metric-label">{label}</div><div className="metric-value">{data.stats[key] ?? 0}</div><div className="metric-foot"><span>Live from your workspace</span></div></article>)}</div>
    <div className="dashboard-grid">
      <section className="panel pipeline-panel"><div className="panel-heading"><div><h2>Pipeline overview</h2><p>Candidate movement across all open roles</p></div><Link to="/pipeline" className="text-link">View pipeline <ArrowUpRight size={15} /></Link></div>
        <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 12, right: 12, left: -22, bottom: 0 }}><defs><linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#5865e8" stopOpacity={0.19} /><stop offset="95%" stopColor="#5865e8" stopOpacity={0.015} /></linearGradient></defs><CartesianGrid stroke="#eef0f5" vertical={false} /><XAxis dataKey="stage" axisLine={false} tickLine={false} tick={{ fill: "#858da1", fontSize: 11 }} interval={0} /><YAxis axisLine={false} tickLine={false} tick={{ fill: "#858da1", fontSize: 11 }} allowDecimals={false} /><Tooltip contentStyle={{ border: "1px solid #e8eaf0", borderRadius: 10, boxShadow: "0 8px 24px #17203a12" }} /><Area type="monotone" dataKey="candidates" stroke="#5865e8" strokeWidth={2.5} fill="url(#area-fill)" /></AreaChart></ResponsiveContainer></div>
        <div className="stage-mini">{chartData.slice(0, 5).map(stage => <div key={stage.stage}><i /><span>{stage.stage}</span><strong>{stage.candidates}</strong></div>)}</div>
      </section>
      <section className="panel activity-panel"><div className="panel-heading"><div><h2>Recent activity</h2><p>Latest changes in the workspace</p></div></div>{data.recent_activity.length ? <div className="activity-list">{data.recent_activity.map((event, index) => <div className="activity-item" key={`${event.action}-${event.entity_id}-${index}`}><div className="activity-indicator">{index === 0 ? <i /> : null}</div><div><strong>{event.action.replaceAll(".", " ")}</strong><small>{event.entity_type} · {new Date(event.created_at).toLocaleString()}</small></div></div>)}</div> : <div className="quiet-empty">Activity will appear here as your team works.</div>}</section>
    </div>
    <section className="panel requisition-panel"><div className="panel-heading"><div><h2>Recent requisitions</h2><p>Your most recently updated roles</p></div><Link to="/requisitions" className="text-link">All requisitions <ArrowUpRight size={15} /></Link></div>
      {data.recent_requisitions.length ? <div className="table-scroll"><table><thead><tr><th>ROLE</th><th>CLIENT</th><th>LOCATION</th><th>STATUS</th><th>CANDIDATES</th><th>SCREENED</th><th /></tr></thead><tbody>{data.recent_requisitions.map(req => <tr key={req.id}><td><strong>{req.title}</strong><small>REQ-{String(req.id).padStart(4, "0")}</small></td><td>{req.organization}</td><td>{req.location || "—"}</td><td><span className="status-pill status-active"><i /> {req.scorecard_approved ? "Scorecard approved" : "Draft"}</span></td><td>{req.candidate_count ?? 0}</td><td>{req.screened_count ?? 0}</td><td><Link className="icon-link" to={`/candidates?requisitionId=${req.id}`} title="View candidates"><ArrowUpRight size={16} /></Link></td></tr>)}</tbody></table></div> : <div className="quiet-empty">No active requisitions yet. Create a requisition to get started.</div>}</section>
  </div>;
}
