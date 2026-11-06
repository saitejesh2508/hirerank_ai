import { useEffect, useRef, useState } from "react";
import { ArrowDownUp, ArrowUpRight, Check, FileUp, RotateCw, Search, UploadCloud } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, EmptyState, ErrorState, Loading, PageTitle, ScoreBadge, SyntheticTag } from "../components/Shared";
import { api } from "../services/api";
import type { Candidate, Requisition } from "../types";

type UploadResult = { file: File; filename: string; status: string; error?: string; external_id?: string; candidate_id?: number; score?: number };
function uploadFiles(requisitionId: number, files: File[], onProgress: (progress: number) => void): Promise<{ results: Omit<UploadResult, "file">[] }> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    files.forEach(file => form.append("files", file));
    form.append("consent_confirmed", "true");
    const request = new XMLHttpRequest();
    request.open("POST", `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/requisitions/${requisitionId}/resumes`);
    const token = localStorage.getItem("hirerank_token");
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);
    request.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100)); };
    request.onload = () => {
      const body = JSON.parse(request.responseText || "{}");
      if (request.status >= 200 && request.status < 300) resolve(body);
      else reject(new Error(body.detail || `Upload failed (${request.status})`));
    };
    request.onerror = () => reject(new Error("Upload connection failed"));
    request.send(form);
  });
}

