import { useEffect, useState } from "react";
import { ArrowUpRight, Check, FilePlus2, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, ErrorState, Loading, PageTitle } from "../components/Shared";
import { api } from "../services/api";
import type { Requisition } from "../types";

type Organization = { id: number; name: string };
type FormData = {
  title: string; organization_id: number; description: string; location: string;
  min_experience: string; max_experience: string; required_skills: string;
  preferred_skills: string; max_notice_days: string; min_ctc: string; max_ctc: string;
};
const emptyForm = (): FormData => ({ title: "", organization_id: 0, description: "", location: "", min_experience: "", max_experience: "", required_skills: "", preferred_skills: "", max_notice_days: "", min_ctc: "", max_ctc: "" });
const asNumber = (value: string) => value === "" ? null : Number(value);
const asSkills = (value: string) => value.split(",").map(skill => skill.trim()).filter(Boolean);

export default function RequisitionsPage() {
  const [items, setItems] = useState<Requisition[] | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => Promise.all([api<Requisition[]>("/api/requisitions"), api<Organization[]>("/api/organizations")]).then(([reqs, orgs]) => {
    setItems(reqs); setOrganizations(orgs);
    if (!form.organization_id && orgs[0]) setForm(current => ({ ...current, organization_id: orgs[0].id }));
  }).catch(reason => setError(reason.message));
  useEffect(() => { void load(); }, []);
  function set<K extends keyof FormData>(key: K, value: FormData[K]) { setForm(current => ({ ...current, [key]: value })); }
  async function extract() {
    setBusy(true); setError(""); setNotice("");
    try {
      const scorecard = await api<Partial<FormData> & { required_skills: string[]; preferred_skills: string[]; note: string }>("/api/requisitions/extract-scorecard", { method: "POST", body: JSON.stringify({ title: form.title, description: form.description }) });
      setForm(current => ({ ...current, title: scorecard.title || current.title, required_skills: scorecard.required_skills.join(", "), preferred_skills: scorecard.preferred_skills.join(", "), location: scorecard.location || current.location, min_experience: scorecard.min_experience?.toString() || current.min_experience, max_experience: scorecard.max_experience?.toString() || current.max_experience, max_notice_days: scorecard.max_notice_days?.toString() || current.max_notice_days }));
      setNotice(scorecard.note);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Extraction failed"); } finally { setBusy(false); }
  }
  async function create(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await api("/api/requisitions", { method: "POST", body: JSON.stringify({
        title: form.title, organization_id: form.organization_id, description: form.description,
        location: form.location || null, min_experience: asNumber(form.min_experience), max_experience: asNumber(form.max_experience),
        required_skills: asSkills(form.required_skills), preferred_skills: asSkills(form.preferred_skills),
        max_notice_days: asNumber(form.max_notice_days), min_ctc: asNumber(form.min_ctc), max_ctc: asNumber(form.max_ctc),
      }) });
      setNotice("Requisition created as a draft. Review and approve its scorecard before resume scoring.");
      setForm(emptyForm());
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create requisition"); } finally { setBusy(false); }
  }
  async function approve(id: number) {
    setError("");
    try { await api(`/api/requisitions/${id}/approve`, { method: "POST", body: JSON.stringify({ approved: true }) }); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Approval failed"); }
  }
  if (!items) return error ? <ErrorState error={error} onRetry={() => { setError(""); void load(); }} /> : <Loading />;
  return <div className="page-stack">
    <PageTitle eyebrow="HIRING WORKSPACE" title="Requisitions" description="Define role requirements, approve an explainable scorecard, then screen candidates." />
    {error && <ErrorState error={error} />}
    {notice && <div className="notice notice-success"><Check size={16} /> {notice}</div>}
    <div className="requisition-layout">
      <section className="panel requisition-form-panel"><div className="panel-heading"><div><div className="section-icon"><FilePlus2 size={17} /></div><h2>Create a requisition</h2><p>Role details become your reviewable screening scorecard.</p></div></div>
        <form className="form-grid" onSubmit={create}>
          <label className="span-two">Job title<input required value={form.title} onChange={event => set("title", event.target.value)} placeholder="e.g. Senior Java Developer" /></label>
          <label>Client organization<select required value={form.organization_id || ""} onChange={event => set("organization_id", Number(event.target.value))}><option value="" disabled>Select client</option>{organizations.map(org => <option value={org.id} key={org.id}>{org.name}</option>)}</select></label>
          <label>Location<input value={form.location} onChange={event => set("location", event.target.value)} placeholder="e.g. Noida" /></label>
          <label className="span-two">Job description<textarea required rows={5} value={form.description} onChange={event => set("description", event.target.value)} placeholder="Paste the role description, responsibilities and expectations…" /></label>
          <div className="span-two"><Button type="button" variant="secondary" disabled={busy || !form.description} onClick={extract}><Sparkles size={15} /> {busy ? "Extracting…" : "Extract scorecard from JD"}</Button><small className="helper-text">Extraction creates an editable draft — verify before saving.</small></div>
          <label>Minimum experience (years)<input type="number" min="0" step="0.5" value={form.min_experience} onChange={event => set("min_experience", event.target.value)} /></label>
          <label>Maximum experience (years)<input type="number" min="0" step="0.5" value={form.max_experience} onChange={event => set("max_experience", event.target.value)} /></label>
          <label className="span-two">Must-have skills<input value={form.required_skills} onChange={event => set("required_skills", event.target.value)} placeholder="Java, Spring Boot, Microservices" /><small className="helper-text">Comma separated · 45% of match score</small></label>
          <label className="span-two">Preferred skills<input value={form.preferred_skills} onChange={event => set("preferred_skills", event.target.value)} placeholder="Hibernate, REST APIs" /><small className="helper-text">Comma separated · 10% of match score</small></label>
          <label>Maximum notice (days)<input type="number" min="0" value={form.max_notice_days} onChange={event => set("max_notice_days", event.target.value)} /></label>
          <div className="field-pair"><label>Min CTC (LPA)<input type="number" min="0" step="0.1" value={form.min_ctc} onChange={event => set("min_ctc", event.target.value)} /></label><label>Max CTC (LPA)<input type="number" min="0" step="0.1" value={form.max_ctc} onChange={event => set("max_ctc", event.target.value)} /></label></div>
          <div className="span-two scorecard-note"><strong>Transparent scoring weights</strong><span>Must-have 45% · Experience 25% · Preferred 10% · Notice 10% · Location 5% · CTC 5%</span></div>
          <div className="span-two form-actions"><Button type="submit" disabled={busy || !organizations.length}>{busy ? "Saving…" : "Save draft scorecard"}</Button></div>
        </form>
      </section>
      <section className="panel req-list-panel"><div className="panel-heading"><div><h2>All requisitions</h2><p>{items.length} role{items.length === 1 ? "" : "s"} in your workspace</p></div></div>
        <div className="req-card-list">{items.map(req => <article className="req-card" key={req.id}><div className="req-card-top"><div className="req-avatar">{req.title.slice(0, 2).toUpperCase()}</div><span className={`status-pill ${req.scorecard_approved ? "status-approved" : "status-draft"}`}><i />{req.scorecard_approved ? "Approved" : "Needs review"}</span></div><h3>{req.title}</h3><div className="req-meta">{req.organization} <span>·</span> {req.location || "Location flexible"}</div><div className="skill-chips">{req.required_skills.slice(0, 4).map(skill => <span key={skill}>{skill}</span>)}{req.required_skills.length > 4 && <span>+{req.required_skills.length - 4}</span>}</div><div className="req-card-bottom">{req.scorecard_approved ? <Link to={`/candidates?requisitionId=${req.id}`} className="text-link">View candidates <ArrowUpRight size={14} /></Link> : <Button type="button" variant="secondary" onClick={() => approve(req.id)}>Approve scorecard</Button>}{req.min_experience !== null && <small>{req.min_experience}–{req.max_experience ?? "—"} yrs</small>}</div></article>)}</div>
      </section>
    </div>
  </div>;
}
