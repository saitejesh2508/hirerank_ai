import { useState } from "react";
import { ArrowRight, Eye, EyeOff, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../services/api";
import type { User } from "../types";

type Props = { onLogin: (user: User) => void };
export default function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ access_token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      localStorage.setItem("hirerank_token", result.access_token);
      onLogin(result.user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in");
    } finally { setBusy(false); }
  }
  return <div className="login-page">
    <div className="login-left"><div className="brand login-brand"><div className="brand-mark">H</div><span>hirerank<span className="brand-ai">.ai</span></span></div>
      <div className="login-copy"><span className="kicker"><Sparkles size={14} /> INTELLIGENCE FOR BETTER HIRING</span><h1>Find the right<br />people, <span>fairly.</span></h1><p>Evidence-led screening for teams building what’s next. Clear signals, confident decisions.</p>
        <div className="login-proof"><div className="proof-avatar-stack"><i>RK</i><i>AM</i><i>PN</i><b>+</b></div><div><strong>Thoughtful hiring, at scale.</strong><small>One workspace for your entire pipeline.</small></div></div></div>
      <div className="login-legal">© 2026 HireRank AI <span>·</span> Privacy-first talent intelligence</div>
    </div>
    <div className="login-right"><form className="login-form" onSubmit={submit}><div className="form-symbol"><ShieldCheck size={20} /></div><div className="eyebrow">WELCOME BACK</div><h2>Sign in to your workspace</h2><p className="login-muted">Use your work email to continue.</p>
        {error && <div className="notice notice-error">{error}</div>}
        <label>Email address<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} placeholder="you@company.com" /></label>
        <label>Password<div className="password-input"><input type={showPassword ? "text" : "password"} autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter your password" /><button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label>
        <button className="button button-primary login-submit" disabled={busy}>{busy ? "Signing in…" : <>Continue <ArrowRight size={16} /></>}</button>
        <div className="demo-box"><div className="demo-title"><Sparkles size={14} /> Demo access</div><div><strong>Recruiter</strong><span>recruiter@hirerank.demo</span><span>Recruiter@123</span></div><div><strong>Client manager</strong><span>client@hirerank.demo</span><span>Client@123</span></div><small>Sample candidate records are synthetic.</small></div>
      </form></div>
  </div>;
}