export default function CandidatesPage() {
  const [params, setParams] = useSearchParams();
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [reqId, setReqId] = useState(params.get("requisitionId") || "");
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("score");
  const [error, setError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { api<Requisition[]>("/api/requisitions").then(setRequisitions).catch(reason => setError(reason.message)); }, []);
  const loadCandidates = () => {
    if (!reqId) { setCandidates([]); return; }
    setParams({ requisitionId: reqId }, { replace: true });
    const search = new URLSearchParams({ q: query, sort });
    if (category) search.set("category", category);
    api<Candidate[]>(`/api/requisitions/${reqId}/candidates?${search}`).then(setCandidates).catch(reason => setError(reason.message));
  };
  useEffect(() => { void loadCandidates(); }, [reqId, query, category, sort]);
  function onFiles(files: FileList | null) {
    if (!files || !reqId) return;
    const selected = Array.from(files);
    const invalid = selected.filter(file => !/\.(pdf|docx)$/i.test(file.name) || file.size > 10 * 1024 * 1024);
    if (selected.length > 500) { setUploadError("A maximum of 500 resumes may be selected."); return; }
    if (invalid.length) { setUploadError(`${invalid.length} file(s) rejected: choose PDF or DOCX files up to 10 MB each.`); return; }
    setUploadError(""); setResults([]); setProgress(0); setUploading(true);
    void uploadFiles(Number(reqId), selected, setProgress).then(response => {
      setResults(response.results.map((result, index) => ({ ...result, file: selected.find(file => file.name === result.filename) || selected[index] })));
      void loadCandidates();
    }).catch(reason => setUploadError(reason.message)).finally(() => setUploading(false));
  }
  async function retry(result: UploadResult) {
    setUploading(true); setUploadError("");
    try {
      const response = await uploadFiles(Number(reqId), [result.file], () => {});
      setResults(current => current.map(item => item === result ? { ...response.results[0], file: result.file } : item));
      void loadCandidates();
    } catch (reason) { setUploadError(reason instanceof Error ? reason.message : "Retry failed"); }
    finally { setUploading(false); }
  }
  const req = requisitions.find(item => String(item.id) === reqId);
  if (error && !requisitions.length) return <ErrorState error={error} />;
  return <div className="page-stack">
    <PageTitle eyebrow="TALENT DISCOVERY" title="Candidate search" description="Review evidence-backed matches. Scores guide review — they never make hiring decisions." />
    {error && <ErrorState error={error} />}
    <div className="candidate-toolbar panel"><label className="select-inline"><span>Requisition</span><select value={reqId} onChange={event => setReqId(event.target.value)}><option value="">Choose a requisition…</option>{requisitions.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><div className="toolbar-spacer" /><Button variant="secondary" disabled={!req?.scorecard_approved || !consentConfirmed || uploading} onClick={() => inputRef.current?.click()}><UploadCloud size={16} /> Upload resumes</Button><input ref={inputRef} className="visually-hidden" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple onChange={event => onFiles(event.target.files)} /></div>
    <label className="consent-confirm"><input type="checkbox" checked={consentConfirmed} onChange={event => setConsentConfirmed(event.target.checked)} /><span>I confirm these candidates have consented to employment screening for this requisition.</span></label>
    {req && !req.scorecard_approved && <div className="notice notice-info">Approve this requisition scorecard before uploading and scoring resumes.</div>}
    {uploading && <div className="upload-progress panel"><div className="progress-title"><span><FileUp size={16} /> Uploading and parsing resumes</span><strong>{progress}%</strong></div><div className="progress-track"><div style={{ width: `${progress}%` }} /></div><small>Resume scores are calculated after parsing completes.</small></div>}
    {uploadError && <div className="notice notice-error">{uploadError}</div>}
    {results.length > 0 && <div className="upload-results panel"><div className="panel-heading"><div><h2>Upload results</h2><p>{results.filter(row => row.status === "success").length} processed · {results.filter(row => row.status === "duplicate").length} duplicates · {results.filter(row => row.status === "failed").length} failed</p></div><button className="text-button" onClick={() => setResults([])}>Dismiss</button></div>{results.map((result, index) => <div className="upload-result" key={`${result.filename}-${index}`}><span className={`result-mark result-${result.status}`}>{result.status === "success" ? <Check size={13} /> : result.status === "duplicate" ? "D" : "!"}</span><strong>{result.filename}</strong><span>{result.error || result.external_id || `${result.score}% match`}</span>{result.status === "failed" && <button className="text-button" onClick={() => void retry(result)} disabled={uploading}><RotateCw size={13} /> Retry</button>}</div>)}</div>}
    <div className="candidate-filters panel"><div className="search-field"><Search size={16} /><input placeholder="Search candidates or skills…" value={query} onChange={event => setQuery(event.target.value)} /></div><select aria-label="Filter by match category" value={category} onChange={event => setCategory(event.target.value)}><option value="">All match categories</option>{["Strong match", "Good match", "Partial match", "Low match"].map(label => <option key={label}>{label}</option>)}</select><button className="sort-button" onClick={() => setSort(current => current === "score" ? "name" : "score")}><ArrowDownUp size={15} /> {sort === "score" ? "Best match" : "Name A–Z"}</button></div>
    {candidates === null ? <Loading /> : !reqId ? <EmptyState title="Choose a requisition" message="Select an approved role above to see its candidate matches." /> : candidates.length === 0 ? <EmptyState title="No candidates found" message="Try adjusting your filters or upload resumes to this requisition." action={<Button variant="secondary" disabled={!req?.scorecard_approved} onClick={() => inputRef.current?.click()}><UploadCloud size={15} /> Upload resumes</Button>} /> : <section className="panel candidates-panel"><div className="panel-heading"><div><h2>Ranked candidates</h2><p>{candidates.length} candidate{candidates.length === 1 ? "" : "s"} · sorted by transparent match score</p></div><span className="score-hint">Scores reflect approved scorecard criteria</span></div><div className="table-scroll"><table className="candidate-table"><thead><tr><th>CANDIDATE</th><th>CURRENT ROLE</th><th>EXPERIENCE</th><th>SKILLS</th><th>NOTICE</th><th>MATCH</th><th /></tr></thead><tbody>{candidates.map(candidate => <tr key={candidate.id}><td><div className="candidate-cell"><div className="candidate-avatar">{candidate.name[0]}</div><div><strong>{candidate.name}</strong><small>{candidate.external_id}</small></div>{candidate.synthetic && <span title="Synthetic sample data"><SparkleMini /></span>}</div></td><td>{candidate.current_role || "Not provided"}</td><td>{candidate.experience_years === null ? "—" : `${candidate.experience_years} yrs`}</td><td><div className="skill-inline">{candidate.skills.slice(0, 2).map(skill => <span key={skill}>{skill}</span>)}{candidate.skills.length > 2 && <small>+{candidate.skills.length - 2}</small>}</div></td><td>{candidate.notice_days === null ? "—" : `${candidate.notice_days} days`}</td><td><ScoreBadge score={candidate.score?.overall_score} category={candidate.score?.category} /></td><td><Link className="icon-link" to={`/candidates/${candidate.id}?requisitionId=${reqId}`} aria-label={`Review ${candidate.name}`}><ArrowUpRight size={16} /></Link></td></tr>)}</tbody></table></div><div className="table-footer"><span>All candidates remain searchable, regardless of score.</span><SyntheticTag /></div></section>}
  </div>;
}

function SparkleMini() { return <span className="mini-synthetic" title="Synthetic candidate">S</span>; }
