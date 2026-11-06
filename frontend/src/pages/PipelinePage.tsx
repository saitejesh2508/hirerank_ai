import { useEffect, useState } from "react";
import { ArrowRight, Clock3, History, MoreHorizontal, UserRound } from "lucide-react";
import { Button, ErrorState, Loading, PageTitle, ScoreBadge } from "../components/Shared";
import { api } from "../services/api";
import type { Candidate } from "../types";

type Column = { stage: string; count: number; candidates: (Candidate & { requisition_id: number; requisition_title: string; updated_at: string })[] };
type Event = { stage: string; note: string | null; created_at: string; changed_by: number };
const stages = ["Sourced", "Parsed", "Screened", "Submitted", "Shortlisted", "Interview", "Selected", "Offer", "Joined"];

export default function PipelinePage() {
  const [columns, setColumns] = useState<Column[] | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<Event[] | null>(null);
  const [selected, setSelected] = useState<{ candidateId: number; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api<Column[]>("/api/pipeline").then(setColumns).catch(reason => setError(reason.message));
  useEffect(() => { void load(); }, []);
  async function move(candidate: Candidate & { requisition_id: number }, stage: string) {
    setBusy(true); setError("");
    try { await api(`/api/pipeline/${candidate.id}/${candidate.requisition_id}`, { method: "PATCH", body: JSON.stringify({ stage }) }); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Pipeline update failed"); }
    finally { setBusy(false); }
  }
  async function showHistory(candidate: Candidate) {
    setSelected({ candidateId: candidate.id, name: candidate.name });
    setHistory(null);
    try { setHistory(await api<Event[]>(`/api/candidates/${candidate.id}/history`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load candidate history"); }
  }
  if (!columns) return error ? <ErrorState error={error} onRetry={() => { setError(""); void load(); }} /> : <Loading />;
  return <div className="page-stack">
    <PageTitle eyebrow="RECRUITMENT OPERATIONS" title="Recruitment pipeline" description="Track candidate progress across all active requisitions. Every stage change is recorded." action={<div className="pipeline-total"><strong>{columns.reduce((sum, column) => sum + column.count, 0)}</strong><span>active profiles</span></div>} />
    {error && <ErrorState error={error} />}
    <div className="pipeline-legend"><span><i className="legend-indigo" />Candidate stage</span><span><Clock3 size={14} /> Updated when an event is recorded</span><span className="pipeline-controls"><Button variant="secondary" disabled={busy} onClick={() => void load()}>Refresh</Button></span></div>
    <div className="kanban-scroll"><div className="kanban-board">{columns.map((column, index) => <section className="kanban-column" key={column.stage}><div className="kanban-header"><div className={`stage-dot stage-dot-${index}`} /><h2>{column.stage}</h2><span>{column.count}</span><button aria-label={`Options for ${column.stage}`} title="Stage actions are available on each candidate card"><MoreHorizontal size={16} /></button></div><div className="kanban-cards">{column.candidates.map(candidate => <article className="pipeline-card" key={`${candidate.id}-${candidate.requisition_id}`}><div className="pipeline-card-top"><div className="pipeline-avatar">{candidate.name[0]}</div><button className="history-button" title="View candidate history" onClick={() => void showHistory(candidate)}><History size={15} /></button></div><h3>{candidate.name}</h3><p>{candidate.current_role || "Role not provided"}</p><div className="pipeline-role">{candidate.requisition_title}</div><div className="pipeline-card-meta"><span>{candidate.experience_years === null ? "—" : `${candidate.experience_years} yrs`}</span><ScoreBadge score={candidate.score?.overall_score} /></div><div className="pipeline-card-foot"><small><Clock3 size={12} />{new Date(candidate.updated_at).toLocaleDateString()}</small><label className="stage-select"><span className="sr-only">Move candidate stage</span><select value={column.stage} disabled={busy} onChange={event => void move(candidate, event.target.value)} aria-label={`Move ${candidate.name} to a different stage`}>{stages.map(stage => <option key={stage}>{stage}</option>)}</select><ArrowRight size={13} /></label></div></article>)}
      {!column.candidates.length && <div className="kanban-empty"><UserRound size={17} /><span>No candidates here</span></div>}</div></section>)}</div></div>
    {selected && <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setSelected(null); }}><section className="history-modal panel" role="dialog" aria-modal="true" aria-label="Candidate history"><div className="panel-heading"><div><h2>Candidate history</h2><p>{selected.name} · audit trail</p></div><button className="close-button" onClick={() => setSelected(null)}>×</button></div>{history === null ? <Loading /> : history.length ? <div className="history-list">{history.map((event, index) => <div className="history-event" key={`${event.stage}-${event.created_at}-${index}`}><div className="history-marker" /><div><strong>{event.stage}</strong>{event.note && <p>{event.note}</p>}<small>{new Date(event.created_at).toLocaleString()} · user #{event.changed_by}</small></div></div>)}</div> : <div className="quiet-empty">No stage history recorded.</div>}</section></div>}
  </div>;
}
